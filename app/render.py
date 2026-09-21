"""Turns a result into text for a terminal.

Kept apart from the command-line plumbing so it can be tested on its own: give
it a result, get back a string. It reads nothing and prints nothing itself.
"""

from __future__ import annotations

from decimal import Decimal

from app.engine import reasons
from app.schemas import Catalog, Option, Result, ResultStatus

RULE = "-" * 72


def money(amount: Decimal | None, currency: str) -> str:
    if amount is None:
        return "unknown"
    return f"{amount.quantize(Decimal('0.01'))} {currency}"


def total_of(cost) -> str:
    """The total, said in a way that does not overstate what is known.

    When the running cost is missing, the figure is a floor. Printing it as a
    plain total would be exactly the "a missing price is not zero" mistake this
    app promises not to make - and with nothing else to pay, that floor is
    0.00, which reads as free.
    """
    if cost is None:
        return "no price"
    if cost.electricity_unknown:
        return f"{money(cost.total, cost.currency)} + running cost"
    return money(cost.total, cost.currency)


def _option_line(option: Option, place: str) -> str:
    cost = option.cost
    upfront = money(cost.upfront, cost.currency) if cost else "-"
    return f"  {place:<3} {option.label[:42]:<42} {total_of(cost):>26}   up front {upfront}"


def _findings(option: Option, indent: str = "       ") -> list[str]:
    return [f"{indent}- {finding.message}" for finding in option.findings]


COMMON_ENOUGH = 0.66
"""How much of a list a caveat has to cover before it is worth saying once at
the top instead of on every row."""


def _common_codes(options: list[Option]) -> list[tuple[str, int]]:
    """Reason codes that cover most of these options, with how many.

    Grouped by code rather than by message, because a message names the option
    it is about and so is never identical twice even when the reason is. The
    count is shown rather than hidden, because "most" is not "all" and the
    reader should not have to assume which.
    """
    total = len(options)
    if total < 3:
        return []

    counts: dict[str, int] = {}
    for option in options:
        for code in {finding.code for finding in option.findings}:
            counts[code] = counts.get(code, 0) + 1

    ordered = [
        (code, count) for code, count in counts.items()
        if count >= 3 and count / total >= COMMON_ENOUGH
    ]
    ordered.sort(key=lambda pair: (-pair[1], pair[0]))
    return ordered


def _cases_cannot_differ(answer: Result) -> bool:
    """True when every case had the same figures to work with.

    Usage and power only move the electricity bill. With no electricity price
    and nothing else recurring, the three cases are the same sum three times.
    """
    totals = {case.total for case in answer.cases}
    if len(totals) > 1:
        return False
    considered = ([answer.best] if answer.best else []) + answer.runners_up + answer.uncertain
    return bool(considered) and all(
        option.cost is not None and option.cost.electricity_unknown
        for option in considered
    )


