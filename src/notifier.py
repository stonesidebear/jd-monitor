"""Notification decision engine.

通知条件: discount >= DISCOUNT_THRESHOLD OR profit >= PROFIT_THRESHOLD

新商品 / 値下げ はこの条件を満たした通知の「理由タグ」としてのみ使う
(単体で通知をトリガーしない。単体トリガーにすると巡回のたびに大量の
新着SALE商品が通知対象になり、「利益商品だけ通知される」というゴール
と矛盾するため)。
"""

from __future__ import annotations

import logging

from config import DISCOUNT_THRESHOLD, PROFIT_THRESHOLD
from src.product import Product

logger = logging.getLogger(__name__)


def should_notify(product: Product) -> bool:
    """True if ``product`` clears the discount or profit bar."""
    return (
        product.discount >= DISCOUNT_THRESHOLD
        or product.profit >= PROFIT_THRESHOLD
    )


def notification_reasons(product: Product) -> list[str]:
    """Human-readable reason tags for a notified product."""
    reasons = []

    if product.discount >= DISCOUNT_THRESHOLD:
        reasons.append(f"{DISCOUNT_THRESHOLD:.0f}% OFF")

    if product.profit >= PROFIT_THRESHOLD:
        reasons.append("HIGH PROFIT")

    if product.is_new:
        reasons.append("NEW")

    if product.is_price_down:
        reasons.append("PRICE DOWN")

    if product.grade == "S":
        reasons.append("S RANK")

    return reasons


def get_notifications(products: list[Product]) -> list[Product]:
    """Return the subset of ``products`` that should be notified."""
    return [p for p in products if should_notify(p)]


def print_notifications(products: list[Product]) -> None:
    """Log every notification target with full detail."""
    notify_list = get_notifications(products)

    logger.info("Notification targets: %d", len(notify_list))

    if not notify_list:
        return

    for i, p in enumerate(notify_list, start=1):
        lines = [
            f"[{i}] {p.name}",
            f"Price          : ¥{p.price:,}",
        ]

        if p.was_price:
            lines.append(f"Was            : ¥{p.was_price:,}")

        lines.append(f"Discount       : {p.discount:.1f}%")

        if p.expected_price:
            lines.append(f"Expected Price : ¥{p.expected_price:,}")

        if p.mercari_price:
            lines.append(f"Mercari Price  : ¥{p.mercari_price:,}")

        lines.append(f"Profit         : ¥{p.profit:,}")
        lines.append(f"Grade          : {p.grade}")

        reasons = notification_reasons(p)
        if reasons:
            lines.append("Reason         : " + ", ".join(reasons))

        lines.append(f"URL            : {p.url}")

        logger.info("\n".join(lines) + "\n" + "-" * 60)

        p.notified = True
