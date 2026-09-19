"""Row-level security and tenant isolation (guide sections 8, 11 and 13)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from tests.integration.conftest import as_tenant, requires_postgres

pytestmark = requires_postgres


def _workspace(session, name: str) -> tuple[uuid.UUID, uuid.UUID]:
    user_id, org_id = uuid.uuid4(), uuid.uuid4()
    session.execute(
        text(
            "INSERT INTO users (id, email, display_name, password_hash) "
            "VALUES (:id,:email,'U','x')"
        ),
        {"id": user_id, "email": f"{name}@example.invalid"},
    )
    session.execute(
        text(
            "INSERT INTO organizations (id, name, default_region, default_currency) "
            "VALUES (:id,:name,'DE','EUR')"
        ),
        {"id": org_id, "name": name},
    )
    return org_id, user_id


def _add_scenario(session, org_id: uuid.UUID, user_id: uuid.UUID, label: str) -> uuid.UUID:
    scenario_id = uuid.uuid4()
    session.execute(
        text(
            """
            INSERT INTO scenario_revisions
              (id, organization_id, created_by, label, schema_version, preset_version, inputs)
            VALUES (:id,:org,:user,:label,'v1','p1','{}'::jsonb)
            """
        ),
        {"id": scenario_id, "org": org_id, "user": user_id, "label": label},
    )
    return scenario_id


def test_the_runtime_role_is_not_privileged(runtime_session):
    """RLS would be meaningless if the runtime role could bypass it."""
    row = runtime_session.execute(
        text(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
    ).one()
    assert row == (False, False)


def test_a_workspace_sees_only_its_own_scenarios(owner_engine, runtime_session):
    with owner_engine.begin() as setup:
        first_org, first_user = _workspace(setup, "first")
        second_org, second_user = _workspace(setup, "second")
        as_tenant(setup, first_org)
        _add_scenario(setup, first_org, first_user, "first workspace scenario")
        as_tenant(setup, second_org)
        _add_scenario(setup, second_org, second_user, "second workspace scenario")

    as_tenant(runtime_session, first_org)
    visible = runtime_session.execute(text("SELECT label FROM scenario_revisions")).all()
    assert [row[0] for row in visible] == ["first workspace scenario"]


def test_no_tenant_context_reveals_nothing(owner_engine, runtime_session):
    """The policy fails closed: an unscoped transaction sees no private rows."""
    with owner_engine.begin() as setup:
        org_id, user_id = _workspace(setup, "closed")
        as_tenant(setup, org_id)
        _add_scenario(setup, org_id, user_id, "private")

    as_tenant(runtime_session, None)
    assert runtime_session.execute(text("SELECT count(*) FROM scenario_revisions")).scalar() == 0


def test_writing_into_another_workspace_is_refused(owner_engine, runtime_session):
    with owner_engine.begin() as setup:
        first_org, first_user = _workspace(setup, "writer")
        other_org, _ = _workspace(setup, "victim")

    as_tenant(runtime_session, first_org)
    with pytest.raises(ProgrammingError):
        _add_scenario(runtime_session, other_org, first_user, "smuggled")
        runtime_session.flush()


def test_context_does_not_survive_the_transaction(owner_engine, runtime_session):
    """``SET LOCAL`` context ends with the transaction, so it cannot leak."""
    with owner_engine.begin() as setup:
        org_id, user_id = _workspace(setup, "transient")
        as_tenant(setup, org_id)
        _add_scenario(setup, org_id, user_id, "scoped")

    as_tenant(runtime_session, org_id)
    assert runtime_session.execute(text("SELECT count(*) FROM scenario_revisions")).scalar() == 1
    runtime_session.commit()

    # A fresh transaction on the same connection starts with no context at all.
    assert runtime_session.execute(text("SELECT count(*) FROM scenario_revisions")).scalar() == 0


def test_audit_rows_cannot_be_altered_by_the_runtime_role(runtime_session):
    privileges = runtime_session.execute(
        text(
            """
            SELECT privilege_type FROM information_schema.table_privileges
            WHERE table_name='audit_events' AND grantee = current_user
            """
        )
    ).scalars().all()
    assert set(privileges) == {"SELECT", "INSERT"}
