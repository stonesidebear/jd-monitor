"""
Project configuration
"""

# ======================================
# Target URL
# ======================================

URL = (
    "https://m.global.jdsports.com/"
    "men/brand/nike/sale/"
    "?jd_sort_order=price-low-high"
)

# ======================================
# Playwright
# ======================================

HEADLESS = True

VIEWPORT_WIDTH = 1400
VIEWPORT_HEIGHT = 2000

PAGE_TIMEOUT = 60_000

# ======================================
# Infinite Scroll
# ======================================

# 1回でスクロールする距離(px)
SCROLL_STEP = 600

# スクロール後の待機(ms)
SCROLL_WAIT = 800

# 新しいAJAXが来なくなってから終了する秒数
IDLE_TIMEOUT = 30

# 万一無限ループになった場合の保険
MAX_SCROLL = 1000

# ======================================
# Paths
# ======================================

DATA_DIR = "data"

AJAX_DIR = "data/ajax"

LATEST_HTML = "data/latest.html"

CSV_DIR = "data/csv"

HISTORY_DIR = "data/history"