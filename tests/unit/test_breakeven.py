"""Crossover detection over cumulative cash schedules (guide section 6)."""

from __future__ import annotations

from decimal import Decimal

from app.engine.breakeven import compare
from app.schemas.common import Money
from app.schemas.result import CostBreakdown, MonthlyCost


def schedule(cumulative: list[str]) -> CostBreakdown:
    """Build a breakdown from an explicit list of cumulative totals."""
    months = []
    previous = Decimal("0")
    for index, value in enumerate(cumulative, start=1):
        total = Decimal(value) - previous
        previous = Decimal(value)
        months.append(
            MonthlyCost(
                month=index,
                energy=None,
                recurring=Money(amount=total, currency="EUR"),
                total=Money(amount=total, currency="EUR"),
                cumulative=Money(amount=Decimal(value), currency="EUR"),
            )
        )
    return CostBreakdown(
        currency="EUR",
        upfront=Money.zero("EUR"),
        monthly=months,
        horizon_total=Money(amount=Decimal(cumulative[-1]), currency="EUR"),
    )


def test_crossover_month_is_reported():
    local = schedule(["800", "830", "860", "890"])
    hosted = schedule(["20", "40", "900", "920"])
    result = compare("local", local, "hosted", hosted, 4)
    assert result.crossover_month == 3
    assert "month 3" in result.note


def test_no_crossover_within_the_horizon_is_stated():
    local = schedule(["2000", "2030", "2060"])
    hosted = schedule(["20", "40", "60"])
    result = compare("local", local, "hosted", hosted, 3)
    assert result.crossover_month is None
    assert "does not become cheaper" in result.note


def test_a_later_reversal_is_reported():
    """An annual renewal can put the subscription back in front."""
    local = schedule(["500", "510", "520", "530"])
    hosted = schedule(["100", "200", "300", "1400"])
    result = compare("hosted", hosted, "local", local, 4)
    assert result.crossover_month == 1
    assert result.later_reversal_months == [4]
    assert "reverses again" in result.note


def test_leading_from_the_first_month_is_recognised():
    cheap = schedule(["10", "20", "30"])
    dear = schedule(["100", "200", "300"])
    result = compare("cheap", cheap, "dear", dear, 3)
    assert result.crossover_month == 1
    assert "from the first month" in result.note
