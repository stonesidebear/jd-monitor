from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(slots=True)
class Product:

    name: str

    price_text: str

    was_text: str

    url: str

    @property
    def price(self) -> float | None:

        return self._to_float(self.price_text)

    @property
    def was(self) -> float | None:

        return self._to_float(self.was_text)

    @property
    def currency(self) -> str:

        if self.price_text.startswith("$"):
            return "$"

        if self.price_text.startswith("£"):
            return "£"

        if self.price_text.startswith("€"):
            return "€"

        return ""

    @property
    def discount_rate(self) -> float | None:

        if self.was is None:
            return None

        if self.price is None:
            return None

        if self.was == 0:
            return None

        return round(
            (1 - self.price / self.was) * 100,
            1,
        )

    def _to_float(
        self,
        value: str,
    ) -> float | None:

        if value == "":
            return None

        m = re.search(
            r"([0-9]+(?:\.[0-9]+)?)",
            value,
        )

        if m is None:
            return None

        return float(m.group(1))