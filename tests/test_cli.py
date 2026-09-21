"""The command line: the same answers as the web API, without a server.

The rendering tests need no database at all. The command tests use the test
database and skip without one, exactly like the API tests.
"""

from __future__ import annotations

import io
from decimal import Decimal

import pytest

from app import render
from app.cli import build_parser, main, request_from_flags
from app.engine.recommend import recommend
from app.schemas import RecommendInput, ResultStatus
from tests.conftest import a_catalog, a_model, a_plan, ask, needs_database


# --------------------------------------------------------------------------- #
# The parser, which needs nothing
# --------------------------------------------------------------------------- #


def test_every_command_is_reachable():
    parser = build_parser()
    for command in ("ask", "options", "catalog", "crawl", "sources", "setup", "serve"):
        assert parser.parse_args([command]).command == command


def test_flags_become_a_valid_request():
    args = build_parser().parse_args([
        "ask", "--workloads", "coding,writing", "--months", "12",
        "--vram", "16", "--ram", "32", "--electricity", "0.30",
        "--region", "US", "--currency", "USD", "--offline",
    ])
    request = request_from_flags(args)
    assert [w.value for w in request.workloads] == ["coding", "writing"]
    assert request.months == 12
    assert request.existing_computer.gpu_vram_gb == Decimal("16")
    assert request.electricity_per_kwh == Decimal("0.30")
    assert request.offline_only is True


def test_leaving_the_computer_out_means_no_computer():
    args = build_parser().parse_args(["ask"])
    assert request_from_flags(args).existing_computer is None


def test_an_unknown_choice_is_refused_by_the_parser():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["ask", "--usage", "enormous"])


def test_a_bad_number_is_refused_with_a_readable_message():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["ask", "--electricity", "cheap"])


def test_the_defaults_match_the_web_api():
    """Both sides must start from the same request, or they would disagree."""
    from_cli = request_from_flags(build_parser().parse_args(["ask"]))
    from_api = RecommendInput(workloads=["coding"])
    assert from_cli.model_dump() == from_api.model_dump()


# --------------------------------------------------------------------------- #
# Rendering, which also needs nothing
# --------------------------------------------------------------------------- #


def test_a_recommendation_reads_as_a_report():
    answer = recommend(ask(), a_catalog())
    text = render.result(answer)
    assert "RECOMMENDATION" in text
    assert answer.best.label in text
    assert "Assumptions:" in text
    assert "Under different assumptions:" in text


def test_ruled_out_options_show_the_reason():
    answer = recommend(ask(offline_only=True), a_catalog())
    text = render.result(answer)
    assert "Ruled out" in text
    assert "offline" in text.lower()


def test_long_lists_are_trimmed_unless_you_ask_for_all():
    """Twelve models far too big for the card, so there is a long list to trim."""
    big = a_catalog(models=[
        a_model(slug=f"m{n}", weights="40", params="70", context=32768) for n in range(12)
    ])
    answer = recommend(ask(), big)
    short = render.result(answer)
    full = render.result(answer, show_all=True)
    assert "use --all to see them" in short
    assert len(full) > len(short)


def test_an_uncertain_answer_says_so_rather_than_picking():
    answer = recommend(ask(), a_catalog(models=[a_model(suitable_for=[])],
                                        plans=[a_plan(suitable_for=[])]))
    assert answer.status is ResultStatus.ONLY_UNCERTAIN_OPTIONS
    text = render.result(answer)
    assert "NO CONFIRMED ANSWER" in text


def test_nothing_fitting_is_stated_plainly():
    answer = recommend(ask(offline_only=True), a_catalog(models=[]))
    assert "NOTHING FITS" in render.result(answer)


def test_unknown_money_is_written_as_unknown():
    assert render.money(None, "EUR") == "unknown"
    assert render.money(Decimal("12.3456"), "EUR") == "12.35 EUR"


def test_an_empty_catalog_tells_you_what_to_run():
    from app.schemas import Catalog

    assert "python -m app crawl" in render.catalog(Catalog())


