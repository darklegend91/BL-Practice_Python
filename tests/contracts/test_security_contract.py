"""Cross-workspace access, unsafe destinations and export safety over HTTP.

Guide section 13: security tests include cross-organization object access,
unsafe destinations and redirects, malicious Markdown and exports.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.security.authz import PlatformRole, WorkspaceRole
from app.seed import load
from app.services.auth import create_user
from tests.contracts.conftest import headers, log_in, scenario_body
from tests.integration.conftest import requires_postgres

pytestmark = requires_postgres


@pytest.fixture
def rival_workspace(owner_engine, seeded):
    """A second workspace with its own analyst, used to attempt cross access."""
    factory = sessionmaker(bind=owner_engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        user = create_user(
            session,
            email="rival@example.invalid",
            display_name="Rival Analyst",
            password=load.DEFAULT_PASSWORD,
            platform_role=PlatformRole.NONE,
        )
        organization_id = uuid.uuid4()
        session.execute(
            text(
                "INSERT INTO organizations (id, name, default_region, default_currency) "
                "VALUES (:id,'Rival Workspace','DE','EUR')"
            ),
            {"id": organization_id},
        )
        session.execute(
            text("SELECT set_config('app.organization_id', :value, true)"),
            {"value": str(organization_id)},
        )
        session.execute(
            text(
                "INSERT INTO memberships (organization_id, user_id, role) "
                "VALUES (:org,:user,:role)"
            ),
            {"org": organization_id, "user": user.id, "role": WorkspaceRole.ANALYST.value},
        )
        session.commit()
        return {"organization_id": organization_id, "email": "rival@example.invalid"}
    finally:
        session.close()


def _saved_run(client, seeded) -> tuple[str, str, dict]:
    token = log_in(client, load.ANALYST_EMAIL)
    auth = headers(token, seeded.organization_id)
    scenario_id = client.post(
        "/v1/scenarios", headers=auth, json={"label": "private", "scenario": scenario_body()}
    ).json()["id"]
    run_id = client.post(
        "/v1/recommendations", headers=auth, json={"scenario_id": scenario_id}
    ).json()["id"]
    return scenario_id, run_id, auth


# --------------------------------------------------------------------------- #
# Cross-workspace access
# --------------------------------------------------------------------------- #


def test_another_workspace_cannot_read_a_saved_scenario(client, seeded, rival_workspace):
    scenario_id, _, _ = _saved_run(client, seeded)
    rival_token = log_in(client, rival_workspace["email"])
    rival_auth = headers(rival_token, rival_workspace["organization_id"])

    response = client.get(f"/v1/scenarios/{scenario_id}", headers=rival_auth)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_another_workspace_cannot_read_a_saved_result(client, seeded, rival_workspace):
    _, run_id, _ = _saved_run(client, seeded)
    rival_token = log_in(client, rival_workspace["email"])
    rival_auth = headers(rival_token, rival_workspace["organization_id"])
    assert client.get(f"/v1/recommendations/{run_id}", headers=rival_auth).status_code == 404


def test_another_workspace_cannot_export_a_saved_result(client, seeded, rival_workspace):
    _, run_id, _ = _saved_run(client, seeded)
    rival_token = log_in(client, rival_workspace["email"])
    rival_auth = headers(rival_token, rival_workspace["organization_id"])
    response = client.get(f"/v1/recommendations/{run_id}/export", headers=rival_auth)
    assert response.status_code == 404


def test_a_known_and_an_unknown_identifier_look_the_same(client, seeded, rival_workspace):
    """Existence must not leak through a different status or message."""
    _, run_id, _ = _saved_run(client, seeded)
    rival_token = log_in(client, rival_workspace["email"])
    rival_auth = headers(rival_token, rival_workspace["organization_id"])

    real = client.get(f"/v1/recommendations/{run_id}", headers=rival_auth)
    invented = client.get(f"/v1/recommendations/{uuid.uuid4()}", headers=rival_auth)
    assert real.status_code == invented.status_code == 404
    assert real.json()["code"] == invented.json()["code"]


def test_a_workspace_lists_only_its_own_scenarios(client, seeded, rival_workspace):
    _saved_run(client, seeded)
    rival_token = log_in(client, rival_workspace["email"])
    rival_auth = headers(rival_token, rival_workspace["organization_id"])
    assert client.get("/v1/scenarios", headers=rival_auth).json()["items"] == []


def test_naming_a_workspace_you_do_not_belong_to_grants_nothing(client, seeded, rival_workspace):
    rival_token = log_in(client, rival_workspace["email"])
    forged = headers(rival_token, seeded.organization_id)
    assert client.get("/v1/scenarios", headers=forged).status_code == 403


# --------------------------------------------------------------------------- #
# Unsafe destinations
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:5432/",
        "http://10.1.2.3/internal",
        "file:///etc/passwd",
    ],
)
def test_an_unsafe_source_cannot_be_registered(client, seeded, url):
    token = log_in(client, load.REVIEWER_EMAIL)
    response = client.post(
        "/v1/admin/sources",
        headers=headers(token, seeded.organization_id),
        json={
            "url": url,
            "allowed_hosts": [],
            "category": "manufacturer",
            "owner": "ops",
            "refresh_interval_seconds": 86400,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "destination_refused"


# --------------------------------------------------------------------------- #
# Export safety
# --------------------------------------------------------------------------- #


def test_csv_export_neutralises_formula_prefixes(client, seeded, owner_engine):
    """A hostile catalog label must not become a live spreadsheet formula."""
    factory = sessionmaker(bind=owner_engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        session.execute(
            text(
                """
                UPDATE catalog_revisions
                SET attributes = jsonb_set(attributes, '{plan_name}',
                                           '"=HYPERLINK(\\"http://attacker.example.com\\")"')
                WHERE attributes ? 'plan_name'
                """
            )
        )
        session.commit()
    finally:
        session.close()

    _, run_id, auth = _saved_run(client, seeded)
    body = client.get(f"/v1/recommendations/{run_id}/export?format=csv", headers=auth).text
    assert "=HYPERLINK" in body  # the value is preserved
    for line in body.splitlines()[1:]:
        for cell in line.split(","):
            assert not cell.startswith("=")


def test_an_oversized_request_is_refused(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    response = client.post(
        "/v1/scenarios",
        headers=headers(token, seeded.organization_id)
        | {"Content-Length": str(50 * 1024 * 1024)},
        content=b"{}",
    )
    assert response.status_code in (413, 422)


def test_repeated_failed_logins_are_rate_limited(client):
    statuses = [
        client.post(
            "/v1/auth/login",
            json={"email": load.ANALYST_EMAIL, "password": "wrong"},
        ).status_code
        for _ in range(15)
    ]
    assert 429 in statuses
