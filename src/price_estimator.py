"""Expected resale price estimation.

Currently a fixed keyword -> price lookup table. This is the seam where
future revisions plug in real market data (OpenAI price estimation,
StockX, Mercari) without touching :mod:`src.profit`.
"""

from __future__ import annotations

from src.product import Product

EXPECTED_PRICES: dict[str, int] = {
    "Air Max 95": 28000,
    "Air Max Plus": 26000,
    "Air Max TL": 24000,
    "Air Max DN": 24000,
    "Vomero": 23000,
    "Jordan 4": 34000,
    "Jordan 3": 30000,
    "Jordan 1": 22000,
    "Jordan": 24000,
    "Samba": 18000,
    "Gazelle": 17000,
    "Campus": 16000,
    "9060": 23000,
    "1906": 22000,
    "2002R": 21000,
    "530": 17000,
    "XT-6": 27000,
    "Gel-Kayano": 23000,
    "Gel-NYC": 22000,
}


def estimate_price(product: Product) -> int:
    """Estimate the resale price of ``product`` in JPY.

    Matches the longest keyword found in the product name so that more
    specific models (e.g. "Jordan 4") win over generic ones (e.g.
    "Jordan"). Returns 0 if no keyword matches.
    """
    name = product.name.lower()

    best_price = 0
    best_keyword = ""

    for keyword, price in EXPECTED_PRICES.items():
        if keyword.lower() in name and len(keyword) > len(best_keyword):
            best_keyword = keyword
            best_price = price

    return best_price
