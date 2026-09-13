"""Scraper for Frasers Group's shared e-commerce platform.

Flannels and Sports Direct (confirmed via manual testing: identical
``data-testid`` markup, identical ``?sort=...&sortDirection=...&dcp=N``
URL scheme, identical 59-items-per-page virtualized grid) both run on
this platform, so one scraper serves every site built on it - a config
module (e.g. ``config_flannels.py``, ``config_sportsdirect.py``) supplies
the URL and per-site tuning, this module supplies the mechanics.

The platform runs Akamai Bot Manager, which fingerprints and blocks
headless Chromium at the HTTP/2 layer (confirmed via manual testing:
``headless=True`` fails immediately with ``ERR_HTTP2_PROTOCOL_ERROR``,
``headless=False`` succeeds). Callers should launch with
``headless=False`` - see the ``xvfb-run`` wrapper in the GitHub Actions
workflows that gives it a virtual display in CI.

Listings are sorted by discount percentage (descending), so instead of
walking an entire catalog like :mod:`src.scraper` does for JD Sports,
this scraper stops as soon as a page's highest discount drops below
``min_discount_to_continue``. Each page's product grid is also
virtualized (only ~14 of ~59 cards exist in the DOM until scrolled), so
every page is scrolled to the bottom before its HTML is captured.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    sync_playwright,
)

from src.sites.frasers.parser import PRODUCT_CARD_SELECTOR, parse_page

logger = logging.getLogger(__name__)

# プラットフォーム共通の挙動 (Flannels/Sports Directで共通に確認済み)。
# サイト固有の値は FrasersScraper のコンストラクタ引数で渡す。

VIEWPORT_WIDTH = 1400
VIEWPORT_HEIGHT = 2000

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

LOCALE = "en-GB"

PAGE_TIMEOUT = 60_000
SELECTOR_TIMEOUT = 20_000

ITEMS_PER_PAGE = 59

SCROLL_STEP_PX = 3000
SCROLL_PAUSE_MS = 400
SCROLL_MAX_ROUNDS = 20

RETRY_LIMIT = 3
RETRY_BACKOFF_BASE = 2.0

REQUEST_DELAY_MIN = 1.5
REQUEST_DELAY_MAX = 3.0

SORT_QUERY = "sort=DISCOUNT_PERCENTAGE&sortDirection=DESC"

_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-GB', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = window.chrome || { runtime: {} };
"""


class ScraperError(Exception):
    """Raised when the scraper cannot recover from a fatal error."""


@dataclass
class ScrapeResult:
    """Container for everything a scrape run produced."""

    pages: list[str] = field(default_factory=list)
    failed_pages: list[int] = field(default_factory=list)
    stopped_early: bool = False


