"""JD Sports Global scraper.

Playwright only (no ``requests``). JD Sports Global moved its listing
pages to a Next.js + Algolia front end (the old ``m.global`` site now
redirects there): the first 72 products are embedded in the page's
``__NEXT_DATA__`` JSON, and the rest load through the "Load more"
button, which POSTs to Algolia and appends the next 72. Everything runs
inside one browser context so Cloudflare cookies and session state stay
valid for the whole run.

Rather than scraping rendered markup, this reads the structured product
hits straight from the SSR data and from the Algolia responses the
"Load more" button triggers - far less brittle than CSS selectors.

Pipeline::

    TOP page -> read __NEXT_DATA__ (page-0 hits, total hit count, page count)
             -> click "Load more" per remaining page, capturing each
                Algolia response -> retry failed pages
"""

from __future__ import annotations

import json
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

from config import (
    AJAX_DIR,
    AJAX_TIMEOUT,
    CLOUDFLARE_MAX_WAIT,
    CLOUDFLARE_WAIT_INTERVAL,
    HEADLESS,
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

# 一覧ページが描画された目印 (商品カードへのリンク)
PRODUCT_LINK_SELECTOR = 'a[href*="/product/"]'

LOAD_MORE_SELECTOR = '[data-test-id="load-more"]'

COOKIE_REJECT_SELECTOR = "#onetrust-reject-all-handler"

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
    """Container for everything a scrape run produced.

    ``hits`` are raw Algolia product records (see :mod:`src.parser`).
    """

    hits: list[dict] = field(default_factory=list)
    total_hits: int = 0
    total_pages: int = 1
    failed_pages: list[int] = field(default_factory=list)


def _requested_page(response) -> int | None:
    """Algolia page index a captured ``/run`` request asked for, or None."""
    try:
        body = json.loads(response.request.post_data or "")
        return int(body["params"]["page"])
    except (ValueError, KeyError, TypeError):
        return None


def _extract_results(payload: dict) -> dict:
    """Return the first Algolia ``results`` entry from an SSR/XHR payload."""
    try:
        return payload["results"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ScraperError(f"Unexpected Algolia response shape: {exc!r}") from exc


def _extract_ssr_results(next_data: dict) -> dict:
    """Return the page-0 Algolia results from the ``__NEXT_DATA__`` JSON."""
    try:
        initial = next_data["props"]["pageProps"]["searchServerState"]["initialResults"]
        composition = next(iter(initial.values()))
        return composition["results"][0]
    except (KeyError, IndexError, TypeError, StopIteration) as exc:
        raise ScraperError(
            f"Listing data not found in __NEXT_DATA__ (site layout changed?): {exc!r}"
        ) from exc


class JDScraper:
    """Playwright-driven scraper for a JD Sports Global SALE listing.

    Usage::

        with JDScraper() as scraper:
            result = scraper.run()
    """

    def __init__(
        self,
        url: str = URL,
        headless: bool = HEADLESS,
        max_pages: int | None = None,
    ) -> None:
        """Initialize the scraper.

        Args:
            url: SALE listing URL to scrape. Defaults to the JD Sports
                Global sportswear SALE listing; other monitors (e.g.
                uniforms, a single brand) pass their own category URL.
            headless: Whether to launch Chromium headless.
            max_pages: Optional cap on result pages fetched (72 products
                each), for local testing. ``None`` means "fetch every
                page".
        """
        self._url = url
        self._headless = headless
        self._max_pages = max_pages

        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._first_hits: list[dict] | None = None
        self._total_hits: int = 0
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
        for stale_file in [*ajax_dir.glob("*.json"), *ajax_dir.glob("*.html")]:
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
    # Cloudflare / cookie consent
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

    def _dismiss_cookie_banner(self, page: Page, wait_ms: int = 0) -> None:
        """Reject non-essential cookies if the consent dialog is up.

        The dialog's overlay intercepts clicks on "Load more", so it has
        to go. Best-effort: a missing banner is the normal case once it
        has been dismissed.
        """
        reject = page.locator(COOKIE_REJECT_SELECTOR)

        try:
            if wait_ms:
                reject.first.wait_for(state="visible", timeout=wait_ms)

            if reject.count() > 0 and reject.first.is_visible():
                reject.first.click(timeout=5_000)
                page.wait_for_timeout(500)
        except PlaywrightError:
            logger.debug("No cookie banner to dismiss", exc_info=True)

    # ------------------------------------------------------------------
    # TOP page
    # ------------------------------------------------------------------

    def _fetch_top_page(self, page: Page) -> tuple[str, list[dict], int, int]:
        """Fetch the TOP page; return (html, page-0 hits, total hits, pages)."""
        logger.info("Opening TOP page: %s", self._url)

        page.goto(self._url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)

        self._wait_for_cloudflare(page)

        page.wait_for_selector(PRODUCT_LINK_SELECTOR, timeout=SELECTOR_TIMEOUT)

        raw = page.evaluate(
            "() => document.getElementById('__NEXT_DATA__')?.textContent ?? null"
        )
        if not raw:
            raise ScraperError("__NEXT_DATA__ not found on listing page")

        results = _extract_ssr_results(json.loads(raw))

        hits = results.get("hits") or []
        total_hits = int(results.get("nbHits", len(hits)))
        total_pages = max(int(results.get("nbPages", 1)), 1)

        if not hits:
            raise ScraperError("Listing page returned no products")

        html = page.content()

        Path(LATEST_HTML).write_text(html, encoding="utf-8")

        screenshot_path = Path(SCREENSHOT_DIR) / "top.png"
        page.screenshot(path=str(screenshot_path), full_page=False)

        logger.info(
            "TOP page loaded: %s bytes, %d products across %d pages",
            f"{len(html):,}",
            total_hits,
            total_pages,
        )

        return html, hits, total_hits, total_pages

    def _fetch_top_page_with_retry(self, page: Page) -> tuple[str, list[dict], int, int]:
        """Fetch the TOP page, retrying with exponential backoff."""
        for attempt in range(1, RETRY_LIMIT + 1):
            try:
                return self._fetch_top_page(page)
            except (PlaywrightError, ScraperError) as exc:
                logger.warning(
                    "TOP page failed (attempt %d/%d): %s",
                    attempt,
                    RETRY_LIMIT,
                    exc,
                )

                screenshot_path = Path(SCREENSHOT_DIR) / f"failed_top_{attempt}.png"
                try:
                    page.screenshot(path=str(screenshot_path))
                except Exception:  # pragma: no cover - best-effort debug artifact
                    logger.debug("Could not capture failure screenshot", exc_info=True)

                if attempt < RETRY_LIMIT:
                    time.sleep(RETRY_BACKOFF_BASE**attempt)

        raise ScraperError(f"TOP page failed after {RETRY_LIMIT} attempts")

    # ------------------------------------------------------------------
    # "Load more" pages
    # ------------------------------------------------------------------

    def _load_more(self, page: Page, page_index: int) -> list[dict]:
        """Click "Load more" once and return the hits Algolia sends back.

        Raises on failure so the caller can retry.
        """
        self._dismiss_cookie_banner(page)

        # The button is rendered client-side after hydration (it is not in
        # the server HTML), so on a slow machine it can appear seconds
        # after the page "loads". Wait for it rather than assuming.
        button = page.locator(LOAD_MORE_SELECTOR).first
        button.wait_for(state="attached", timeout=SELECTOR_TIMEOUT)

        logger.info("Loading page index %d", page_index)

        # Only accept the response to *this* page's request. Right after
        # hydration the page re-runs its initial (page 0) search on its
        # own, and that late response would otherwise be mistaken for the
        # reply to the click - silently returning page 0 again and
        # dropping a real page of products.
        with page.expect_response(
            lambda r: (
                "algolia" in r.url
                and "/run" in r.url
                and r.request.method == "POST"
                and r.ok
                and _requested_page(r) == page_index
            ),
            timeout=AJAX_TIMEOUT,
        ) as response_info:
            # A real mouse click gets swallowed whenever the consent
            # dialog's overlay is up (it can appear late on a slow
            # machine), so click from JS instead - that works either way.
            button.evaluate("el => el.click()")

        results = _extract_results(response_info.value.json())

        hits = results.get("hits") or []

        if not hits:
            raise ScraperError(f"Algolia returned no hits for page index {page_index}")

        served_page = int(results.get("page", -1))

        if served_page != page_index:
            raise ScraperError(
                f"Asked Algolia for page index {page_index} but got {served_page}"
            )

        file_path = Path(AJAX_DIR) / f"{page_index:04d}.json"
        file_path.write_text(json.dumps(hits, ensure_ascii=False), encoding="utf-8")

        return hits

    def _load_more_with_retry(self, page: Page, page_index: int) -> list[dict] | None:
        """Load one more page, retrying with exponential backoff."""
        for attempt in range(1, RETRY_LIMIT + 1):
            try:
                return self._load_more(page, page_index)
            except (PlaywrightError, ScraperError) as exc:
                logger.warning(
                    "Page index %d failed (attempt %d/%d): %s",
                    page_index,
                    attempt,
                    RETRY_LIMIT,
                    exc,
                )

                screenshot_path = (
                    Path(SCREENSHOT_DIR) / f"failed_{page_index:04d}_{attempt}.png"
                )
                try:
                    page.screenshot(path=str(screenshot_path))
                except Exception:  # pragma: no cover - best-effort debug artifact
                    logger.debug("Could not capture failure screenshot", exc_info=True)

                if attempt < RETRY_LIMIT:
                    time.sleep(RETRY_BACKOFF_BASE**attempt)

        logger.error("Page index %d failed after %d attempts", page_index, RETRY_LIMIT)
        return None

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def open_top_page(self) -> tuple[str, int]:
        """Fetch only the TOP page and return (html, total_hits).

        Cheap relative to a full scrape: it skips every "Load more"
        request, the AI estimator, and the market-price lookups. The
        returned total product count is the change signal used to decide
        whether the full run is worth doing - see :mod:`src.watch`. Must
        be called before :meth:`scrape_remaining`.
        """
        if self._context is None:
            raise RuntimeError("JDScraper must be used as a context manager")

        self._page = self._context.new_page()

        html, hits, total_hits, total_pages = self._fetch_top_page_with_retry(self._page)

        if self._max_pages is not None:
            total_pages = min(total_pages, self._max_pages)

        self._first_hits = hits
        self._total_hits = total_hits
        self._total_pages = total_pages

        return html, total_hits

    def scrape_remaining(self) -> ScrapeResult:
        """Load every remaining page after :meth:`open_top_page` was called."""
        if self._page is None or self._first_hits is None:
            raise RuntimeError("open_top_page() must be called first")

        page = self._page
        total_pages = self._total_pages

        # Best effort: the dialog shows up a few seconds after load.
        self._dismiss_cookie_banner(page, wait_ms=10_000)

        hits_by_page: dict[int, list[dict]] = {0: self._first_hits}
        failed_pages: list[int] = []

        # Algolia pages are zero-based; page 0 came with the TOP page.
        for page_index in range(1, total_pages):
            hits = self._load_more_with_retry(page, page_index)

            if hits is None:
                failed_pages.append(page_index)
                # Without a working button no later page can load either.
                if page.locator(LOAD_MORE_SELECTOR).count() == 0:
                    failed_pages.extend(range(page_index + 1, total_pages))
                    break
            else:
                hits_by_page[page_index] = hits

            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        page.close()

        if failed_pages:
            # An incomplete listing must never be saved as the new state:
            # the missing products would look "new" on the next run (a
            # flood of re-notifications) and the catalog-size gate would
            # then consider the catalog already handled.
            raise ScraperError(
                f"Incomplete scrape: {len(failed_pages)} of {total_pages} page(s) "
                f"failed {failed_pages}; refusing to save partial data"
            )

        all_hits = [hit for n in sorted(hits_by_page) for hit in hits_by_page[n]]

        logger.info(
            "Scraping finished: pages=%d/%d, hits=%d, failed=%s",
            len(hits_by_page),
            total_pages,
            len(all_hits),
            failed_pages or "none",
        )

        return ScrapeResult(
            hits=all_hits,
            total_hits=self._total_hits,
            total_pages=total_pages,
            failed_pages=failed_pages,
        )

    def run(self) -> ScrapeResult:
        """Run the full scrape: TOP page + every remaining page."""
        self.open_top_page()
        return self.scrape_remaining()


def scrape(max_pages: int | None = None) -> ScrapeResult:
    """Convenience wrapper: run a full scrape and return the result."""
    with JDScraper(max_pages=max_pages) as scraper:
        return scraper.run()
