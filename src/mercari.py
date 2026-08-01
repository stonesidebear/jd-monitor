"""Mercari market price lookup.

Only called for products that already cleared the notification bar
(:func:`src.notifier.get_notifications`), not the full ~1,490-item
catalog - querying Mercari for every product would be slow and
disrespectful of their servers. Results are cached on disk by product
name so a given item is never searched twice.

Playwright only, matching the rest of the project: Mercari's search
results are client-rendered, so a plain HTTP GET would return an empty
shell.
"""

from __future__ import annotations

import json
import logging
import random
import statistics
import time
import urllib.parse
from pathlib import Path

from playwright.sync_api import (
    Browser,
    BrowserContext,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from config import (
    MERCARI_CACHE_PATH,
    MERCARI_REQUEST_DELAY_MAX,
    MERCARI_REQUEST_DELAY_MIN,
    MERCARI_RETRY_LIMIT,
    MERCARI_SAMPLE_SIZE,
    MERCARI_SEARCH_URL,
    MERCARI_TIMEOUT,
)
from src.product import Product

logger = logging.getLogger(__name__)

ITEM_LINK_SELECTOR = 'a[href^="/item/"]'
ITEM_NAME_SELECTOR = '[data-testid="thumbnail-item-name"]'
ITEM_PRICE_SELECTOR = ".merPrice"


def _cache_key(product: Product) -> str:
    return product.name.strip().lower()


def _load_cache() -> dict[str, int]:
    path = Path(MERCARI_CACHE_PATH)

    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Mercari cache file is corrupt, starting fresh: %s", path)
        return {}


def _save_cache(cache: dict[str, int]) -> None:
    path = Path(MERCARI_CACHE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


class MercariClient:
    """Playwright-driven Mercari search client.

    Usage::

        with MercariClient() as client:
            price = client.get_market_price("adidas samba")
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def __enter__(self) -> "MercariClient":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(locale="ja-JP")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def _search(self, query: str) -> int | None:
        """Fetch the search results page and return the median asking price."""
        if self._context is None:
            raise RuntimeError("MercariClient must be used as a context manager")

        page = self._context.new_page()

        try:
            url = MERCARI_SEARCH_URL.format(query=urllib.parse.quote(query))
            page.goto(url, wait_until="domcontentloaded", timeout=MERCARI_TIMEOUT)

            try:
                page.wait_for_selector(ITEM_LINK_SELECTOR, timeout=MERCARI_TIMEOUT)
            except PlaywrightTimeoutError:
                logger.info("No Mercari results for %r", query)
                return None

            links = page.query_selector_all(ITEM_LINK_SELECTOR)

            prices: list[int] = []

            for link in links[:MERCARI_SAMPLE_SIZE]:
                price_el = link.query_selector(ITEM_PRICE_SELECTOR)

                if price_el is None:
                    continue

                digits = "".join(c for c in price_el.inner_text() if c.isdigit())

                if digits:
                    prices.append(int(digits))

            if not prices:
                return None

            return round(statistics.median(prices))
        finally:
            page.close()

    def get_market_price(self, query: str) -> int | None:
        """Return the median Mercari asking price for ``query``, or None."""
        for attempt in range(1, MERCARI_RETRY_LIMIT + 1):
            try:
                return self._search(query)
            except Exception:
                logger.warning(
                    "Mercari search failed for %r (attempt %d/%d)",
                    query,
                    attempt,
                    MERCARI_RETRY_LIMIT,
                    exc_info=True,
                )
                if attempt < MERCARI_RETRY_LIMIT:
                    time.sleep(2.0 * attempt)

        return None


def attach_mercari_prices(products: list[Product]) -> None:
    """Set ``mercari_price`` on each product, using and updating the cache."""
    if not products:
        return

    cache = _load_cache()
    to_fetch = [p for p in products if _cache_key(p) not in cache]

    for p in products:
        cached = cache.get(_cache_key(p))
        if cached:
            p.mercari_price = cached

    if not to_fetch:
        return

    logger.info("Fetching Mercari market price for %d product(s)", len(to_fetch))

    with MercariClient() as client:
        for i, product in enumerate(to_fetch):
            price = client.get_market_price(product.name)

            cache[_cache_key(product)] = price or 0

            if price:
                product.mercari_price = price

            if i < len(to_fetch) - 1:
                time.sleep(
                    random.uniform(MERCARI_REQUEST_DELAY_MIN, MERCARI_REQUEST_DELAY_MAX)
                )

    _save_cache(cache)
