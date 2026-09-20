"""The decision itself. No database and no network, so these run instantly."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.engine import reasons
from app.engine.recommend import recommend
from app.schemas import Catalog, Deployment, ResultStatus
from tests.conftest import a_catalog, a_gpu, a_model, a_plan, a_system, ask


def codes(option) -> set[str]:
    return {finding.code for finding in option.findings}


def everything(result) -> list:
    found = list(result.runners_up) + list(result.uncertain) + list(result.ruled_out)
    if result.best:
        found.append(result.best)
    return found


def find(result, fragment: str):
    for option in everything(result):
        if fragment in option.id or fragment in option.label:
            return option
    raise AssertionError(f"no option matching {fragment!r}")


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #


def test_an_unknown_option_is_rejected():
    with pytest.raises(ValidationError):
        ask(workloads=["telepathy"])


def test_an_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        ask(free_money=True)


def test_a_negative_price_is_rejected():
    with pytest.raises(ValidationError):
        ask(electricity_per_kwh=Decimal("-0.10"))


def test_true_is_not_a_number():
    with pytest.raises(ValidationError):
        ask(seats=True)


def test_months_are_bounded():
    with pytest.raises(ValidationError):
        ask(months=0)
    with pytest.raises(ValidationError):
        ask(months=61)


# --------------------------------------------------------------------------- #
# The options become visible numbers
# --------------------------------------------------------------------------- #


def test_the_numbers_behind_the_options_are_reported_back(catalog):
    result = recommend(ask(usage="heavy", context="long_document"), catalog)
    assert result.inputs_used.requests_per_day == 300
    assert result.inputs_used.context_tokens == 65_536


def test_the_same_question_gives_the_same_answer(catalog):
    first = recommend(ask(), catalog, now=None)
    second = recommend(ask(), catalog, now=first.created_at)
    assert first.model_dump(exclude={"created_at"}) == second.model_dump(exclude={"created_at"})


# --------------------------------------------------------------------------- #
# Things that rule an option out
# --------------------------------------------------------------------------- #


def test_offline_only_rules_out_every_subscription(catalog):
    result = recommend(ask(offline_only=True), catalog)
    subscriptions = [
        option for option in everything(result)
        if option.deployment is Deployment.SUBSCRIPTION
    ]
    assert subscriptions
    for option in subscriptions:
        assert option.fits is False
        assert reasons.OFFLINE_ONLY in codes(option)


def test_needing_api_access_rules_out_a_chat_only_plan(catalog):
    result = recommend(ask(access="application_integration"), catalog)
    plan = find(result, "Plan chat")
    assert reasons.NO_API_ACCESS in codes(plan)
    assert plan.fits is False


def test_a_plan_not_sold_in_your_region_is_ruled_out(catalog):
    result = recommend(ask(region="ES"), catalog)
    assert reasons.NOT_IN_YOUR_REGION in codes(find(result, "Plan chat"))


def test_a_model_too_big_for_the_card_is_ruled_out():
    catalog = a_catalog(models=[a_model(slug="big", weights="40", params="70", context=32768)])
    result = recommend(ask(), catalog)
    option = find(result, "existing_computer")
    assert reasons.NOT_ENOUGH_VRAM in codes(option)
    assert option.fits is False


def test_system_memory_is_not_added_to_graphics_memory():
    """32 GB of system RAM plus 16 GB of VRAM still does not host a 40 GB model."""
    catalog = a_catalog(models=[a_model(slug="big", weights="40", params="70", context=32768)])
    result = recommend(ask(), catalog)
    option = find(result, "existing_computer")
    assert option.memory.gpu_total_gb > Decimal("16")
    assert reasons.NOT_ENOUGH_VRAM in codes(option)


def test_more_people_at_once_can_stop_a_model_fitting():
    catalog = a_catalog(models=[a_model()])
    alone = recommend(ask(context="long_document"), catalog)
    crowded = recommend(ask(context="long_document", people_at_once=4), catalog)
    assert find(alone, "existing_computer").fits is True
    assert find(crowded, "existing_computer").fits is False


def test_asking_for_more_context_than_a_plan_supports_rules_it_out(catalog):
    result = recommend(ask(context="long_document"), catalog)
    assert reasons.CONTEXT_TOO_SHORT in codes(find(result, "Plan chat"))


def test_a_plan_whose_daily_limit_is_too_low_is_ruled_out():
    catalog = a_catalog(plans=[a_plan(messages_per_day=10)])
    result = recommend(ask(usage="heavy"), catalog)
    assert reasons.DAILY_LIMIT_TOO_LOW in codes(find(result, "Plan chat"))


def test_a_model_marked_unsuitable_is_ruled_out():
    catalog = a_catalog(models=[a_model(suitable_for=["writing"])])
    result = recommend(ask(workloads=["coding"]), catalog)
    assert reasons.NOT_SUITABLE_FOR_WORKLOAD in codes(find(result, "existing_computer"))


def test_the_upfront_budget_is_respected(catalog):
    result = recommend(ask(budget_upfront=Decimal("100")), catalog)
    assert reasons.OVER_UPFRONT_BUDGET in codes(find(result, "Machine workstation"))


def test_the_setup_time_limit_is_respected(catalog):
    result = recommend(ask(setup_skill="beginner", hours_for_setup=Decimal("1")), catalog)
    assert reasons.TOO_MUCH_SETUP in codes(find(result, "existing_computer"))


def test_commercial_use_rules_out_a_model_that_forbids_it():
    catalog = a_catalog(models=[a_model(commercial_use=False)])
    result = recommend(ask(commercial_use=True), catalog)
    assert reasons.COMMERCIAL_USE_NOT_ALLOWED in codes(find(result, "existing_computer"))


# --------------------------------------------------------------------------- #
# Missing facts are uncertain, never assumed fine
# --------------------------------------------------------------------------- #


def test_an_unknown_licence_is_uncertain_not_permission():
    catalog = a_catalog(models=[a_model(commercial_use=None)])
    result = recommend(ask(commercial_use=True), catalog)
    option = find(result, "existing_computer")
    assert reasons.COMMERCIAL_USE_UNKNOWN in codes(option)
    assert option.uncertain is True


def test_a_plan_with_no_published_limit_is_uncertain():
    catalog = a_catalog(plans=[a_plan(messages_per_day=None)])
    result = recommend(ask(), catalog)
    option = find(result, "Plan chat")
    assert reasons.DAILY_LIMIT_UNKNOWN in codes(option)
    assert option.uncertain is True


def test_nothing_recorded_about_a_workload_is_uncertain():
    catalog = a_catalog(models=[a_model(suitable_for=[])])
    result = recommend(ask(), catalog)
    assert reasons.SUITABILITY_UNKNOWN in codes(find(result, "existing_computer"))


def test_uncertain_options_do_not_compete_with_confirmed_ones():
    catalog = a_catalog(models=[a_model(suitable_for=[])])
    result = recommend(ask(), catalog)
    confirmed = {option.id for option in result.runners_up}
    if result.best:
        confirmed.add(result.best.id)
    assert not (confirmed & {option.id for option in result.uncertain})


def test_a_missing_electricity_price_is_not_free_electricity(catalog):
    result = recommend(ask(electricity_per_kwh=None), catalog)
    option = find(result, "existing_computer")
    assert reasons.NO_ELECTRICITY_PRICE in codes(option)
    assert option.cost.electricity_unknown is True
    assert all(month.electricity is None for month in option.cost.months)


def test_assumed_power_is_declared():
    catalog = a_catalog()
    result = recommend(
        ask(existing_computer={"label": "my computer", "gpu_vram_gb": "16",
                               "system_ram_gb": "32"}),
        catalog,
    )
    assert reasons.POWER_IS_ASSUMED in codes(find(result, "existing_computer"))


def test_a_model_with_no_published_size_gets_no_estimate():
    catalog = a_catalog(models=[a_model(weights_gb=None)])
    result = recommend(ask(), catalog)
    assert find(result, "existing_computer").memory is None


def test_an_approximate_estimate_says_so():
    catalog = a_catalog(models=[a_model(layers=None, kv_heads=None, head_dim=None)])
    result = recommend(ask(), catalog)
    option = find(result, "existing_computer")
    assert option.memory.approximate is True
    assert reasons.MEMORY_ESTIMATE_APPROXIMATE in codes(option)


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #


def test_what_you_already_own_costs_nothing_extra(catalog):
    result = recommend(ask(), catalog)
    assert find(result, "existing_computer").cost.upfront == Decimal("0.0000")


def test_a_whole_machine_is_priced_as_a_whole_machine(catalog):
    result = recommend(ask(), catalog)
    assert find(result, "Machine workstation").cost.upfront == Decimal("2150.0000")


def test_a_monthly_plan_is_charged_every_month():
    catalog = a_catalog(plans=[a_plan(price="20.00", interval="monthly")])
    result = recommend(ask(months=3), catalog)
    plan = find(result, "Plan chat")
    assert [month.subscription for month in plan.cost.months] == [Decimal("20.0000")] * 3


def test_an_annual_plan_is_not_quietly_spread_over_a_short_comparison():
    catalog = a_catalog(plans=[a_plan(slug="annual", price="180.00", interval="annual",
                                      min_seats=3, messages_per_day=500)])
    result = recommend(ask(months=2, seats=3), catalog)
    plan = find(result, "Plan annual")
    assert plan.cost.months[0].subscription == Decimal("540.0000")  # 180 x 3 seats
    assert plan.cost.months[1].subscription == Decimal("0.0000")
    assert plan.cost.total == Decimal("540.0000")


def test_an_annual_plan_renews_in_month_thirteen():
    catalog = a_catalog(plans=[a_plan(slug="annual", price="180.00", interval="annual",
                                      messages_per_day=500)])
    result = recommend(ask(months=14), catalog)
    plan = find(result, "Plan annual")
    charged = [month.month for month in plan.cost.months if month.subscription > 0]
    assert charged == [1, 13]


def test_the_minimum_number_of_seats_is_applied():
    catalog = a_catalog(plans=[a_plan(slug="team", min_seats=3, messages_per_day=500)])
    result = recommend(ask(seats=1, months=1), catalog)
    assert find(result, "Plan team").cost.months[0].subscription == Decimal("60.0000")


def test_electricity_follows_the_stated_formula(catalog):
    result = recommend(ask(months=1), catalog)
    option = find(result, "existing_computer")
    expected = (
        Decimal("30.4375")
        * (Decimal("410") * Decimal("8") + Decimal("70") * Decimal("2"))
        / Decimal(1000)
        * Decimal("0.32")
    ).quantize(Decimal("0.0001"))
    assert option.cost.months[0].electricity == expected


def test_a_priced_item_in_another_currency_cannot_be_bought():
    catalog = a_catalog(hardware=[a_system(currency="USD")])
    result = recommend(ask(), catalog)
    assert reasons.NO_PRICE in codes(find(result, "Machine workstation"))


def test_running_totals_only_go_up(catalog):
    result = recommend(ask(), catalog)
    totals = [month.running_total for month in find(result, "existing_computer").cost.months]
    assert totals == sorted(totals)


# --------------------------------------------------------------------------- #
# Ordering, break-even and assumptions
# --------------------------------------------------------------------------- #


def test_cheapest_first_when_that_is_the_priority(catalog):
    result = recommend(ask(priority="lowest_cost"), catalog)
    ordered = ([result.best] if result.best else []) + result.runners_up
    assert [option.cost.total for option in ordered] == sorted(
        option.cost.total for option in ordered
    )


def test_offline_control_prefers_your_own_machine(catalog):
    result = recommend(ask(priority="offline_control"), catalog)
    assert result.best.deployment is not Deployment.SUBSCRIPTION


def test_least_setup_orders_by_hours(catalog):
    result = recommend(ask(priority="least_setup"), catalog)
    ordered = ([result.best] if result.best else []) + result.runners_up
    assert [option.setup_hours for option in ordered] == sorted(
        option.setup_hours for option in ordered
    )


def test_break_even_is_explained_in_words(catalog):
    result = recommend(ask(), catalog)
    assert result.break_even
    assert all(entry.note for entry in result.break_even)


def test_all_three_assumption_cases_are_reported(catalog):
    result = recommend(ask(), catalog)
    assert [case.case for case in result.cases] == ["low", "base", "high"]


def test_a_changing_winner_is_flagged(catalog):
    result = recommend(ask(months=36, electricity_per_kwh=Decimal("0.115")), catalog)
    winners = {case.winner for case in result.cases}
    assert result.answer_changes_with_assumptions == (len(winners) > 1)
    if result.answer_changes_with_assumptions:
        assert reasons.ANSWER_DEPENDS_ON_ASSUMPTIONS in {n.code for n in result.notes}


# --------------------------------------------------------------------------- #
# Overall outcomes
# --------------------------------------------------------------------------- #


def test_nothing_fits_is_a_real_answer():
    """Offline only, and nothing downloadable to run offline with."""
    catalog = a_catalog(models=[])
    result = recommend(ask(offline_only=True), catalog)
    assert result.status is ResultStatus.NOTHING_FITS
    assert result.best is None
    assert result.ruled_out


def test_only_uncertain_options_is_its_own_answer():
    catalog = a_catalog(
        models=[a_model(suitable_for=[])], plans=[a_plan(suitable_for=[])]
    )
    result = recommend(ask(), catalog)
    assert result.status is ResultStatus.ONLY_UNCERTAIN_OPTIONS
    assert result.best is None
    assert result.uncertain


def test_an_empty_catalog_says_to_run_the_crawler():
    result = recommend(ask(), Catalog())
    assert result.status is ResultStatus.NOTHING_FITS
    assert reasons.CATALOG_EMPTY in {note.code for note in result.notes}


def test_the_assumptions_are_always_stated(catalog):
    result = recommend(ask(), catalog)
    assert any("whole machine" in note for note in result.assumptions)
    assert any("never added together" in note for note in result.assumptions)


def test_every_message_is_a_real_sentence(catalog):
    result = recommend(ask(offline_only=True), catalog)
    for option in everything(result):
        for finding in option.findings:
            assert finding.message
            assert "missing " not in finding.message


def test_each_option_points_at_where_its_data_came_from():
    catalog = a_catalog(
        models=[a_model(source_url="https://example.invalid/models")],
        plans=[a_plan(source_url="https://example.invalid/plans")],
    )
    result = recommend(ask(), catalog)
    assert any(option.sources for option in everything(result))
