"""Request validation, authorization, pagination, idempotency and typed errors.

Guide section 13: contract tests check the shape of the API, not the engine.
"""

from __future__ import annotations

import uuid

import pytest

from app.seed import load
from tests.contracts.conftest import headers, log_in, scenario_body
from tests.integration.conftest import requires_postgres

pytestmark = requires_postgres


# --------------------------------------------------------------------------- #
# Health and documentation
# --------------------------------------------------------------------------- #


def test_liveness_and_readiness_are_separate(client):
    assert client.get("/health/live").json()["status"] == "live"
    assert client.get("/health/ready").json()["status"] == "ready"


def test_openapi_documents_every_versioned_route(client):
    paths = client.get("/openapi.json").json()["paths"]
    for expected in (
        "/v1/auth/login",
        "/v1/questionnaire",
        "/v1/catalog/hardware",
        "/v1/catalog/models",
        "/v1/catalog/plans",
        "/v1/scenarios",
        "/v1/recommendations",
        "/v1/admin/sources",
        "/v1/admin/crawl-jobs",
    ):
        assert expected in paths


# --------------------------------------------------------------------------- #
# Authentication and authorization
# --------------------------------------------------------------------------- #


def test_an_unauthenticated_request_is_401_with_a_structured_body(client):
    response = client.get("/v1/questionnaire")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "not_authenticated"
    assert body["correlation_id"]


def test_wrong_credentials_do_not_reveal_whether_the_account_exists(client):
    known = client.post(
        "/v1/auth/login",
        json={"email": load.ANALYST_EMAIL, "password": "wrong-password-entirely"},
    )
    unknown = client.post(
        "/v1/auth/login",
        json={"email": "nobody@example.invalid", "password": "wrong-password-entirely"},
    )
    assert known.status_code == unknown.status_code == 401
    assert known.json()["message"] == unknown.json()["message"]


