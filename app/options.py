"""What every option means, and the exact numbers it turns into.

``GET /options`` returns this. Nothing is hidden: if picking ``medium`` means
80 requests a day, you can see that before you ask for a recommendation, and
the number you actually got is echoed back in the result.
"""

from __future__ import annotations

from decimal import Decimal

from app.schemas import (
    AccessRequirement,
    ContextSize,
    InputsUsed,
    Priority,
    RecommendInput,
    RunningTime,
    SetupSkill,
    UsageLevel,
    Workload,
)

# How many requests a day each usage level means.
REQUESTS_PER_DAY: dict[UsageLevel, int] = {
    UsageLevel.LIGHT: 20,
    UsageLevel.MEDIUM: 80,
    UsageLevel.HEAVY: 300,
}

# How many tokens of context each size means.
CONTEXT_TOKENS: dict[ContextSize, int] = {
    ContextSize.SHORT_CONVERSATION: 8_192,
    ContextSize.LONG_DOCUMENT: 65_536,
}

# Hours per day the machine is busy and idle.
RUNNING_HOURS: dict[RunningTime, tuple[Decimal, Decimal]] = {
    RunningTime.OCCASIONAL: (Decimal("2"), Decimal("1")),
    RunningTime.WORKDAY: (Decimal("8"), Decimal("2")),
    RunningTime.ALWAYS_ON: (Decimal("8"), Decimal("16")),
}

# Setup takes longer if you have done it less often.
SETUP_MULTIPLIER: dict[SetupSkill, Decimal] = {
    SetupSkill.BEGINNER: Decimal("2.0"),
    SetupSkill.COMFORTABLE: Decimal("1.0"),
    SetupSkill.EXPERIENCED: Decimal("0.6"),
}

LABELS: dict[str, str] = {
    "coding": "Writing and reviewing code",
    "studying": "Studying and explanations",
    "writing": "Writing and editing text",
    "document_analysis": "Reading and summarising documents",
    "interactive_use": "A person types and reads answers",
    "application_integration": "Another program calls the model",
    "light": "Light - about 20 requests a day",
    "medium": "Medium - about 80 requests a day",
    "heavy": "Heavy - about 300 requests a day",
    "short_conversation": "Short conversation - about 8k tokens",
    "long_document": "Long document - about 64k tokens",
    "occasional": "Occasional - 2 h busy, 1 h idle per day",
    "workday": "Workday - 8 h busy, 2 h idle per day",
    "always_on": "Always on - 8 h busy, 16 h idle per day",
    "beginner": "Beginner - setup takes twice as long",
    "comfortable": "Comfortable - setup takes the usual time",
    "experienced": "Experienced - setup is quicker",
    "lowest_cost": "Cheapest over the whole period",
    "least_setup": "Least time spent setting it up",
    "offline_control": "Keep everything on my own machine",
}


def _choices(enum_class, extra: dict[str, object] | None = None) -> list[dict]:
    items = []
    for member in enum_class:
        entry = {"id": member.value, "label": LABELS.get(member.value, member.value)}
        if extra and member in extra:
            entry["means"] = extra[member]
        items.append(entry)
    return items


def all_options() -> dict:
    """The full menu, including what each preset expands to."""
    return {
        "workloads": _choices(Workload),
        "access": _choices(AccessRequirement),
        "usage": _choices(UsageLevel, {k: {"requests_per_day": v} for k, v in REQUESTS_PER_DAY.items()}),
        "context": _choices(ContextSize, {k: {"tokens": v} for k, v in CONTEXT_TOKENS.items()}),
        "running_time": _choices(
            RunningTime,
            {
                k: {"active_hours_per_day": str(v[0]), "idle_hours_per_day": str(v[1])}
                for k, v in RUNNING_HOURS.items()
            },
        ),
        "setup_skill": _choices(
            SetupSkill, {k: {"effort_multiplier": str(v)} for k, v in SETUP_MULTIPLIER.items()}
        ),
        "priority": _choices(Priority),
        "numbers": [
            {"field": "seats", "unit": "people", "min": 1, "max": 1000, "default": 1},
            {"field": "people_at_once", "unit": "sessions", "min": 1, "max": 64, "default": 1},
            {"field": "months", "unit": "months", "min": 1, "max": 60, "default": 24},
            {"field": "hours_for_setup", "unit": "hours", "min": 0, "max": 500, "default": 16},
            {"field": "electricity_per_kwh", "unit": "money per kWh", "min": 0,
             "note": "Leave it out and running cost is reported as unknown, not as zero."},
            {"field": "budget_upfront", "unit": "money", "min": 0},
            {"field": "budget_monthly", "unit": "money", "min": 0},
        ],
        "switches": [
            {"field": "offline_only", "note": "Rules out every subscription."},
            {"field": "commercial_use", "note": "Requires a licence that allows it."},
        ],
    }


def expand(request: RecommendInput) -> InputsUsed:
    """Turn the chosen options into the exact numbers used, and record them."""
    active, idle = RUNNING_HOURS[request.running_time]
    return InputsUsed(
        requests_per_day=REQUESTS_PER_DAY[request.usage],
        context_tokens=CONTEXT_TOKENS[request.context],
        active_hours_per_day=active,
        idle_hours_per_day=idle,
        setup_effort_multiplier=SETUP_MULTIPLIER[request.setup_skill],
        months=request.months,
        currency=request.currency,
    )
