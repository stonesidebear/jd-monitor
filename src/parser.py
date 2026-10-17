"""Algolia hits -> Product parsing.

Consumes a :class:`src.scraper.ScrapeResult` (the raw product records
JD Sports Global's listing is built from), converts prices to JPY and
returns deduplicated :class:`~src.product.Product` objects.
"""

from __future__ import annotations

import logging

from src.currency import convert
from src.product import Product
from src.scraper import ScrapeResult

logger = logging.getLogger(__name__)

BASE_URL = "https://www.global.jdsports.com"

# 商品ページURLの末尾に付くストアID (例: /product/<slug>/19701379_jdsportsjx/)
STORE_SUFFIX = "jdsportsjx"

# サイト移行前のURL形式。移行前のCSVの行と突き合わせるためだけに使う。
LEGACY_BASE_URL = "https://m.global.jdsports.com"


def _parse_hit(hit: dict) -> Product | None:
    """Convert a single Algolia product record into a Product, or None."""
    slug = hit.get("slug")
    object_id = hit.get("objectID")

    if not slug or not object_id:
        logger.debug("Skipping hit without slug/objectID: %r", hit.get("name"))
        return None

    url = f"{BASE_URL}/product/{slug}/{object_id}_{STORE_SUFFIX}/"

    # "£25.00" のように通貨記号付きの文字列を使い、currency.convert に
    # 通貨判定と丸めを任せる (数値フィールドだけだと通貨が分からない)。
    price_text = hit.get("priceFormatted") or f"£{hit.get('price', 0)}"
    was_text = hit.get("wasPriceFormatted") or ""

    price = convert(price_text)

    if price <= 0:
        logger.debug("Skipping hit with no parsable price: %s", url)
        return None

    product_ref = hit.get("productRef")
    legacy_url = (
        f"{LEGACY_BASE_URL}/product/{slug}/{product_ref}/" if product_ref else ""
    )

    return Product(
        name=hit.get("name", ""),
        url=url,
        price=price,
        was_price=convert(was_text),
        legacy_url=legacy_url,
    )


def parse(result: ScrapeResult) -> list[Product]:
    """Parse every hit of ``result`` into a deduplicated Product list."""
    products: list[Product] = []
    seen_urls: set[str] = set()

    logger.info("Parsing %d product record(s)", len(result.hits))

    for hit in result.hits:
        product = _parse_hit(hit)

        if product is None or product.url in seen_urls:
            continue

        seen_urls.add(product.url)
        products.append(product)

    logger.info("Products parsed: %d", len(products))

    # 重複/パース不能で大きく減っている場合はページ取得の取りこぼしや
    # サイト仕様変更の兆候なので、ログで気づけるようにする。
    if len(products) < len(result.hits):
        logger.warning(
            "%d of %d product record(s) were dropped (duplicates or unparsable)",
            len(result.hits) - len(products),
            len(result.hits),
        )

    return products
