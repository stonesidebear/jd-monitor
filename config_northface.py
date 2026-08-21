"""JD North Face Monitor - site-specific configuration.

Same JD Sports Global site/mechanism as ``config.py`` - only the listing
URL, notify condition and storage paths differ, so this monitor reuses
``src.scraper.JDScraper`` and ``src.parser`` as-is.

通知条件: 割引率が DISCOUNT_THRESHOLD 以上の商品が追加された時のみ通知
(本体監視の75%より低いしきい値。The North Faceは本体監視のブランド
一覧にも含まれるが、75%未満の値下げは本体の通知条件を満たさないため
拾われない。ここで専用の低いしきい値を設ける)。
"""

from __future__ import annotations

import os

from config import MAIL_TO as _DEFAULT_MAIL_TO

# ======================================================================
# 対象URL
# ======================================================================

URL = "https://m.global.jdsports.com/men/brand/the-north-face/sale/?jd_sort_order=price-low-high"

# ======================================================================
# 通知条件
# ======================================================================

DISCOUNT_THRESHOLD = 60.0

# ======================================================================
# 保存先パス
# ======================================================================

CSV_PATH = "data/csv_northface/products.csv"

HISTORY_DIR = "data/history_northface"

SCREENSHOT_DIR = "data/screenshots_northface"

LOG_FILE = "data/logs/northface_monitor.log"

WATCH_PAGE_COUNT_PATH = "data/watch_page_count_northface.txt"

# ======================================================================
# メール通知
# ======================================================================
# JD Sports本体と同じ宛先をデフォルトで再利用する。別アドレスにしたい
# 場合は MAIL_TO_NORTHFACE 環境変数で上書きできる。

MAIL_TO = os.environ.get("MAIL_TO_NORTHFACE", "") or _DEFAULT_MAIL_TO

SUBJECT_PREFIX = "[JD North Face Monitor]"