def result(answer: Result, *, show_all: bool = False) -> str:
    """The whole answer, formatted for reading."""
    out: list[str] = []
    used = answer.inputs_used

    out.append(RULE)
    if answer.status is ResultStatus.RECOMMENDED:
        out.append("RECOMMENDATION")
    elif answer.status is ResultStatus.ONLY_UNCERTAIN_OPTIONS:
        out.append("NO CONFIRMED ANSWER - every option is missing a fact")
    else:
        out.append("NOTHING FITS")
    out.append(RULE)

    out.append(
        f"Based on about {used.requests_per_day} requests a day, "
        f"{used.context_tokens} tokens of context, over {used.months} months."
    )
    out.append("")

    if answer.best is not None:
        out.append("Best option:")
        out.append(_option_line(answer.best, "1."))
        if answer.best.memory:
            memory = answer.best.memory
            rough = " (rough estimate)" if memory.approximate else ""
            out.append(f"       needs about {memory.gpu_total_gb} GB of graphics memory{rough}")
        if answer.best.setup_hours is not None:
            out.append(f"       about {answer.best.setup_hours} hours to set up")
        out.extend(_findings(answer.best))
        for url in answer.best.sources:
            out.append(f"       source: {url}")
        out.append("")

    if answer.runners_up:
        out.append("Also works:")
        for place, option in enumerate(answer.runners_up[:5], start=2):
            out.append(_option_line(option, f"{place}."))
        out.append("")

    if answer.uncertain:
        out.append(f"Missing a fact, so not confirmed ({len(answer.uncertain)}):")

        # Most of these caveats are the same on every option, because they come
        # from what the source does not publish rather than from the option.
        # Saying them once leaves the list readable and the differences visible.
        common = _common_codes(answer.uncertain)
        hoisted = {code for code, _ in common}
        if common:
            total = len(answer.uncertain)
            out.append("  What most of them have in common:")
            for code, count in common:
                how_many = "all of them" if count == total else f"{count} of {total}"
                out.append(f"    - {reasons.in_short(code)}  ({how_many})")
            out.append("")

        for place, option in enumerate(answer.uncertain[:5], start=1):
            out.append(_option_line(option, f"{place}."))
            extra = [f.message for f in option.findings if f.code not in hoisted]
            out.extend(f"       - {message}" for message in extra)
        if len(answer.uncertain) > 5:
            out.append(f"       ...and {len(answer.uncertain) - 5} more")
        out.append("")

    if answer.ruled_out:
        out.append(f"Ruled out ({len(answer.ruled_out)}):")
        shown = answer.ruled_out if show_all else answer.ruled_out[:5]
        for option in shown:
            blocking = [f for f in option.findings if f.blocking]
            why = blocking[0].message if blocking else "no reason recorded"
            out.append(f"  x   {option.label[:44]:<44}")
            out.append(f"       {why}")
        if not show_all and len(answer.ruled_out) > 5:
            out.append(f"       ...and {len(answer.ruled_out) - 5} more (use --all to see them)")
        out.append("")

    if answer.break_even:
        out.append("Break-even:")
        for entry in answer.break_even[:3]:
            out.append(f"  - {entry.note}")
        out.append("")

    if answer.cases:
        # Cases carry the option's identifier; people want its name.
        known = {
            option.id: option
            for group in (
                [answer.best] if answer.best else [],
                answer.runners_up, answer.uncertain,
            )
            for option in group
        }
        out.append("Under different assumptions:")
        for case in answer.cases:
            winning = known.get(case.winner) if case.winner else None
            winner = winning.label if winning else (case.winner or "nothing fits")
            if case.total is None:
                total = ""
            elif winning is not None and winning.cost is not None and (
                winning.cost.electricity_unknown
            ):
                # Same floor, same caveat: do not print it as a settled figure.
                total = f"  {case.total.quantize(Decimal('0.01'))} + running cost"
            else:
                total = f"  {case.total.quantize(Decimal('0.01'))}"
            out.append(f"  {case.case:<5} {case.description:<34} {winner[:40]}{total}")
        if answer.answer_changes_with_assumptions:
            out.append("  ! the winner changes between these, so treat it as close")
        elif _cases_cannot_differ(answer):
            out.append(
                "  these are identical because the running cost is unknown, so there "
                "is nothing for the assumptions to change"
            )
        out.append("")

    out.append("Assumptions:")
    for note in answer.assumptions:
        out.append(f"  - {note}")

    if answer.notes:
        out.append("")
        out.append("Notes:")
        for note in answer.notes:
            out.append(f"  - {note.message}")

    return "\n".join(out)


def catalog(stored: Catalog) -> str:
    """What is in the catalog, as a table."""
    out: list[str] = []

    out.append(f"Hardware ({len(stored.hardware)})")
    if stored.hardware:
        out.append(f"  {'name':<34}{'vram':>7}{'board W':>9}{'price':>12}")
        for card in stored.hardware:
            price = (
                f"{card.price.quantize(Decimal('0.01'))} {card.currency}"
                if card.price is not None else "-"
            )
            out.append(
                f"  {card.name[:33]:<34}"
                f"{(str(card.vram_gb) if card.vram_gb else '-'):>7}"
                f"{(str(card.gpu_board_watts) if card.gpu_board_watts else '-'):>9}"
                f"{price:>12}"
            )
    out.append("")

    out.append(f"Models ({len(stored.models)})")
    if stored.models:
        out.append(f"  {'name':<40}{'size GB':>9}{'context':>10}")
        for model in stored.models[:20]:
            out.append(
                f"  {model.name[:39]:<40}"
                f"{(str(model.weights_gb) if model.weights_gb else '-'):>9}"
                f"{(str(model.max_context) if model.max_context else '-'):>10}"
            )
        if len(stored.models) > 20:
            out.append(f"  ...and {len(stored.models) - 20} more")
    out.append("")

    out.append(f"Subscription plans ({len(stored.plans)})")
    for plan in stored.plans:
        price = (
            f"{plan.price.quantize(Decimal('0.01'))} {plan.currency}"
            if plan.price is not None else "-"
        )
        out.append(f"  {plan.provider} {plan.name[:30]:<32}{price:>12} / {plan.billing_interval.value}")

    if stored.is_empty:
        out.append("")
        out.append("The catalog is empty. Run:  python -m app crawl")

    return "\n".join(out)


def crawl_report(report: dict) -> str:
    out = [
        f"Visited {report['sources_visited']} source(s), "
        f"wrote {report['catalog_rows_written']} row(s), "
        f"{report['failures']} failure(s).",
        "",
    ]
    for entry in report["details"]:
        if "error" in entry:
            out.append(f"  FAILED  {entry['url']}")
            out.append(f"          {entry['error']}")
            continue
        changed = "changed" if entry.get("changed") else "unchanged"
        out.append(
            f"  ok      {entry['url']}"
        )
        out.append(
            f"          {entry.get('rows_found', 0)} row(s) read, page {changed}, "
            f"via {entry.get('adapter', '?')}"
        )
        for note in entry.get("notes", []):
            out.append(f"          note: {note}")
    return "\n".join(out)
