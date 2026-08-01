"""Product data model.

A ``Product`` holds already-normalized data (JPY prices). HTML parsing
and currency conversion happen in :mod:`src.parser`; this module stays a
plain data container so every downstream stage (profit, notifier,
storage) can rely on a stable schema.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Product:
    """A single JD Sports SALE product, normalized to JPY."""

    name: str
    url: str
    price: int
    was_price: int = 0

    # ------------------------------------------------------------
    # 利益計算 / AI査定 (src.profit が設定する)
    # ------------------------------------------------------------

    expected_price: int = 0
    profit: int = 0
    grade: str = "-"

    # ------------------------------------------------------------
    # 外部相場 (src.mercari が通知対象商品にのみ設定する)
    # ------------------------------------------------------------

    mercari_price: int = 0

    # ------------------------------------------------------------
    # 差分判定 (main.py が前回データと比較して設定する)
    # ------------------------------------------------------------

    is_new: bool = False
    is_price_down: bool = False
    notified: bool = False

    @property
    def discount(self) -> float:
        """Discount percentage off ``was_price``. 0 if unknown."""
        if self.was_price <= 0:
            return 0.0
        return (self.was_price - self.price) / self.was_price * 100

    def __str__(self) -> str:
        return (
            f"{self.name}\n"
            f"Price          : {self.price}\n"
            f"Was            : {self.was_price}\n"
            f"Discount       : {self.discount:.1f}%\n"
            f"Expected Price : {self.expected_price}\n"
            f"Profit         : {self.profit}\n"
            f"Grade          : {self.grade}"
        )