def test_logout_revokes_the_session(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    auth = headers(token, seeded.organization_id)
    assert client.get("/v1/questionnaire", headers=auth).status_code == 200
    assert client.post("/v1/auth/logout", headers=auth).status_code == 204
    assert client.get("/v1/questionnaire", headers=auth).status_code == 401


def test_a_request_naming_no_workspace_cannot_read_workspace_data(client, seeded):
    """Workspace context is required; it is never inferred from the account."""
    token = log_in(client, load.ANALYST_EMAIL)
    assert client.get("/v1/questionnaire", headers=headers(token)).status_code == 403


def test_an_analyst_cannot_register_a_source(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    response = client.post(
        "/v1/admin/sources",
        headers=headers(token, seeded.organization_id),
        json={
            "url": "https://vendor.example.invalid/page",
            "allowed_hosts": ["vendor.example.invalid"],
            "category": "manufacturer",
            "owner": "ops",
            "refresh_interval_seconds": 86400,
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_a_workspace_owner_is_not_a_catalog_publisher(client, seeded):
    """Workspace roles and platform catalog roles are deliberately separate."""
    token = log_in(client, load.ANALYST_EMAIL)
    response = client.post(
        "/v1/admin/catalog/drafts",
        headers=headers(token, seeded.organization_id),
        json={
            "kind": "hardware",
            "slug": "smuggled",
            "schema_version": "catalog-test",
            "attributes": {},
        },
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def test_invalid_input_returns_422_with_field_errors(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    response = client.post(
        "/v1/scenarios",
        headers=headers(token, seeded.organization_id),
        json={"label": "bad", "scenario": scenario_body() | {"planning_period_months": 0}},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_request"
    assert any("planning_period_months" in error["field"] for error in body["field_errors"])


def test_an_unknown_field_is_rejected(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    response = client.post(
        "/v1/scenarios",
        headers=headers(token, seeded.organization_id),
        json={"label": "bad", "scenario": scenario_body() | {"free_upgrade": True}},
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Catalog and questionnaire
# --------------------------------------------------------------------------- #


def test_the_questionnaire_returns_options_with_stable_identifiers(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    body = client.get(
        "/v1/questionnaire", headers=headers(token, seeded.organization_id)
    ).json()
    assert body["preset_version"]
    assert {option["id"] for option in body["workloads"]} == {
        "coding", "studying", "writing", "document_analysis"
    }
    medium = next(level for level in body["usage_levels"] if level["id"] == "medium")
    assert medium["requests_per_day"] == 80  # presets are shown before use


def test_catalog_listing_is_paginated_with_a_maximum_page_size(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    page = client.get(
        "/v1/catalog/hardware?limit=2",
        headers=headers(token, seeded.organization_id),
    ).json()
    assert page["limit"] == 2
    assert len(page["items"]) == 2

    capped = client.get(
        "/v1/catalog/hardware?limit=100000",
        headers=headers(token, seeded.organization_id),
    ).json()
    assert capped["limit"] <= 100


def test_catalog_ordering_is_stable_across_pages(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    auth = headers(token, seeded.organization_id)
    first = client.get("/v1/catalog/hardware?limit=1&offset=0", headers=auth).json()
    second = client.get("/v1/catalog/hardware?limit=1&offset=1", headers=auth).json()
    assert first["items"][0]["slug"] != second["items"][0]["slug"]


def test_catalog_history_exposes_the_supporting_evidence(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    auth = headers(token, seeded.organization_id)
    item_id = client.get("/v1/catalog/hardware", headers=auth).json()["items"][0]["item_id"]
    history = client.get(f"/v1/catalog/items/{item_id}/history", headers=auth).json()
    assert history
    assert history[0]["claims"]


# --------------------------------------------------------------------------- #
# Scenarios and recommendations
# --------------------------------------------------------------------------- #


def test_saving_a_scenario_returns_201_and_the_stored_input(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    response = client.post(
        "/v1/scenarios",
        headers=headers(token, seeded.organization_id),
        json={"label": "baseline", "scenario": scenario_body()},
    )
    assert response.status_code == 201
    assert response.json()["scenario"]["region"] == "DE"


def test_a_recommendation_records_its_versions(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    auth = headers(token, seeded.organization_id)
    scenario_id = client.post(
        "/v1/scenarios", headers=auth, json={"label": "b", "scenario": scenario_body()}
    ).json()["id"]

    response = client.post(
        "/v1/recommendations", headers=auth, json={"scenario_id": scenario_id}
    )
    assert response.status_code == 201
    result = response.json()["result"]
    assert result["policy_version"]
    assert result["app_version"]
    assert result["scenario"]["preset_version"]
    assert result["catalog_revision_ids"]


def test_no_suitable_candidate_is_a_domain_outcome_not_a_server_error(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    auth = headers(token, seeded.organization_id)
    impossible = scenario_body(
        constraints={"offline_required": True},
        context_requirement="custom",
        context_tokens=1_000_000,
    )
    scenario_id = client.post(
        "/v1/scenarios", headers=auth, json={"label": "impossible", "scenario": impossible}
    ).json()["id"]

    response = client.post(
        "/v1/recommendations", headers=auth, json={"scenario_id": scenario_id}
    )
    assert response.status_code == 201
    assert response.json()["result"]["status"] == "no_feasible_option"


def test_a_stored_result_is_returned_unchanged(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    auth = headers(token, seeded.organization_id)
    scenario_id = client.post(
        "/v1/scenarios", headers=auth, json={"label": "b", "scenario": scenario_body()}
    ).json()["id"]
    created = client.post(
        "/v1/recommendations", headers=auth, json={"scenario_id": scenario_id}
    ).json()

    fetched = client.get(f"/v1/recommendations/{created['id']}", headers=auth).json()
    assert fetched["result"] == created["result"]


def test_an_idempotency_key_replays_the_saved_outcome(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    auth = headers(token, seeded.organization_id)
    scenario_id = client.post(
        "/v1/scenarios", headers=auth, json={"label": "b", "scenario": scenario_body()}
    ).json()["id"]

    first = client.post(
        "/v1/recommendations",
        headers=auth | {"Idempotency-Key": "abc-123"},
        json={"scenario_id": scenario_id},
    )
    second = client.post(
        "/v1/recommendations",
        headers=auth | {"Idempotency-Key": "abc-123"},
        json={"scenario_id": scenario_id},
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_the_same_key_with_a_different_request_is_a_conflict(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    auth = headers(token, seeded.organization_id)
    first_id = client.post(
        "/v1/scenarios", headers=auth, json={"label": "a", "scenario": scenario_body()}
    ).json()["id"]
    second_id = client.post(
        "/v1/scenarios",
        headers=auth,
        json={"label": "b", "scenario": scenario_body(planning_period_months=12)},
    ).json()["id"]

    client.post(
        "/v1/recommendations",
        headers=auth | {"Idempotency-Key": "same-key"},
        json={"scenario_id": first_id},
    )
    conflict = client.post(
        "/v1/recommendations",
        headers=auth | {"Idempotency-Key": "same-key"},
        json={"scenario_id": second_id},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"


def test_json_and_csv_export(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    auth = headers(token, seeded.organization_id)
    scenario_id = client.post(
        "/v1/scenarios", headers=auth, json={"label": "b", "scenario": scenario_body()}
    ).json()["id"]
    run_id = client.post(
        "/v1/recommendations", headers=auth, json={"scenario_id": scenario_id}
    ).json()["id"]

    as_json = client.get(f"/v1/recommendations/{run_id}/export", headers=auth)
    assert as_json.status_code == 200
    assert as_json.json()["status"]

    as_csv = client.get(f"/v1/recommendations/{run_id}/export?format=csv", headers=auth)
    assert as_csv.status_code == 200
    assert as_csv.headers["content-type"].startswith("text/csv")
    assert "candidate_id,label,deployment" in as_csv.text


def test_a_missing_record_is_404_and_does_not_confirm_existence(client, seeded):
    token = log_in(client, load.ANALYST_EMAIL)
    response = client.get(
        f"/v1/recommendations/{uuid.uuid4()}",
        headers=headers(token, seeded.organization_id),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


# --------------------------------------------------------------------------- #
# Crawl jobs
# --------------------------------------------------------------------------- #


def test_queueing_a_crawl_returns_202_and_never_crawls_inline(client, seeded):
    token = log_in(client, load.REVIEWER_EMAIL)
    auth = headers(token, seeded.organization_id)
    created = client.post(
        "/v1/admin/sources",
        headers=auth,
        json={
            "url": "https://vendor.example.invalid/accelerators",
            "allowed_hosts": ["vendor.example.invalid"],
            "category": "manufacturer",
            "owner": "ops",
            "refresh_interval_seconds": 86400,
        },
    )
    assert created.status_code == 201, created.text
    source_id = created.json()["id"]

    response = client.post(
        "/v1/admin/crawl-jobs", headers=auth, json={"source_id": source_id}
    )
    assert response.status_code == 202
    assert response.json()["source_id"] == source_id


def test_a_correlation_id_is_returned_on_every_response(client):
    response = client.get("/health/live")
    assert response.headers["X-Correlation-Id"]
