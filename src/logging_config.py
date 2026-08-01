"""Centralized logging setup for JD Monitor.

Every module obtains its logger via ``logging.getLogger(__name__)`` after
``setup_logging()`` has been called once from the entry point (main.py).
"""

from __future__ import annotations

import logging
from pathlib import Path

from config import LOG_FILE, LOG_LEVEL


def setup_logging(level: str = LOG_LEVEL) -> None:
    """Configure the root logger with a console and a file handler.

    Args:
        level: Logging level name (e.g. "INFO", "DEBUG").
    """
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Playwright / urllib3 等の外部ライブラリは WARNING 以上のみ出力する
    logging.getLogger("playwright").setLevel(logging.WARNING)
