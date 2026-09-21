"""Every Pydantic contract the app uses, in one place.

Three groups:

* **Options and input** - what you may choose, and what you POST to /recommend.
* **Catalog** - the rows the crawler fills in and the engine reads.
* **Result** - what /recommend gives back.

A value of ``None`` in the catalog means *unknown*. Unknown is never treated as
zero, and never counts as a requirement that has been met.
"""

from __future__ import annotations

import datetime as dt
import enum
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --------------------------------------------------------------------------- #
# Options: every choice is a stable identifier, never a display position
# --------------------------------------------------------------------------- #


class Workload(str, enum.Enum):
    CODING = "coding"
    STUDYING = "studying"
    WRITING = "writing"
    DOCUMENT_ANALYSIS = "document_analysis"


class AccessRequirement(str, enum.Enum):
    INTERACTIVE_USE = "interactive_use"
    APPLICATION_INTEGRATION = "application_integration"


class UsageLevel(str, enum.Enum):
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


class ContextSize(str, enum.Enum):
    SHORT_CONVERSATION = "short_conversation"
    LONG_DOCUMENT = "long_document"


class RunningTime(str, enum.Enum):
    OCCASIONAL = "occasional"
    WORKDAY = "workday"
    ALWAYS_ON = "always_on"


class SetupSkill(str, enum.Enum):
    BEGINNER = "beginner"
    COMFORTABLE = "comfortable"
    EXPERIENCED = "experienced"


class Priority(str, enum.Enum):
    LOWEST_COST = "lowest_cost"
    LEAST_SETUP = "least_setup"
    OFFLINE_CONTROL = "offline_control"


class BillingInterval(str, enum.Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class Deployment(str, enum.Enum):
    EXISTING_COMPUTER = "existing_computer"
    UPGRADE = "upgrade"
    NEW_MACHINE = "new_machine"
    SUBSCRIPTION = "subscription"


class ResultStatus(str, enum.Enum):
    RECOMMENDED = "recommended"
    ONLY_UNCERTAIN_OPTIONS = "only_uncertain_options"
    NOTHING_FITS = "nothing_fits"


class Strict(BaseModel):
    """Unknown fields are rejected so a typo is an error, not a silent default."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]
Hours = Annotated[Decimal, Field(ge=0, le=24, max_digits=5, decimal_places=2)]


def _not_a_bool(value: object) -> object:
    """``True == 1`` in Python; it is still not a number anyone meant to type."""
    if isinstance(value, bool):
        raise ValueError("a true/false value is not a number here")
    return value


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #


class ExistingComputer(Strict):
    """What you already own. It costs nothing new, so it starts with an advantage."""

    label: str = "my computer"
    gpu_vram_gb: Decimal | None = Field(default=None, ge=0, le=512)
    system_ram_gb: Decimal | None = Field(default=None, ge=0, le=4096)
    active_watts: Decimal | None = Field(default=None, ge=0, le=5000)
    idle_watts: Decimal | None = Field(default=None, ge=0, le=5000)

    @field_validator("*", mode="before")
    @classmethod
    def _reject_bools(cls, value: object) -> object:
        return _not_a_bool(value)


class RecommendInput(Strict):
    """The body you POST to ``/recommend``. Every field is an option or a number."""

    workloads: list[Workload] = Field(min_length=1)
    access: AccessRequirement = AccessRequirement.INTERACTIVE_USE
    usage: UsageLevel = UsageLevel.MEDIUM
    context: ContextSize = ContextSize.SHORT_CONVERSATION

    seats: int = Field(default=1, ge=1, le=1000)
    people_at_once: int = Field(default=1, ge=1, le=64)
    months: int = Field(default=24, ge=1, le=60)

    region: str = Field(default="DE", pattern=r"^[A-Z]{2}$")
    currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")

    existing_computer: ExistingComputer | None = None

    running_time: RunningTime = RunningTime.WORKDAY
    electricity_per_kwh: Money | None = None

    setup_skill: SetupSkill = SetupSkill.COMFORTABLE
    hours_for_setup: Decimal = Field(default=Decimal("16"), ge=0, le=500)

    budget_upfront: Money | None = None
    budget_monthly: Money | None = None

    offline_only: bool = False
    commercial_use: bool = False

    priority: Priority = Priority.LOWEST_COST

    @field_validator("seats", "people_at_once", "months", mode="before")
    @classmethod
    def _counts_are_numbers(cls, value: object) -> object:
        return _not_a_bool(value)


class InputsUsed(Strict):
    """The options above turned into the exact numbers the engine used."""

    requests_per_day: int
    context_tokens: int
    active_hours_per_day: Hours
    idle_hours_per_day: Hours
    setup_effort_multiplier: Decimal
    months: int
    currency: str


# --------------------------------------------------------------------------- #
# Catalog: what the crawler writes and the engine reads
# --------------------------------------------------------------------------- #


class Hardware(Strict):
    slug: str
    name: str
    role: str  # "gpu" for an upgrade part, "system" for a whole machine
    vram_gb: Decimal | None = None
    ram_gb: Decimal | None = None
    active_watts: Decimal | None = None
    """Measured draw of the whole machine under load. Not a card's rating."""
    idle_watts: Decimal | None = None
    gpu_board_watts: Decimal | None = None
    """What the card itself is rated for. A real figure, but not the same thing
    as whole-machine draw, so it is kept in its own column and only ever used
    to build an assumption that is labelled as one."""
    price: Decimal | None = None
    currency: str | None = None
    region: str | None = None
    price_note: str | None = None
    """Where the price came from and what kind of price it is."""
    setup_hours: Decimal = Decimal("2")
    source_url: str | None = None
    updated_at: dt.datetime | None = None


class Model(Strict):
    slug: str
    name: str
    params_b: Decimal | None = None
    quantization: str | None = None
    weights_gb: Decimal | None = None
    max_context: int | None = None
    layers: int | None = None
    kv_heads: int | None = None
    head_dim: int | None = None
    commercial_use: bool | None = None
    suitable_for: list[Workload] = Field(default_factory=list)
    setup_hours: Decimal = Decimal("3")
    source_url: str | None = None
    updated_at: dt.datetime | None = None


class Plan(Strict):
    slug: str
    provider: str
    name: str
    price: Decimal | None = None
    currency: str | None = None
    billing_interval: BillingInterval = BillingInterval.MONTHLY
    min_seats: int = 1
    regions: list[str] = Field(default_factory=list)
    max_context: int | None = None
    messages_per_day: int | None = None
    supports_api: bool | None = None
    commercial_use: bool | None = None
    suitable_for: list[Workload] = Field(default_factory=list)
    setup_hours: Decimal = Decimal("1")
    source_url: str | None = None
    updated_at: dt.datetime | None = None


class Catalog(Strict):
    """Everything the engine is allowed to look at for one request."""

    hardware: list[Hardware] = Field(default_factory=list)
    models: list[Model] = Field(default_factory=list)
    plans: list[Plan] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.hardware or self.models or self.plans)


