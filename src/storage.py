from __future__ import annotations

from pathlib import Path
import csv

from config import CSV_DIR
from src.product import Product


CSV_FILE = Path(CSV_DIR) / "products.csv"


def save(products: list[Product]) -> None:
    """
    Save products to CSV.
    """

    Path(CSV_DIR).mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        CSV_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.writer(f)

        writer.writerow(
            [
                "name",
                "price",
                "was",
                "currency",
                "discount_rate",
                "url",
            ]
        )

        for p in products:

            writer.writerow(
                [
                    p.name,
                    p.price,
                    p.was,
                    p.currency,
                    p.discount_rate,
                    p.url,
                ]
            )


def load() -> dict[str, Product]:
    """
    Load previous CSV.

    Returns
    -------
    dict[url, Product]
    """

    if not CSV_FILE.exists():
        return {}

    previous = {}

    with open(
        CSV_FILE,
        newline="",
        encoding="utf-8",
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            previous[row["url"]] = Product(
                name=row["name"],
                price_text=str(row["price"]),
                was_text=str(row["was"]),
                url=row["url"],
            )

    return previous


def diff(
    previous: dict[str, Product],
    current: list[Product],
):
    """
    Compare previous and current products.

    Returns
    -------
    tuple

    (
        new_products,
        price_down_products,
    )
    """

    new_products = []

    price_down = []

    for product in current:

        if product.url not in previous:

            new_products.append(product)

            continue

        old = previous[product.url]

        if (
            old.price is not None
            and product.price is not None
            and product.price < old.price
        ):

            price_down.append(product)

    return (
        new_products,
        price_down,
    )