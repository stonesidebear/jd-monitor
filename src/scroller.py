from playwright.sync_api import TimeoutError

from config import (
    IDLE_TIMEOUT,
    MAX_SCROLL,
    SCROLL_STEP,
    SCROLL_WAIT,
)


def scroll_to_end(page, collector):
    """
    Scroll until no new AJAX responses arrive.
    """

    previous_products = 0

    for i in range(MAX_SCROLL):

        # 少しずつスクロール（人間らしい動き）
        page.evaluate(
            f"window.scrollBy(0, {SCROLL_STEP})"
        )

        page.wait_for_timeout(SCROLL_WAIT)

        try:
            page.wait_for_load_state(
                "networkidle",
                timeout=3000,
            )
        except TimeoutError:
            pass

        products = page.locator(
            "li.productListItem"
        ).count()

        last_url = "-"

        if collector.responses:
            last_url = collector.responses[-1]["url"]

        print(
            f"[{i + 1:04}] "
            f"Products={products:<5} "
            f"AJAX={collector.count:<4} "
            f"Idle={collector.idle_seconds:5.1f}s"
        )

        # 商品数が増えたら最下部へ一気に寄せる
        if products > previous_products:

            page.evaluate(
                """
                window.scrollTo(
                    0,
                    document.body.scrollHeight
                )
                """
            )

            previous_products = products

        # 新しいAJAXが一定時間来なければ終了
        if collector.idle_seconds >= IDLE_TIMEOUT:

            print()

            print("=" * 60)
            print("No new AJAX detected.")
            print("Scrolling finished.")
            print("=" * 60)

            break

    else:

        print()

        print("=" * 60)
        print("Reached MAX_SCROLL.")
        print("=" * 60)