# --------------------------------------------------------------------------- #
# Result
# --------------------------------------------------------------------------- #


class Finding(Strict):
    """One named rule that fired, with a sentence you can show a person."""

    code: str
    message: str
    blocking: bool = False


class MemoryNeeded(Strict):
    weights_gb: Decimal
    context_cache_gb: Decimal
    overhead_gb: Decimal
    gpu_total_gb: Decimal
    system_ram_total_gb: Decimal
    approximate: bool


class Month(Strict):
    month: int
    electricity: Decimal | None
    subscription: Decimal
    total: Decimal
    running_total: Decimal


class Cost(Strict):
    currency: str
    upfront: Decimal
    months: list[Month]
    total: Decimal
    electricity_unknown: bool = False


class BreakEven(Strict):
    versus: str
    cheaper_from_month: int | None
    flips_back_in_months: list[int] = Field(default_factory=list)
    note: str


class Case(Strict):
    """One of the low / base / high assumption runs."""

    case: str
    description: str
    winner: str | None
    total: Decimal | None


class Option(Strict):
    """One candidate the engine considered."""

    id: str
    label: str
    deployment: Deployment
    fits: bool
    uncertain: bool
    cost: Cost | None = None
    memory: MemoryNeeded | None = None
    setup_hours: Decimal | None = None
    findings: list[Finding] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class Result(Strict):
    status: ResultStatus
    inputs_used: InputsUsed
    best: Option | None = None
    runners_up: list[Option] = Field(default_factory=list)
    uncertain: list[Option] = Field(default_factory=list)
    ruled_out: list[Option] = Field(default_factory=list)
    break_even: list[BreakEven] = Field(default_factory=list)
    cases: list[Case] = Field(default_factory=list)
    answer_changes_with_assumptions: bool = False
    assumptions: list[str] = Field(default_factory=list)
    notes: list[Finding] = Field(default_factory=list)
    created_at: dt.datetime
