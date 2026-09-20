"""The whole decision, as one function.

``recommend(request, catalog)`` touches no database and no network. Give it the
same request and the same catalog and it returns the same answer every time,
which is what makes it easy to test and easy to trust.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from app.engine import breakeven, candidates as build_candidates, costing, feasibility, ranking, reasons
from app.engine.costing import NoPrice
from app.engine.policy import DEFAULT_POLICY, Policy
from app.options import expand
from app.schemas import (
    Case, Catalog, Deployment, Finding, Option, RecommendInput, Result, ResultStatus,
)


def _assumption_notes(request: RecommendInput, used, policy: Policy) -> list[str]:
    notes = [
        f"About {used.requests_per_day} requests a day and {used.context_tokens} "
        f"tokens of context, from the options you chose.",
        f"The machine is busy {used.active_hours_per_day} h and idle "
        f"{used.idle_hours_per_day} h a day.",
        f"A month counts as {policy.days_per_month} days.",
        "Electricity is counted for the whole machine, not just the graphics card.",
        "Graphics memory and system memory are checked separately, never added together.",
    ]
    if request.existing_computer is not None:
        notes.append(
            "Hardware you already own costs nothing extra here. No resale value is "
            "assumed either."
        )
    if request.electricity_per_kwh is None:
        notes.append("No electricity price was given, so running cost is unknown.")
    return notes


def _evaluate(candidate, request: RecommendInput, used, policy: Policy) -> Option:
    check = feasibility.check(candidate, request, used, policy)

    cost = None
    if not check.blocked:
        try:
            cost = costing.build(candidate, request, used, policy)
        except NoPrice:
            check.note(
                reasons.NO_PRICE, blocking=True,
                option=candidate.label, region=request.region,
            )

    if cost is not None:
        if request.budget_upfront is not None and cost.upfront > request.budget_upfront:
            check.note(
                reasons.OVER_UPFRONT_BUDGET, blocking=True,
                cost=cost.upfront, budget=request.budget_upfront,
            )
        if request.budget_monthly is not None and cost.months:
            worst = max(month.total for month in cost.months)
            if worst > request.budget_monthly:
                check.note(
                    reasons.OVER_MONTHLY_BUDGET, blocking=True,
                    cost=worst, budget=request.budget_monthly,
                )

    parts = [candidate.machine, candidate.model, candidate.plan]
    hours = costing.setup_hours(parts, used)
    if hours > request.hours_for_setup:
        check.note(
            reasons.TOO_MUCH_SETUP, blocking=True,
            hours=hours, allowed=request.hours_for_setup,
        )

    return Option(
        id=candidate.id,
        label=candidate.label,
        deployment=candidate.deployment,
        fits=not check.blocked,
        uncertain=check.uncertain,
        cost=cost if not check.blocked else None,
        memory=check.memory,
        setup_hours=hours,
        findings=check.findings,
        sources=candidate.sources,
    )


def _three_cases(pairs, request: RecommendInput, used, policy: Policy) -> tuple[list[Case], bool]:
    """Re-cost everything that fits under low, base and high assumptions."""
    cases: list[Case] = []
    winners: list[str | None] = []

    for assumptions in costing.three_cases(policy):
        best_id: str | None = None
        best_total: Decimal | None = None
        for candidate, option in pairs:
            try:
                cost = costing.build(candidate, request, used, policy, assumptions)
            except NoPrice:
                continue
            if best_total is None or cost.total < best_total:
                best_total, best_id = cost.total, option.id
        cases.append(Case(
            case=assumptions.case,
            description=assumptions.description,
            winner=best_id,
            total=best_total,
        ))
        winners.append(best_id)

    changes = len({winner for winner in winners if winner is not None}) > 1
    return cases, changes


def recommend(
    request: RecommendInput,
    catalog: Catalog,
    policy: Policy = DEFAULT_POLICY,
    *,
    now: dt.datetime | None = None,
) -> Result:
    """Work out what this person should do."""
    used = expand(request)
    created = now or dt.datetime.now(dt.timezone.utc)

    if catalog.is_empty:
        return Result(
            status=ResultStatus.NOTHING_FITS,
            inputs_used=used,
            assumptions=_assumption_notes(request, used, policy),
            notes=[Finding(
                code=reasons.CATALOG_EMPTY,
                message=reasons.say(reasons.CATALOG_EMPTY),
                blocking=True,
            )],
            created_at=created,
        )

    pairs = [
        (candidate, _evaluate(candidate, request, used, policy))
        for candidate in build_candidates.build(request, catalog, policy)
    ]

    solid = [pair for pair in pairs if pair[1].fits and not pair[1].uncertain]
    shaky = [pair[1] for pair in pairs if pair[1].fits and pair[1].uncertain]
    impossible = [pair[1] for pair in pairs if not pair[1].fits]

    ordered = ranking.rank([option for _, option in solid], request.priority)
    ordered_shaky = ranking.rank(shaky, request.priority)

    cases, changes = _three_cases(solid, request, used, policy)

    notes: list[Finding] = []
    if changes:
        notes.append(Finding(
            code=reasons.ANSWER_DEPENDS_ON_ASSUMPTIONS,
            message=reasons.say(reasons.ANSWER_DEPENDS_ON_ASSUMPTIONS),
        ))

    comparisons = []
    if ordered:
        best = ordered[0]
        for other in (ordered[1:] + ordered_shaky)[:10]:
            if best.cost and other.cost:
                comparisons.append(
                    breakeven.compare(best.id, best.cost, other.id, other.cost, used.months)
                )
        if comparisons and all(entry.cheaper_from_month is None for entry in comparisons):
            notes.append(Finding(
                code=reasons.NEVER_PAYS_OFF,
                message=reasons.say(reasons.NEVER_PAYS_OFF, months=used.months),
            ))

    if ordered:
        status = ResultStatus.RECOMMENDED
        best_option, rest = ordered[0], ordered[1:]
    elif ordered_shaky:
        status = ResultStatus.ONLY_UNCERTAIN_OPTIONS
        best_option, rest = None, []
    else:
        status = ResultStatus.NOTHING_FITS
        best_option, rest = None, []

    return Result(
        status=status,
        inputs_used=used,
        best=best_option,
        runners_up=rest,
        uncertain=ordered_shaky,
        ruled_out=impossible,
        break_even=comparisons,
        cases=cases,
        answer_changes_with_assumptions=changes,
        assumptions=_assumption_notes(request, used, policy),
        notes=notes,
        created_at=created,
    )
