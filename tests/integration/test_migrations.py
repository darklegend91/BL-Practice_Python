"""Migrations, constraints and the immutability guarantees (guide section 13)."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.integration.conftest import as_tenant, requires_postgres

pytestmark = requires_postgres


def test_every_expected_table_exists(owner_session):
    found = {
        row[0]
        for row in owner_session.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        )
    }
    for expected in (
        "users", "sessions", "organizations", "memberships", "sources", "crawl_jobs",
        "source_snapshots", "catalog_items", "catalog_revisions", "evidence_claims",
        "price_observations", "plan_model_access", "benchmark_observations", "reviews",
        "inventory_items", "scenario_revisions", "recommendation_runs",
        "recommendation_evidence", "audit_events", "idempotency_keys",
    ):
        assert expected in found


def test_timestamps_are_timezone_aware(owner_session):
    naive = owner_session.execute(
        text(
            """
            SELECT table_name, column_name FROM information_schema.columns
            WHERE table_schema='public' AND data_type='timestamp without time zone'
            """
        )
    ).all()
    assert naive == []


def test_money_columns_use_exact_numeric(owner_session):
    rows = owner_session.execute(
        text(
            """
            SELECT numeric_precision, numeric_scale FROM information_schema.columns
            WHERE table_schema='public' AND table_name='price_observations'
              AND column_name='amount'
            """
        )
    ).one()
    assert rows == (18, 4)


def test_negative_amounts_are_refused(owner_session):
    owner_session.execute(
        text(
            """
            INSERT INTO catalog_items (id, kind, slug) VALUES (:id,'hardware','x')
            """
        ),
        {"id": (item_id := uuid.uuid4())},
    )
    owner_session.execute(
        text(
            """
            INSERT INTO users (id, email, display_name, password_hash)
            VALUES (:id,'a@example.invalid','A','x')
            """
        ),
        {"id": (user_id := uuid.uuid4())},
    )
    owner_session.execute(
        text(
            """
            INSERT INTO catalog_revisions
              (id, item_id, schema_version, attributes, review_status, author_id)
            VALUES (:id,:item,'v1','{}'::jsonb,'draft',:author)
            """
        ),
        {"id": (revision_id := uuid.uuid4()), "item": item_id, "author": user_id},
    )
    with pytest.raises(IntegrityError):
        owner_session.execute(
            text(
                """
                INSERT INTO price_observations
                  (revision_id, seller, region, currency, amount, tax_included, observed_at)
                VALUES (:revision,'S','DE','EUR',-1,true,now())
                """
            ),
            {"revision": revision_id},
        )


def test_a_referenced_revision_cannot_be_deleted(owner_session):
    """Evidence behind a saved decision is superseded, never removed."""
    ids = _minimal_published_revision(owner_session)
    as_tenant(owner_session, ids["org"])
    owner_session.execute(
        text(
            """
            INSERT INTO scenario_revisions
              (id, organization_id, created_by, label, schema_version, preset_version, inputs)
            VALUES (:id,:org,:user,'s','v1','p1','{}'::jsonb)
            """
        ),
        {"id": (scenario_id := uuid.uuid4()), "org": ids["org"], "user": ids["user"]},
    )
    owner_session.execute(
        text(
            """
            INSERT INTO recommendation_runs
              (id, organization_id, scenario_revision_id, created_by, policy_version,
               app_version, catalog_snapshot_id, inputs, outputs)
            VALUES (:id,:org,:scenario,:user,'p','a',:snap,'{}'::jsonb,'{}'::jsonb)
            """
        ),
        {
            "id": (run_id := uuid.uuid4()),
            "org": ids["org"],
            "scenario": scenario_id,
            "user": ids["user"],
            "snap": uuid.uuid4(),
        },
    )
    owner_session.execute(
        text(
            """
            INSERT INTO recommendation_evidence
              (organization_id, run_id, revision_id)
            VALUES (:org,:run,:revision)
            """
        ),
        {"org": ids["org"], "run": run_id, "revision": ids["revision"]},
    )
    owner_session.flush()

    with pytest.raises(DBAPIError) as failure:
        owner_session.execute(
            text("DELETE FROM catalog_revisions WHERE id = :id"), {"id": ids["revision"]}
        )
    assert "supersede it instead" in str(failure.value)


def test_a_saved_result_is_immutable(owner_session):
    ids = _minimal_published_revision(owner_session)
    as_tenant(owner_session, ids["org"])
    owner_session.execute(
        text(
            """
            INSERT INTO scenario_revisions
              (id, organization_id, created_by, label, schema_version, preset_version, inputs)
            VALUES (:id,:org,:user,'s','v1','p1','{}'::jsonb)
            """
        ),
        {"id": (scenario_id := uuid.uuid4()), "org": ids["org"], "user": ids["user"]},
    )
    owner_session.execute(
        text(
            """
            INSERT INTO recommendation_runs
              (id, organization_id, scenario_revision_id, created_by, policy_version,
               app_version, catalog_snapshot_id, inputs, outputs)
            VALUES (:id,:org,:scenario,:user,'p','a',:snap,'{}'::jsonb,
                    '{"status":"recommended"}'::jsonb)
            """
        ),
        {
            "id": (run_id := uuid.uuid4()),
            "org": ids["org"],
            "scenario": scenario_id,
            "user": ids["user"],
            "snap": uuid.uuid4(),
        },
    )
    owner_session.flush()

    with pytest.raises(DBAPIError) as failure:
        owner_session.execute(
            text(
                "UPDATE recommendation_runs SET outputs = '{\"status\":\"changed\"}'::jsonb "
                "WHERE id = :id"
            ),
            {"id": run_id},
        )
    assert "immutable" in str(failure.value)


def test_a_run_cannot_reference_another_workspaces_scenario(owner_session):
    """The compound foreign key refuses a cross-organization relationship."""
    first = _minimal_published_revision(owner_session)
    other_org = uuid.uuid4()
    as_tenant(owner_session, other_org)
    owner_session.execute(
        text(
            "INSERT INTO organizations (id, name, default_region, default_currency) "
            "VALUES (:id,'Other','DE','EUR')"
        ),
        {"id": other_org},
    )
    owner_session.execute(
        text(
            """
            INSERT INTO scenario_revisions
              (id, organization_id, created_by, label, schema_version, preset_version, inputs)
            VALUES (:id,:org,:user,'s','v1','p1','{}'::jsonb)
            """
        ),
        {"id": (scenario_id := uuid.uuid4()), "org": other_org, "user": first["user"]},
    )
    owner_session.flush()

    # Switch to the first workspace: its own rows pass row security, so the
    # compound foreign key is what refuses the cross-organization reference.
    as_tenant(owner_session, first["org"])
    with pytest.raises(IntegrityError):
        owner_session.execute(
            text(
                """
                INSERT INTO recommendation_runs
                  (organization_id, scenario_revision_id, created_by, policy_version,
                   app_version, catalog_snapshot_id, inputs, outputs)
                VALUES (:org,:scenario,:user,'p','a',:snap,'{}'::jsonb,'{}'::jsonb)
                """
            ),
            {
                "org": first["org"],  # different workspace from the scenario
                "scenario": scenario_id,
                "user": first["user"],
                "snap": uuid.uuid4(),
            },
        )


def _minimal_published_revision(session) -> dict:
    user_id, org_id = uuid.uuid4(), uuid.uuid4()
    item_id, revision_id = uuid.uuid4(), uuid.uuid4()
    session.execute(
        text(
            "INSERT INTO users (id, email, display_name, password_hash) "
            "VALUES (:id,:email,'A','x')"
        ),
        {"id": user_id, "email": f"{user_id}@example.invalid"},
    )
    session.execute(
        text(
            "INSERT INTO organizations (id, name, default_region, default_currency) "
            "VALUES (:id,:name,'DE','EUR')"
        ),
        {"id": org_id, "name": f"Org {org_id}"},
    )
    session.execute(
        text("INSERT INTO catalog_items (id, kind, slug) VALUES (:id,'hardware',:slug)"),
        {"id": item_id, "slug": str(item_id)},
    )
    session.execute(
        text(
            """
            INSERT INTO catalog_revisions
              (id, item_id, schema_version, attributes, review_status, author_id, published_at)
            VALUES (:id,:item,'v1','{}'::jsonb,'published',:author, now())
            """
        ),
        {"id": revision_id, "item": item_id, "author": user_id},
    )
    session.flush()
    return {"user": user_id, "org": org_id, "item": item_id, "revision": revision_id}
