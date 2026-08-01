"""Profit calculation engine.

Sets ``expected_price``, ``profit`` and ``grade`` on each ``Product``.
"""

from __future__ import annotations

import logging

from config import GRADE_S_DISCOUNT, GRADE_THRESHOLDS
from src.ai_estimator import estimate_price as ai_estimate_price
from src.price_estimator import estimate_price as static_estimate_price
from src.product import Product

logger = logging.getLogger(__name__)


def calc_grade(product: Product) -> str:
    """Rank a product S/A/B/C/D based on discount and profit."""
    if product.discount >= GRADE_S_DISCOUNT:
        return "S"

    if product.profit >= GRADE_THRESHOLDS["S"]:
        return "S"
    if product.profit >= GRADE_THRESHOLDS["A"]:
        return "A"
    if product.profit >= GRADE_THRESHOLDS["B"]:
        return "B"
    if product.profit >= GRADE_THRESHOLDS["C"]:
        return "C"

    return "D"


def calculate_profit(product: Product) -> Product:
    """Populate ``expected_price``, ``profit`` and ``grade`` on ``product``.

    AI estimation (OpenAI) is tried first; if it is disabled, has no
    answer, or the request fails, the static keyword dictionary is used
    instead so a bad API call never blanks out a known product.
    """
    expected_price = ai_estimate_price(product)

    if expected_price is None:
        expected_price = static_estimate_price(product)

    product.expected_price = expected_price

    if expected_price == 0:
        product.profit = 0
        product.grade = "?"
        return product

    product.profit = expected_price - product.price
    product.grade = calc_grade(product)

    return product


def calculate_all(products: list[Product]) -> list[Product]:
    """Run ``calculate_profit`` over every product and log a top-10 summary."""
    logger.info("Calculating profit for %d products", len(products))

    for product in products:
        calculate_profit(product)

    ranked = sorted(products, key=lambda p: p.profit, reverse=True)

    for p in ranked[:10]:
        logger.info("%6d yen | %s | %s", p.profit, p.grade, p.name)

    return products
