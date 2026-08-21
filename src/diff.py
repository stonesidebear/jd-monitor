"""Diff logic shared by every site's entry point.

Compares the current scrape against the previous run's persisted CSV so
each site's ``main`` module can mark new/price-down products and figure
out which notifications are genuinely new (not already sent last run).
"""

from __future__ import annotations

from src.product import Product


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
