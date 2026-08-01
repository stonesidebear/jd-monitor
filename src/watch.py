"""Cheap "did the catalog size change" check.

Fetching and parsing every AJAX page is far more expensive than the
TOP page alone, so we gate the full scrape on ``data-pagescount``
(the total page count already present on the TOP page - no extra
request needed): if it hasn't changed since the last run, we skip the
rest of the pipeline.

This is a deliberate trade-off, not a fully correct change detector:
an item that was already listed getting marked down further (without
any item being added or removed) won't move the page count and will
be missed between full scrapes. In practice, further markdowns tend to
happen alongside inventory changes, so this is an accepted risk in
exchange for polling much more often without hammering JD Sports with
a full 61-page crawl every time.
"""

from __future__ import annotations

import logging
from pathlib import Path

from config import WATCH_PAGE_COUNT_PATH

logger = logging.getLogger(__name__)


def load_page_count() -> int | None:
    """Return the page count saved by the previous run, or None."""
    path = Path(WATCH_PAGE_COUNT_PATH)

    if not path.exists():
        return None

    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        logger.warning("Watch page-count file is corrupt/unreadable: %s", path)
        return None


def save_page_count(total_pages: int) -> None:
    """Persist ``total_pages`` so the next run can compare against it."""
    path = Path(WATCH_PAGE_COUNT_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(total_pages), encoding="utf-8")
