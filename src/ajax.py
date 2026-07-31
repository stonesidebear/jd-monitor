from __future__ import annotations

from pathlib import Path
from time import time

from config import AJAX_DIR


class AjaxCollector:
    """
    Collect AJAX responses from JD Sports.
    """

    def __init__(self):

        self.responses = []
        self.seen_urls = set()

        self.last_new_response = time()

    @property
    def idle_seconds(self) -> float:
        """
        Seconds since last NEW ajax response.
        """
        return time() - self.last_new_response

    @property
    def count(self) -> int:
        """
        Number of unique ajax pages.
        """
        return len(self.responses)

    def handle_response(self, response):

        url = response.url

        if "AJAX=1" not in url:
            return

        if "sale/" not in url:
            return

        if url in self.seen_urls:
            return

        try:

            html = response.text()

        except Exception:

            return

        self.seen_urls.add(url)

        self.last_new_response = time()

        self.responses.append(
            {
                "url": url,
                "html": html,
            }
        )

        print(
            f"Captured ({self.count}) : {url}"
        )

    def save(self):

        Path(AJAX_DIR).mkdir(
            parents=True,
            exist_ok=True,
        )

        for i, item in enumerate(self.responses):

            filename = (
                Path(AJAX_DIR)
                / f"{i:04}.html"
            )

            filename.write_text(
                item["html"],
                encoding="utf-8",
            )

    def html_list(self):
        """
        Return all ajax html.
        """

        return [
            item["html"]
            for item in self.responses
        ]

    def urls(self):

        return [
            item["url"]
            for item in self.responses
        ]