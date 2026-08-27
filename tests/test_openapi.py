from pathlib import Path

import pytest
import yaml


SPEC_PATH = Path(__file__).parents[1] / "openapi.yaml"


@pytest.fixture(scope="module")
def specification():
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def test_openapi_document_has_required_metadata(specification):
    assert specification["openapi"] == "3.1.0"
    assert specification["info"]["title"] == (
        "Async Web Intelligence Collector API"
    )
    assert specification["info"]["version"] == "1.0.0"


@pytest.mark.parametrize(
    ("path", "method"),
    [("/crawl", "post"), ("/health", "get"), ("/results", "get")],
)
def test_openapi_documents_server_endpoints(specification, path, method):
    assert method in specification["paths"][path]
    assert "responses" in specification["paths"][path][method]


def test_crawl_request_requires_a_non_empty_url_list(specification):
    schema = specification["components"]["schemas"]["CrawlRequest"]

    assert schema["required"] == ["urls"]
    assert schema["properties"]["urls"]["type"] == "array"
    assert schema["properties"]["urls"]["minItems"] == 1
    assert schema["properties"]["urls"]["items"] == {
        "type": "string",
        "format": "uri",
    }


def test_response_schemas_require_their_contract_fields(specification):
    schemas = specification["components"]["schemas"]

    assert set(schemas["CrawlResponse"]["required"]) == {
        "total_urls",
        "successful",
        "failed",
        "results",
    }
    assert schemas["HealthResponse"]["required"] == ["status"]
    assert set(schemas["ResultsResponse"]["required"]) == {
        "count",
        "results",
    }


def test_all_local_schema_references_resolve(specification):
    schemas = specification["components"]["schemas"]

    def walk(value):
        if isinstance(value, dict):
            if "$ref" in value:
                prefix = "#/components/schemas/"
                assert value["$ref"].startswith(prefix)
                assert value["$ref"].removeprefix(prefix) in schemas
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(specification)
