"""The questionnaire definition served by ``GET /v1/questionnaire``.

Options carry a stable identifier plus a separate human label, and presets are
published as the explicit values they expand into, so a user can see the
assumptions before a result is computed (guide section 4).
"""

from __future__ import annotations

from decimal import Decimal

from app.schemas.common import (
    ContextRequirement,
    Priority,
    ResponseLength,
    SetupPreference,
    StrictModel,
    UsageLevel,
    Workload,
)
from app.version import PRESET_VERSION


class Option(StrictModel):
    id: str
    label: str
    help_text: str = ""


class NumericField(StrictModel):
    id: str
    label: str
    unit: str
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    help_text: str = ""


class UsagePreset(StrictModel):
    """Explicit expansion of a usage level. Shown before the result is computed."""

    id: UsageLevel
    label: str
    requests_per_day: int
    response_length: ResponseLength


class ContextPreset(StrictModel):
    id: ContextRequirement
    label: str
    context_tokens: int | None


class OperatingTimePreset(StrictModel):
    id: str
    label: str
    active_hours_per_day: Decimal
    idle_hours_per_day: Decimal


class SetupEffortPreset(StrictModel):
    """Effort multipliers applied to a candidate's baseline setup hours."""

    id: SetupPreference
    label: str
    effort_multiplier: Decimal
    max_acceptable_setup_hours: Decimal


class Questionnaire(StrictModel):
    preset_version: str
    workloads: list[Option]
    access_requirements: list[Option]
    usage_levels: list[UsagePreset]
    response_lengths: list[Option]
    context_requirements: list[ContextPreset]
    setup_preferences: list[SetupEffortPreset]
    operating_time_presets: list[OperatingTimePreset]
    priorities: list[Option]
    numeric_fields: list[NumericField]


USAGE_PRESETS: dict[UsageLevel, UsagePreset] = {
    UsageLevel.LIGHT: UsagePreset(
        id=UsageLevel.LIGHT,
        label="Light",
        requests_per_day=20,
        response_length=ResponseLength.SHORT,
    ),
    UsageLevel.MEDIUM: UsagePreset(
        id=UsageLevel.MEDIUM,
        label="Medium",
        requests_per_day=80,
        response_length=ResponseLength.MEDIUM,
    ),
    UsageLevel.HEAVY: UsagePreset(
        id=UsageLevel.HEAVY,
        label="Heavy",
        requests_per_day=300,
        response_length=ResponseLength.LONG,
    ),
}

CONTEXT_PRESETS: dict[ContextRequirement, ContextPreset] = {
    ContextRequirement.SHORT_CONVERSATION: ContextPreset(
        id=ContextRequirement.SHORT_CONVERSATION,
        label="Short conversation",
        context_tokens=8_192,
    ),
    ContextRequirement.LONG_DOCUMENT: ContextPreset(
        id=ContextRequirement.LONG_DOCUMENT,
        label="Long document",
        context_tokens=65_536,
    ),
    ContextRequirement.CUSTOM: ContextPreset(
        id=ContextRequirement.CUSTOM, label="Custom", context_tokens=None
    ),
}

OPERATING_TIME_PRESETS: dict[str, OperatingTimePreset] = {
    "workday": OperatingTimePreset(
        id="workday",
        label="Workday (8 active / 2 idle hours)",
        active_hours_per_day=Decimal("8"),
        idle_hours_per_day=Decimal("2"),
    ),
    "always_on": OperatingTimePreset(
        id="always_on",
        label="Always on (8 active / 16 idle hours)",
        active_hours_per_day=Decimal("8"),
        idle_hours_per_day=Decimal("16"),
    ),
    "occasional": OperatingTimePreset(
        id="occasional",
        label="Occasional (2 active / 1 idle hours)",
        active_hours_per_day=Decimal("2"),
        idle_hours_per_day=Decimal("1"),
    ),
}

SETUP_PRESETS: dict[SetupPreference, SetupEffortPreset] = {
    SetupPreference.BEGINNER: SetupEffortPreset(
        id=SetupPreference.BEGINNER,
        label="Beginner",
        effort_multiplier=Decimal("2.0"),
        max_acceptable_setup_hours=Decimal("6"),
    ),
    SetupPreference.COMFORTABLE: SetupEffortPreset(
        id=SetupPreference.COMFORTABLE,
        label="Comfortable",
        effort_multiplier=Decimal("1.0"),
        max_acceptable_setup_hours=Decimal("16"),
    ),
    SetupPreference.EXPERIENCED: SetupEffortPreset(
        id=SetupPreference.EXPERIENCED,
        label="Experienced",
        effort_multiplier=Decimal("0.6"),
        max_acceptable_setup_hours=Decimal("40"),
    ),
}

_LABELS = {
    Workload.CODING: "Coding",
    Workload.STUDYING: "Studying",
    Workload.WRITING: "Writing",
    Workload.DOCUMENT_ANALYSIS: "Document analysis",
    Priority.LOWEST_CASH_COST: "Lowest cash cost",
    Priority.LEAST_SETUP: "Least setup effort",
    Priority.OFFLINE_CONTROL: "Offline control",
}


def build_questionnaire() -> Questionnaire:
    return Questionnaire(
        preset_version=PRESET_VERSION,
        workloads=[Option(id=w.value, label=_LABELS[w]) for w in Workload],
        access_requirements=[
            Option(
                id="interactive_use",
                label="Interactive use",
                help_text="A person types and reads answers.",
            ),
            Option(
                id="application_integration",
                label="Application integration",
                help_text=(
                    "Another program must call the model. A chat subscription does "
                    "not automatically provide this."
                ),
            ),
        ],
        usage_levels=[
            *USAGE_PRESETS.values(),
            UsagePreset(
                id=UsageLevel.CUSTOM,
                label="Custom",
                requests_per_day=0,
                response_length=ResponseLength.MEDIUM,
            ),
        ],
        response_lengths=[
            Option(id=r.value, label=r.value.capitalize()) for r in ResponseLength
        ],
        context_requirements=list(CONTEXT_PRESETS.values()),
        setup_preferences=list(SETUP_PRESETS.values()),
        operating_time_presets=list(OPERATING_TIME_PRESETS.values()),
        priorities=[Option(id=p.value, label=_LABELS[p]) for p in Priority],
        numeric_fields=[
            NumericField(
                id="planning_period_months",
                label="Planning period",
                unit="months",
                minimum=Decimal(1),
                maximum=Decimal(60),
            ),
            NumericField(id="seats", label="Seats", unit="people", minimum=Decimal(1)),
            NumericField(
                id="concurrent_sessions",
                label="Simultaneous local sessions",
                unit="sessions",
                minimum=Decimal(1),
            ),
            NumericField(
                id="electricity_tariff",
                label="Electricity tariff",
                unit="money per kWh",
                minimum=Decimal(0),
            ),
            NumericField(
                id="budget_upfront", label="Upfront budget", unit="money", minimum=Decimal(0)
            ),
            NumericField(
                id="budget_monthly", label="Monthly budget", unit="money", minimum=Decimal(0)
            ),
            NumericField(
                id="setup_allowance_hours",
                label="Setup time available",
                unit="hours",
                minimum=Decimal(0),
            ),
            NumericField(
                id="maintenance_allowance_hours_per_month",
                label="Maintenance time available",
                unit="hours per month",
                minimum=Decimal(0),
            ),
        ],
    )
