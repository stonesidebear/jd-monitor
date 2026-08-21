"""CSV persistence.

``products.csv`` always holds the latest snapshot (used to diff against
on the next run). ``data/history/YYYY-MM-DD.csv`` accumulates one
snapshot per day so price trends can be analyzed later.
"""

from __future__ import annotations

import csv
import logging
from datetime import date
from pathlib import Path

from config import CSV_PATH, HISTORY_DIR
from src.product import Product

logger = logging.getLogger(__name__)

_FIELDNAMES = [
    "url",
    "name",
    "price",
    "was_price",
    "discount",
    "expected_price",
    "mercari_price",
    "profit",
    "grade",
    "is_new",
    "is_price_down",
    "notified",
]


def _to_row(product: Product) -> list:
    return [
        product.url,
        product.name,
        product.price,
        product.was_price,
        round(product.discount, 1),
        product.expected_price,
        product.mercari_price,
        product.profit,
        product.grade,
        product.is_new,
        product.is_price_down,
        product.notified,
    ]


def load_products(csv_path: str = CSV_PATH) -> dict[str, dict]:
    """Load the previous run's CSV, keyed by product URL.

    Returns an empty dict on the very first run (no CSV yet).
    """
    path = Path(csv_path)

    if not path.exists():
        return {}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        products = {row["url"]: row for row in reader}

    logger.info("Loaded %d previous products from %s", len(products), path)

    return products


def save_products(products: list[Product], csv_path: str = CSV_PATH) -> None:
    """Overwrite ``products.csv`` with the current snapshot."""
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(_FIELDNAMES)

        for product in products:
            writer.writerow(_to_row(product))

    logger.info("Saved %d products to %s", len(products), path)


def save_history(products: list[Product], history_dir: str = HISTORY_DIR) -> None:
    """Append today's snapshot to ``{history_dir}/YYYY-MM-DD.csv``."""
    history_path = Path(history_dir)
    history_path.mkdir(parents=True, exist_ok=True)

    path = history_path / f"{date.today().isoformat()}.csv"

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(_FIELDNAMES)

        for product in products:
            writer.writerow(_to_row(product))

    logger.info("Saved history snapshot to %s", path)
