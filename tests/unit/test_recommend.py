"""End-to-end behaviour of the pure engine (guide sections 6 and 13)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from app.engine.policy import Policy
from app.engine.reasons import Reason
from app.engine.recommend import recommend
from app.schemas.common import Claimed, DeploymentKind, EvidenceQuality, ResultStatus
from app.schemas.scenario import expand
from app.seed.dataset import SEED_EPOCH
from tests.conftest import make_scenario


def run(snapshot, policy=None, **overrides):
    return recommend(
        expand(make_scenario(**overrides)),
        snapshot,
        policy or Policy(),
        as_of=SEED_EPOCH,
        created_at=SEED_EPOCH,
    )


def codes(candidate) -> set[Reason]:
    return {finding.code for finding in candidate.findings}


def all_candidates(result):
    found = list(result.alternatives) + list(result.uncertain) + list(result.ruled_out)
    if result.selected:
        found.append(result.selected)
    return found


def find(result, fragment):
    for candidate in all_candidates(result):
        if fragment in candidate.candidate_id:
            return candidate
    raise AssertionError(f"no candidate matching {fragment!r}")


# --------------------------------------------------------------------------- #
# Determinism and reproducibility
# --------------------------------------------------------------------------- #


def test_same_inputs_produce_the_same_result(snapshot):
    first = run(snapshot)
    second = run(snapshot)
    assert first.model_dump() == second.model_dump()


def test_result_records_every_version_that_influenced_it(snapshot):
    result = run(snapshot)
    assert result.policy_version
    assert result.app_version
    assert result.scenario.preset_version
    assert result.catalog_snapshot_id == snapshot.snapshot_id
    assert set(result.catalog_revision_ids) == set(snapshot.revision_ids())


# --------------------------------------------------------------------------- #
# Hard constraints
# --------------------------------------------------------------------------- #


def test_offline_requirement_rules_out_every_subscription(snapshot):
    result = run(snapshot, constraints={"offline_required": True})
    hosted = [
        candidate
        for candidate in all_candidates(result)
        if candidate.deployment is DeploymentKind.HOSTED_SUBSCRIPTION
    ]
    assert hosted
    for candidate in hosted:
        assert candidate.feasible is False
        assert Reason.OFFLINE_REQUIRED in codes(candidate)


def test_application_integration_rules_out_an_interactive_only_plan(snapshot):
    result = run(snapshot, access_requirement="application_integration")
    chat = find(result, "Assistant Monthly")
    assert Reason.ACCESS_TYPE_UNSUPPORTED in codes(chat)
    assert chat.feasible is False


def test_unavailable_region_rules_a_plan_out(snapshot):
    result = run(snapshot, region="ES")
    chat = find(result, "Assistant Monthly")
    assert Reason.REGION_UNAVAILABLE in codes(chat)


def test_unverified_commercial_use_is_uncertainty_not_permission(snapshot):
    result = run(snapshot, constraints={"commercial_use": True})
    large = find(result, "70B")
    assert Reason.COMMERCIAL_USE_UNVERIFIED in codes(large)
    assert Reason.LICENSE_UNVERIFIED in codes(large)


def test_context_beyond_documented_support_rules_a_candidate_out(snapshot):
    result = run(snapshot, context_requirement="custom", context_tokens=200_000)
    chat = find(result, "Assistant Monthly")
    assert Reason.CONTEXT_UNSUPPORTED in codes(chat)
    assert chat.feasible is False


def test_upfront_budget_is_enforced(snapshot):
    result = run(snapshot, budget={"upfront": {"amount": "100", "currency": "EUR"}})
    workstation = find(result, "Workstation 24G:8B")
    assert Reason.BUDGET_UPFRONT_EXCEEDED in codes(workstation)


def test_setup_allowance_is_enforced(snapshot):
    result = run(snapshot, setup_preference="beginner", setup_allowance_hours=Decimal("1"))
    local = find(result, "existing_local")
    assert Reason.SETUP_EFFORT_EXCEEDED in codes(local)


# --------------------------------------------------------------------------- #
# Uncertainty is never a pass
# --------------------------------------------------------------------------- #


def test_undocumented_plan_limit_is_uncertainty(snapshot):
    result = run(snapshot, access_requirement="application_integration", seats=3)
    team = find(result, "Team Annual")
    assert Reason.SUBSCRIPTION_LIMIT_UNKNOWN in codes(team)
    assert team.uncertain is True


def test_unknown_capability_is_separated_from_a_supported_claim(snapshot):
    result = run(snapshot, workloads=["document_analysis"])
    small = find(result, "existing_local:desk PC:8B")
    assert Reason.CAPABILITY_UNKNOWN in codes(small)
    assert small.uncertain is True


def test_required_capability_evidence_rules_out_unknown_claims(snapshot):
    result = run(
        snapshot, Policy(require_capability_evidence=True), workloads=["document_analysis"]
    )
    small = find(result, "existing_local:desk PC:8B")
    assert small.feasible is False


def test_uncertain_candidates_are_kept_out_of_the_ranked_list(snapshot):
    result = run(snapshot, workloads=["document_analysis"])
    ranked_ids = {candidate.candidate_id for candidate in result.alternatives}
    if result.selected:
        ranked_ids.add(result.selected.candidate_id)
    uncertain_ids = {candidate.candidate_id for candidate in result.uncertain}
    assert not (ranked_ids & uncertain_ids)


def test_stale_price_blocks_a_confident_recommendation(snapshot):
    later = SEED_EPOCH + dt.timedelta(days=40)
    result = recommend(
        expand(make_scenario()), snapshot, Policy(), as_of=later, created_at=later
    )
    chat = find(result, "Assistant Monthly")
    assert Reason.PRICE_STALE in codes(chat)
    assert chat.feasible is False


def test_stale_evidence_may_be_used_deliberately_and_keeps_its_warning(snapshot):
    later = SEED_EPOCH + dt.timedelta(days=40)
    result = recommend(
        expand(make_scenario()),
        snapshot,
        Policy(allow_stale_evidence=True),
        as_of=later,
        created_at=later,
    )
    chat = find(result, "Assistant Monthly")
    assert Reason.PRICE_STALE in codes(chat)
    assert chat.feasible is True
    assert chat.uncertain is True


def test_missing_tariff_is_reported_rather_than_treated_as_free_electricity(snapshot):
    result = run(snapshot, electricity_tariff_per_kwh=None)
    local = find(result, "existing_local:desk PC:8B")
    assert Reason.ELECTRICITY_TARIFF_MISSING in codes(local)
    assert local.cost is not None and local.cost.energy_unknown is True


# --------------------------------------------------------------------------- #
# Memory
# --------------------------------------------------------------------------- #


def test_a_model_too_large_for_the_gpu_is_ruled_out(snapshot):
    result = run(snapshot)
    large = find(result, "existing_local:desk PC:70B")
    assert Reason.VRAM_INSUFFICIENT in codes(large)
    assert large.feasible is False


def test_system_ram_is_not_pooled_with_vram(snapshot):
    """32 GB of system RAM plus 16 GB VRAM still cannot host a 40 GB model."""
    result = run(snapshot)
    large = find(result, "existing_local:desk PC:70B")
    assert large.memory is not None
    assert large.memory.total_gpu_gb > Decimal("16")
    assert Reason.VRAM_INSUFFICIENT in codes(large)


def test_more_concurrent_sessions_can_make_a_fitting_model_stop_fitting(snapshot):
    """One session fits in 16 GB at 32k tokens; four sessions of cache do not."""
    fits = run(snapshot, context_requirement="custom", context_tokens=32_768)
    crowded = run(
        snapshot, context_requirement="custom", context_tokens=32_768, concurrent_sessions=4
    )
    assert find(fits, "existing_local:desk PC:8B").feasible is True
    assert find(crowded, "existing_local:desk PC:8B").feasible is False


# --------------------------------------------------------------------------- #
# Ranking, break-even and sensitivity
# --------------------------------------------------------------------------- #


def test_lowest_cash_cost_priority_selects_the_cheapest_horizon(snapshot):
    result = run(snapshot, priority="lowest_cash_cost")
    assert result.status is ResultStatus.RECOMMENDED
    ranked = ([result.selected] if result.selected else []) + result.alternatives
    totals = [candidate.cost.horizon_total.amount for candidate in ranked]
    assert totals == sorted(totals)


def test_offline_control_priority_prefers_a_local_deployment(snapshot):
    result = run(snapshot, priority="offline_control")
    assert result.selected is not None
    assert result.selected.deployment is not DeploymentKind.HOSTED_SUBSCRIPTION


def test_least_setup_priority_orders_by_effort(snapshot):
    result = run(snapshot, priority="least_setup")
    ranked = ([result.selected] if result.selected else []) + result.alternatives
    hours = [candidate.setup_hours for candidate in ranked]
    assert hours == sorted(hours)


def test_break_even_is_reported_against_alternatives(snapshot):
    result = run(snapshot)
    assert result.break_even
    for entry in result.break_even:
        assert entry.note


def test_the_selected_candidate_leads_from_the_first_month(snapshot):
    """Ranked by cash cost, the selection is already ahead at month one."""
    result = run(snapshot, priority="lowest_cash_cost")
    assert result.break_even
    assert all(entry.crossover_month == 1 for entry in result.break_even)


def test_sensitivity_reports_all_three_assumption_cases(snapshot):
    result = run(snapshot)
    assert [case.case_id for case in result.sensitivity] == ["low", "base", "high"]


def test_a_changing_winner_is_labelled_sensitive(snapshot):
    """Energy assumptions decide between a local machine and a subscription here."""
    result = run(
        snapshot,
        planning_period_months=36,
        electricity_tariff_per_kwh={"amount": "0.115", "currency": "EUR"},
    )
    if result.sensitive_to_assumptions:
        assert Reason.RESULT_SENSITIVE_TO_ASSUMPTIONS in {
            finding.code for finding in result.findings
        }
    leaders = {case.leading_candidate_id for case in result.sensitivity}
    assert result.sensitive_to_assumptions == (len(leaders) > 1)


# --------------------------------------------------------------------------- #
# Domain outcomes
# --------------------------------------------------------------------------- #


def test_no_feasible_option_is_a_domain_outcome(snapshot):
    result = run(
        snapshot,
        constraints={"offline_required": True},
        context_requirement="custom",
        context_tokens=1_000_000,
    )
    assert result.status is ResultStatus.NO_FEASIBLE_OPTION
    assert result.selected is None
    assert result.ruled_out


def test_only_uncertain_candidates_yield_insufficient_evidence(snapshot):
    empty_capability = snapshot.model_copy(
        update={
            "models": [
                model.model_copy(update={"capability_claims": {}}) for model in snapshot.models
            ],
            "plans": [
                plan.model_copy(update={"capability_claims": {}}) for plan in snapshot.plans
            ],
        }
    )
    result = run(empty_capability)
    assert result.status is ResultStatus.INSUFFICIENT_EVIDENCE
    assert result.selected is None
    assert result.uncertain


def test_currency_mismatch_asks_for_input_instead_of_guessing(snapshot):
    priced_in_dollars = snapshot.model_copy(update={"currency": "USD"})
    result = run(priced_in_dollars)
    assert result.status is ResultStatus.NEEDS_INPUT
    assert "currency" in result.missing_fields


def test_assumptions_are_stated_on_every_result(snapshot):
    result = run(snapshot)
    assert any("Whole-system power" in note for note in result.assumptions)
    assert any("never pooled" in note for note in result.assumptions)


def test_every_finding_renders_a_readable_message(snapshot):
    result = run(snapshot, constraints={"offline_required": True})
    for candidate in all_candidates(result):
        for finding in candidate.findings:
            assert finding.message
            assert "missing value for" not in finding.message
