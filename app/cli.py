"""The command line. Everything the web API does, without starting a server.

    python -m app                  pick what to do from a menu
    python -m app ask              answer questions, get a recommendation
    python -m app serve            start the web API instead
    python -m app options          what you can choose
    python -m app catalog          what is in the catalog
    python -m app crawl            fetch the sources again
    python -m app sources          list or add sources
    python -m app setup            create the tables and load the examples

``ask`` with no flags asks you the questions one at a time. With flags it runs
straight through, which is what you want in a script.

The command line and the web API share the same engine and the same catalog, so
they cannot disagree with each other.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from decimal import Decimal, InvalidOperation

from app import catalog as catalog_loader, render
from app.options import (
    CONTEXT_TOKENS, REQUESTS_PER_DAY, RUNNING_HOURS, SETUP_MULTIPLIER, all_options,
)
from app.schemas import (
    AccessRequirement, ContextSize, Priority, RecommendInput, RunningTime, SetupSkill,
    UsageLevel, Workload,
)
from app.version import APP_VERSION

MENU = """
LLM Fit Advisor {version}

How do you want to use it?

  1  Answer some questions here and get a recommendation
  2  Start the web API instead  (http://localhost:8000/docs)
  3  Show what is in the catalog
  4  Fetch the sources again
  5  Show the questions and what each answer means
  q  Quit
""".strip()


# --------------------------------------------------------------------------- #
# Asking questions
# --------------------------------------------------------------------------- #


def _pick(label: str, choices: list[tuple[str, str]], default: str) -> str:
    """Show a numbered list and read one answer. Enter keeps the default."""
    print(f"\n{label}")
    for number, (value, text) in enumerate(choices, start=1):
        marker = " (default)" if value == default else ""
        print(f"  {number}  {text}{marker}")
    while True:
        raw = input("> ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1][0]
        for value, _ in choices:
            if raw == value:
                return value
        print("  Pick one of the numbers above, or press Enter for the default.")


def _pick_many(label: str, choices: list[tuple[str, str]], default: list[str]) -> list[str]:
    print(f"\n{label}  (several allowed, separated by commas)")
    for number, (value, text) in enumerate(choices, start=1):
        print(f"  {number}  {text}")
    while True:
        raw = input("> ").strip()
        if not raw:
            return default
        picked: list[str] = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit() and 1 <= int(part) <= len(choices):
                picked.append(choices[int(part) - 1][0])
            elif any(part == value for value, _ in choices):
                picked.append(part)
        if picked:
            return list(dict.fromkeys(picked))
        print("  Pick at least one number from the list above.")


def _number(label: str, default, *, allow_blank: bool = True):
    shown = "blank for unknown" if default is None else f"default {default}"
    while True:
        raw = input(f"\n{label}  ({shown})\n> ").strip()
        if not raw:
            return default
        try:
            return Decimal(raw)
        except InvalidOperation:
            print("  That is not a number.")


def _yes_no(label: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    raw = input(f"\n{label}  ({suffix})\n> ").strip().lower()
    if not raw:
        return default
    return raw.startswith("y")


def _labelled(section: str) -> list[tuple[str, str]]:
    return [(item["id"], item["label"]) for item in all_options()[section]]


def ask_interactively() -> RecommendInput:
    """Walk through the questions and build the request."""
    print("\nAnswer these, or press Enter to take the default.")

    workloads = _pick_many("What do you want it for?", _labelled("workloads"), ["coding"])
    access = _pick("How will you use it?", _labelled("access"), "interactive_use")
    usage = _pick("How much will you use it?", _labelled("usage"), "medium")
    context = _pick("How much text at once?", _labelled("context"), "short_conversation")
    months = _number("Compare over how many months?", 24)
    priority = _pick("What matters most?", _labelled("priority"), "lowest_cost")

    has_computer = _yes_no("Do you already have a computer to run this on?", True)
    existing = None
    if has_computer:
        vram = _number("How much graphics memory does it have, in GB?", None)
        ram = _number("How much system memory, in GB?", None)
        existing = {
            "label": "my computer",
            "gpu_vram_gb": vram,
            "system_ram_gb": ram,
        }

    running = _pick("How long does it run each day?", _labelled("running_time"), "workday")
    electricity = _number("What do you pay per kWh?", None)
    skill = _pick("How comfortable are you setting things up?",
                  _labelled("setup_skill"), "comfortable")
    offline = _yes_no("Does everything have to stay on your own machine?", False)
    commercial = _yes_no("Is this for commercial use?", False)

    return RecommendInput(
        workloads=[Workload(w) for w in workloads],
        access=AccessRequirement(access),
        usage=UsageLevel(usage),
        context=ContextSize(context),
        months=int(months),
        priority=Priority(priority),
        existing_computer=existing,
        running_time=RunningTime(running),
        electricity_per_kwh=electricity,
        setup_skill=SetupSkill(skill),
        offline_only=offline,
        commercial_use=commercial,
    )


def request_from_flags(args) -> RecommendInput:
    """Build the request from command-line flags."""
    existing = None
    if args.vram or args.ram or args.active_watts or args.idle_watts:
        existing = {
            "label": args.computer_name,
            "gpu_vram_gb": args.vram,
            "system_ram_gb": args.ram,
            "active_watts": args.active_watts,
            "idle_watts": args.idle_watts,
        }

    return RecommendInput(
        workloads=[Workload(w) for w in args.workloads.split(",") if w],
        access=AccessRequirement(args.access),
        usage=UsageLevel(args.usage),
        context=ContextSize(args.context),
        seats=args.seats,
        people_at_once=args.people_at_once,
        months=args.months,
        region=args.region,
        currency=args.currency,
        existing_computer=existing,
        running_time=RunningTime(args.running_time),
        electricity_per_kwh=args.electricity,
        setup_skill=SetupSkill(args.setup_skill),
        hours_for_setup=args.hours_for_setup,
        budget_upfront=args.budget_upfront,
        budget_monthly=args.budget_monthly,
        offline_only=args.offline,
        commercial_use=args.commercial,
        priority=Priority(args.priority),
    )


# --------------------------------------------------------------------------- #
# What each command does
# --------------------------------------------------------------------------- #


def do_ask(args) -> int:
    from app.db import session_scope
    from app.rates import Rates, parse_override

    request = ask_interactively() if args.interactive else request_from_flags(args)

    rates = Rates()
    for override in args.rate or []:
        try:
            rates.add(parse_override(override, request.currency))
        except ValueError as error:
            print(f"--rate {override}: {error}", file=sys.stderr)
            return 1

    with session_scope() as session:
        answer = catalog_loader.answer_for(session, request, rates=rates)

    if args.json:
        print(json.dumps(answer.model_dump(mode="json"), indent=2))
    else:
        print(render.result(answer, show_all=args.all))
    return 0


def do_options(args) -> int:
    if args.json:
        print(json.dumps(all_options(), indent=2))
        return 0

    print("What you can choose\n")
    for section, meaning in (
        ("workloads", None),
        ("access", None),
        ("usage", REQUESTS_PER_DAY),
        ("context", CONTEXT_TOKENS),
        ("running_time", RUNNING_HOURS),
        ("setup_skill", SETUP_MULTIPLIER),
        ("priority", None),
    ):
        print(f"{section}:")
        for item in all_options()[section]:
            means = f"   -> {item['means']}" if "means" in item else ""
            print(f"  {item['id']:<22} {item['label']}{means}")
        print()

    print("numbers you can give:")
    for item in all_options()["numbers"]:
        bounds = ""
        if "min" in item:
            bounds = f"  ({item['min']}..{item.get('max', 'any')})"
        print(f"  {item['field']:<34} in {item['unit']}{bounds}")
    return 0


def do_catalog(args) -> int:
    from app.db import session_scope

    with session_scope() as session:
        stored = catalog_loader.load(session, region=args.region)

    if args.json:
        print(json.dumps(stored.model_dump(mode="json"), indent=2))
    else:
        print(render.catalog(stored))
    return 0


def do_crawl(args) -> int:
    from app import crawler
    from app.db import session_scope
    from app.seed import add_examples, add_real

    if args.real or args.examples:
        with session_scope() as session:
            added = add_real(session) if args.real else add_examples(session)
        print(f"Registered {added} new source(s).")

    with session_scope() as session:
        report = asyncio.run(crawler.crawl_all(session)).as_dict()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render.crawl_report(report))
    return 1 if report["failures"] and not report["catalog_rows_written"] else 0


def do_sources(args) -> int:
    from sqlalchemy import select

    from app import netguard
    from app.db import Source, session_scope

    if args.add:
        try:
            netguard.check_shape(args.add)
        except netguard.Blocked as blocked:
            print(f"Refused: {blocked}", file=sys.stderr)
            return 1
        with session_scope() as session:
            session.add(Source(url=args.add, label=args.label, adapter=args.adapter))
        print(f"Added {args.add} (read with the {args.adapter} reader).")
        print("Now run:  python -m app crawl")
        return 0

    with session_scope() as session:
        rows = session.scalars(select(Source).order_by(Source.url)).all()
        listing = [
            {"url": r.url, "label": r.label, "adapter": r.adapter, "enabled": r.enabled}
            for r in rows
        ]

    if args.json:
        print(json.dumps(listing, indent=2))
        return 0

    if not listing:
        print("No sources registered. Try:  python -m app crawl --examples")
        return 0
    print(f"{'adapter':<16}{'url'}")
    for row in listing:
        mark = "" if row["enabled"] else "  (disabled)"
        print(f"{row['adapter']:<16}{row['url']}{mark}")
    return 0


def do_setup(args) -> int:
    import subprocess

    print("Creating the tables...")
    done = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True,
    )
    if done.returncode != 0:
        print(done.stdout + done.stderr, file=sys.stderr)
        print("\nThe tables could not be created. Is the database running, and is "
              "LLMFIT_DATABASE_URL right?", file=sys.stderr)
        return 1
    print("Tables are ready.")

    from app.db import session_scope
    from app.seed import add_examples, add_real

    with session_scope() as session:
        added = add_real(session) if args.real else add_examples(session)
    kind = "real" if args.real else "example"
    print(f"Registered {added} {kind} source(s).")
    print("\nNext:  python -m app crawl     then:  python -m app ask")
    return 0


def do_serve(args) -> int:
    import uvicorn

    # Flushed, because when this is piped to a file stdout is block-buffered
    # and the banner would otherwise turn up after uvicorn's own output.
    print(f"Web API on http://{args.host}:{args.port}", flush=True)
    print(f"Try it in a browser: http://{args.host}:{args.port}/docs", flush=True)
    print("Stop it with Ctrl-C.\n", flush=True)
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def do_menu(args) -> int:
    """Shown when the command is run with nothing after it."""
    print(MENU.format(version=APP_VERSION))
    choice = input("\n> ").strip().lower()

    if choice in ("q", "quit", "exit"):
        return 0
    if choice == "1":
        return do_ask(_defaults("ask", interactive=True))
    if choice == "2":
        return do_serve(_defaults("serve"))
    if choice == "3":
        return do_catalog(_defaults("catalog"))
    if choice == "4":
        return do_crawl(_defaults("crawl"))
    if choice == "5":
        return do_options(_defaults("options"))

    print("Did not recognise that. Run with --help to see every command.")
    return 1


def _defaults(command: str, **overrides):
    """The same defaults argparse would give, for choices made from the menu."""
    parsed = build_parser().parse_args([command])
    for name, value in overrides.items():
        setattr(parsed, name, value)
    return parsed


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #


def _decimal(text: str) -> Decimal:
    try:
        return Decimal(text)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app",
        description=(
            "Should you run a language model on your own computer, or pay for a "
            "subscription? Run with no command to pick from a menu."
        ),
    )
    parser.add_argument("--version", action="version", version=APP_VERSION)
    commands = parser.add_subparsers(dest="command")

    ask = commands.add_parser("ask", help="answer questions and get a recommendation")
    ask.add_argument("-i", "--interactive", action="store_true",
                     help="ask the questions one at a time")
    ask.add_argument("--workloads", default="coding",
                     help="comma separated: coding, studying, writing, document_analysis")
    ask.add_argument("--access", default="interactive_use",
                     choices=[m.value for m in AccessRequirement])
    ask.add_argument("--usage", default="medium", choices=[m.value for m in UsageLevel])
    ask.add_argument("--context", default="short_conversation",
                     choices=[m.value for m in ContextSize])
    ask.add_argument("--seats", type=int, default=1)
    ask.add_argument("--people-at-once", type=int, default=1)
    ask.add_argument("--months", type=int, default=24)
    ask.add_argument("--region", default="DE")
    ask.add_argument("--currency", default="EUR",
                     help="three-letter code, for example INR")
    ask.add_argument("--rate", action="append", metavar="USD=88.20",
                     help="an exchange rate into your currency; repeatable")
    ask.add_argument("--computer-name", default="my computer")
    ask.add_argument("--vram", type=_decimal, help="graphics memory you already have, GB")
    ask.add_argument("--ram", type=_decimal, help="system memory you already have, GB")
    ask.add_argument("--active-watts", type=_decimal, help="measured draw under load")
    ask.add_argument("--idle-watts", type=_decimal, help="measured draw when idle")
    ask.add_argument("--running-time", default="workday",
                     choices=[m.value for m in RunningTime])
    ask.add_argument("--electricity", type=_decimal, help="price per kWh")
    ask.add_argument("--setup-skill", default="comfortable",
                     choices=[m.value for m in SetupSkill])
    ask.add_argument("--hours-for-setup", type=_decimal, default=Decimal("16"))
    ask.add_argument("--budget-upfront", type=_decimal)
    ask.add_argument("--budget-monthly", type=_decimal)
    ask.add_argument("--offline", action="store_true", help="rule out every subscription")
    ask.add_argument("--commercial", action="store_true", help="require a commercial licence")
    ask.add_argument("--priority", default="lowest_cost", choices=[m.value for m in Priority])
    ask.add_argument("--all", action="store_true", help="show every ruled-out option")
    ask.add_argument("--json", action="store_true", help="print the raw result")
    ask.set_defaults(run=do_ask)

    options = commands.add_parser("options", help="what you can choose, and what it means")
    options.add_argument("--json", action="store_true")
    options.set_defaults(run=do_options)

    catalog = commands.add_parser("catalog", help="what the answer would be based on")
    catalog.add_argument("--region", help="only offers for this country")
    catalog.add_argument("--json", action="store_true")
    catalog.set_defaults(run=do_catalog)

    crawl = commands.add_parser("crawl", help="fetch every registered source now")
    crawl.add_argument("--real", action="store_true",
                       help="register the real sources first (needs LLMFIT_CRAWLER=crawl4ai)")
    crawl.add_argument("--examples", action="store_true",
                       help="register the bundled example sources first")
    crawl.add_argument("--json", action="store_true")
    crawl.set_defaults(run=do_crawl)

    sources = commands.add_parser("sources", help="list or add the pages to read")
    sources.add_argument("--add", metavar="URL", help="register a page")
    sources.add_argument("--label", default="", help="a name for it")
    sources.add_argument("--adapter", default="factblock",
                         help="which reader understands it")
    sources.add_argument("--json", action="store_true")
    sources.set_defaults(run=do_sources)

    setup = commands.add_parser("setup", help="create the tables and register sources")
    setup.add_argument("--real", action="store_true", help="register the real sources")
    setup.set_defaults(run=do_setup)

    serve = commands.add_parser("serve", help="start the web API instead")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true", help="restart when the code changes")
    serve.set_defaults(run=do_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        return do_menu(args)

    try:
        return args.run(args)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130
    except Exception as error:  # noqa: BLE001 - the terminal wants a sentence, not a trace
        print(f"\n{type(error).__name__}: {error}", file=sys.stderr)
        if "could not connect" in str(error).lower() or "does not exist" in str(error).lower():
            print("\nIs PostgreSQL running, and has 'python -m app setup' been run?",
                  file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
