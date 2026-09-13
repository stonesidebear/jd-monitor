"""Karrimor (Sports Direct) Monitor - site-specific configuration.

Sports Direct runs on the same Frasers Group platform as Flannels
(confirmed via manual testing: identical markup, sort/pagination
scheme, and Akamai bot protection) - see ``src.sites.frasers``. This
file only defines what's specific to this monitor: the listing URL,
discount cutoff, storage paths and mail routing.
"""

from __future__ import annotations

import os

# ======================================================================
# 対象URL
# ======================================================================

BASE_URL = "https://www.sportsdirect.com/karrimor/all-karrimor"

MAX_PAGES = 20

# このページの最大割引率がこの値を下回ったら、以降のページ取得を打ち切る
MIN_DISCOUNT_TO_CONTINUE = 60.0

# ======================================================================
# Playwright
# ======================================================================
# Flannelsと同じくAkamai Bot Managerがheadlessモードを検知してブロック
# するため、headless=Falseで起動する(CI側はXvfb経由)。

HEADLESS = False

# ======================================================================
# 保存先パス
# ======================================================================

CSV_PATH = "data/csv_karrimor/products.csv"

HISTORY_DIR = "data/history_karrimor"

SCREENSHOT_DIR = "data/screenshots_karrimor"

LOG_FILE = "data/logs/karrimor_monitor.log"

# ======================================================================
# メール通知
# ======================================================================
# Flannelsと同じく専用の宛先Secretを使う(未設定ならメール送信は
# 自動的にスキップされる)。

MAIL_TO = os.environ.get("MAIL_TO_KARRIMOR", "")

SUBJECT_PREFIX = "[Karrimor Monitor]"