class FrasersScraper:
    """Playwright-driven scraper for a Frasers Group discount-sorted listing.

    Usage::

        with FrasersScraper(base_url=..., min_discount_to_continue=60.0,
                             screenshot_dir="data/screenshots_x") as scraper:
            result = scraper.run()
    """

    def __init__(
        self,
        base_url: str,
        min_discount_to_continue: float,
        screenshot_dir: str,
        max_pages: int = 20,
        headless: bool = False,
    ) -> None:
        """Initialize the scraper.

        Args:
            base_url: Listing URL (without the sort/pagination query
                string), e.g. ``"https://www.flannels.com/clearance/men/..."``.
            min_discount_to_continue: Stop fetching further pages once a
                page's highest discount drops below this.
            screenshot_dir: Where to save debug/failure screenshots.
            max_pages: Safety cap in case the discount never drops
                below the floor.
            headless: Whether to launch Chromium headless. Should stay
                False against this platform - see module docstring.
        """
        self._base_url = base_url
        self._min_discount_to_continue = min_discount_to_continue
        self._screenshot_dir = screenshot_dir
        self._max_pages = max_pages
        self._headless = headless

        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def __enter__(self) -> "FrasersScraper":
        self._playwright = sync_playwright().start()

        self._browser = self._playwright.chromium.launch(
            headless=self._headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        self._context = self._browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            user_agent=USER_AGENT,
            locale=LOCALE,
        )
        self._context.add_init_script(_STEALTH_INIT_SCRIPT)

        Path(self._screenshot_dir).mkdir(parents=True, exist_ok=True)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def _build_url(self, page_no: int) -> str:
        if page_no == 1:
            return f"{self._base_url}?{SORT_QUERY}"
        return f"{self._base_url}?{SORT_QUERY}&dcp={page_no}"

    # ------------------------------------------------------------------
    # Virtualized grid handling
    # ------------------------------------------------------------------

    def _render_all_cards(self, page: Page) -> int:
        """Scroll to the bottom until the card count stops growing."""
        prev_count = -1
        stable_rounds = 0

        for _ in range(SCROLL_MAX_ROUNDS):
            page.mouse.wheel(0, SCROLL_STEP_PX)
            page.wait_for_timeout(SCROLL_PAUSE_MS)

            count = page.locator(PRODUCT_CARD_SELECTOR).count()

            if count == prev_count:
                stable_rounds += 1
                if stable_rounds >= 2:
                    break
            else:
                stable_rounds = 0

            prev_count = count

            if count >= ITEMS_PER_PAGE:
                break

        return page.locator(PRODUCT_CARD_SELECTOR).count()

    # ------------------------------------------------------------------
    # Page fetch
    # ------------------------------------------------------------------

    def _fetch_page(self, page: Page, page_no: int) -> str:
        url = self._build_url(page_no)

        logger.info("Fetching page %d: %s", page_no, url)

        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)

        page.wait_for_selector(PRODUCT_CARD_SELECTOR, timeout=SELECTOR_TIMEOUT)

        rendered = self._render_all_cards(page)

        logger.info("Page %d: %d cards rendered", page_no, rendered)

        return page.content()

    def _fetch_page_with_retry(self, page: Page, page_no: int) -> str | None:
        for attempt in range(1, RETRY_LIMIT + 1):
            try:
                return self._fetch_page(page, page_no)
            except PlaywrightError as exc:
                logger.warning(
                    "Page %d failed (attempt %d/%d): %s",
                    page_no,
                    attempt,
                    RETRY_LIMIT,
                    exc,
                )

                screenshot_path = Path(self._screenshot_dir) / f"failed_{page_no:04d}_{attempt}.png"
                try:
                    page.screenshot(path=str(screenshot_path))
                except Exception:  # pragma: no cover - best-effort debug artifact
                    logger.debug("Could not capture failure screenshot", exc_info=True)

                if attempt < RETRY_LIMIT:
                    time.sleep(RETRY_BACKOFF_BASE**attempt)

        logger.error("Page %d failed after %d attempts", page_no, RETRY_LIMIT)
        return None

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def run(self) -> ScrapeResult:
        """Fetch pages (highest discount first) until the discount tails off."""
        if self._context is None:
            raise RuntimeError("FrasersScraper must be used as a context manager")

        page = self._context.new_page()

        pages: list[str] = []
        failed_pages: list[int] = []
        stopped_early = False

        try:
            for page_no in range(1, self._max_pages + 1):
                html = self._fetch_page_with_retry(page, page_no)

                if html is None:
                    failed_pages.append(page_no)
                    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
                    continue

                pages.append(html)

                page_products = parse_page(html, self._base_url)

                if not page_products:
                    logger.info("Page %d had no parsable products, stopping.", page_no)
                    stopped_early = True
                    break

                max_discount = max(p.discount for p in page_products)

                if max_discount < self._min_discount_to_continue:
                    logger.info(
                        "Page %d max discount %.1f%% < %.1f%%, stopping.",
                        page_no,
                        max_discount,
                        self._min_discount_to_continue,
                    )
                    stopped_early = True
                    break

                if page_no < self._max_pages:
                    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
            else:
                logger.warning(
                    "Reached MAX_PAGES=%d without discount dropping below %.1f%%.",
                    self._max_pages,
                    self._min_discount_to_continue,
                )
        finally:
            page.close()

        logger.info(
            "Scraping finished: pages=%d, failed=%s, stopped_early=%s",
            len(pages),
            failed_pages or "none",
            stopped_early,
        )

        return ScrapeResult(pages=pages, failed_pages=failed_pages, stopped_early=stopped_early)
