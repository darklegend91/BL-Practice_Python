"""Hard constraints and uncertainty classification (guide section 6, steps 4-5).

Every check returns named findings. A finding marked ``blocking`` rules the
candidate out; an unknown value is recorded as uncertainty and never counts as a
satisfied check.
"""

from __future__ import annotations

import datetime as dt

from app.engine.candidates import Candidate
from app.engine.freshness import is_stale
from app.engine.memory import estimate as estimate_memory
from app.engine.policy import Policy
from app.engine.reasons import Reason, render
from app.schemas.catalog import CatalogSnapshot
from app.schemas.common import Claimed, DeploymentKind, Evidenced
from app.schemas.result import Finding, MemoryEstimate, SourceLink
from app.schemas.scenario import ExpandedScenario


class Assessment:
    """Mutable accumulator used while checking one candidate."""

    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.evidence: list[SourceLink] = []
        self.memory: MemoryEstimate | None = None

    def add(self, reason: Reason, *, blocking: bool = False, **values: object) -> None:
        self.findings.append(
            Finding(code=reason, message=render(reason, **values), blocking=blocking)
        )

    def cite(self, field_name: str, evidenced: Evidenced) -> None:
        reference = evidenced.evidence
        if reference is None:
            return
        self.evidence.append(
            SourceLink(
                field_name=field_name,
                source_url=reference.source_url,
                excerpt=reference.excerpt,
                reviewed_at=reference.reviewed_at,
                snapshot_id=reference.snapshot_id,
            )
        )

    @property
    def blocked(self) -> bool:
        return any(finding.blocking for finding in self.findings)

    @property
    def uncertain(self) -> bool:
        return any(finding.code in UNCERTAINTY_CODES for finding in self.findings)


UNCERTAINTY_CODES = {
    Reason.LICENSE_UNVERIFIED,
    Reason.COMMERCIAL_USE_UNVERIFIED,
    Reason.CAPABILITY_UNKNOWN,
    Reason.MEMORY_ESTIMATE_APPROXIMATE,
    Reason.PERFORMANCE_UNKNOWN,
    Reason.POWER_ASSUMED,
    Reason.PRICE_STALE,
    Reason.PRICE_MISSING,
    Reason.SPEC_STALE,
    Reason.SUBSCRIPTION_LIMIT_UNKNOWN,
    Reason.CONTEXT_SUPPORT_UNKNOWN,
    Reason.ELECTRICITY_TARIFF_MISSING,
}


def assess(
    candidate: Candidate,
    scenario: ExpandedScenario,
    snapshot: CatalogSnapshot,
    policy: Policy,
    as_of: dt.datetime,
) -> Assessment:
    result = Assessment()
    if candidate.deployment is DeploymentKind.HOSTED_SUBSCRIPTION:
        _assess_plan(candidate, scenario, policy, as_of, result)
    else:
        _assess_local(candidate, scenario, snapshot, policy, as_of, result)
    _assess_specs_freshness(candidate, policy, as_of, result)
    return result


# --------------------------------------------------------------------------- #
# Hosted subscriptions
# --------------------------------------------------------------------------- #


