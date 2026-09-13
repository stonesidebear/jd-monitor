"""Karrimor (Sports Direct) Monitor - entry point.

Thin wrapper around src.sites.frasers.cli, which holds the actual
pipeline shared by every site on the Frasers Group platform.
"""

from __future__ import annotations

import config_karrimor
from src.sites.frasers.cli import main as _run


def main() -> None:
    _run(config_karrimor)


if __name__ == "__main__":
    main()
