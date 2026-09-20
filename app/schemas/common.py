"""Shared value types: stable option identifiers, money, and evidence wrappers.

The API always speaks stable identifiers such as ``coding``; display labels live
next to them but are never the wire value (guide section 4).
"""

from __future__ import annotations

import datetime as dt
import enum
from decimal import Decimal
from typing import Annotated, Generic, TypeVar
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

T = TypeVar("T")

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_\-]{0,63}$")]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
RegionCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]


class StrictModel(BaseModel):
    """Base contract: unknown fields are rejected, values are not re-coerced loosely."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


# --------------------------------------------------------------------------- #
# Option identifiers
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
    CUSTOM = "custom"


class ResponseLength(str, enum.Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class ContextRequirement(str, enum.Enum):
    SHORT_CONVERSATION = "short_conversation"
    LONG_DOCUMENT = "long_document"
    CUSTOM = "custom"


class SetupPreference(str, enum.Enum):
    BEGINNER = "beginner"
    COMFORTABLE = "comfortable"
    EXPERIENCED = "experienced"


class Priority(str, enum.Enum):
    LOWEST_CASH_COST = "lowest_cash_cost"
    LEAST_SETUP = "least_setup"
    OFFLINE_CONTROL = "offline_control"


class DeploymentKind(str, enum.Enum):
    EXISTING_LOCAL = "existing_local"
    LOCAL_UPGRADE = "local_upgrade"
    NEW_LOCAL_MACHINE = "new_local_machine"
    HOSTED_SUBSCRIPTION = "hosted_subscription"


class BillingInterval(str, enum.Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class Claimed(str, enum.Enum):
    """Three-valued evidence state. ``UNKNOWN`` never satisfies a constraint."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class EvidenceQuality(str, enum.Enum):
    """Freshness and completeness label - not a probability of correctness."""

    COMPLETE_AND_FRESH = "complete_and_fresh"
    COMPLETE_BUT_STALE = "complete_but_stale"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class ReviewStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ResultStatus(str, enum.Enum):
    RECOMMENDED = "recommended"
    NEEDS_INPUT = "needs_input"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_FEASIBLE_OPTION = "no_feasible_option"


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #

MONEY_PLACES = Decimal("0.0001")


class Money(StrictModel):
    """An exact amount with its currency. Mixing currencies needs a conversion record."""

    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    currency: CurrencyCode

    @field_validator("amount", mode="before")
    @classmethod
    def _reject_bool_and_nonfinite(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean is not a valid money amount")
        if isinstance(value, float) and value != value:  # NaN
            raise ValueError("money amount must be finite")
        if isinstance(value, Decimal) and not value.is_finite():
            raise ValueError("money amount must be finite")
        return value

    def __add__(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def scaled(self, factor: Decimal) -> "Money":
        return Money(amount=self.amount * Decimal(factor), currency=self.currency)

    def _same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"cannot combine {self.currency} and {other.currency} without a "
                "reviewed conversion record"
            )

    @classmethod
    def zero(cls, currency: str) -> "Money":
        return cls(amount=Decimal("0"), currency=currency)


class CurrencyConversion(StrictModel):
    """A manually reviewed conversion. The application never calls a rate API."""

    from_currency: CurrencyCode
    to_currency: CurrencyCode
    rate: Decimal = Field(gt=0, max_digits=18, decimal_places=8)
    as_of: dt.date
    source_url: str
    reviewed_by: str


# --------------------------------------------------------------------------- #
# Evidence
# --------------------------------------------------------------------------- #


class EvidenceRef(StrictModel):
    """Points a single material claim at the snapshot that supports it."""

    claim_id: UUID
    field_name: str
    snapshot_id: UUID | None = None
    source_url: str | None = None
    excerpt: str = Field(default="", max_length=2000)
    review_status: ReviewStatus = ReviewStatus.DRAFT
    reviewed_at: dt.datetime | None = None
    observed_at: dt.datetime | None = None

    @model_validator(mode="after")
    def _published_needs_review_time(self) -> "EvidenceRef":
        if self.review_status is ReviewStatus.PUBLISHED and self.reviewed_at is None:
            raise ValueError("a published claim must record its review timestamp")
        return self


class Evidenced(StrictModel, Generic[T]):
    """A typed value together with the claim that backs it.

    ``value is None`` means *unknown*, which is different from zero or false and
    never counts as a satisfied constraint (guide section 6, step 5).
    """

    value: T | None = None
    evidence: EvidenceRef | None = None

    @property
    def known(self) -> bool:
        return self.value is not None

    def require(self, what: str) -> T:
        if self.value is None:
            raise LookupError(f"{what} is unknown")
        return self.value


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)
