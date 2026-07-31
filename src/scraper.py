from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://m.global.jdsports.com/men/brand/nike/sale/?jd_sort_order=price-low-high"


def get_html():

    ajax_responses = []

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={"width": 1400, "height": 2000}
        )

        def save_ajax(response):

            if (
                "AJAX=1" in response.url
                and "sale/" in response.url
            ):

                try:
                    text = response.text()

                    ajax_responses.append(
                        {
                            "url": response.url,
                            "html": text,
                        }
                    )

                    print(f"Captured : {response.url}")

                except Exception as e:
                    print(e)

        page.on("response", save_ajax)

        print("Opening JD Sports...")

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_selector("#productListMain")

        previous = 0
        same_count = 0

        for _ in range(100):

            page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )

            # スクロール後にAJAX完了を待つ
            page.wait_for_timeout(2500)

            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                # networkidleにならなくても続行
                pass

            count = page.locator(
                "li.productListItem"
            ).count()

            print(
                f"Products : {count} | AJAX : {len(ajax_responses)}"
            )

            if count == previous:
                same_count += 1
            else:
                same_count = 0

            previous = count

            if same_count >= 5:
                print("Finished scrolling.")
                break

        Path("data/ajax").mkdir(
            parents=True,
            exist_ok=True,
        )

        for i, item in enumerate(ajax_responses):

            with open(
                f"data/ajax/{i:03}.html",
                "w",
                encoding="utf-8",
            ) as f:

                f.write(item["html"])

        html = page.content()

        browser.close()

        return html