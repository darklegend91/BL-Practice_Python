"""Typed catalog contracts and the immutable snapshot the engine reads.

Downloadable model variants, commercial plans and hardware are kept strictly
apart; a proprietary model's advertised capability never implies that a given
subscription includes it (guide section 2).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import (
    AccessRequirement,
    BillingInterval,
    Claimed,
    CurrencyCode,
    Evidenced,
    Money,
    RegionCode,
    ReviewStatus,
    StrictModel,
    Workload,
)
from app.version import CATALOG_SCHEMA_VERSION

Gb = Annotated[Decimal, Field(ge=0, le=100_000, max_digits=12, decimal_places=3)]
Watts = Annotated[Decimal, Field(ge=0, le=10_000, max_digits=8, decimal_places=2)]


class RevisionHeader(StrictModel):
    item_id: UUID
    revision_id: UUID
    schema_version: str = CATALOG_SCHEMA_VERSION
    review_status: ReviewStatus
    published_at: dt.datetime | None = None
    specs_reviewed_at: dt.datetime | None = None

    @model_validator(mode="after")
    def _published_has_timestamp(self) -> "RevisionHeader":
        if self.review_status is ReviewStatus.PUBLISHED and self.published_at is None:
            raise ValueError("a published revision must record published_at")
        return self


# --------------------------------------------------------------------------- #
# Hardware
# --------------------------------------------------------------------------- #


class HardwareKind(StrictModel):
    pass


class HardwareRevision(StrictModel):
    """A purchasable component or complete system.

    ``component_role`` distinguishes a bare GPU from a complete machine; a GPU
    price alone is never a complete system price (guide section 6).
    """

    header: RevisionHeader
    component_role: str  # gpu | ram | storage | psu | complete_system
    vendor: str
    model_name: str
    vram_gb: Evidenced[Gb] = Evidenced()
    system_ram_gb: Evidenced[Gb] = Evidenced()
    storage_gb: Evidenced[Gb] = Evidenced()
    whole_system_active_watts: Evidenced[Watts] = Evidenced()
    whole_system_idle_watts: Evidenced[Watts] = Evidenced()
    gpu_board_power_watts: Evidenced[Watts] = Evidenced()
    requires_components: list[str] = Field(default_factory=list)
    baseline_setup_hours: Decimal = Field(default=Decimal("2"), ge=0, le=200)


class PriceObservation(StrictModel):
    """One retailer's offer. Never overwritten by another retailer's price."""

    observation_id: UUID
    revision_id: UUID
    seller: str
    region: RegionCode
    price: Money
    tax_included: bool
    billing_interval: BillingInterval | None = None
    in_stock: Claimed = Claimed.UNKNOWN
    observed_at: dt.datetime
    reviewed_at: dt.datetime | None = None
    source_url: str | None = None


# --------------------------------------------------------------------------- #
# Downloadable model variants
# --------------------------------------------------------------------------- #


class LicenseTerms(StrictModel):
    """Open weights and an open-source license are different things."""

    open_weights: Claimed = Claimed.UNKNOWN
    osi_approved_license: Claimed = Claimed.UNKNOWN
    commercial_use_permitted: Claimed = Claimed.UNKNOWN
    license_name: str | None = None


class ModelArchitecture(StrictModel):
    """Only used to size the attention cache; absent values make it approximate."""

    layers: int | None = Field(default=None, ge=1, le=1000)
    kv_heads: int | None = Field(default=None, ge=1, le=1024)
    head_dim: int | None = Field(default=None, ge=1, le=4096)
    kv_bytes_per_element: int = Field(default=2, ge=1, le=4)


class ModelRevision(StrictModel):
    header: RevisionHeader
    family: str
    variant_name: str
    parameters_billion: Evidenced[Decimal] = Evidenced()
    quantization: str  # e.g. "Q4_K_M", "fp16"
    weights_gb: Evidenced[Gb] = Evidenced()
    max_context_tokens: Evidenced[int] = Evidenced()
    architecture: ModelArchitecture = ModelArchitecture()
    supported_runtimes: list[str] = Field(default_factory=list)
    license: LicenseTerms = LicenseTerms()
    capability_claims: dict[Workload, Claimed] = Field(default_factory=dict)
    runtime_overhead_gb: Decimal = Field(default=Decimal("1.0"), ge=0, le=64)
    baseline_setup_hours: Decimal = Field(default=Decimal("3"), ge=0, le=200)

    def capability(self, workload: Workload) -> Claimed:
        return self.capability_claims.get(workload, Claimed.UNKNOWN)


class BenchmarkObservation(StrictModel):
    """A measurement is only comparable to the exact configuration it was taken on."""

    observation_id: UUID
    model_revision_id: UUID
    quantization: str
    gpu_model: str
    runtime: str
    context_tokens: int
    concurrency: int
    tokens_per_second: Decimal = Field(ge=0)
    measured_at: dt.datetime
    source_url: str | None = None


# --------------------------------------------------------------------------- #
# Hosted subscription plans
# --------------------------------------------------------------------------- #


class PlanLimits(StrictModel):
    messages_per_day: Evidenced[int] = Evidenced()
    max_context_tokens: Evidenced[int] = Evidenced()
    fair_use_note: str | None = None


class PlanRevision(StrictModel):
    header: RevisionHeader
    provider: str
    plan_name: str
    price: Money
    billing_interval: BillingInterval
    minimum_seats: int = Field(default=1, ge=1)
    commitment_months: int = Field(default=1, ge=1, le=60)
    available_regions: list[RegionCode] = Field(default_factory=list)
    supported_access: list[AccessRequirement] = Field(default_factory=list)
    limits: PlanLimits = PlanLimits()
    capability_claims: dict[Workload, Claimed] = Field(default_factory=dict)
    commercial_use_permitted: Claimed = Claimed.UNKNOWN
    price_reviewed_at: dt.datetime | None = None
    baseline_setup_hours: Decimal = Field(default=Decimal("0.5"), ge=0, le=200)

    def capability(self, workload: Workload) -> Claimed:
        return self.capability_claims.get(workload, Claimed.UNKNOWN)


class PlanModelAccess(StrictModel):
    """Which model revision a plan documents access to, and under what conditions."""

    plan_revision_id: UUID
    model_revision_id: UUID
    conditions: str = ""
    reviewed_at: dt.datetime | None = None


# --------------------------------------------------------------------------- #
# Snapshot
# --------------------------------------------------------------------------- #


class CatalogSnapshot(StrictModel):
    """A consistent, immutable set of published revisions selected for one run."""

    snapshot_id: UUID
    taken_at: dt.datetime
    currency: CurrencyCode
    hardware: list[HardwareRevision] = Field(default_factory=list)
    models: list[ModelRevision] = Field(default_factory=list)
    plans: list[PlanRevision] = Field(default_factory=list)
    prices: list[PriceObservation] = Field(default_factory=list)
    benchmarks: list[BenchmarkObservation] = Field(default_factory=list)
    plan_model_access: list[PlanModelAccess] = Field(default_factory=list)

    @model_validator(mode="after")
    def _only_published_revisions(self) -> "CatalogSnapshot":
        for group in (self.hardware, self.models, self.plans):
            for revision in group:
                if revision.header.review_status is not ReviewStatus.PUBLISHED:
                    raise ValueError(
                        "a recommendation snapshot may only contain published revisions; "
                        f"{revision.header.revision_id} is {revision.header.review_status.value}"
                    )
        return self

    def offers_for(self, revision_id: UUID, region: str) -> list[PriceObservation]:
        return [
            price
            for price in self.prices
            if price.revision_id == revision_id and price.region == region
        ]

    def revision_ids(self) -> list[UUID]:
        return [
            revision.header.revision_id
            for group in (self.hardware, self.models, self.plans)
            for revision in group
        ]
