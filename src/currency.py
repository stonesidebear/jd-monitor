"""Currency conversion.

JD Sports Global displays prices in GBP (£), EUR (€) or USD ($) depending
on the shopper's detected region. This module converts raw price text
into JPY using the fixed rates in ``config.CURRENCY_RATES``.

The rates are a temporary placeholder; a future revision should replace
them with a live FX rate API.
"""

from __future__ import annotations

import re

from config import CURRENCY_RATES

_SYMBOL_TO_CODE = {
    "£": "GBP",
    "€": "EUR",
    "$": "USD",
}

_NUMBER_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)")


def convert(text: str) -> int:
    """Extract a price from ``text`` and convert it to JPY.

    Args:
        text: Raw price text, e.g. ``"Now £150.00"`` or ``"¥12,000"``.
            Thousands separators are stripped before parsing.

    Returns:
        The price in JPY, rounded to the nearest integer. 0 if no
        numeric value could be found.
    """
    if not text:
        return 0

    match = _NUMBER_RE.search(text)

    if not match:
        return 0

    value = float(match.group(1).replace(",", ""))

    for symbol, code in _SYMBOL_TO_CODE.items():
        if symbol in text:
            return round(value * CURRENCY_RATES[code])

    # 通貨記号がない場合は既に円表記とみなす
    return round(value)
