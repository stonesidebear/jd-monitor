"""Cheap "did the catalog size change" check.

Loading every result page is far more expensive than the TOP page
alone, so we gate the full scrape on the total product count the TOP
page already reports (no extra request needed): if it hasn't changed
since the last run, we skip the rest of the pipeline.

(The saved value used to be the page count, hence the ``page_count``
names kept here and in the config/workflow file paths. Since JD Sports
moved to 72 products per page, the page count moves far too rarely to
be a useful signal, so the product count is stored in the same file
instead. A stale old-style value just reads as "changed" once.)

This is a deliberate trade-off, not a fully correct change detector:
an item that was already listed getting marked down further (without
any item being added or removed) won't move the count and will be
missed between full scrapes. In practice, further markdowns tend to
happen alongside inventory changes, so this is an accepted risk in
exchange for polling much more often without hammering JD Sports with
a full crawl every time.
"""

from __future__ import annotations

import logging
from pathlib import Path

from config import WATCH_PAGE_COUNT_PATH

logger = logging.getLogger(__name__)


def load_page_count(path: str = WATCH_PAGE_COUNT_PATH) -> int | None:
    """Return the product count saved by the previous run, or None."""
    file_path = Path(path)

    if not file_path.exists():
        return None

    try:
        return int(file_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        logger.warning("Watch count file is corrupt/unreadable: %s", file_path)
        return None


def save_page_count(total_hits: int, path: str = WATCH_PAGE_COUNT_PATH) -> None:
    """Persist ``total_hits`` so the next run can compare against it."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(str(total_hits), encoding="utf-8")