def test_a_crawl_report_shows_failures_and_notes():
    text = render.crawl_report({
        "sources_visited": 2, "catalog_rows_written": 3, "failures": 1,
        "details": [
            {"url": "https://a.example", "adapter": "factblock", "changed": True,
             "rows_found": 3, "notes": ["2 rows left out"]},
            {"url": "https://b.example", "error": "no saved page"},
        ],
    })
    assert "FAILED" in text and "no saved page" in text
    assert "2 rows left out" in text


# --------------------------------------------------------------------------- #
# Running the commands for real
# --------------------------------------------------------------------------- #


pytestmark_db = needs_database


@needs_database
def test_ask_prints_a_report(cli_database, capsys):
    assert main(["ask", "--workloads", "coding", "--vram", "16", "--ram", "32"]) == 0
    printed = capsys.readouterr().out
    assert "Based on about" in printed


@needs_database
def test_ask_can_print_raw_output(cli_database, capsys):
    import json

    assert main(["ask", "--json"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert "status" in body and "inputs_used" in body


@needs_database
def test_catalog_lists_what_is_stored(cli_database, capsys):
    assert main(["catalog"]) == 0
    printed = capsys.readouterr().out
    assert "Hardware" in printed and "Models" in printed


@needs_database
def test_sources_can_be_listed_and_added(cli_database, capsys):
    assert main(["sources", "--add", "https://vendor.example.com/prices"]) == 0
    assert main(["sources"]) == 0
    assert "vendor.example.com" in capsys.readouterr().out


@needs_database
def test_an_unsafe_source_is_refused(cli_database, capsys):
    assert main(["sources", "--add", "http://127.0.0.1/admin"]) == 1
    assert "Refused" in capsys.readouterr().err


@needs_database
def test_options_prints_what_each_answer_means(cli_database, capsys):
    assert main(["options"]) == 0
    printed = capsys.readouterr().out
    assert "requests_per_day" in printed
    assert "coding" in printed


# --------------------------------------------------------------------------- #
# The menu and the interactive questions
# --------------------------------------------------------------------------- #


def _answers(monkeypatch, replies: list[str]) -> None:
    supply = iter(replies)
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(supply, ""))


def test_the_menu_offers_both_ways_to_run_it(capsys, monkeypatch):
    _answers(monkeypatch, ["q"])
    assert main([]) == 0
    printed = capsys.readouterr().out
    assert "Answer some questions here" in printed
    assert "Start the web API" in printed


def test_the_menu_understands_quitting(monkeypatch):
    _answers(monkeypatch, ["quit"])
    assert main([]) == 0


def test_the_menu_rejects_nonsense_without_crashing(capsys, monkeypatch):
    _answers(monkeypatch, ["banana"])
    assert main([]) == 1
    assert "Did not recognise" in capsys.readouterr().out


def test_the_questions_can_be_answered_by_number(monkeypatch):
    from app.cli import ask_interactively

    _answers(monkeypatch, [
        "1",      # workloads -> coding
        "1",      # access -> interactive use
        "2",      # usage -> medium
        "1",      # context -> short conversation
        "12",     # months
        "1",      # priority -> lowest cost
        "y",      # have a computer
        "16",     # vram
        "32",     # ram
        "2",      # running time -> workday
        "0.30",   # electricity
        "2",      # setup skill -> comfortable
        "n",      # offline
        "n",      # commercial
    ])
    request = ask_interactively()
    assert [w.value for w in request.workloads] == ["coding"]
    assert request.months == 12
    assert request.existing_computer.gpu_vram_gb == Decimal("16")
    assert request.electricity_per_kwh == Decimal("0.30")
    assert request.offline_only is False


def test_pressing_enter_takes_the_default(monkeypatch):
    from app.cli import ask_interactively

    _answers(monkeypatch, [""] * 20)
    request = ask_interactively()
    assert [w.value for w in request.workloads] == ["coding"]
    assert request.months == 24
    assert request.usage.value == "medium"


def test_several_workloads_can_be_given_at_once(monkeypatch):
    from app.cli import ask_interactively

    _answers(monkeypatch, ["1,3"] + [""] * 20)
    request = ask_interactively()
    assert [w.value for w in request.workloads] == ["coding", "writing"]


# --------------------------------------------------------------------------- #
# An incomplete total must never read as a settled one
# --------------------------------------------------------------------------- #


def test_an_unknown_running_cost_is_not_presented_as_a_total():
    """Without an electricity price the total is a floor, and 0.00 reads as free."""
    answer = recommend(ask(electricity_per_kwh=None), a_catalog())
    local = next(
        o for o in answer.uncertain + answer.runners_up + ([answer.best] if answer.best else [])
        if o.cost is not None and o.cost.electricity_unknown
    )
    line = render.total_of(local.cost)
    assert "running cost" in line
    assert line != render.money(local.cost.total, local.cost.currency)


def test_a_complete_total_is_shown_plainly():
    answer = recommend(ask(), a_catalog())
    complete = next(
        o for o in [answer.best] + answer.runners_up
        if o.cost is not None and not o.cost.electricity_unknown
    )
    assert "running cost" not in render.total_of(complete.cost)


def test_the_cost_says_whether_it_is_complete():
    answer = recommend(ask(electricity_per_kwh=None), a_catalog())
    local = next(o for o in answer.uncertain if o.cost and o.cost.electricity_unknown)
    assert local.cost.total_is_complete is False


def test_every_incomplete_total_in_a_report_carries_the_caveat():
    """Check the options themselves, not a substring of the rendered line.

    An earlier version of this test looked for "0.00 EUR" before "up front",
    which also matches "480.00 EUR".
    """
    answer = recommend(ask(electricity_per_kwh=None), a_catalog())
    shown = ([answer.best] if answer.best else []) + answer.runners_up + answer.uncertain
    incomplete = [o for o in shown if o.cost is not None and o.cost.electricity_unknown]
    assert incomplete, "this scenario should produce at least one incomplete total"
    for option in incomplete:
        assert "running cost" in render.total_of(option.cost)
    complete = [o for o in shown if o.cost is not None and not o.cost.electricity_unknown]
    for option in complete:
        assert "running cost" not in render.total_of(option.cost)


# --------------------------------------------------------------------------- #
# The assumption cases must describe something
# --------------------------------------------------------------------------- #


def test_the_cases_cover_options_that_are_merely_uncertain():
    """With nothing confirmed, the three cases used to report 'nothing'."""
    answer = recommend(ask(), a_catalog(models=[a_model(suitable_for=[])],
                                        plans=[a_plan(suitable_for=[])]))
    assert answer.status is ResultStatus.ONLY_UNCERTAIN_OPTIONS
    assert all(case.winner is not None for case in answer.cases)


def test_the_cases_name_the_option_rather_than_its_identifier():
    answer = recommend(ask(), a_catalog(models=[a_model(suitable_for=[])],
                                        plans=[a_plan(suitable_for=[])]))
    text = render.result(answer)
    winner = next(o for o in answer.uncertain if o.id == answer.cases[0].winner)
    assert winner.label[:20] in text


# --------------------------------------------------------------------------- #
# Findings name the thing they are about
# --------------------------------------------------------------------------- #


def test_a_models_context_limit_is_reported_against_the_model():
    """The limit belongs to the model, not to the model-plus-machine pairing."""
    catalog = a_catalog(models=[a_model(slug="small", context=4096)])
    answer = recommend(ask(context="long_document"), catalog)
    option = next(o for o in answer.ruled_out if "small" in o.id)
    message = next(f.message for f in option.findings if f.code == "CONTEXT_TOO_SHORT")
    assert message.startswith("Model small")
    assert " on my computer handles" not in message


# --------------------------------------------------------------------------- #
# Repeated caveats are said once
# --------------------------------------------------------------------------- #


def test_caveats_shared_by_most_options_are_stated_once_with_a_count():
    catalog = a_catalog(models=[
        a_model(slug=f"m{n}", suitable_for=[], layers=None, kv_heads=None, head_dim=None)
        for n in range(6)
    ])
    answer = recommend(ask(electricity_per_kwh=None), catalog)
    text = render.result(answer)
    assert "What most of them have in common:" in text
    assert "of " in text  # the "(N of M)" coverage
    # The hoisted caveat should not also appear on every row.
    assert text.count("layer sizes are not published") <= 2


def test_a_caveat_on_only_some_options_stays_on_its_own_rows():
    from app.render import _common_codes

    answer = recommend(ask(), a_catalog())
    rare = _common_codes(answer.uncertain[:1])
    assert rare == []  # too few options to summarise
