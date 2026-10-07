"""Converting prices, without calling anything.

A rate is a fact somebody wrote down on a date. These check it is applied
faithfully, disclosed, and never invented.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from app.catalog import Converted, _to_currency
from app.rates import Rate, Rates, parse_override


def a_rate(base="USD", quote="INR", rate="88.00") -> Rate:
    return Rate(base=base, quote=quote, rate=Decimal(rate),
                as_of=dt.date(2026, 9, 1), source="test")


def convert(price, currency, wanted, rates, name="Thing"):
    seen = Converted()
    return _to_currency(price, currency, wanted, rates, seen, name, None), seen


# --------------------------------------------------------------------------- #
# The rate itself
# --------------------------------------------------------------------------- #


def test_a_rate_is_applied_exactly():
    assert a_rate().convert(Decimal("1199")) == Decimal("105512.00")


def test_a_rate_says_when_it_was_checked_and_where_it_came_from():
    described = a_rate().describe()
    assert "1 USD = 88.00 INR" in described
    assert "2026-09-01" in described
    assert "test" in described


def test_the_same_currency_needs_no_rate():
    assert Rates([a_rate()]).find("INR", "INR") is None
    assert Rates([a_rate()]).can_convert("INR", "INR") is True


def test_a_rate_given_at_question_time_wins():
    rates = Rates([a_rate(rate="88.00")])
    rates.add(a_rate(rate="100.00"))
    assert rates.find("USD", "INR").rate == Decimal("100.00")


@pytest.mark.parametrize("text", ["USD=88.20", "usd = 88.20", "EUR=95"])
def test_a_rate_can_be_given_on_the_command_line(text):
    parsed = parse_override(text, "INR")
    assert parsed.quote == "INR"
    assert parsed.rate > 0
    assert parsed.base.isupper() and len(parsed.base) == 3


@pytest.mark.parametrize("text", ["88.20", "DOLLARS=88", "USD=lots", "USD=0", "USD=-5"])
def test_a_nonsense_rate_is_refused(text):
    with pytest.raises(ValueError):
        parse_override(text, "INR")


# --------------------------------------------------------------------------- #
# Applying it to a price
# --------------------------------------------------------------------------- #


def test_a_price_already_in_your_currency_is_left_alone():
    (price, currency, note), seen = convert(Decimal("100"), "INR", "INR", Rates([a_rate()]))
    assert (price, currency, note) == (Decimal("100"), "INR", None)
    assert seen.rates_used == []


def test_a_price_is_converted_and_the_rate_recorded():
    (price, currency, note), seen = convert(
        Decimal("1199"), "USD", "INR", Rates([a_rate()]), name="RTX 4080"
    )
    assert price == Decimal("105512.00")
    assert currency == "INR"
    assert "Converted from 1199 USD" in note
    assert "1 USD = 88.00 INR" in note
    assert seen.rates_used and "88.00" in seen.rates_used[0]


def test_a_converted_price_warns_about_duty_and_tax():
    (_, _, note), _ = convert(Decimal("1199"), "USD", "INR", Rates([a_rate()]))
    assert "import duty or local tax is not included" in note


def test_a_price_with_no_rate_is_dropped_not_guessed():
    """A number in the wrong currency is worse than no number."""
    (price, currency, _), seen = convert(
        Decimal("1199"), "USD", "JPY", Rates([a_rate()]), name="RTX 4080"
    )
    assert price is None and currency is None
    assert seen.left_out and "no reviewed USD/JPY rate" in seen.left_out[0]


def test_an_unknown_price_stays_unknown():
    (price, _, _), seen = convert(None, "USD", "INR", Rates([a_rate()]))
    assert price is None
    assert seen.rates_used == []


def test_nothing_happens_when_no_currency_is_asked_for():
    (price, currency, _), _ = convert(Decimal("50"), "USD", None, Rates([a_rate()]))
    assert (price, currency) == (Decimal("50"), "USD")


def test_each_rate_is_recorded_once_however_many_prices_use_it():
    rates, seen = Rates([a_rate()]), Converted()
    for name in ("A", "B", "C"):
        _to_currency(Decimal("10"), "USD", "INR", rates, seen, name, None)
    assert len(seen.rates_used) == 1
