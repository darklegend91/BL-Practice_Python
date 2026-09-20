"""When one option becomes cheaper than another, if it ever does.

Compares the running totals month by month rather than only the end, so an
annual renewal is visible and a comparison that flips back is reported.
"""

from __future__ import annotations

from app.schemas import BreakEven, Cost


def compare(mine: str, mine_cost: Cost, theirs: str, theirs_cost: Cost, months: int) -> BreakEven:
    cheaper_from: int | None = None
    flips: list[int] = []
    was_cheaper: bool | None = None

    for month in range(1, months + 1):
        cheaper = mine_cost.months[month - 1].running_total <= theirs_cost.months[month - 1].running_total

        if was_cheaper is None:
            was_cheaper = cheaper
            if cheaper:
                cheaper_from = month
            continue

        if cheaper != was_cheaper:
            if cheaper_from is None and cheaper:
                cheaper_from = month
            else:
                flips.append(month)
            was_cheaper = cheaper

    if cheaper_from is None:
        note = f"{mine} never becomes cheaper than {theirs} within {months} months."
    elif cheaper_from == 1:
        note = f"{mine} is cheaper than {theirs} from the very first month."
    else:
        note = f"{mine} becomes cheaper than {theirs} in month {cheaper_from}."
    if flips:
        note += f" It swaps back in month {', '.join(map(str, flips))}."

    return BreakEven(
        versus=theirs, cheaper_from_month=cheaper_from, flips_back_in_months=flips, note=note
    )
