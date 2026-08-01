"""Cheap "did anything change" check for the SALE TOP page.

Fetching and parsing the TOP page is much cheaper than the full run
(61 more AJAX pages, AI estimation, Mercari lookups, email), so we use
it as a gate: only pay for the full pipeline when the signature of the
24 cheapest items (page 1, already sorted price-low-high - exactly
where a newly discounted item would show up) has actually changed.

The signature is built from (url, price) pairs rather than a raw HTML
hash so it isn't tripped by incidental page noise (ad rotation,
tracking params, timestamps).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from config import WATCH_SIGNATURE_PATH
from src.parser import parse_page

logger = logging.getLogger(__name__)


def compute_signature(top_html: str) -> str:
    """Hash the (url, price) pairs found on the TOP page."""
    products = parse_page(top_html)
    pairs = sorted(f"{p.url}:{p.price}" for p in products)
    return hashlib.sha256("|".join(pairs).encode("utf-8")).hexdigest()


def load_signature() -> str | None:
    """Return the signature saved by the previous run, or None."""
    path = Path(WATCH_SIGNATURE_PATH)

    if not path.exists():
        return None

    signature = path.read_text(encoding="utf-8").strip()

    return signature or None


def save_signature(signature: str) -> None:
    """Persist ``signature`` so the next run can compare against it."""
    path = Path(WATCH_SIGNATURE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(signature, encoding="utf-8")
