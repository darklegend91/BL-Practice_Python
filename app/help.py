"""The self-documenting part of the API.

Every POST has a matching GET that tells you what to send it, and ``GET /``
explains the whole project. The choices and defaults here are read from the
Pydantic models rather than typed out again, so they cannot drift away from
what the code actually accepts.
"""

from __future__ import annotations

from app.schemas import (
    AccessRequirement, ContextSize, ExistingComputer, Priority, RecommendInput,
    RunningTime, SetupSkill, Strict, UsageLevel, Workload,
)
from app.version import APP_VERSION


class FieldHelp(Strict):
    name: str
    required: bool
    default: str | None = None
    choices: list[str] | None = None
    note: str


class EndpointHelp(Strict):
    """Everything you need to call one endpoint, in one response."""

    method: str
    path: str
    what_it_does: str
    send_this: dict | None = None
    fields: list[FieldHelp] = []
    you_get_back: list[str] = []
    try_it: str


class EndpointSummary(Strict):
    method: str
    path: str
    what_it_does: str
    details_at: str | None = None


class Home(Strict):
    name: str
    version: str
    what_this_is: list[str]
    login_required: bool
    the_flow: list[str]
    endpoints: list[EndpointSummary]
    first_time_setup: list[str]
    a_worked_example: dict
    how_the_answer_is_worked_out: list[str]
    what_it_will_not_do: list[str]
    known_limitations: list[str]
    where_to_look_next: dict


def _choices(enum_class) -> list[str]:
    return [member.value for member in enum_class]


def _default(model, name: str) -> str | None:
    field = model.model_fields[name]
    if field.is_required():
        return None
    value = field.default
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _field(name: str, note: str, choices=None, model=RecommendInput) -> FieldHelp:
    field = model.model_fields[name]
    return FieldHelp(
        name=name,
        required=field.is_required(),
        default=_default(model, name),
        choices=_choices(choices) if choices else None,
        note=note,
    )


# --------------------------------------------------------------------------- #
# POST /recommend
# --------------------------------------------------------------------------- #

EXAMPLE_ASK = {
    "workloads": ["coding"],
    "usage": "medium",
    "months": 24,
    "electricity_per_kwh": "0.32",
    "existing_computer": {
        "label": "my desk PC",
        "gpu_vram_gb": "16",
        "system_ram_gb": "32",
        "active_watts": "410",
        "idle_watts": "70",
    },
}


def recommend_help() -> EndpointHelp:
    return EndpointHelp(
        method="POST",
        path="/recommend",
        what_it_does=(
            "Takes your answers and tells you whether to run a model on your own "
            "computer or pay for a subscription. Nothing is stored and nothing is "
            "crawled while you wait."
        ),
        send_this=EXAMPLE_ASK,
        fields=[
            _field("workloads", "What you want it for. Pick one or more.", Workload),
            _field("access", "Whether a program needs to call it, or only a person.",
                   AccessRequirement),
            _field("usage", "How much you use it. GET /options shows the requests a day "
                            "each one means.", UsageLevel),
            _field("context", "How much text is in play at once.", ContextSize),
            _field("seats", "How many people are paying for it."),
            _field("people_at_once", "How many use it simultaneously. This drives memory "
                                     "needs on your own machine."),
            _field("months", "How long to compare over. 1 to 60."),
            _field("region", "Two-letter country code. Decides which prices and plans apply."),
            _field("currency", "Three-letter code. Anything priced in another currency is "
                               "not comparable and is excluded."),
            _field("existing_computer", "What you already own, as an object. Leave it out "
                                        "and only new machines and subscriptions are "
                                        "compared. See existing_computer_fields below."),
            _field("running_time", "How long the machine runs each day.", RunningTime),
            _field("electricity_per_kwh", "Your electricity price, as a string like "
                                          "\"0.32\". Leave it out and running cost is "
                                          "reported as unknown, never as zero."),
            _field("setup_skill", "How much setup time to allow for. Multiplies the "
                                  "estimated hours.", SetupSkill),
            _field("hours_for_setup", "The most setup time you will accept."),
            _field("budget_upfront", "Most you will spend at once. Anything over it is "
                                     "ruled out."),
            _field("budget_monthly", "Most you will spend in any one month."),
            _field("offline_only", "true rules out every subscription."),
            _field("commercial_use", "true requires a licence that allows it. An "
                                     "unconfirmed licence counts as uncertain, not as "
                                     "permission."),
            _field("priority", "What to optimise for when ordering the results.", Priority),
        ],
        you_get_back=[
            "status - recommended, only_uncertain_options, or nothing_fits",
            "inputs_used - the exact numbers your options turned into",
            "best - the winner, with its month-by-month costs",
            "runners_up - the rest that work, in order",
            "uncertain - options with a fact missing, kept separate so they cannot win",
            "ruled_out - everything impossible, each with the reason in plain words",
            "break_even - when the winner became cheaper than each of the others",
            "cases - the same comparison under low, base and high assumptions",
            "assumptions - what it assumed, written out",
        ],
        try_it=(
            "curl -X POST localhost:8000/recommend -H 'Content-Type: application/json' "
            "-d '{\"workloads\":[\"coding\"]}'"
        ),
    )


