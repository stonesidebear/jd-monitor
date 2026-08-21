"""HTML -> Product parsing for Flannels' clearance listing.

Each page's HTML is expected to already have every product card fully
rendered (see :mod:`src.sites.flannels.scraper`, which scrolls the
virtualized grid before capturing the page) - this module just extracts
data from the resulting markup.
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup
from bs4.element import Tag

from src.currency import convert
from src.product import Product

logger = logging.getLogger(__name__)

PRODUCT_CARD_SELECTOR = '[data-testid="product-card"]'
SPONSORED_LABEL_SELECTOR = '[data-testid="sponsored-label"]'


def _extract_text(item: Tag, selector: str) -> str:
    node = item.select_one(selector)
    return node.get_text(" ", strip=True) if node else ""


def _parse_card(card: Tag) -> Product | None:
    """Convert a single ``[data-testid="product-card"]`` into a Product."""
    if card.select_one(SPONSORED_LABEL_SELECTOR) is not None:
        return None

    href = card.get("href", "")
    if not href:
        return None

    url = href if href.startswith("http") else f"https://www.flannels.com{href}"

    brand = _extract_text(card, '[data-testid="product-card-brand"]')
    name_suffix = _extract_text(card, '[data-testid="product-card-name-without-brand"]')
    name = f"{brand} {name_suffix}".strip()

    ticket_text = _extract_text(card, '[data-testid="ticket-price"]')
    price_full_text = _extract_text(card, '[data-testid="price"]')

    # ".price" は割引時「現在価格+定価」が連結して入る (例: "£199£1,999")。
    # 定価テキストを取り除いた残りが現在価格。
    sale_text = price_full_text.replace(ticket_text, "", 1) if ticket_text else price_full_text

    price = convert(sale_text)

    if price <= 0:
        logger.debug("Skipping card with no parsable price: %s", url)
        return None

    return Product(
        name=name,
        url=url,
        price=price,
        was_price=convert(ticket_text),
    )


def parse_page(html: str) -> list[Product]:
    """Parse a single fully-rendered listing page into Products."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(PRODUCT_CARD_SELECTOR)

    products = [_parse_card(card) for card in cards]

    return [p for p in products if p is not None]


def parse(html_pages: list[str]) -> list[Product]:
    """Parse every page into a deduplicated Product list."""
    products: list[Product] = []
    seen_urls: set[str] = set()

    logger.info("Parsing %d HTML page(s)", len(html_pages))

    for page_no, html in enumerate(html_pages, start=1):
        page_products = parse_page(html)

        logger.debug("Page %02d: %d parsed items", page_no, len(page_products))

        for product in page_products:
            if product.url in seen_urls:
                continue

            seen_urls.add(product.url)
            products.append(product)

    logger.info("Products parsed: %d", len(products))

    return products
