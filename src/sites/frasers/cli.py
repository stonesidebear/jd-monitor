"""Shared entry-point pipeline for every Frasers Group platform monitor.

Flannels, Sports Direct/Karrimor, and any future site on this platform
follow an identical pipeline (see :mod:`src.sites.frasers.scraper` for
why one scraper/parser serves all of them) - only the config module
differs (URL, discount cutoff, storage paths, mail routing). Each
site's ``main_<site>.py`` is a thin wrapper that calls :func:`main`
with its own config module, mirroring main.py's pipeline shape (see
src/diff.py for the shared diff logic) but with no page-count
skip-gate: the discount-sorted early-stop in
:mod:`src.sites.frasers.scraper` already keeps each run cheap
regardless of the site's total catalog size.
"""

from __future__ import annotations

import argparse
import logging
from types import ModuleType

from src.diff import already_notified_urls, apply_diff
from src.logging_config import setup_logging
from src.mailer import send_notification_email
from src.mercari import attach_mercari_prices
from src.notifier import get_notifications, print_notifications
from src.profit import calculate_all
from src.sites.frasers.parser import parse
from src.sites.frasers.scraper import FrasersScraper
from src.storage import load_products, save_history, save_products

logger = logging.getLogger(__name__)


def _parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
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


def main(config: ModuleType) -> None:
    """Run the full pipeline for one Frasers-platform site.

    Args:
        config: A site config module (e.g. ``config_flannels``) exposing
            ``BASE_URL``, ``MIN_DISCOUNT_TO_CONTINUE``, ``MAX_PAGES``,
            ``HEADLESS``, ``SCREENSHOT_DIR``, ``CSV_PATH``,
            ``HISTORY_DIR``, ``LOG_FILE``, ``MAIL_TO``, ``SUBJECT_PREFIX``.
    """
    setup_logging(log_file=config.LOG_FILE)

    args = _parse_args(config.SUBJECT_PREFIX)

    logger.info("Loading previous products...")
    previous = load_products(csv_path=config.CSV_PATH)
    logger.info("Previous products: %d", len(previous))

    max_pages = args.max_pages if args.max_pages is not None else config.MAX_PAGES

    with FrasersScraper(
        base_url=config.BASE_URL,
        min_discount_to_continue=config.MIN_DISCOUNT_TO_CONTINUE,
        screenshot_dir=config.SCREENSHOT_DIR,
        max_pages=max_pages,
        headless=config.HEADLESS,
    ) as scraper:
        result = scraper.run()

    products = parse(result.pages, config.BASE_URL)

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
        send_notification_email(new_targets, mail_to=config.MAIL_TO, subject_prefix=config.SUBJECT_PREFIX)

    logger.info("=" * 60)
    logger.info("New Products    : %d", new_count)
    logger.info("Price Down      : %d", price_down_count)
    logger.info("Qualifying      : %d", len(notify_targets))
    logger.info("Notified (new)  : %d", len(new_targets))
    logger.info("Failed Pages    : %s", result.failed_pages or "none")
    logger.info("=" * 60)

    save_products(products, csv_path=config.CSV_PATH)
    save_history(products, history_dir=config.HISTORY_DIR)