def existing_computer_fields() -> list[FieldHelp]:
    return [
        FieldHelp(name="label", required=False, default="my computer",
                  note="What to call it in the answer."),
        FieldHelp(name="gpu_vram_gb", required=False,
                  note="Graphics memory in GB. Without it, no local option can be "
                       "confirmed to fit."),
        FieldHelp(name="system_ram_gb", required=False, note="System memory in GB."),
        FieldHelp(name="active_watts", required=False,
                  note="Measured draw under load. Without it a figure is assumed and the "
                       "option is marked uncertain."),
        FieldHelp(name="idle_watts", required=False, note="Measured draw when idle."),
    ]


# --------------------------------------------------------------------------- #
# POST /sources and POST /crawl
# --------------------------------------------------------------------------- #


def sources_help() -> EndpointHelp:
    return EndpointHelp(
        method="POST",
        path="/sources",
        what_it_does=(
            "Registers a page for the crawler. It is fetched the next time you call "
            "POST /crawl. Internal and private addresses are refused."
        ),
        send_this={"url": "https://vendor.example.com/prices", "label": "vendor prices"},
        fields=[
            FieldHelp(name="url", required=True,
                      note="http or https only, on a public address, no username or "
                           "password in the URL."),
            FieldHelp(name="label", required=False, default="",
                      note="A name for you, so you can tell your sources apart."),
        ],
        you_get_back=["The registered url, label and enabled flag."],
        try_it=(
            "curl -X POST localhost:8000/sources -H 'Content-Type: application/json' "
            "-d '{\"url\":\"https://vendor.example.com/prices\"}'"
        ),
    )


def crawl_help() -> EndpointHelp:
    return EndpointHelp(
        method="POST",
        path="/crawl",
        what_it_does=(
            "Fetches every enabled source now, stores the page, and writes what it can "
            "read into the catalog. Runs while you wait. Send no body."
        ),
        send_this=None,
        fields=[],
        you_get_back=[
            "sources_visited - how many it tried",
            "catalog_rows_written - how many hardware, model and plan rows it wrote",
            "failures - how many sources could not be read",
            "details - per source: whether the page changed, rows found, or the error",
        ],
        try_it="curl -X POST localhost:8000/crawl",
    )


# --------------------------------------------------------------------------- #
# GET /
# --------------------------------------------------------------------------- #


