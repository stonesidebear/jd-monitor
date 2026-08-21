"""Flannels Monitor - site-specific configuration.

Mirrors ``config.py`` but scoped to Flannels' clearance listing. Shared
secrets/thresholds (AI estimation, SMTP, Mercari, grading) live only in
``config.py`` - the modules that use them (``src.profit``,
``src.ai_estimator``, ``src.mercari``, ``src.mailer``, ``src.currency``)
already import them from there directly, so this file only defines what
genuinely differs for Flannels.
"""

from __future__ import annotations

import os

# ======================================================================
# 対象URL / ソート / ページネーション
# ======================================================================
# 割引率降順ソートなので、全15,000件超のカタログを毎回スクレイプする必要
# はない。上位ページ(割引率が高いページ)だけを見て、割引率が
# MIN_DISCOUNT_TO_CONTINUE を下回ったら以降のページ取得を打ち切る。

BASE_URL = "https://www.flannels.com/clearance/men/shop-by-price/under-250"

SORT_QUERY = "sort=DISCOUNT_PERCENTAGE&sortDirection=DESC"

# 1ページあたりの商品数 (Flannelsのページネーション固定値)
ITEMS_PER_PAGE = 59

# 安全装置: 割引率での早期打ち切りが機能しなかった場合でも、
# 最大でもこのページ数までしか取得しない
MAX_PAGES = 20

# このページの最大割引率がこの値を下回ったら、以降のページ取得を打ち切る
# (通知しきい値 DISCOUNT_THRESHOLD より低めに設定し、取りこぼしを防ぐ)
MIN_DISCOUNT_TO_CONTINUE = 60.0

# ======================================================================
# Playwright / ブラウザ
# ======================================================================
# FlannelsはAkamai Bot Managerを使っており、headlessモードのChromiumを
# HTTP/2フィンガープリントで検知してブロックする(実機検証済み: headless
# =Trueは即ERR_HTTP2_PROTOCOL_ERROR、headless=Falseは正常に200)。
# そのためheadless=Falseで起動する。CI(GitHub Actions)側はXvfbで仮想
# ディスプレイを用意し、xvfb-run経由で実行する(ワークフロー参照)。

HEADLESS = False

VIEWPORT_WIDTH = 1400
VIEWPORT_HEIGHT = 2000

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

LOCALE = "en-GB"

# ページ取得のタイムアウト (ms)
PAGE_TIMEOUT = 60_000

# 商品リスト待機のタイムアウト (ms)
SELECTOR_TIMEOUT = 20_000

# ======================================================================
# 仮想スクロール対策
# ======================================================================
# 各ページの商品グリッドは仮想スクロール(react-window的な実装)で描画
# されており、ページ読み込み直後は59件中14件程度しかDOMに存在しない。
# 最下部までスクロールしてすべてのカードを描画させてから取得する。

SCROLL_STEP_PX = 3000

SCROLL_PAUSE_MS = 400

SCROLL_MAX_ROUNDS = 20

# ======================================================================
# リトライ / レート制御
# ======================================================================

RETRY_LIMIT = 3

RETRY_BACKOFF_BASE = 2.0

REQUEST_DELAY_MIN = 1.5

REQUEST_DELAY_MAX = 3.0

# ======================================================================
# 保存先パス
# ======================================================================
# JD Sportsとデータが混ざらないよう、CSV/history/ログ/スクリーンショット
# は専用ディレクトリに分ける。AI査定キャッシュ・メルカリキャッシュは
# 商品名がキーで、サイトが違っても同じ商品なら使い回せるため、
# config.py のものをそのまま共有する(再利用でコスト削減になる)。

CSV_DIR = "data/csv_flannels"

CSV_PATH = "data/csv_flannels/products.csv"

HISTORY_DIR = "data/history_flannels"

SCREENSHOT_DIR = "data/screenshots_flannels"

LOG_FILE = "data/logs/flannels_monitor.log"

# ======================================================================
# メール通知
# ======================================================================
# JD Sportsとは別のメールアドレスで受け取るため、専用のSecretを使う。
# 未設定ならメール送信は自動的にスキップされる。

MAIL_TO = os.environ.get("MAIL_TO_FLANNELS", "")

SUBJECT_PREFIX = "[Flannels Monitor]"