def _assess_plan(
    candidate: Candidate,
    scenario: ExpandedScenario,
    policy: Policy,
    as_of: dt.datetime,
    result: Assessment,
) -> None:
    plan = candidate.plan
    assert plan is not None
    source = scenario.source

    if source.constraints.offline_required:
        result.add(Reason.OFFLINE_REQUIRED, blocking=True, candidate=candidate.label)
    elif not source.constraints.external_processing_allowed:
        result.add(
            Reason.EXTERNAL_PROCESSING_NOT_ALLOWED, blocking=True, candidate=candidate.label
        )

    if source.region not in plan.available_regions:
        result.add(
            Reason.REGION_UNAVAILABLE,
            blocking=True,
            candidate=candidate.label,
            region=source.region,
        )

    if source.access_requirement not in plan.supported_access:
        result.add(
            Reason.ACCESS_TYPE_UNSUPPORTED,
            blocking=True,
            candidate=candidate.label,
            access_requirement=source.access_requirement.value,
        )

    if source.constraints.commercial_use:
        if plan.commercial_use_permitted is Claimed.UNSUPPORTED:
            result.add(
                Reason.COMMERCIAL_USE_NOT_PERMITTED,
                blocking=True,
                candidate=candidate.label,
                license_name=plan.plan_name,
            )
        elif plan.commercial_use_permitted is Claimed.UNKNOWN:
            result.add(Reason.COMMERCIAL_USE_UNVERIFIED, candidate=candidate.label)

    context_limit = plan.limits.max_context_tokens
    result.cite("plan.limits.max_context_tokens", context_limit)
    if context_limit.value is None:
        result.add(Reason.CONTEXT_SUPPORT_UNKNOWN, candidate=candidate.label)
    elif context_limit.value < scenario.context_tokens:
        result.add(
            Reason.CONTEXT_UNSUPPORTED,
            blocking=True,
            candidate=candidate.label,
            supported=context_limit.value,
            requested=scenario.context_tokens,
        )

    daily_limit = plan.limits.messages_per_day
    result.cite("plan.limits.messages_per_day", daily_limit)
    if daily_limit.value is None:
        # A chat plan without a documented limit cannot be compared with the
        # workload; that is uncertainty, not a pass.
        result.add(Reason.SUBSCRIPTION_LIMIT_UNKNOWN, candidate=candidate.label)
    elif daily_limit.value < scenario.work_volume.requests_per_day:
        result.add(
            Reason.PLAN_LIMIT_BELOW_WORKLOAD,
            blocking=True,
            candidate=candidate.label,
            limit=daily_limit.value,
            requested=scenario.work_volume.requests_per_day,
        )

    _check_capabilities(plan.capability, candidate.label, scenario, policy, result)

    if is_stale(plan.price_reviewed_at, as_of, policy.price_freshness_days):
        result.add(
            Reason.PRICE_STALE,
            blocking=not policy.allow_stale_evidence,
            candidate=candidate.label,
            reviewed_at=(
                plan.price_reviewed_at.date().isoformat()
                if plan.price_reviewed_at
                else "never"
            ),
            max_age=policy.price_freshness_days,
        )


# --------------------------------------------------------------------------- #
# Local deployments
# --------------------------------------------------------------------------- #


def _assess_local(
    candidate: Candidate,
    scenario: ExpandedScenario,
    snapshot: CatalogSnapshot,
    policy: Policy,
    as_of: dt.datetime,
    result: Assessment,
) -> None:
    model = candidate.model
    hardware = candidate.hardware
    assert model is not None and hardware is not None
    source = scenario.source

    # A locally run model is reachable by a local program, so both interactive
    # use and application integration are supported without a further check.

    if source.constraints.commercial_use:
        permitted = model.license.commercial_use_permitted
        if permitted is Claimed.UNSUPPORTED:
            result.add(
                Reason.COMMERCIAL_USE_NOT_PERMITTED,
                blocking=True,
                candidate=candidate.label,
                license_name=model.license.license_name or "its license",
            )
        elif permitted is Claimed.UNKNOWN:
            result.add(Reason.COMMERCIAL_USE_UNVERIFIED, candidate=candidate.label)
            if model.license.license_name is None:
                result.add(Reason.LICENSE_UNVERIFIED, candidate=candidate.label)

    context_support = model.max_context_tokens
    result.cite("model.max_context_tokens", context_support)
    if context_support.value is None:
        result.add(Reason.CONTEXT_SUPPORT_UNKNOWN, candidate=candidate.label)
    elif context_support.value < scenario.context_tokens:
        result.add(
            Reason.CONTEXT_UNSUPPORTED,
            blocking=True,
            candidate=candidate.label,
            supported=context_support.value,
            requested=scenario.context_tokens,
        )

    result.cite("model.weights_gb", model.weights_gb)
    memory = estimate_memory(
        model,
        scenario.context_tokens,
        source.concurrent_sessions,
        policy,
        cpu_only=candidate.cpu_only,
    )
    result.memory = memory
    if memory is None:
        result.add(Reason.CAPABILITY_UNKNOWN, candidate=candidate.label, workload="memory sizing")
    else:
        if memory.approximate:
            result.add(Reason.MEMORY_ESTIMATE_APPROXIMATE, model=model.variant_name)
        _check_memory_fit(candidate, memory, scenario, result)

    _check_capabilities(model.capability, candidate.label, scenario, policy, result)
    _check_performance_evidence(candidate, scenario, snapshot, result)

    if not hardware.power_is_measured:
        result.add(Reason.POWER_ASSUMED, candidate=hardware.label)

    if source.electricity_tariff_per_kwh is None:
        result.add(Reason.ELECTRICITY_TARIFF_MISSING)

    _check_hardware_prices(candidate, scenario, snapshot, policy, as_of, result)



