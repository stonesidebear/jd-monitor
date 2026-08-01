"""HTML -> Product parsing.

Consumes a :class:`src.scraper.ScrapeResult` (TOP page HTML + every AJAX
page HTML), extracts each product listing, converts prices to JPY and
returns deduplicated :class:`~src.product.Product` objects.
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup
from bs4.element import Tag

from src.currency import convert
from src.product import Product
from src.scraper import ScrapeResult

logger = logging.getLogger(__name__)

BASE_URL = "https://m.global.jdsports.com"

PRODUCT_ITEM_SELECTOR = "li.productListItem"


def _extract_text(item: Tag, selector: str) -> str:
    node = item.select_one(selector)
    return node.get_text(" ", strip=True) if node else ""


def _parse_item(item: Tag) -> Product | None:
    """Convert a single ``li.productListItem`` into a Product, or None."""
    image = item.select_one("a.itemImage")
    if image is None:
        return None

    href = image.get("href", "")
    if not href:
        return None

    url = BASE_URL + href

    name = _extract_text(item, ".itemTitle a")

    # ".now" は割引後価格のみを含む。".pri" には Save% も含まれ得るため
    # 優先度は .now > .pri とする。
    price_text = _extract_text(item, ".now") or _extract_text(item, ".pri")
    was_text = _extract_text(item, ".was")

    price = convert(price_text)

    if price <= 0:
        logger.debug("Skipping item with no parsable price: %s", url)
        return None

    return Product(
        name=name,
        url=url,
        price=price,
        was_price=convert(was_text),
    )


def parse_page(html: str) -> list[Product]:
    """Parse a single HTML page into Products (no cross-page dedup)."""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(PRODUCT_ITEM_SELECTOR)

    products = [_parse_item(item) for item in items]

    return [p for p in products if p is not None]


def parse(result: ScrapeResult) -> list[Product]:
    """Parse every page of ``result`` into a deduplicated Product list."""
    products: list[Product] = []
    seen_urls: set[str] = set()

    html_pages = [result.main_html, *result.ajax_pages]

    logger.info("Parsing %d HTML page(s)", len(html_pages))

    for page_no, html in enumerate(html_pages):
        page_products = parse_page(html)

        logger.debug("Page %02d: %d parsed items", page_no, len(page_products))

        for product in page_products:
            if product.url in seen_urls:
                continue

            seen_urls.add(product.url)
            products.append(product)

    logger.info("Products parsed: %d", len(products))

    return products
