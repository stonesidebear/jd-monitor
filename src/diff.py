"""Diff logic shared by every site's entry point.

Compares the current scrape against the previous run's persisted CSV so
each site's ``main`` module can mark new/price-down products and figure
out which notifications are genuinely new (not already sent last run).
"""

from __future__ import annotations

from src.product import Product


def adopt_legacy_urls(products: list[Product], previous: dict[str, dict]) -> int:
    """Re-key ``previous`` rows saved under a product's old-site URL.

    JD Sports Global changed its product URL format when it moved to its
    new site, so every row in a pre-migration CSV would otherwise look
    like a brand-new product (and a flood of already-seen items would be
    re-notified as new). Each product carries the URL it used to have in
    ``legacy_url``; if ``previous`` has a row under that URL and none
    under the new one, move it across so price history and the
    ``notified`` flag carry over. Mutates ``previous`` in place and
    returns how many rows were moved. A no-op once the CSV has been
    saved with the new URLs.
    """
    moved = 0

    for product in products:
        legacy = product.legacy_url

        if legacy and product.url not in previous and legacy in previous:
            previous[product.url] = previous.pop(legacy)
            moved += 1

    return moved


def apply_diff(products: list[Product], previous: dict[str, dict]) -> tuple[int, int]:
    """Mark ``is_new`` / ``is_price_down`` on each product in-place."""
    new_count = 0
    price_down_count = 0

    for product in products:
        old = previous.get(product.url)

        if old is None:
            product.is_new = True
            new_count += 1
            continue

        try:
            old_price = int(old["price"])
        except (KeyError, ValueError):
            old_price = product.price

        if product.price < old_price:
            product.is_price_down = True
            price_down_count += 1

    return new_count, price_down_count


def already_notified_urls(previous: dict[str, dict]) -> set[str]:
    """URLs that were already sent in a prior run's notification.

    A product's ``notified`` CSV column reflects whether it qualified
    for notification *last* run; comparing against it lets us send only
    genuinely new notifications each run instead of re-sending the same
    still-on-sale items every run.
    """
    return {url for url, row in previous.items() if row.get("notified") == "True"}
