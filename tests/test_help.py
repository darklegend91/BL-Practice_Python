"""The API explains itself: every POST has a GET beside it, and / explains all.

These tests are the reason the documentation cannot quietly go stale. Add a
field or an endpoint without documenting it and one of them fails.
"""

from __future__ import annotations

from app.schemas import ExistingComputer, RecommendInput
from tests.conftest import needs_database

pytestmark = needs_database


def paths(client) -> dict:
    return client.get("/openapi.json").json()["paths"]


# --------------------------------------------------------------------------- #
# The rule: no POST without a GET explaining it
# --------------------------------------------------------------------------- #


def test_every_post_endpoint_has_a_get_that_explains_it(client):
    spec = paths(client)
    posts = [path for path, methods in spec.items() if "post" in methods]
    assert posts, "there should be POST endpoints to check"

    for path in posts:
        helper = path if "get" in spec.get(path, {}) else f"{path}/help"
        assert "get" in spec.get(helper, {}), (
            f"POST {path} has no GET explaining it; expected GET {helper}"
        )


def test_the_help_endpoints_answer_without_a_database_or_a_body(client):
    for path in ("/", "/recommend", "/sources/help", "/crawl"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.json(), path


# --------------------------------------------------------------------------- #
# GET /recommend
# --------------------------------------------------------------------------- #


def test_every_input_field_is_documented(client):
    documented = {field["name"] for field in client.get("/recommend").json()["fields"]}
    assert documented == set(RecommendInput.model_fields), (
        "GET /recommend must document exactly the fields POST /recommend accepts"
    )


def test_the_nested_computer_fields_are_documented_too(client):
    documented = {
        field["name"]
        for field in client.get("/recommend").json()["existing_computer_fields"]
    }
    assert documented == set(ExistingComputer.model_fields)


def test_the_documented_choices_match_the_real_ones(client):
    fields = {f["name"]: f for f in client.get("/recommend").json()["fields"]}
    assert fields["workloads"]["choices"] == [
        "coding", "studying", "writing", "document_analysis"
    ]
    assert fields["priority"]["choices"] == [
        "lowest_cost", "least_setup", "offline_control"
    ]


def test_the_documented_defaults_match_the_real_ones(client):
    fields = {f["name"]: f for f in client.get("/recommend").json()["fields"]}
    assert fields["months"]["default"] == "24"
    assert fields["usage"]["default"] == "medium"
    assert fields["workloads"]["required"] is True
    assert fields["usage"]["required"] is False


def test_only_workloads_is_marked_required(client):
    fields = client.get("/recommend").json()["fields"]
    assert [f["name"] for f in fields if f["required"]] == ["workloads"]


def test_the_example_body_is_actually_accepted(client):
    """The example in the help must be a request the API really takes."""
    example = client.get("/recommend").json()["send_this"]
    assert client.post("/recommend", json=example).status_code == 200


def test_the_example_body_validates_against_the_input_model(client):
    example = client.get("/recommend").json()["send_this"]
    RecommendInput.model_validate(example)  # raises if the help has drifted


def test_it_says_what_comes_back(client):
    body = client.get("/recommend").json()
    assert any("status" in line for line in body["you_get_back"])
    assert any("uncertain" in line for line in body["you_get_back"])
    assert body["try_it"].startswith("curl")


# --------------------------------------------------------------------------- #
# The other two POSTs
# --------------------------------------------------------------------------- #


def test_sources_help_example_is_accepted(client):
    example = client.get("/sources/help").json()["send_this"]
    assert client.post("/sources", json=example).status_code == 201


def test_crawl_help_says_it_needs_no_body(client):
    body = client.get("/crawl").json()
    assert body["send_this"] is None
    assert body["fields"] == []
    assert "no body" in body["what_it_does"].lower()


# --------------------------------------------------------------------------- #
# GET /
# --------------------------------------------------------------------------- #


def test_home_lists_every_real_endpoint(client):
    spec = paths(client)
    real = {
        (method.upper(), path)
        for path, methods in spec.items()
        for method in methods
        if method in ("get", "post")
    }
    listed = {
        (entry["method"], entry["path"]) for entry in client.get("/").json()["endpoints"]
    }
    missing = real - listed
    assert not missing, f"GET / does not mention: {sorted(missing)}"


def test_home_says_there_is_no_login(client):
    assert client.get("/").json()["login_required"] is False


def test_home_explains_the_flow_and_the_setup(client):
    body = client.get("/").json()
    assert len(body["the_flow"]) >= 5
    assert any("alembic" in step for step in body["first_time_setup"])
    assert any("app.crawler" in step for step in body["first_time_setup"])


def test_home_is_honest_about_the_limitations(client):
    limitations = " ".join(client.get("/").json()["known_limitations"])
    assert "fact-block format" in limitations
    assert "zero rows" in limitations


def test_home_says_what_it_will_not_do(client):
    refusals = " ".join(client.get("/").json()["what_it_will_not_do"])
    assert "never added together" in refusals or "one pool" in refusals
    assert "zero" in refusals


def test_the_worked_example_command_is_runnable(client):
    example = client.get("/").json()["a_worked_example"]
    assert example["step_3_ask"].startswith("curl -X POST")
    assert "/recommend" in example["step_3_ask"]


def test_home_points_at_the_deeper_docs(client):
    where = client.get("/").json()["where_to_look_next"]
    assert where["full_guide"] == "docs/guide.md"
    assert where["interactive_docs"] == "/docs"
