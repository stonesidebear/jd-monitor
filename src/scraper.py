"""JD Sports Global scraper.

Playwright only (no ``requests``). Fetches the SALE listing TOP page,
reads the total page count from the pagination marker, then walks every
AJAX page inside the same authenticated browser context so Cloudflare
cookies and session state stay valid for the whole run.

Pipeline::

    TOP page -> wait for #productListMain -> read data-pagescount
             -> loop AJAX pages -> save HTML -> retry failed pages
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from config import (
    AJAX_DIR,
    AJAX_TIMEOUT,
    CLOUDFLARE_MAX_WAIT,
    CLOUDFLARE_WAIT_INTERVAL,
    HEADLESS,
    ITEMS_PER_PAGE,
    LATEST_HTML,
    LOCALE,
    PAGE_TIMEOUT,
    REQUEST_DELAY_MAX,
    REQUEST_DELAY_MIN,
    RETRY_BACKOFF_BASE,
    RETRY_LIMIT,
    SCREENSHOT_DIR,
    SELECTOR_TIMEOUT,
    URL,
    USER_AGENT,
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
)

logger = logging.getLogger(__name__)

PRODUCT_LIST_SELECTOR = "#productListMain"
PAGE_COUNT_SELECTOR = "li.infiniteScrollLoader"

_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = window.chrome || { runtime: {} };
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters)
);
"""


class ScraperError(Exception):
    """Raised when the scraper cannot recover from a fatal error."""


@dataclass
class ScrapeResult:
    """Container for everything a scrape run produced."""

    main_html: str
    ajax_pages: list[str] = field(default_factory=list)
    total_pages: int = 1
    failed_pages: list[int] = field(default_factory=list)


def _build_ajax_url(base_url: str, start: int) -> str:
    """Build the AJAX pagination URL for a given item offset.

    JD Sports appends ``&from=N`` if the base URL already has a query
    string, otherwise it starts a new one with ``?from=N``.
    """
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}from={start}&AJAX=1"


def _get_total_pages(html: str) -> int:
    """Read ``data-pagescount`` from the infinite-scroll marker."""
    soup = BeautifulSoup(html, "html.parser")
    loader = soup.select_one(PAGE_COUNT_SELECTOR)

    if loader is None:
        logger.warning("infiniteScrollLoader not found, assuming 1 page")
        return 1

    try:
        return int(loader["data-pagescount"])
    except (KeyError, ValueError):
        logger.warning("data-pagescount missing/invalid, assuming 1 page")
        return 1


