"""The result contract (guide section 6, "Result contract").

Results are immutable. Viewing a historical result never recomputes it against
today's prices, so every version identifier that influenced it is stored here.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    DeploymentKind,
    EvidenceQuality,
    Money,
    ResultStatus,
    StrictModel,
)
from app.schemas.scenario import ExpandedScenario
from app.engine.reasons import Reason
from app.version import APP_VERSION, RESULT_SCHEMA_VERSION


class Finding(StrictModel):
    """One named rule outcome with its rendered explanation."""

    code: Reason
    message: str
    blocking: bool = False


class SourceLink(StrictModel):
    field_name: str
    source_url: str | None
    excerpt: str = ""
    reviewed_at: dt.datetime | None = None
    snapshot_id: UUID | None = None


class MemoryEstimate(StrictModel):
    weights_gb: Decimal
    kv_cache_gb: Decimal
    runtime_overhead_gb: Decimal
    total_gpu_gb: Decimal
    total_system_ram_gb: Decimal
    approximate: bool
    method: str


class MonthlyCost(StrictModel):
    month: int  # 1-based
    energy: Money | None
    recurring: Money
    total: Money
    cumulative: Money


class CostBreakdown(StrictModel):
    currency: str
    upfront: Money
    monthly: list[MonthlyCost]
    horizon_total: Money
    optional_time_cost: Money | None = None
    energy_unknown: bool = False
    rounding_policy: str = "decimal, 4 places, half-even; displayed at 2 places"


class BreakEven(StrictModel):
    against_candidate_id: str
    crossover_month: int | None
    later_reversal_months: list[int] = Field(default_factory=list)
    note: str = ""


class SensitivityCase(StrictModel):
    case_id: str  # low | base | high
    description: str
    leading_candidate_id: str | None
    horizon_total: Money | None


class CandidateResult(StrictModel):
    candidate_id: str
    label: str
    deployment: DeploymentKind
    feasible: bool
    uncertain: bool
    cost: CostBreakdown | None = None
    memory: MemoryEstimate | None = None
    setup_hours: Decimal | None = None
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[SourceLink] = Field(default_factory=list)
    evidence_quality: EvidenceQuality = EvidenceQuality.PARTIAL
    catalog_revision_ids: list[UUID] = Field(default_factory=list)

    @property
    def blocking_reasons(self) -> list[Reason]:
        return [f.code for f in self.findings if f.blocking]


class RecommendationResult(StrictModel):
    result_schema_version: str = RESULT_SCHEMA_VERSION
    app_version: str = APP_VERSION
    policy_version: str
    catalog_snapshot_id: UUID
    catalog_revision_ids: list[UUID] = Field(default_factory=list)
    created_at: dt.datetime

    status: ResultStatus
    scenario: ExpandedScenario

    selected: CandidateResult | None = None
    alternatives: list[CandidateResult] = Field(default_factory=list)
    uncertain: list[CandidateResult] = Field(default_factory=list)
    ruled_out: list[CandidateResult] = Field(default_factory=list)

    break_even: list[BreakEven] = Field(default_factory=list)
    sensitivity: list[SensitivityCase] = Field(default_factory=list)
    sensitive_to_assumptions: bool = False

    missing_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    evidence_quality: EvidenceQuality = EvidenceQuality.PARTIAL
