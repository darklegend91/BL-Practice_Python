"""The pure recommendation function (guide section 6).

``recommend`` performs no network calls, no database work and no browser work.
Given the same expanded scenario, catalog snapshot and policy it always returns
the same result.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from uuid import UUID, uuid4

from app.engine import breakeven, candidates as candidate_gen, costing, feasibility, ranking
from app.engine.costing import Assumptions, PriceUnavailable
from app.engine.feasibility import UNCERTAINTY_CODES
from app.engine.policy import DEFAULT_POLICY, Policy
from app.engine.reasons import Reason, render
from app.schemas.catalog import CatalogSnapshot
from app.schemas.common import (
    Claimed,
    DeploymentKind,
    EvidenceQuality,
    Money,
    Priority,
    ResultStatus,
    utc_now,
)
from app.schemas.result import (
    CandidateResult,
    Finding,
    RecommendationResult,
    SensitivityCase,
)
from app.schemas.scenario import ExpandedScenario


def _evidence_quality(result: CandidateResult) -> EvidenceQuality:
    codes = {finding.code for finding in result.findings}
    if Reason.PRICE_MISSING in codes or Reason.CAPABILITY_UNKNOWN in codes:
        return EvidenceQuality.INSUFFICIENT
    stale = {Reason.PRICE_STALE, Reason.SPEC_STALE} & codes
    partial = {
        Reason.MEMORY_ESTIMATE_APPROXIMATE,
        Reason.PERFORMANCE_UNKNOWN,
        Reason.POWER_ASSUMED,
        Reason.SUBSCRIPTION_LIMIT_UNKNOWN,
        Reason.CONTEXT_SUPPORT_UNKNOWN,
        Reason.COMMERCIAL_USE_UNVERIFIED,
        Reason.LICENSE_UNVERIFIED,
        Reason.ELECTRICITY_TARIFF_MISSING,
    } & codes
    if partial:
        return EvidenceQuality.PARTIAL
    if stale:
        return EvidenceQuality.COMPLETE_BUT_STALE
    return EvidenceQuality.COMPLETE_AND_FRESH


def _assumption_notes(scenario: ExpandedScenario, policy: Policy) -> list[str]:
    notes = [
        f"Presets applied: {scenario.applied_presets or 'none'} "
        f"(preset version {scenario.preset_version}).",
        f"Operating time: {scenario.operating_time.active_hours_per_day} h active and "
        f"{scenario.operating_time.idle_hours_per_day} h idle per day.",
        f"A month is {policy.days_per_month} days.",
        "Whole-system power is used; a GPU board power limit is not a measured "
        "whole-system figure.",
        "GPU VRAM and system RAM are checked separately and never pooled.",
    ]
    if scenario.source.inventory is not None:
        notes.append(
            "Existing equipment has zero new purchase cost in the cash comparison; "
            "no resale or depreciation value is assumed."
        )
    if scenario.source.electricity_tariff_per_kwh is None:
        notes.append("No electricity tariff was supplied, so operating cost is unknown.")
    return notes


def _evaluate(
    candidate,
    scenario: ExpandedScenario,
    snapshot: CatalogSnapshot,
    policy: Policy,
    as_of: dt.datetime,
) -> CandidateResult:
    assessment = feasibility.assess(candidate, scenario, snapshot, policy, as_of)

    cost = None
    if not assessment.blocked:
        try:
            cost = costing.build(candidate, scenario, snapshot, policy)
        except PriceUnavailable:
            assessment.add(
                Reason.PRICE_MISSING,
                blocking=True,
                candidate=candidate.label,
                region=scenario.source.region,
            )

    if cost is not None:
        _check_budgets(cost, scenario, assessment, candidate.label)

    hours = costing.setup_hours(candidate, scenario)
    if hours > scenario.max_acceptable_setup_hours:
        assessment.add(
            Reason.SETUP_EFFORT_EXCEEDED,
            blocking=True,
            setup_hours=hours,
            allowance=scenario.max_acceptable_setup_hours,
            setup_preference=scenario.source.setup_preference.value,
        )
    if hours > scenario.source.setup_allowance_hours:
        assessment.add(
            Reason.SETUP_EFFORT_EXCEEDED,
            blocking=True,
            setup_hours=hours,
            allowance=scenario.source.setup_allowance_hours,
            setup_preference=scenario.source.setup_preference.value,
        )

    result = CandidateResult(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        deployment=candidate.deployment,
        feasible=not assessment.blocked,
        uncertain=assessment.uncertain,
        cost=cost if not assessment.blocked else None,
        memory=assessment.memory,
        setup_hours=hours,
        findings=assessment.findings,
        evidence=assessment.evidence,
        catalog_revision_ids=candidate.revision_ids,
    )
    return result.model_copy(update={"evidence_quality": _evidence_quality(result)})


def _check_budgets(cost, scenario: ExpandedScenario, assessment, label: str) -> None:
    budget = scenario.source.budget
    if budget.upfront is not None and cost.upfront.amount > budget.upfront.amount:
        assessment.add(
            Reason.BUDGET_UPFRONT_EXCEEDED,
            blocking=True,
            upfront=cost.upfront.amount,
            budget=budget.upfront.amount,
        )
    if budget.monthly is not None and cost.monthly:
        worst = max(month.total.amount for month in cost.monthly)
        if worst > budget.monthly.amount:
            assessment.add(
                Reason.BUDGET_MONTHLY_EXCEEDED,
                blocking=True,
                monthly=worst,
                budget=budget.monthly.amount,
            )


def _sensitivity(
    feasible,
    scenario: ExpandedScenario,
    snapshot: CatalogSnapshot,
    policy: Policy,
) -> tuple[list[SensitivityCase], bool]:
    """Re-cost the feasible set under low/base/high assumptions."""
    outcomes: list[SensitivityCase] = []
    leaders: list[str | None] = []

    for case in costing.cases(policy):
        best_id: str | None = None
        best_total: Money | None = None
        for candidate, result in feasible:
            try:
                cost = costing.build(candidate, scenario, snapshot, policy, case)
            except PriceUnavailable:
                continue
            if best_total is None or cost.horizon_total.amount < best_total.amount:
                best_total, best_id = cost.horizon_total, result.candidate_id
        outcomes.append(
            SensitivityCase(
                case_id=case.case_id,
                description=case.description,
                leading_candidate_id=best_id,
                horizon_total=best_total,
            )
        )
        leaders.append(best_id)

    sensitive = len({leader for leader in leaders if leader is not None}) > 1
    return outcomes, sensitive


def recommend(
    scenario: ExpandedScenario,
    snapshot: CatalogSnapshot,
    policy: Policy = DEFAULT_POLICY,
    *,
    as_of: dt.datetime | None = None,
    created_at: dt.datetime | None = None,
) -> RecommendationResult:
    """Evaluate one scenario against one immutable catalog snapshot."""
    as_of = as_of or snapshot.taken_at
    created_at = created_at or utc_now()

    if snapshot.currency != scenario.currency:
        return RecommendationResult(
            policy_version=policy.version,
            catalog_snapshot_id=snapshot.snapshot_id,
            created_at=created_at,
            status=ResultStatus.NEEDS_INPUT,
            scenario=scenario,
            missing_fields=["currency"],
            findings=[
                Finding(
                    code=Reason.PRICE_MISSING,
                    message=(
                        f"The catalog snapshot is priced in {snapshot.currency} but the "
                        f"scenario uses {scenario.currency}; a reviewed conversion is "
                        "required."
                    ),
                    blocking=True,
                )
            ],
            evidence_quality=EvidenceQuality.INSUFFICIENT,
        )

    generated = candidate_gen.generate(scenario, snapshot, policy)
    evaluated = [
        (candidate, _evaluate(candidate, scenario, snapshot, policy, as_of))
        for candidate in generated
    ]

    feasible = [pair for pair in evaluated if pair[1].feasible and not pair[1].uncertain]
    uncertain = [pair for pair in evaluated if pair[1].feasible and pair[1].uncertain]
    ruled_out = [pair[1] for pair in evaluated if not pair[1].feasible]

    priority = scenario.source.priority
    ranked = ranking.rank([pair[1] for pair in feasible], priority)
    ranked_uncertain = ranking.rank([pair[1] for pair in uncertain], priority)

    sensitivity, sensitive = _sensitivity(feasible, scenario, snapshot, policy)

    findings: list[Finding] = []
    if sensitive:
        findings.append(
            Finding(
                code=Reason.RESULT_SENSITIVE_TO_ASSUMPTIONS,
                message=render(Reason.RESULT_SENSITIVE_TO_ASSUMPTIONS),
            )
        )

    break_evens = []
    if ranked:
        selected = ranked[0]
        others = ranked[1:] + ranked_uncertain
        for other in others[:10]:
            if selected.cost and other.cost:
                break_evens.append(
                    breakeven.compare(
                        selected.candidate_id,
                        selected.cost,
                        other.candidate_id,
                        other.cost,
                        scenario.months,
                    )
                )
        if all(entry.crossover_month is None for entry in break_evens) and break_evens:
            findings.append(
                Finding(
                    code=Reason.NO_BREAK_EVEN_IN_HORIZON,
                    message=render(Reason.NO_BREAK_EVEN_IN_HORIZON, months=scenario.months),
                )
            )

    if ranked:
        status = ResultStatus.RECOMMENDED
        selected_result: CandidateResult | None = ranked[0]
        alternatives = ranked[1:]
    elif ranked_uncertain:
        status = ResultStatus.INSUFFICIENT_EVIDENCE
        selected_result = None
        alternatives = []
    else:
        status = ResultStatus.NO_FEASIBLE_OPTION
        selected_result = None
        alternatives = []

    quality = (
        selected_result.evidence_quality
        if selected_result is not None
        else EvidenceQuality.INSUFFICIENT
    )

    return RecommendationResult(
        policy_version=policy.version,
        catalog_snapshot_id=snapshot.snapshot_id,
        catalog_revision_ids=snapshot.revision_ids(),
        created_at=created_at,
        status=status,
        scenario=scenario,
        selected=selected_result,
        alternatives=alternatives,
        uncertain=ranked_uncertain,
        ruled_out=ruled_out,
        break_even=break_evens,
        sensitivity=sensitivity,
        sensitive_to_assumptions=sensitive,
        assumptions=_assumption_notes(scenario, policy),
        findings=findings,
        evidence_quality=quality,
    )
