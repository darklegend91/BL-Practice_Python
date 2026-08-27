from types import SimpleNamespace

import pytest
import requests

from http_methods import requests_client


def response(status_code, text="body", content_type="text/html"):
    return SimpleNamespace(
        status_code=status_code,
        text=text,
        content=text.encode("utf-8"),
        headers={"Content-Type": content_type},
    )


def test_fetch_page_returns_success_response(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response(200, "GPU page")

    monkeypatch.setattr(requests_client.requests, "get", fake_get)

    result = requests_client.fetch_page("https://example.com/gpu", timeout=4)

    assert captured == {
        "url": "https://example.com/gpu",
        "headers": requests_client.HEADERS,
        "timeout": 4,
    }
    assert result["status"] == "success"
    assert result["status_code"] == 200
    assert result["content"] == "GPU page"
    assert result["content_length"] == len(b"GPU page")
    assert result["content_type"] == "text/html"
    assert result["error"] is None
    assert result["total_time"] >= 0


@pytest.mark.parametrize(
    ("status_code", "error"),
    [
        (404, "Client error: HTTP 404"),
        (503, "Server error: HTTP 503"),
        (302, "Unexpected HTTP status: 302"),
    ],
)
def test_fetch_page_classifies_non_success_statuses(
    monkeypatch, status_code, error
):
    monkeypatch.setattr(
        requests_client.requests,
        "get",
        lambda *args, **kwargs: response(status_code),
    )

    result = requests_client.fetch_page("https://example.com")

    assert result["status"] == "failed"
    assert result["status_code"] == status_code
    assert result["content"] is None
    assert result["content_length"] == 0
    assert result["error"] == error


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (requests.exceptions.InvalidURL("bad URL"), "Invalid URL: bad URL"),
        (requests.exceptions.Timeout("slow"), "Request timed out"),
        (
            requests.exceptions.ConnectionError("offline"),
            "Connection failure: offline",
        ),
        (requests.exceptions.RequestException("broken"), "broken"),
    ],
)
def test_fetch_page_handles_request_exceptions(monkeypatch, exception, error):
    def fail(*args, **kwargs):
        raise exception

    monkeypatch.setattr(requests_client.requests, "get", fail)

    result = requests_client.fetch_page("not-a-url")

    assert result["status"] == "failed"
    assert result["status_code"] is None
    assert result["content"] is None
    assert result["content_length"] == 0
    assert result["content_type"] is None
    assert result["total_time"] >= 0
    assert result["error"] == error


def test_fetch_rtx_pages_keeps_input_order(monkeypatch, capsys):
    seen = []

    def fake_fetch(url):
        seen.append(url)
        return {
            "url": url,
            "status": "success",
            "status_code": 200,
            "content": "ok",
            "content_length": 2,
            "content_type": "text/plain",
            "total_time": 0.01,
            "error": None,
        }

    monkeypatch.setattr(requests_client, "fetch_page", fake_fetch)

    results = requests_client.fetch_rtx_pages(["first", "second"])

    assert seen == ["first", "second"]
    assert [item["url"] for item in results] == ["first", "second"]
    assert "Fetching 2/2" in capsys.readouterr().out


def test_save_results_to_file_writes_json(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = [{"url": "https://example.com", "status": "success"}]
    target = tmp_path / "output" / "requests.json"

    requests_client.save_results_to_file(result, str(target))

    assert target.read_text(encoding="utf-8") == (
        '[\n    {\n        "url": "https://example.com",\n'
        '        "status": "success"\n    }\n]'
    )
