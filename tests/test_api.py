"""The HTTP side: no login anywhere, and the data is visible."""

from __future__ import annotations

from tests.conftest import needs_database

pytestmark = needs_database

SOURCES = [
    "https://sample-vendor.example.invalid/gpus",
    "https://sample-models.example.invalid/open-models",
    "https://sample-host.example.invalid/plans",
]

ASK = {
    "workloads": ["coding"],
    "usage": "medium",
    "months": 24,
    "electricity_per_kwh": "0.32",
    "existing_computer": {
        "label": "my computer", "gpu_vram_gb": "16", "system_ram_gb": "32",
        "active_watts": "410", "idle_watts": "70",
    },
}


def fill(client) -> dict:
    for url in SOURCES:
        assert client.post("/sources", json={"url": url}).status_code == 201
    response = client.post("/crawl")
    assert response.status_code == 200
    return response.json()


# --------------------------------------------------------------------------- #
# No login anywhere
# --------------------------------------------------------------------------- #


def test_every_route_works_without_any_credentials(client):
    fill(client)
    for method, path in [
        ("get", "/"), ("get", "/health"), ("get", "/options"), ("get", "/catalog"),
        ("get", "/pages"), ("get", "/sources"), ("get", "/sources/help"),
        ("get", "/recommend"), ("get", "/crawl"),
    ]:
        assert getattr(client, method)(path).status_code == 200, path
    assert client.post("/recommend", json=ASK).status_code == 200


def test_there_is_no_login_or_register_route(client):
    paths = client.get("/openapi.json").json()["paths"]
    for absent in ("/login", "/register", "/auth", "/v1/auth/login", "/token"):
        assert absent not in paths


def test_the_whole_api_is_this_short_list(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    assert paths == {
        "/", "/health", "/options", "/recommend", "/catalog", "/pages",
        "/sources", "/sources/help", "/crawl",
    }


# --------------------------------------------------------------------------- #
# Options
# --------------------------------------------------------------------------- #


def test_options_show_what_each_choice_means(client):
    body = client.get("/options").json()
    medium = next(item for item in body["usage"] if item["id"] == "medium")
    assert medium["means"]["requests_per_day"] == 80
    assert {item["id"] for item in body["workloads"]} == {
        "coding", "studying", "writing", "document_analysis"
    }


def test_the_numbers_you_can_send_are_listed(client):
    fields = {item["field"] for item in client.get("/options").json()["numbers"]}
    assert {"months", "seats", "electricity_per_kwh"} <= fields


# --------------------------------------------------------------------------- #
# The main endpoint
# --------------------------------------------------------------------------- #


def test_sending_answers_gets_a_recommendation(client):
    fill(client)
    body = client.post("/recommend", json=ASK).json()
    assert body["status"] == "recommended"
    assert body["best"]["label"]
    assert body["best"]["cost"]["total"]
    assert body["inputs_used"]["requests_per_day"] == 80


def test_the_answer_explains_what_was_ruled_out_and_why(client):
    fill(client)
    body = client.post("/recommend", json=ASK).json()
    assert body["ruled_out"]
    blocking = [
        finding for option in body["ruled_out"] for finding in option["findings"]
        if finding["blocking"]
    ]
    assert blocking
    assert all(finding["message"] for finding in blocking)


def test_the_answer_lists_the_assumptions_it_made(client):
    fill(client)
    body = client.post("/recommend", json=ASK).json()
    assert body["assumptions"]
    assert body["cases"]


def test_an_empty_catalog_tells_you_to_crawl(client):
    body = client.post("/recommend", json=ASK).json()
    assert body["status"] == "nothing_fits"
    assert any(note["code"] == "CATALOG_EMPTY" for note in body["notes"])


def test_only_the_required_field_is_actually_required(client):
    fill(client)
    response = client.post("/recommend", json={"workloads": ["coding"]})
    assert response.status_code == 200


def test_a_bad_option_is_explained_not_just_rejected(client):
    response = client.post("/recommend", json={"workloads": ["telepathy"]})
    assert response.status_code == 422
    body = response.json()
    assert "GET /options" in body["error"]
    assert any("workloads" in field["field"] for field in body["fields"])


def test_an_unknown_field_is_rejected(client):
    response = client.post(
        "/recommend", json={"workloads": ["coding"], "free_upgrade": True}
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Seeing the data
# --------------------------------------------------------------------------- #


def test_the_catalog_shows_what_the_answer_used(client):
    fill(client)
    body = client.get("/catalog").json()
    assert len(body["hardware"]) == 3
    assert len(body["models"]) == 2
    assert len(body["plans"]) == 2
    assert all(row["source_url"] for row in body["hardware"])


def test_the_catalog_can_be_narrowed_to_a_region(client):
    fill(client)
    assert client.get("/catalog?region=DE").json()["hardware"]
    assert client.get("/catalog?region=ES").json()["hardware"] == []


def test_the_crawled_pages_are_visible(client):
    fill(client)
    pages = client.get("/pages").json()
    assert len(pages) == 3
    assert all(page["rows_found"] > 0 for page in pages)
    assert all(page["characters"] > 0 for page in pages)


def test_crawling_reports_what_it_did(client):
    report = fill(client)
    assert report["sources_visited"] == 3
    assert report["catalog_rows_written"] == 7
    assert report["failures"] == 0


def test_an_unsafe_source_cannot_be_registered(client):
    for url in ("http://127.0.0.1/admin", "http://169.254.169.254/", "file:///etc/passwd"):
        response = client.post("/sources", json={"url": url})
        assert response.status_code == 422, url


def test_health_reports_the_database(client):
    assert client.get("/health").json()["status"] == "ok"
