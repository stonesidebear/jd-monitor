"""JD Monitor v1.0 - Project configuration.

This module is the single source of truth for every tunable value used
across the project (scraper, parser, profit engine, notifier, storage).
Business logic modules must not hardcode values that live here.
"""

from __future__ import annotations

import os

# ======================================================================
# Target URL
# ======================================================================

URL = (
    "https://m.global.jdsports.com/"
    "men/brand/"
    "nike,adidas,adidas-originals,asics,"
    "berghaus,birkenstock,boss,"
    "calvin-klein,calvin-klein-jeans,"
    "calvin-klein-performance,"
    "calvin-klein-underwear,"
    "canterbury,champion,columbia,"
    "converse,ea7,emporio-armani-ea7,"
    "fila,fred-perry,jack-wolfskin,"
    "jordan,lacoste,mammut,"
    "new-balance,new-era,nike-sb,"
    "polo-ralph-lauren,puma,"
    "reebok,superga,"
    "the-north-face,timberland,"
    "tommy-hilfiger,"
    "tommy-hilfiger-underwear,"
    "tommy-jeans,"
    "ugg,umbro,"
    "under-armour,vans/"
    "sale/?jd_sort_order=price-low-high"
)

# 1ページあたりの商品数 (JD Sports AJAX ページネーションの固定値)
ITEMS_PER_PAGE = 24

# ======================================================================
# Playwright / ブラウザ
# ======================================================================

HEADLESS = True

VIEWPORT_WIDTH = 1400
VIEWPORT_HEIGHT = 2000

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

LOCALE = "en-GB"

# TOPページ取得のタイムアウト (ms)
PAGE_TIMEOUT = 60_000

# AJAXページ取得のタイムアウト (ms)
AJAX_TIMEOUT = 30_000

# 商品リスト待機のタイムアウト (ms)
SELECTOR_TIMEOUT = 20_000

# ======================================================================
# Cloudflare 対策
# ======================================================================

# Cloudflareチャレンジ画面を検知した際の最大待機回数
CLOUDFLARE_MAX_WAIT = 5

# 1回あたりの待機時間 (ms)
CLOUDFLARE_WAIT_INTERVAL = 3_000

# ======================================================================
# リトライ / レート制御
# ======================================================================

# 各ページ取得の最大リトライ回数
RETRY_LIMIT = 3

# リトライ間隔 (秒) の基準値。試行回数に応じて指数的に増加させる。
RETRY_BACKOFF_BASE = 2.0

# AJAXページ間で挿入するランダムディレイ (秒) - Bot検知回避用
REQUEST_DELAY_MIN = 0.8
REQUEST_DELAY_MAX = 2.2

# ======================================================================
# 保存先パス
# ======================================================================

DATA_DIR = "data"

AJAX_DIR = "data/ajax"

LATEST_HTML = "data/latest.html"

SCREENSHOT_DIR = "data/screenshots"

CSV_DIR = "data/csv"

CSV_PATH = "data/csv/products.csv"

HISTORY_DIR = "data/history"

LOG_DIR = "data/logs"

LOG_FILE = "data/logs/jd_monitor.log"

AI_CACHE_PATH = "data/ai_price_cache.json"

WATCH_PAGE_COUNT_PATH = "data/watch_page_count.txt"

# ======================================================================
# 通貨換算
# ======================================================================
# JD Sports Global は £ / € / $ で価格表示される。日本円換算の暫定レート。
# 将来的には為替APIへ差し替える。

CURRENCY_RATES = {
    "GBP": 200,
    "EUR": 170,
    "USD": 150,
}

# ======================================================================
# 利益ランク しきい値
# ======================================================================

GRADE_THRESHOLDS = {
    "S": 20_000,
    "A": 15_000,
    "B": 10_000,
    "C": 5_000,
}

# 割引率がこの値以上なら無条件でSランク
GRADE_S_DISCOUNT = 75.0

# ======================================================================
# 通知条件
# ======================================================================
# 通知対象 = 割引率 >= DISCOUNT_THRESHOLD OR 利益 >= PROFIT_THRESHOLD
# 新商品/値下げは通知の可否には使わず、通知メッセージ内の理由タグとして表示する。

DISCOUNT_THRESHOLD = 75.0

PROFIT_THRESHOLD = 5_000

# ======================================================================
# AI価格査定 (Claude API)
# ======================================================================
# ANTHROPIC_API_KEY が未設定の場合、AI査定は自動的にスキップされ
# price_estimator.py の固定辞書にフォールバックする (課金なし・安全側)。

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

ANTHROPIC_MODEL = "claude-haiku-4-5"

ANTHROPIC_TIMEOUT = 20.0

# ======================================================================
# メール通知
# ======================================================================
# SMTP_USER / SMTP_PASSWORD / MAIL_TO のいずれかが未設定なら
# メール送信は自動的にスキップされる (パイプラインは失敗しない)。
# Gmailの場合 SMTP_PASSWORD にはアプリパスワードを使用すること。

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")

SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

SMTP_USER = os.environ.get("SMTP_USER", "")

SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

# 送信元 (未指定ならSMTP_USERと同じ)
MAIL_FROM = os.environ.get("MAIL_FROM", "") or SMTP_USER

# 宛先。複数指定はカンマ区切り
MAIL_TO = os.environ.get("MAIL_TO", "")

# ======================================================================
# メルカリ相場取得
# ======================================================================
# 通知対象になった商品「だけ」を都度検索する (全1490商品を毎回検索する
# と実行時間・相手サーバーへの負荷が大きすぎるため)。キャッシュにより
# 同じ商品名は再検索しない。

MERCARI_SEARCH_URL = "https://jp.mercari.com/search?keyword={query}&status=on_sale"

MERCARI_CACHE_PATH = "data/mercari_cache.json"

# 相場算出に使う出品件数の上限 (中央値のサンプル数)
MERCARI_SAMPLE_SIZE = 15

MERCARI_TIMEOUT = 20_000

MERCARI_RETRY_LIMIT = 2

MERCARI_REQUEST_DELAY_MIN = 1.0
MERCARI_REQUEST_DELAY_MAX = 2.5

# ======================================================================
# Logging
# ======================================================================

LOG_LEVEL = "INFO"