def _check_memory_fit(
    candidate: Candidate,
    memory: MemoryEstimate,
    scenario: ExpandedScenario,
    result: Assessment,
) -> None:
    hardware = candidate.hardware
    model = candidate.model
    assert hardware is not None and model is not None

    if memory.total_gpu_gb > 0:
        available = hardware.gpu_vram_gb
        if available is None or available < memory.total_gpu_gb:
            result.add(
                Reason.VRAM_INSUFFICIENT,
                blocking=True,
                model=model.variant_name,
                required_gb=memory.total_gpu_gb,
                context=scenario.context_tokens,
                concurrency=scenario.source.concurrent_sessions,
                gpu=hardware.label,
                available_gb=available if available is not None else "an unknown amount of",
            )

    available_ram = hardware.system_ram_gb
    if available_ram is None or available_ram < memory.total_system_ram_gb:
        result.add(
            Reason.SYSTEM_RAM_INSUFFICIENT,
            blocking=True,
            model=model.variant_name,
            required_gb=memory.total_system_ram_gb,
            available_gb=available_ram if available_ram is not None else "an unknown amount of",
        )


def _check_performance_evidence(
    candidate: Candidate,
    scenario: ExpandedScenario,
    snapshot: CatalogSnapshot,
    result: Assessment,
) -> None:
    model = candidate.model
    hardware = candidate.hardware
    assert model is not None and hardware is not None
    matches = [
        benchmark
        for benchmark in snapshot.benchmarks
        if benchmark.model_revision_id == model.header.revision_id
        and benchmark.quantization == model.quantization
        and benchmark.context_tokens >= scenario.context_tokens
        and benchmark.concurrency >= scenario.source.concurrent_sessions
    ]
    if not matches:
        result.add(
            Reason.PERFORMANCE_UNKNOWN,
            model=model.variant_name,
            gpu=hardware.label,
            context=scenario.context_tokens,
        )


def _check_hardware_prices(
    candidate: Candidate,
    scenario: ExpandedScenario,
    snapshot: CatalogSnapshot,
    policy: Policy,
    as_of: dt.datetime,
    result: Assessment,
) -> None:
    hardware = candidate.hardware
    assert hardware is not None
    for revision_id in hardware.purchased_revisions:
        offers = snapshot.offers_for(revision_id, scenario.source.region)
        if not offers:
            result.add(
                Reason.PRICE_MISSING,
                blocking=True,
                candidate=hardware.label,
                region=scenario.source.region,
            )
            continue
        freshest = max(
            offers, key=lambda offer: offer.reviewed_at or dt.datetime.min.replace(tzinfo=dt.timezone.utc)
        )
        if is_stale(freshest.reviewed_at, as_of, policy.price_freshness_days):
            result.add(
                Reason.PRICE_STALE,
                blocking=not policy.allow_stale_evidence,
                candidate=hardware.label,
                reviewed_at=(
                    freshest.reviewed_at.date().isoformat() if freshest.reviewed_at else "never"
                ),
                max_age=policy.price_freshness_days,
            )


# --------------------------------------------------------------------------- #
# Shared checks
# --------------------------------------------------------------------------- #


def _check_capabilities(
    lookup,
    label: str,
    scenario: ExpandedScenario,
    policy: Policy,
    result: Assessment,
) -> None:
    for workload in scenario.source.workloads:
        claim = lookup(workload)
        if claim is Claimed.UNSUPPORTED:
            result.add(
                Reason.CAPABILITY_UNSUPPORTED,
                blocking=True,
                candidate=label,
                workload=workload.value,
            )
        elif claim is Claimed.UNKNOWN:
            result.add(
                Reason.CAPABILITY_UNKNOWN,
                blocking=policy.require_capability_evidence,
                candidate=label,
                workload=workload.value,
            )


def _assess_specs_freshness(
    candidate: Candidate, policy: Policy, as_of: dt.datetime, result: Assessment
) -> None:
    headers = []
    if candidate.model:
        headers.append((candidate.model.variant_name, candidate.model.header))
    if candidate.plan:
        headers.append((candidate.plan.plan_name, candidate.plan.header))
    for label, header in headers:
        if is_stale(header.specs_reviewed_at, as_of, policy.spec_freshness_days):
            result.add(
                Reason.SPEC_STALE,
                candidate=label,
                reviewed_at=(
                    header.specs_reviewed_at.date().isoformat()
                    if header.specs_reviewed_at
                    else "never"
                ),
                max_age=policy.spec_freshness_days,
            )
