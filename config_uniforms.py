"""JD Uniforms Monitor - site-specific configuration.

Same JD Sports Global site/mechanism as ``config.py`` (Cloudflare, AJAX
pagination, HTML structure) - only the listing URL, notify condition and
storage paths differ, so this monitor reuses ``src.scraper.JDScraper``
and ``src.parser`` as-is. Shared secrets/thresholds stay in ``config.py``
and are imported directly from there by the modules that use them
(``src.mailer``, ``src.ai_estimator``, ``src.mercari``, ...).

通知条件: 新商品(is_new)が追加された時のみ通知。ユニフォームは在庫が
すぐ売り切れるため、割引率/利益額に関わらず「新しく出た」こと自体が
価値のあるシグナルなので、本体(main.py)とは別の通知条件にしている。
"""

from __future__ import annotations

import os

from config import MAIL_TO as _DEFAULT_MAIL_TO

# ======================================================================
# 対象URL
# ======================================================================
# ブランドを絞らず(/men/sale/)、home/away/third/fourthキーワードで検索。
# 本体監視のブランドホワイトリストに含まれないメーカーのユニフォームも
# 拾えるよう、意図的にブランド指定なしにしている。

URL = "https://m.global.jdsports.com/men/sale/?q=home/away/third/fourth&jd_sort_order=price-low-high"

# ======================================================================
# 保存先パス
# ======================================================================

CSV_PATH = "data/csv_uniforms/products.csv"

HISTORY_DIR = "data/history_uniforms"

SCREENSHOT_DIR = "data/screenshots_uniforms"

LOG_FILE = "data/logs/uniforms_monitor.log"

WATCH_PAGE_COUNT_PATH = "data/watch_page_count_uniforms.txt"

# ======================================================================
# メール通知
# ======================================================================
# JD Sports本体と同じ監視対象(同じサイト)のため、デフォルトは本体と
# 同じ宛先(config.MAIL_TO)を再利用する。別アドレスにしたい場合は
# MAIL_TO_UNIFORMS環境変数で上書きできる。

MAIL_TO = os.environ.get("MAIL_TO_UNIFORMS", "") or _DEFAULT_MAIL_TO

SUBJECT_PREFIX = "[JD Uniforms Monitor]"
