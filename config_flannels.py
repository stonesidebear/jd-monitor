"""Flannels Monitor - site-specific configuration.

Flannels runs on Frasers Group's shared platform (see
``src.sites.frasers``), so this file only defines what's genuinely
specific to Flannels: the listing URL, discount cutoff, storage paths
and mail routing. Platform mechanics (Playwright settings, virtualized
grid handling, retry/scroll behavior) live in
``src.sites.frasers.scraper`` since they're identical across every site
on this platform. Shared secrets/thresholds (AI estimation, SMTP,
Mercari, grading) live only in ``config.py``.
"""

from __future__ import annotations

import os

# ======================================================================
# 対象URL
# ======================================================================
# 割引率降順ソートなので、全15,000件超のカタログを毎回スクレイプする必要
# はない。上位ページ(割引率が高いページ)だけを見て、割引率が
# MIN_DISCOUNT_TO_CONTINUE を下回ったら以降のページ取得を打ち切る
# (src.sites.frasers.scraper参照)。

BASE_URL = "https://www.flannels.com/clearance/men/shop-by-price/under-250"

# 安全装置: 割引率での早期打ち切りが機能しなかった場合でも、
# 最大でもこのページ数までしか取得しない
MAX_PAGES = 20

# このページの最大割引率がこの値を下回ったら、以降のページ取得を打ち切る
# (通知しきい値 DISCOUNT_THRESHOLD より低めに設定し、取りこぼしを防ぐ)
MIN_DISCOUNT_TO_CONTINUE = 60.0

# ======================================================================
# Playwright
# ======================================================================
# FlannelsはAkamai Bot Managerを使っており、headlessモードのChromiumを
# HTTP/2フィンガープリントで検知してブロックする(実機検証済み: headless
# =Trueは即ERR_HTTP2_PROTOCOL_ERROR、headless=Falseは正常に200)。
# そのためheadless=Falseで起動する。CI(GitHub Actions)側はXvfbで仮想
# ディスプレイを用意し、xvfb-run経由で実行する(ワークフロー参照)。

HEADLESS = False

# ======================================================================
# 保存先パス
# ======================================================================
# JD Sportsとデータが混ざらないよう、CSV/history/ログ/スクリーンショット
# は専用ディレクトリに分ける。AI査定キャッシュ・メルカリキャッシュは
# 商品名がキーで、サイトが違っても同じ商品なら使い回せるため、
# config.py のものをそのまま共有する(再利用でコスト削減になる)。

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
