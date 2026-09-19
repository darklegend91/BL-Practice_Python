"""The seeded catalog round-trips through PostgreSQL into the engine.

This is the stage 1 and stage 2 completion check from guide section 14: a
reviewer can publish revisions, and a recommendation reproduces against frozen
catalog versions.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from app.catalog import snapshot_builder
from app.engine.recommend import recommend
from app.schemas.common import ResultStatus, ReviewStatus
from app.schemas.scenario import expand
from app.seed import dataset, load
from tests.conftest import make_scenario
from tests.integration.conftest import requires_postgres

pytestmark = requires_postgres


@pytest.fixture
def seeded(owner_session):
    return load.seed(owner_session, as_of=dataset.SEED_EPOCH)


def test_seeding_publishes_through_the_review_workflow(owner_session, seeded):
    assert seeded.published == 7  # 3 hardware, 2 models, 2 plans
    assert seeded.editor_id != seeded.reviewer_id


def test_the_snapshot_contains_only_published_revisions(owner_session, seeded):
    snapshot = snapshot_builder.build(owner_session, currency="EUR", region="DE")
    assert len(snapshot.hardware) == 3
    assert len(snapshot.models) == 2
    assert len(snapshot.plans) == 2
    for group in (snapshot.hardware, snapshot.models, snapshot.plans):
        for revision in group:
            assert revision.header.review_status is ReviewStatus.PUBLISHED


def test_evidence_is_attached_to_the_values_it_supports(owner_session, seeded):
    snapshot = snapshot_builder.build(owner_session, currency="EUR", region="DE")
    gpu = next(item for item in snapshot.hardware if item.model_name == "Accelerator 16G")
    assert gpu.vram_gb.value == Decimal("16")
    assert gpu.vram_gb.evidence is not None
    assert gpu.vram_gb.evidence.review_status is ReviewStatus.PUBLISHED
    assert "16 GB" in gpu.vram_gb.evidence.excerpt


def test_only_matching_region_and_currency_offers_are_selected(owner_session, seeded):
    snapshot = snapshot_builder.build(owner_session, currency="EUR", region="DE")
    assert snapshot.prices
    assert {price.region for price in snapshot.prices} == {"DE"}

    elsewhere = snapshot_builder.build(owner_session, currency="EUR", region="ES")
    assert elsewhere.prices == []


def test_a_recommendation_runs_against_the_stored_catalog(owner_session, seeded):
    snapshot = snapshot_builder.build(
        owner_session, currency="EUR", region="DE", taken_at=dataset.SEED_EPOCH
    )
    result = recommend(
        expand(make_scenario()), snapshot, as_of=dataset.SEED_EPOCH, created_at=dataset.SEED_EPOCH
    )
    assert result.status is ResultStatus.RECOMMENDED
    assert result.selected is not None
    assert result.catalog_revision_ids


def test_the_same_frozen_snapshot_reproduces_the_same_result(owner_session, seeded):
    snapshot = snapshot_builder.build(
        owner_session, currency="EUR", region="DE", taken_at=dataset.SEED_EPOCH
    )
    scenario = expand(make_scenario())
    first = recommend(scenario, snapshot, as_of=dataset.SEED_EPOCH, created_at=dataset.SEED_EPOCH)
    second = recommend(scenario, snapshot, as_of=dataset.SEED_EPOCH, created_at=dataset.SEED_EPOCH)
    assert first.model_dump() == second.model_dump()


def test_seeding_twice_does_not_duplicate_anything(owner_session):
    first = load.seed(owner_session, as_of=dataset.SEED_EPOCH)
    second = load.seed(owner_session, as_of=dataset.SEED_EPOCH)
    assert first.published == 7
    assert second.published == 0


def test_freshness_reporting_separates_specs_from_prices(owner_session, seeded):
    from app.catalog import freshness

    much_later = dataset.SEED_EPOCH + dt.timedelta(days=15)
    report = freshness.catalog_report(owner_session, now=much_later)
    hardware = [entry for entry in report if entry.kind == "hardware"]
    assert hardware
    for entry in hardware:
        assert entry.prices_stale is True  # 7-day price policy
        assert entry.specs_stale is False  # 30-day specification policy
