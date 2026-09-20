"""The structured input contract (guide section 4).

Two shapes exist on purpose:

``ScenarioInput``   what a caller submits; presets may still be unexpanded.
``ExpandedScenario`` the deterministic expansion that the engine consumes and
                     that is persisted with every result.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from app.schemas.common import (
    AccessRequirement,
    ContextRequirement,
    CurrencyCode,
    CurrencyConversion,
    Money,
    Priority,
    RegionCode,
    ResponseLength,
    SetupPreference,
    StrictModel,
    UsageLevel,
    Workload,
)
from app.schemas.questionnaire import (
    CONTEXT_PRESETS,
    OPERATING_TIME_PRESETS,
    SETUP_PRESETS,
    USAGE_PRESETS,
)
from app.version import PRESET_VERSION, SCENARIO_SCHEMA_VERSION

Hours = Annotated[Decimal, Field(ge=0, le=24, max_digits=6, decimal_places=3)]
NonNegative = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=6)]


def _reject_bool(value: object) -> object:
    """A boolean is not a number here, even though Python says ``True == 1``."""
    if isinstance(value, bool):
        raise ValueError("a boolean is not a valid numeric value")
    return value


class HardwareInventory(StrictModel):
    """Equipment the user already owns. Zero new purchase cost in the cash view."""

    label: str = "existing computer"
    gpu_model: str | None = None
    gpu_vram_gb: Decimal | None = Field(default=None, ge=0, le=1024)
    gpu_count: int = Field(default=1, ge=0, le=8)
    cpu_model: str | None = None
    system_ram_gb: Decimal | None = Field(default=None, ge=0, le=4096)
    free_storage_gb: Decimal | None = Field(default=None, ge=0, le=1_000_000)
    dedicated_to_this_workload: bool = True
    measured_active_watts: Decimal | None = Field(default=None, ge=0, le=5000)
    measured_idle_watts: Decimal | None = Field(default=None, ge=0, le=5000)

    @field_validator(
        "gpu_vram_gb",
        "system_ram_gb",
        "free_storage_gb",
        "measured_active_watts",
        "measured_idle_watts",
        mode="before",
    )
    @classmethod
    def _no_bools(cls, value: object) -> object:
        return _reject_bool(value)

    @model_validator(mode="after")
    def _gpu_fields_agree(self) -> "HardwareInventory":
        if self.gpu_count == 0 and self.gpu_vram_gb:
            raise ValueError("gpu_vram_gb was given but gpu_count is 0")
        return self


class WorkVolume(StrictModel):
    requests_per_day: int = Field(ge=0, le=100_000)
    response_length: ResponseLength


class OperatingTime(StrictModel):
    active_hours_per_day: Hours
    idle_hours_per_day: Hours

    @field_validator("active_hours_per_day", "idle_hours_per_day", mode="before")
    @classmethod
    def _no_bools(cls, value: object) -> object:
        return _reject_bool(value)

    @model_validator(mode="after")
    def _fits_in_a_day(self) -> "OperatingTime":
        if self.active_hours_per_day + self.idle_hours_per_day > Decimal(24):
            raise ValueError("active plus idle time cannot exceed 24 hours per day")
        return self


class Constraints(StrictModel):
    offline_required: bool = False
    external_processing_allowed: bool = True
    commercial_use: bool = False

    @model_validator(mode="after")
    def _offline_excludes_external(self) -> "Constraints":
        if self.offline_required and self.external_processing_allowed:
            # Not contradictory input, but the stricter of the two wins so a
            # hosted candidate cannot slip through a permissive second flag.
            object.__setattr__(self, "external_processing_allowed", False)
        return self


class Budget(StrictModel):
    upfront: Money | None = None
    monthly: Money | None = None


class ScenarioInput(StrictModel):
    """Submitted scenario. ``usage_level`` may still be a preset identifier."""

    schema_version: str = SCENARIO_SCHEMA_VERSION

    workloads: list[Workload] = Field(min_length=1)
    access_requirement: AccessRequirement

    usage_level: UsageLevel
    work_volume: WorkVolume | None = None

    context_requirement: ContextRequirement
    context_tokens: int | None = Field(default=None, ge=256, le=2_000_000)

    seats: int = Field(default=1, ge=1, le=10_000)
    concurrent_sessions: int = Field(default=1, ge=1, le=256)
    planning_period_months: int = Field(ge=1, le=60)

    budget: Budget = Budget()
    region: RegionCode
    currency: CurrencyCode

    inventory: HardwareInventory | None = None

    operating_time_preset: str | None = None
    operating_time: OperatingTime | None = None
    electricity_tariff_per_kwh: Money | None = None

    setup_preference: SetupPreference
    setup_allowance_hours: NonNegative = Decimal("8")
    maintenance_allowance_hours_per_month: NonNegative = Decimal("2")
    hourly_value: Money | None = None

    constraints: Constraints = Constraints()
    priority: Priority

    currency_conversions: list[CurrencyConversion] = Field(default_factory=list)

    @field_validator("seats", "concurrent_sessions", "planning_period_months", mode="before")
    @classmethod
    def _counts_are_not_bools(cls, value: object) -> object:
        return _reject_bool(value)

    @model_validator(mode="after")
    def _custom_choices_need_values(self) -> "ScenarioInput":
        if self.usage_level is UsageLevel.CUSTOM and self.work_volume is None:
            raise ValueError("usage_level 'custom' requires an explicit work_volume")
        if self.context_requirement is ContextRequirement.CUSTOM and self.context_tokens is None:
            raise ValueError("context_requirement 'custom' requires context_tokens")
        if self.operating_time_preset is None and self.operating_time is None:
            raise ValueError("give either operating_time_preset or explicit operating_time")
        if self.operating_time_preset is not None and self.operating_time is not None:
            raise ValueError("give only one of operating_time_preset and operating_time")
        if (
            self.operating_time_preset is not None
            and self.operating_time_preset not in OPERATING_TIME_PRESETS
        ):
            raise ValueError(f"unknown operating_time_preset {self.operating_time_preset!r}")
        return self

    @model_validator(mode="after")
    def _money_uses_one_currency(self) -> "ScenarioInput":
        amounts = [
            self.budget.upfront,
            self.budget.monthly,
            self.electricity_tariff_per_kwh,
            self.hourly_value,
        ]
        for money in amounts:
            if money is not None and money.currency != self.currency:
                known = {
                    (c.from_currency, c.to_currency) for c in self.currency_conversions
                }
                if (money.currency, self.currency) not in known:
                    raise ValueError(
                        f"{money.currency} amount given without a reviewed conversion "
                        f"to {self.currency}"
                    )
        return self


class ExpandedScenario(StrictModel):
    """Every preset replaced by the explicit value that was actually used."""

    schema_version: str = SCENARIO_SCHEMA_VERSION
    preset_version: str = PRESET_VERSION

    source: ScenarioInput
    work_volume: WorkVolume
    context_tokens: int
    operating_time: OperatingTime
    setup_effort_multiplier: Decimal
    max_acceptable_setup_hours: Decimal
    applied_presets: dict[str, str]

    @property
    def currency(self) -> str:
        return self.source.currency

    @property
    def months(self) -> int:
        return self.source.planning_period_months


def expand(scenario: ScenarioInput) -> ExpandedScenario:
    """Replace preset identifiers with explicit values, recording what was applied."""
    applied: dict[str, str] = {}

    if scenario.work_volume is not None:
        volume = scenario.work_volume
    else:
        preset = USAGE_PRESETS[scenario.usage_level]
        volume = WorkVolume(
            requests_per_day=preset.requests_per_day, response_length=preset.response_length
        )
        applied["usage_level"] = preset.id.value

    if scenario.context_tokens is not None:
        context_tokens = scenario.context_tokens
    else:
        preset_context = CONTEXT_PRESETS[scenario.context_requirement].context_tokens
        assert preset_context is not None  # guarded by ScenarioInput validation
        context_tokens = preset_context
        applied["context_requirement"] = scenario.context_requirement.value

    if scenario.operating_time is not None:
        operating = scenario.operating_time
    else:
        assert scenario.operating_time_preset is not None
        time_preset = OPERATING_TIME_PRESETS[scenario.operating_time_preset]
        operating = OperatingTime(
            active_hours_per_day=time_preset.active_hours_per_day,
            idle_hours_per_day=time_preset.idle_hours_per_day,
        )
        applied["operating_time"] = time_preset.id

    setup = SETUP_PRESETS[scenario.setup_preference]
    applied["setup_preference"] = setup.id.value

    return ExpandedScenario(
        source=scenario,
        work_volume=volume,
        context_tokens=context_tokens,
        operating_time=operating,
        setup_effort_multiplier=setup.effort_multiplier,
        max_acceptable_setup_hours=setup.max_acceptable_setup_hours,
        applied_presets=applied,
    )
