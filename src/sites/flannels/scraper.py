"""Flannels clearance listing scraper.

Flannels runs Akamai Bot Manager, which fingerprints and blocks headless
Chromium at the HTTP/2 layer (confirmed via manual testing:
``headless=True`` fails immediately with ``ERR_HTTP2_PROTOCOL_ERROR``,
``headless=False`` succeeds). This scraper therefore always launches a
full (non-headless) browser - see ``config_flannels.HEADLESS`` and the
``xvfb-run`` wrapper in the GitHub Actions workflow that gives it a
virtual display in CI.

The listing is sorted by discount percentage (descending), so instead of
walking the entire ~15,000-item catalog like :mod:`src.scraper` does for
JD Sports, this scraper stops as soon as a page's highest discount drops
below ``MIN_DISCOUNT_TO_CONTINUE``. Each page's product grid is also
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

from config_flannels import (
    BASE_URL,
    HEADLESS,
    ITEMS_PER_PAGE,
    LOCALE,
    MAX_PAGES,
    MIN_DISCOUNT_TO_CONTINUE,
    PAGE_TIMEOUT,
    REQUEST_DELAY_MAX,
    REQUEST_DELAY_MIN,
    RETRY_BACKOFF_BASE,
    RETRY_LIMIT,
    SCREENSHOT_DIR,
    SCROLL_MAX_ROUNDS,
    SCROLL_PAUSE_MS,
    SCROLL_STEP_PX,
    SELECTOR_TIMEOUT,
    SORT_QUERY,
    USER_AGENT,
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
)
from src.sites.flannels.parser import PRODUCT_CARD_SELECTOR, parse_page

logger = logging.getLogger(__name__)

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


def _build_url(page_no: int) -> str:
    if page_no == 1:
        return f"{BASE_URL}?{SORT_QUERY}"
    return f"{BASE_URL}?{SORT_QUERY}&dcp={page_no}"


class FlannelsScraper:
    """Playwright-driven scraper for Flannels' discount-sorted clearance listing.

    Usage::

        with FlannelsScraper() as scraper:
            result = scraper.run()
    """

    def __init__(self, headless: bool = HEADLESS, max_pages: int | None = None) -> None:
        self._headless = headless
        self._max_pages = max_pages if max_pages is not None else MAX_PAGES

        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def __enter__(self) -> "FlannelsScraper":
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

        Path(SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

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
        url = _build_url(page_no)

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

                screenshot_path = Path(SCREENSHOT_DIR) / f"failed_{page_no:04d}_{attempt}.png"
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
            raise RuntimeError("FlannelsScraper must be used as a context manager")

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

                page_products = parse_page(html)

                if not page_products:
                    logger.info("Page %d had no parsable products, stopping.", page_no)
                    stopped_early = True
                    break

                max_discount = max(p.discount for p in page_products)

                if max_discount < MIN_DISCOUNT_TO_CONTINUE:
                    logger.info(
                        "Page %d max discount %.1f%% < %.1f%%, stopping.",
                        page_no,
                        max_discount,
                        MIN_DISCOUNT_TO_CONTINUE,
                    )
                    stopped_early = True
                    break

                if page_no < self._max_pages:
                    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
            else:
                logger.warning(
                    "Reached MAX_PAGES=%d without discount dropping below %.1f%%.",
                    self._max_pages,
                    MIN_DISCOUNT_TO_CONTINUE,
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


def scrape(max_pages: int | None = None) -> ScrapeResult:
    """Convenience wrapper: run a full scrape and return the result."""
    with FlannelsScraper(max_pages=max_pages) as scraper:
        return scraper.run()
