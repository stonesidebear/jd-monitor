from bs4 import BeautifulSoup

from src.product import Product


BASE_URL = "https://m.global.jdsports.com"


def parse(result: dict) -> list[Product]:
    """
    Parse the main page and all AJAX pages into Product objects.

    Parameters
    ----------
    result : dict
        {
            "main": "<html>...</html>",
            "ajax": [
                "<html>...</html>",
                ...
            ]
        }

    Returns
    -------
    list[Product]
    """

    products: list[Product] = []

    seen_urls = set()

    html_list = [
        result["main"],
        *result["ajax"],
    ]

    for html in html_list:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        items = soup.select(
            "li.productListItem"
        )

        for item in items:

            title = item.select_one(
                ".itemTitle a"
            )

            price = (
                item.select_one(".pri")
                or item.select_one(".now")
            )

            was = item.select_one(".was")

            image = item.select_one(
                "a.itemImage"
            )

            if image is None:
                continue

            href = image.get(
                "href",
                "",
            )

            if not href:
                continue

            url = BASE_URL + href

            # 重複商品を除外
            if url in seen_urls:
                continue

            seen_urls.add(url)

            product = Product(
                name=(
                    title.get_text(strip=True)
                    if title
                    else ""
                ),
                price_text=(
                    price.get_text(
                        " ",
                        strip=True,
                    )
                    if price
                    else ""
                ),
                was_text=(
                    was.get_text(
                        " ",
                        strip=True,
                    )
                    if was
                    else ""
                ),
                url=url,
            )

            products.append(product)

    print()
    print("=" * 60)
    print(f"Products Parsed : {len(products)}")
    print("=" * 60)

    return products