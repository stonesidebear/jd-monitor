"""AI-based resale price estimation via the Claude API.

Results are cached on disk (keyed by normalized product name) so the
same product is never billed twice across runs, per the "毎回APIを叩か
ない" requirement. If ``ANTHROPIC_API_KEY`` is not set, or the request
fails for any reason, this module returns ``None`` and the caller
(:mod:`src.profit`) falls back to the static keyword estimator instead
of failing the whole pipeline.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from config import AI_CACHE_PATH, ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_TIMEOUT
from src.product import Product

logger = logging.getLogger(__name__)

_NUMBER_RE = re.compile(r"\d+")

_SYSTEM_PROMPT = (
    "あなたはスニーカー・アパレルの日本国内リセール相場に詳しい査定士です。"
    "与えられた商品名から、日本国内での中古/リセール相場価格を円で見積もり、"
    "整数のみを出力してください。説明・単位・カンマは一切不要です。"
    "相場が全く分からない場合は 0 とだけ出力してください。"
)

_cache: dict[str, int] | None = None


def _cache_key(product: Product) -> str:
    return product.name.strip().lower()


def _load_cache() -> dict[str, int]:
    global _cache

    if _cache is not None:
        return _cache

    path = Path(AI_CACHE_PATH)

    if not path.exists():
        _cache = {}
        return _cache

    try:
        _cache = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("AI cache file is corrupt, starting fresh: %s", path)
        _cache = {}

    return _cache


def _save_cache() -> None:
    if _cache is None:
        return

    path = Path(AI_CACHE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _call_claude(product: Product) -> int | None:
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed; skipping AI estimation")
        return None

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=ANTHROPIC_TIMEOUT)

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=20,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": product.name}],
        )

        content = next(
            (block.text for block in response.content if block.type == "text"), ""
        )
    except Exception:
        logger.warning("Claude request failed for %r", product.name, exc_info=True)
        return None

    match = _NUMBER_RE.search(content.replace(",", ""))

    if not match:
        logger.warning("Could not parse AI response for %r: %r", product.name, content)
        return None

    price = int(match.group())

    return price if price > 0 else None


def estimate_price(product: Product) -> int | None:
    """Return an AI-estimated JPY resale price, or ``None`` if unavailable.

    ``None`` means "AI could not answer" (disabled, no match, request
    failed) - callers should fall back to another estimator, not treat
    it as a confirmed price of 0.
    """
    if not ANTHROPIC_API_KEY:
        return None

    cache = _load_cache()
    key = _cache_key(product)

    if key in cache:
        cached_price = cache[key]
        return cached_price if cached_price > 0 else None

    price = _call_claude(product)

    cache[key] = price or 0
    _save_cache()

    return price
