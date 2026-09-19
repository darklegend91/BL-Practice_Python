"""Cost rules from guide section 6, "Cost calculation"."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from app.engine import costing
from app.engine.candidates import generate
from app.engine.costing import PriceUnavailable
from app.schemas.common import BillingInterval, DeploymentKind, Money
from app.schemas.scenario import expand
from tests.conftest import make_scenario


def _by_deployment(scenario, snapshot, policy, deployment, contains=""):
    for candidate in generate(scenario, snapshot, policy):
        if candidate.deployment is deployment and contains in candidate.candidate_id:
            return candidate
    raise AssertionError(f"no candidate for {deployment} containing {contains!r}")


def test_existing_hardware_has_no_upfront_cash_cost(scenario, snapshot, policy):
    candidate = _by_deployment(scenario, snapshot, policy, DeploymentKind.EXISTING_LOCAL)
    cost = costing.build(candidate, scenario, snapshot, policy)
    assert cost.upfront == Money(amount=Decimal("0.0000"), currency="EUR")


def test_new_machine_is_priced_as_a_complete_system(scenario, snapshot, policy):
    candidate = _by_deployment(scenario, snapshot, policy, DeploymentKind.NEW_LOCAL_MACHINE)
    cost = costing.build(candidate, scenario, snapshot, policy)
    assert cost.upfront.amount == Decimal("2150.0000")


def test_cheapest_reviewed_offer_is_used_and_retailers_are_not_merged(
    scenario, snapshot, policy
):
    candidate = _by_deployment(
        scenario, snapshot, policy, DeploymentKind.LOCAL_UPGRADE, "Accelerator 24G"
    )
    cost = costing.build(candidate, scenario, snapshot, policy)
    assert cost.upfront.amount == Decimal("780.0000")  # not the 4% marked-up offer


def test_missing_price_raises_rather_than_counting_as_zero(scenario, snapshot, policy):
    candidate = _by_deployment(scenario, snapshot, policy, DeploymentKind.NEW_LOCAL_MACHINE)
    without_prices = snapshot.model_copy(update={"prices": []})
    with pytest.raises(PriceUnavailable):
        costing.build(candidate, scenario, without_prices, policy)


def test_monthly_energy_follows_the_documented_formula(scenario, snapshot, policy):
    candidate = _by_deployment(scenario, snapshot, policy, DeploymentKind.EXISTING_LOCAL)
    kwh = costing.monthly_energy_kwh(scenario, candidate, policy, costing.BASE_CASE)
    expected = policy.days_per_month * (
        Decimal("410") * Decimal("8") + Decimal("70") * Decimal("2")
    ) / Decimal(1000)
    assert kwh == expected


def test_missing_tariff_leaves_energy_unknown_not_zero(snapshot, policy):
    scenario = expand(make_scenario(electricity_tariff_per_kwh=None))
    candidate = _by_deployment(scenario, snapshot, policy, DeploymentKind.EXISTING_LOCAL)
    cost = costing.build(candidate, scenario, snapshot, policy)
    assert cost.energy_unknown is True
    assert all(month.energy is None for month in cost.monthly)


def test_monthly_plan_is_billed_every_month(snapshot, policy):
    scenario = expand(make_scenario(planning_period_months=3))
    candidate = _by_deployment(
        scenario, snapshot, policy, DeploymentKind.HOSTED_SUBSCRIPTION, "Assistant Monthly"
    )
    cost = costing.build(candidate, scenario, snapshot, policy)
    assert [month.recurring.amount for month in cost.monthly] == [Decimal("20.0000")] * 3
    assert cost.horizon_total.amount == Decimal("60.0000")


def test_annual_commitment_is_not_prorated_for_a_short_comparison(snapshot, policy):
    """A twelve-month commitment is charged in full even over two months."""
    scenario = expand(make_scenario(planning_period_months=2, seats=3))
    candidate = _by_deployment(
        scenario, snapshot, policy, DeploymentKind.HOSTED_SUBSCRIPTION, "Team Annual"
    )
    cost = costing.build(candidate, scenario, snapshot, policy)
    assert cost.monthly[0].recurring.amount == Decimal("540.0000")  # 180 x 3 seats
    assert cost.monthly[1].recurring.amount == Decimal("0.0000")
    assert cost.horizon_total.amount == Decimal("540.0000")


def test_annual_plan_renews_at_month_thirteen(snapshot, policy):
    scenario = expand(make_scenario(planning_period_months=14, seats=3))
    candidate = _by_deployment(
        scenario, snapshot, policy, DeploymentKind.HOSTED_SUBSCRIPTION, "Team Annual"
    )
    cost = costing.build(candidate, scenario, snapshot, policy)
    charged = [m.month for m in cost.monthly if m.recurring.amount > 0]
    assert charged == [1, 13]


def test_minimum_seats_are_enforced(snapshot, policy):
    scenario = expand(make_scenario(planning_period_months=12, seats=1))
    candidate = _by_deployment(
        scenario, snapshot, policy, DeploymentKind.HOSTED_SUBSCRIPTION, "Team Annual"
    )
    cost = costing.build(candidate, scenario, snapshot, policy)
    assert cost.monthly[0].recurring.amount == Decimal("540.0000")  # 3 seat minimum


def test_time_cost_is_optional_and_separate_from_cash(snapshot, policy):
    scenario = expand(
        make_scenario(
            planning_period_months=12,
            hourly_value={"amount": "50", "currency": "EUR"},
            maintenance_allowance_hours_per_month=Decimal("1"),
        )
    )
    candidate = _by_deployment(
        scenario, snapshot, policy, DeploymentKind.HOSTED_SUBSCRIPTION, "Assistant Monthly"
    )
    cost = costing.build(candidate, scenario, snapshot, policy)
    assert cost.optional_time_cost is not None
    # Cash total is untouched by the time valuation.
    assert cost.horizon_total.amount == Decimal("240.0000")


def test_no_time_cost_without_an_hourly_value(scenario, snapshot, policy):
    candidate = _by_deployment(scenario, snapshot, policy, DeploymentKind.EXISTING_LOCAL)
    cost = costing.build(candidate, scenario, snapshot, policy)
    assert cost.optional_time_cost is None


def test_cumulative_schedule_is_monotonic(scenario, snapshot, policy):
    candidate = _by_deployment(scenario, snapshot, policy, DeploymentKind.EXISTING_LOCAL)
    cost = costing.build(candidate, scenario, snapshot, policy)
    totals = [month.cumulative.amount for month in cost.monthly]
    assert totals == sorted(totals)


def test_currencies_are_never_silently_mixed():
    with pytest.raises(ValueError):
        Money(amount=Decimal("1"), currency="EUR") + Money(amount=Decimal("1"), currency="USD")
