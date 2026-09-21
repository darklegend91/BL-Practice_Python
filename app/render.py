"""Turns a result into text for a terminal.

Kept apart from the command-line plumbing so it can be tested on its own: give
it a result, get back a string. It reads nothing and prints nothing itself.
"""

from __future__ import annotations

from decimal import Decimal

from app.schemas import Catalog, Option, Result, ResultStatus

RULE = "-" * 72


def money(amount: Decimal | None, currency: str) -> str:
    if amount is None:
        return "unknown"
    return f"{amount.quantize(Decimal('0.01'))} {currency}"


def _option_line(option: Option, place: str) -> str:
    cost = option.cost
    total = money(cost.total, cost.currency) if cost else "no price"
    upfront = money(cost.upfront, cost.currency) if cost else "-"
    return f"  {place:<3} {option.label[:44]:<44} {total:>16}   up front {upfront}"


def _findings(option: Option, indent: str = "       ") -> list[str]:
    return [f"{indent}- {finding.message}" for finding in option.findings]


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
        for place, option in enumerate(answer.uncertain[:5], start=1):
            out.append(_option_line(option, f"{place}."))
            out.extend(_findings(option))
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
        out.append("Under different assumptions:")
        for case in answer.cases:
            winner = case.winner or "nothing"
            total = f" at {case.total.quantize(Decimal('0.01'))}" if case.total else ""
            out.append(f"  {case.case:<5} {case.description:<38} {winner[:30]}{total}")
        if answer.answer_changes_with_assumptions:
            out.append("  ! the winner changes between these, so treat it as close")
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