class JDScraper:
    """Playwright-driven scraper for the JD Sports Global SALE listing.

    Usage::

        with JDScraper() as scraper:
            result = scraper.run()
    """

    def __init__(self, headless: bool = HEADLESS, max_pages: int | None = None) -> None:
        """Initialize the scraper.

        Args:
            headless: Whether to launch Chromium headless.
            max_pages: Optional cap on AJAX pages fetched, for local
                testing. ``None`` means "fetch every page".
        """
        self._headless = headless
        self._max_pages = max_pages

        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._top_html: str | None = None
        self._total_pages: int = 1

    def __enter__(self) -> "JDScraper":
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

        ajax_dir = Path(AJAX_DIR)
        ajax_dir.mkdir(parents=True, exist_ok=True)
        for stale_file in ajax_dir.glob("*.html"):
            stale_file.unlink()

        Path(SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)
        Path(LATEST_HTML).parent.mkdir(parents=True, exist_ok=True)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    # ------------------------------------------------------------------
    # Cloudflare
    # ------------------------------------------------------------------

    def _is_cloudflare_challenge(self, page: Page) -> bool:
        title = page.title()
        if "just a moment" in title.lower():
            return True
        return page.locator("#challenge-running").count() > 0

    def _wait_for_cloudflare(self, page: Page) -> None:
        """Block until the Cloudflare challenge clears, or raise."""
        for attempt in range(1, CLOUDFLARE_MAX_WAIT + 1):
            if not self._is_cloudflare_challenge(page):
                return

            logger.info(
                "Cloudflare challenge detected, waiting (%d/%d)",
                attempt,
                CLOUDFLARE_MAX_WAIT,
            )
            page.wait_for_timeout(CLOUDFLARE_WAIT_INTERVAL)

        if self._is_cloudflare_challenge(page):
            raise ScraperError("Cloudflare challenge did not clear in time")

    # ------------------------------------------------------------------
    # TOP page
    # ------------------------------------------------------------------

    def _fetch_top_page(self, page: Page) -> tuple[str, int]:
        """Fetch the SALE TOP page and return (html, total_pages)."""
        logger.info("Opening TOP page: %s", URL)

        page.goto(URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)

        self._wait_for_cloudflare(page)

        page.wait_for_selector(
            PRODUCT_LIST_SELECTOR, timeout=SELECTOR_TIMEOUT
        )

        html = page.content()

        Path(LATEST_HTML).write_text(html, encoding="utf-8")

        screenshot_path = Path(SCREENSHOT_DIR) / "top.png"
        page.screenshot(path=str(screenshot_path), full_page=False)

        total_pages = _get_total_pages(html)

        logger.info(
            "TOP page loaded: %s bytes, %d pages total",
            f"{len(html):,}",
            total_pages,
        )

        return html, total_pages

    # ------------------------------------------------------------------
    # AJAX pages
    # ------------------------------------------------------------------

    def _fetch_ajax_page(self, page: Page, page_no: int) -> str:
        """Fetch a single AJAX page. Raises on failure."""
        start = (page_no - 1) * ITEMS_PER_PAGE
        ajax_url = _build_ajax_url(URL, start)

        logger.info("Fetching page %d: %s", page_no, ajax_url)

        page.goto(ajax_url, wait_until="domcontentloaded", timeout=AJAX_TIMEOUT)

        self._wait_for_cloudflare(page)

        page.wait_for_selector(
            "li.productListItem", timeout=SELECTOR_TIMEOUT
        )

        html = page.content()

        file_path = Path(AJAX_DIR) / f"{page_no - 2:04d}.html"
        file_path.write_text(html, encoding="utf-8")

        return html

    def _fetch_ajax_page_with_retry(self, page: Page, page_no: int) -> str | None:
        """Fetch one AJAX page, retrying with exponential backoff."""
        for attempt in range(1, RETRY_LIMIT + 1):
            try:
                return self._fetch_ajax_page(page, page_no)
            except (PlaywrightTimeoutError, ScraperError) as exc:
                logger.warning(
                    "Page %d failed (attempt %d/%d): %s",
                    page_no,
                    attempt,
                    RETRY_LIMIT,
                    exc,
                )

                screenshot_path = (
                    Path(SCREENSHOT_DIR) / f"failed_{page_no:04d}_{attempt}.png"
                )
                try:
                    page.screenshot(path=str(screenshot_path))
                except Exception:  # pragma: no cover - best-effort debug artifact
                    logger.debug("Could not capture failure screenshot", exc_info=True)

                if attempt < RETRY_LIMIT:
                    backoff = RETRY_BACKOFF_BASE ** attempt
                    time.sleep(backoff)

        logger.error("Page %d failed after %d attempts", page_no, RETRY_LIMIT)
        return None

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def open_top_page(self) -> tuple[str, int]:
        """Fetch only the TOP page and return (html, total_pages).

        Cheap relative to a full scrape: it skips every AJAX page, the
        AI estimator, and the market-price lookups. Used to check
        whether anything changed before paying for the full run - see
        :mod:`src.watch`. Must be called before :meth:`scrape_remaining`.
        """
        if self._context is None:
            raise RuntimeError("JDScraper must be used as a context manager")

        self._page = self._context.new_page()

        main_html, total_pages = self._fetch_top_page(self._page)

        if self._max_pages is not None:
            total_pages = min(total_pages, self._max_pages)

        self._top_html = main_html
        self._total_pages = total_pages

        return main_html, total_pages

    def scrape_remaining(self) -> ScrapeResult:
        """Fetch every AJAX page after :meth:`open_top_page` was called."""
        if self._page is None or self._top_html is None:
            raise RuntimeError("open_top_page() must be called first")

        page = self._page
        main_html = self._top_html
        total_pages = self._total_pages

        html_by_page: dict[int, str] = {}
        failed_pages: list[int] = []

        page_numbers = range(2, total_pages + 1)

        for page_no in page_numbers:
            html = self._fetch_ajax_page_with_retry(page, page_no)

            if html is None:
                failed_pages.append(page_no)
            else:
                html_by_page[page_no] = html

            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        if failed_pages:
            logger.info("Retrying %d failed page(s): %s", len(failed_pages), failed_pages)

            still_failed: list[int] = []

            for page_no in failed_pages:
                html = self._fetch_ajax_page_with_retry(page, page_no)

                if html is None:
                    still_failed.append(page_no)
                else:
                    html_by_page[page_no] = html

                time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

            failed_pages = still_failed

        page.close()

        ajax_pages = [html_by_page[n] for n in sorted(html_by_page)]

        logger.info(
            "Scraping finished: main=%s bytes, ajax_pages=%d/%d, failed=%s",
            f"{len(main_html):,}",
            len(ajax_pages),
            total_pages - 1,
            failed_pages or "none",
        )

        return ScrapeResult(
            main_html=main_html,
            ajax_pages=ajax_pages,
            total_pages=total_pages,
            failed_pages=failed_pages,
        )

    def run(self) -> ScrapeResult:
        """Run the full scrape: TOP page + every AJAX page."""
        self.open_top_page()
        return self.scrape_remaining()


def scrape(max_pages: int | None = None) -> ScrapeResult:
    """Convenience wrapper: run a full scrape and return the result."""
    with JDScraper(max_pages=max_pages) as scraper:
        return scraper.run()
