"""Flannels Monitor - entry point.

Scrapes Flannels' discount-sorted men's clearance listing, diffs it
against the previous run, calculates expected profit, logs notification
targets and persists the new snapshot. Mirrors main.py's pipeline shape
(see src/diff.py for the shared diff logic) but has no page-count
skip-gate: the discount-sorted early-stop in
:mod:`src.sites.flannels.scraper` already keeps each run cheap
regardless of the site's total catalog size.
"""

from __future__ import annotations

import argparse
import logging

from config_flannels import CSV_PATH, HISTORY_DIR, LOG_FILE, MAIL_TO, SUBJECT_PREFIX
from src.diff import already_notified_urls, apply_diff
from src.logging_config import setup_logging
from src.mailer import send_notification_email
from src.mercari import attach_mercari_prices
from src.notifier import get_notifications, print_notifications
from src.profit import calculate_all
from src.sites.flannels.parser import parse
from src.sites.flannels.scraper import FlannelsScraper
from src.storage import load_products, save_history, save_products

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Flannels Monitor")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit the number of listing pages fetched (debug/testing only).",
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


def main() -> None:
    setup_logging(log_file=LOG_FILE)

    args = _parse_args()

    logger.info("Loading previous products...")
    previous = load_products(csv_path=CSV_PATH)
    logger.info("Previous products: %d", len(previous))

    with FlannelsScraper(max_pages=args.max_pages) as scraper:
        result = scraper.run()

    products = parse(result.pages)

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
        send_notification_email(new_targets, mail_to=MAIL_TO, subject_prefix=SUBJECT_PREFIX)

    logger.info("=" * 60)
    logger.info("New Products    : %d", new_count)
    logger.info("Price Down      : %d", price_down_count)
    logger.info("Qualifying      : %d", len(notify_targets))
    logger.info("Notified (new)  : %d", len(new_targets))
    logger.info("Failed Pages    : %s", result.failed_pages or "none")
    logger.info("=" * 60)

    save_products(products, csv_path=CSV_PATH)
    save_history(products, history_dir=HISTORY_DIR)


if __name__ == "__main__":
    main()
