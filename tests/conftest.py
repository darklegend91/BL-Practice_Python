"""Shared fixtures. Nothing here touches the network or a live vendor site."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from app.engine.policy import Policy
from app.schemas.scenario import ScenarioInput, expand
from app.seed.dataset import SEED_EPOCH, build_snapshot


@pytest.fixture
def as_of() -> dt.datetime:
    return SEED_EPOCH


@pytest.fixture
def snapshot():
    return build_snapshot()


@pytest.fixture
def policy() -> Policy:
    return Policy()


def make_scenario(**overrides) -> ScenarioInput:
    """A workable default scenario; keyword arguments replace individual fields."""
    base = dict(
        workloads=["coding"],
        access_requirement="interactive_use",
        usage_level="medium",
        context_requirement="short_conversation",
        planning_period_months=24,
        region="DE",
        currency="EUR",
        operating_time_preset="workday",
        setup_preference="comfortable",
        setup_allowance_hours=Decimal("40"),
        priority="lowest_cash_cost",
        electricity_tariff_per_kwh={"amount": "0.32", "currency": "EUR"},
        inventory={
            "label": "desk PC",
            "gpu_model": "Accelerator 16G",
            "gpu_vram_gb": "16",
            "system_ram_gb": "32",
            "free_storage_gb": "500",
            "measured_active_watts": "410",
            "measured_idle_watts": "70",
        },
    )
    base.update(overrides)
    return ScenarioInput(**base)


@pytest.fixture
def scenario():
    return expand(make_scenario())