def home() -> Home:
    return Home(
        name="LLM Fit Advisor",
        version=APP_VERSION,
        what_this_is=[
            "Answers one question: should you run a language model on your own computer, "
            "or pay for a subscription?",
            "You pick from fixed options and give a few numbers. There is no free text "
            "and nothing to phrase carefully.",
            "It runs no model and calls no model API. The answer is arithmetic over a "
            "catalog that the crawler fills in.",
            "It compares four things: the computer you already have, that computer plus "
            "a new graphics card, a whole new machine, and the subscription plans it "
            "knows about.",
        ],
        login_required=False,
        the_flow=[
            "1. You register pages worth reading      -> POST /sources",
            "2. The crawler fetches them              -> POST /crawl",
            "3. It stores the page text               -> GET /pages",
            "4. It reads rows out of that text        -> GET /catalog",
            "5. You ask your question                 -> POST /recommend",
        ],
        endpoints=[
            EndpointSummary(method="GET", path="/",
                            what_it_does="This page. What the project is and how to use it."),
            EndpointSummary(method="GET", path="/options",
                            what_it_does="Every choice you can make, and the number each "
                                         "one turns into."),
            EndpointSummary(method="POST", path="/recommend",
                            what_it_does="Send your answers, get the recommendation.",
                            details_at="GET /recommend"),
            EndpointSummary(method="GET", path="/recommend",
                            what_it_does="What to send to POST /recommend: every field, "
                                         "its choices, and an example body."),
            EndpointSummary(method="GET", path="/catalog",
                            what_it_does="The hardware, models and plans an answer is "
                                         "based on. Add ?region=DE to narrow it."),
            EndpointSummary(method="GET", path="/pages",
                            what_it_does="What the crawler fetched, and how many rows it "
                                         "understood from each page."),
            EndpointSummary(method="GET", path="/sources",
                            what_it_does="The pages the crawler visits."),
            EndpointSummary(method="POST", path="/sources",
                            what_it_does="Register a page for the crawler.",
                            details_at="GET /sources/help"),
            EndpointSummary(method="GET", path="/sources/help",
                            what_it_does="What to send to POST /sources."),
            EndpointSummary(method="POST", path="/crawl",
                            what_it_does="Fetch every source again now.",
                            details_at="GET /crawl"),
            EndpointSummary(method="GET", path="/crawl",
                            what_it_does="What POST /crawl does and what it returns."),
            EndpointSummary(method="GET", path="/health",
                            what_it_does="Is the app up and the database reachable."),
            EndpointSummary(method="GET", path="/docs",
                            what_it_does="Interactive documentation you can click through."),
        ],
        first_time_setup=[
            "createuser llmfit --createdb && createdb llmfit --owner llmfit",
            "export LLMFIT_DATABASE_URL=postgresql+psycopg://llmfit:llmfit@localhost:5432/llmfit",
            "alembic upgrade head            # create the five tables",
            "python -m app.seed              # register the example sources",
            "python -m app.crawler           # fill the catalog from them",
            "uvicorn app.main:app --reload   # start it",
        ],
        a_worked_example={
            "step_1_see_the_choices": "curl localhost:8000/options",
            "step_2_see_what_to_send": "curl localhost:8000/recommend",
            "step_3_ask": (
                "curl -X POST localhost:8000/recommend "
                "-H 'Content-Type: application/json' -d '"
                '{"workloads":["coding"],"usage":"medium","months":24,'
                '"electricity_per_kwh":"0.32",'
                '"existing_computer":{"gpu_vram_gb":"16","system_ram_gb":"32"}}'
                "'"
            ),
            "step_4_check_what_it_used": "curl localhost:8000/catalog",
            "note": "Only workloads is required. Everything else has a default.",
        },
        how_the_answer_is_worked_out=[
            "Memory: the weights, plus a cache that grows with context length and how "
            "many people use it at once, plus an allowance for the runtime. Graphics "
            "memory and system memory are checked separately and never added together.",
            "Money: Decimal throughout. Hardware you already own costs nothing extra. An "
            "annual plan is charged in full when it renews, not spread across a shorter "
            "comparison. Electricity is counted for the whole machine.",
            "Missing facts: a missing price is not zero, and an unknown licence is not "
            "permission. Anything with a fact missing is marked uncertain and listed "
            "apart, so it can never win by default.",
            "Three cases: everything is costed again with lower and higher use and power. "
            "If the winner changes, the answer says so.",
        ],
        what_it_will_not_do=[
            "Add graphics memory and system memory together as if they were one pool.",
            "Treat a missing price or electricity rate as zero.",
            "Spread a twelve-month commitment across a two-month comparison.",
            "Assume a licence allows commercial use because nobody said otherwise.",
            "Tell you a model will be fast. It checks whether it fits, not how quick it is.",
        ],
        known_limitations=[
            "The crawler reads a specific fact-block format, described in docs/guide.md. "
            "Point it at an ordinary vendor page and you get zero rows rather than wrong "
            "ones. Reading a real site means writing a small converter for that site.",
            "By default the crawler reads saved example pages, not the internet. Set "
            "LLMFIT_CRAWLER=crawl4ai and install requirements-crawler.txt to fetch real "
            "URLs.",
            "The example catalog describes invented products at .invalid addresses. It "
            "exists so the app works end to end before you have real sources.",
            "Nothing is stored per user. There are no accounts and no saved history.",
        ],
        where_to_look_next={
            "full_guide": "docs/guide.md",
            "interactive_docs": "/docs",
            "the_decision_itself": "app/engine/recommend.py",
            "the_page_format_the_crawler_reads": "docs/guide.md, section 'Adding your own source'",
        },
    )
