"""Input contract rules from guide section 4."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.scenario import OperatingTime, ScenarioInput, expand
from tests.conftest import make_scenario


def test_unknown_option_is_rejected():
    with pytest.raises(ValidationError):
        make_scenario(workloads=["telepathy"])


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        make_scenario(secret_discount=True)


def test_negative_money_is_rejected():
    with pytest.raises(ValidationError):
        make_scenario(electricity_tariff_per_kwh={"amount": "-0.10", "currency": "EUR"})


def test_boolean_is_not_accepted_as_a_count():
    with pytest.raises(ValidationError):
        make_scenario(seats=True)


def test_active_plus_idle_time_above_a_day_is_rejected():
    with pytest.raises(ValidationError):
        OperatingTime(active_hours_per_day=Decimal("16"), idle_hours_per_day=Decimal("10"))


def test_custom_usage_requires_explicit_volume():
    with pytest.raises(ValidationError):
        make_scenario(usage_level="custom")


def test_custom_context_requires_token_count():
    with pytest.raises(ValidationError):
        make_scenario(context_requirement="custom")


def test_mixed_currency_without_a_conversion_is_rejected():
    with pytest.raises(ValidationError):
        make_scenario(electricity_tariff_per_kwh={"amount": "0.30", "currency": "USD"})


def test_offline_requirement_overrides_a_permissive_external_flag():
    scenario = make_scenario(
        constraints={"offline_required": True, "external_processing_allowed": True}
    )
    assert scenario.constraints.external_processing_allowed is False


def test_presets_expand_to_explicit_values_and_are_recorded():
    expanded = expand(make_scenario(usage_level="heavy"))
    assert expanded.work_volume.requests_per_day == 300
    assert expanded.applied_presets["usage_level"] == "heavy"
    assert expanded.operating_time.active_hours_per_day == Decimal("8")


def test_planning_period_is_bounded():
    with pytest.raises(ValidationError):
        make_scenario(planning_period_months=0)
    with pytest.raises(ValidationError):
        make_scenario(planning_period_months=61)
