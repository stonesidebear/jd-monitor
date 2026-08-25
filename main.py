"""JD Monitor v1.0 - entry point.

Scrapes the JD Sports Global SALE listing, diffs it against the previous
run, calculates expected profit, logs notification targets and persists
the new snapshot.
"""

from __future__ import annotations

import argparse
import logging

from config import URL
from src.diff import already_notified_urls, apply_diff
from src.logging_config import setup_logging
from src.mailer import send_notification_email, send_update_detected_email
from src.mercari import attach_mercari_prices
from src.notifier import get_notifications, print_notifications
from src.parser import parse
from src.profit import calculate_all
from src.scraper import JDScraper
from src.storage import load_products, save_history, save_products
from src.watch import load_page_count, save_page_count

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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run the full scrape even if the page count is unchanged.",
    )
    return parser.parse_args()


def main() -> None:
    setup_logging()

    args = _parse_args()

    logger.info("Loading previous products...")
    previous = load_products()
    logger.info("Previous products: %d", len(previous))

    with JDScraper(max_pages=args.max_pages) as scraper:
        _, total_pages = scraper.open_top_page()

        previous_pages = load_page_count()
        changed = total_pages != previous_pages

        if not changed and not args.force:
            logger.info(
                "Catalog page count unchanged (%d pages) - skipping full scrape.",
                total_pages,
            )
            return

        save_page_count(total_pages)

        if changed:
            logger.info(
                "Catalog page count changed (%s -> %d), running full scrape.",
                previous_pages,
                total_pages,
            )
            if not args.skip_email:
                send_update_detected_email(URL, previous_pages, total_pages)
        else:
            logger.info("--force given with no page-count change, running full scrape anyway.")

        result = scraper.scrape_remaining()

    products = parse(result)

    new_count, price_down_count = apply_diff(products, previous)

    calculate_all(products)

    # 今回条件を満たした商品全体 (コンソールログ・notified永続化に使う)
    notify_targets = get_notifications(products)

    # そのうち前回まだ通知していなかったものだけ (メール・メルカリ相場取得に使う)
    already_notified = already_notified_urls(previous)
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
