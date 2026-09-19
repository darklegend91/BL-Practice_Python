"""Break-even between two cumulative cash schedules (guide section 6).

Crossovers are found by walking the horizon month by month, so an annual
renewal step is visible and later reversals are reported rather than hidden by
comparing only the endpoints.
"""

from __future__ import annotations

from app.schemas.result import BreakEven, CostBreakdown


def compare(
    subject_id: str,
    subject: CostBreakdown,
    reference_id: str,
    reference: CostBreakdown,
    months: int,
) -> BreakEven:
    """Find when ``subject`` stops being the more expensive of the two, if ever."""
    crossover: int | None = None
    reversals: list[int] = []

    previous_cheaper: bool | None = None
    for month in range(1, months + 1):
        subject_total = subject.monthly[month - 1].cumulative.amount
        reference_total = reference.monthly[month - 1].cumulative.amount
        cheaper = subject_total <= reference_total

        if previous_cheaper is None:
            previous_cheaper = cheaper
            if cheaper:
                crossover = month
            continue

        if cheaper != previous_cheaper:
            if crossover is None and cheaper:
                crossover = month
            else:
                reversals.append(month)
            previous_cheaper = cheaper

    if crossover is None:
        note = (
            f"{subject_id} does not become cheaper than {reference_id} within "
            f"{months} months."
        )
    elif crossover == 1:
        note = f"{subject_id} is cheaper than {reference_id} from the first month."
    else:
        note = f"{subject_id} becomes cheaper than {reference_id} in month {crossover}."
    if reversals:
        note += f" The comparison reverses again in month(s) {', '.join(map(str, reversals))}."

    return BreakEven(
        against_candidate_id=reference_id,
        crossover_month=crossover,
        later_reversal_months=reversals,
        note=note,
    )
