"""JD Monitor v1.0 - entry point.

Scrapes the JD Sports Global SALE listing, diffs it against the previous
run, calculates expected profit, logs notification targets and persists
the new snapshot.
"""

from __future__ import annotations

import argparse
import logging

from src.logging_config import setup_logging
from src.mailer import send_notification_email
from src.mercari import attach_mercari_prices
from src.notifier import get_notifications, print_notifications
from src.parser import parse
from src.product import Product
from src.profit import calculate_all
from src.scraper import scrape
from src.storage import load_products, save_history, save_products

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JD Monitor v1.0")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit the number of AJAX pages fetched (debug/testing only).",
    )
    parser.add_argument(
        "--skip-mercari",
        action="store_true",
        help="Skip Mercari market price lookup (debug/testing only).",
    )
    parser.add_argument(
        "--skip-email",
        action="store_true",
        help="Skip sending the notification email (debug/testing only).",
    )
    return parser.parse_args()


def _apply_diff(products: list[Product], previous: dict[str, dict]) -> tuple[int, int]:
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


def _already_notified_urls(previous: dict[str, dict]) -> set[str]:
    """URLs that were already sent in a prior run's notification.

    A product's ``notified`` CSV column reflects whether it qualified
    for notification *last* run; comparing against it lets us send only
    genuinely new notifications each run instead of re-sending the same
    still-on-sale items every few hours.
    """
    return {url for url, row in previous.items() if row.get("notified") == "True"}


def main() -> None:
    setup_logging()

    args = _parse_args()

    logger.info("Loading previous products...")
    previous = load_products()
    logger.info("Previous products: %d", len(previous))

    result = scrape(max_pages=args.max_pages)

    products = parse(result)

    new_count, price_down_count = _apply_diff(products, previous)

    calculate_all(products)

    # 今回条件を満たした商品全体 (コンソールログ・notified永続化に使う)
    notify_targets = get_notifications(products)

    # そのうち前回まだ通知していなかったものだけ (メール・メルカリ相場取得に使う)
    already_notified = _already_notified_urls(previous)
    new_targets = [p for p in notify_targets if p.url not in already_notified]

    if new_targets and not args.skip_mercari:
        attach_mercari_prices(new_targets)

    print_notifications(products)

    if not args.skip_email:
        send_notification_email(new_targets)

    logger.info("=" * 60)
    logger.info("New Products    : %d", new_count)
    logger.info("Price Down      : %d", price_down_count)
    logger.info("Qualifying      : %d", len(notify_targets))
    logger.info("Notified (new)  : %d", len(new_targets))
    logger.info("Failed Pages    : %s", result.failed_pages or "none")
    logger.info("=" * 60)

    save_products(products)
    save_history(products)


if __name__ == "__main__":
    main()
