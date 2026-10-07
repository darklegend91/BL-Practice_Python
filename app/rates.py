"""Exchange rates, written down rather than fetched.

The catalog holds prices in whatever currency the source quoted: US dollars
from Wikipedia's launch prices, euros from the example pages. To answer in
rupees, or in anything else, those have to be converted.

This app does not call an exchange-rate service. A rate is a fact somebody
checked on a date, so it is written here with that date and where it came from,
the same way every other fact in the catalog is. That means it goes stale, and
the result says which rate it used and when it was checked so you can see that
for yourself.

To use a rate of your own, either edit this file or pass one at the time you
ask:

    python -m app ask --currency INR --rate USD=88.20

Nothing is converted without a rate. A price with no route to your currency is
left out, which is the same thing the app does with any other missing fact.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from app.schemas import Strict


class Rate(Strict):
    """One reviewed conversion, and where it came from."""

    base: str
    quote: str
    rate: Decimal
    as_of: dt.date
    source: str

    def convert(self, amount: Decimal) -> Decimal:
        return (amount * self.rate).quantize(Decimal("0.01"))

    def describe(self) -> str:
        return (
            f"1 {self.base} = {self.rate} {self.quote}, checked on "
            f"{self.as_of.isoformat()} ({self.source})"
        )


# Rates last reviewed on the date shown. They are a starting point, not a live
# feed, and they are certainly out of date by the time you read this. Pass
# --rate to override one, or edit the numbers here.
REVIEWED = [
    Rate(base="USD", quote="INR", rate=Decimal("88.00"), as_of=dt.date(2026, 9, 1),
         source="manually entered, needs checking before you rely on it"),
    Rate(base="EUR", quote="INR", rate=Decimal("95.00"), as_of=dt.date(2026, 9, 1),
         source="manually entered, needs checking before you rely on it"),
    Rate(base="USD", quote="EUR", rate=Decimal("0.92"), as_of=dt.date(2026, 9, 1),
         source="manually entered, needs checking before you rely on it"),
    Rate(base="EUR", quote="USD", rate=Decimal("1.09"), as_of=dt.date(2026, 9, 1),
         source="manually entered, needs checking before you rely on it"),
]


class Rates:
    """The rates available for one question."""

    def __init__(self, rates: list[Rate] | None = None) -> None:
        self._by_pair: dict[tuple[str, str], Rate] = {}
        for rate in rates if rates is not None else REVIEWED:
            self._by_pair[(rate.base, rate.quote)] = rate

    def add(self, rate: Rate) -> None:
        """A rate given at question time wins over the one written down here."""
        self._by_pair[(rate.base, rate.quote)] = rate

    def find(self, base: str, quote: str) -> Rate | None:
        if base == quote:
            return None  # nothing to do
        return self._by_pair.get((base, quote))

    def can_convert(self, base: str, quote: str) -> bool:
        return base == quote or self.find(base, quote) is not None


def parse_override(text: str, quote: str) -> Rate:
    """Read ``USD=88.20`` as one rate into the currency being asked about."""
    if "=" not in text:
        raise ValueError(f"a rate looks like USD=88.20, not {text!r}")
    base, _, amount = text.partition("=")
    base = base.strip().upper()
    if len(base) != 3 or not base.isalpha():
        raise ValueError(f"{base!r} is not a three-letter currency code")
    try:
        value = Decimal(amount.strip())
    except Exception as error:
        raise ValueError(f"{amount.strip()!r} is not a number") from error
    if value <= 0:
        raise ValueError("a rate has to be greater than zero")
    return Rate(
        base=base, quote=quote, rate=value, as_of=dt.date.today(),
        source="given on the command line",
    )
