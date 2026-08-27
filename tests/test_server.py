from io import BytesIO
import json

import pytest

import server


def make_handler(path, body=b""):
    handler = object.__new__(server.IntelligenceHandler)
    handler.path = path
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    handler.wfile = BytesIO()
    handler.status_codes = []
    handler.response_headers = []
    handler.send_response = handler.status_codes.append
    handler.send_header = lambda name, value: handler.response_headers.append(
        (name, value)
    )
    handler.end_headers = lambda: None
    return handler


def response_json(handler):
    return json.loads(handler.wfile.getvalue().decode("utf-8"))


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/", {"Server Status": "Running"}),
        ("/health", {"status": "healthy"}),
    ],
)
def test_status_endpoints(path, expected):
    handler = make_handler(path)

    handler.do_GET()

    assert handler.status_codes == [200]
    assert response_json(handler) == expected
    assert ("Content-Type", "application/json") in handler.response_headers


def test_results_returns_saved_records(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    records = [{"model": "GeForce RTX 5090"}]
    (output / "normalized_results.json").write_text(
        json.dumps(records), encoding="utf-8"
    )
    handler = make_handler("/results")

    handler.do_GET()

    assert handler.status_codes == [200]
    assert response_json(handler) == {"count": 1, "results": records}


def test_results_returns_empty_collection_when_file_is_missing(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    handler = make_handler("/results")

    handler.do_GET()

    assert handler.status_codes == [200]
    assert response_json(handler) == {"count": 0, "results": []}


def test_unknown_get_endpoint_returns_404():
    handler = make_handler("/missing")

    handler.do_GET()

    assert handler.status_codes == [404]
    assert response_json(handler) == {"error": "Endpoint not found"}


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (b"not json", {"error": "Invalid JSON"}),
        (b"{}", {"error": "urls field is required"}),
        (b'{"urls": []}', {"error": "urls field is required"}),
    ],
)
def test_crawl_rejects_invalid_requests(body, expected):
    handler = make_handler("/crawl", body)

    handler.do_POST()

    assert handler.status_codes == [400]
    assert response_json(handler) == expected


def test_crawl_returns_summary(monkeypatch):
    async def fake_fetch_many(urls):
        assert urls == ["one", "two"]
        return [
            {"url": "one", "status": "success"},
            {"url": "two", "status": "failed"},
        ]

    monkeypatch.setattr(server, "async_fetch_many", fake_fetch_many)
    body = json.dumps({"urls": ["one", "two"]}).encode("utf-8")
    handler = make_handler("/crawl", body)

    handler.do_POST()

    assert handler.status_codes == [200]
    assert response_json(handler) == {
        "total_urls": 2,
        "successful": 1,
        "failed": 1,
        "results": [
            {"url": "one", "status": "success"},
            {"url": "two", "status": "failed"},
        ],
    }


def test_unknown_post_endpoint_returns_404():
    handler = make_handler("/missing")

    handler.do_POST()

    assert handler.status_codes == [404]
    assert response_json(handler) == {"error": "Endpoint not found"}
