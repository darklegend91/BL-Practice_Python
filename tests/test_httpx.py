import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from http_methods import httpx_client


def response(status_code, text="body", content_type="text/html"):
    return SimpleNamespace(
        status_code=status_code,
        text=text,
        content=text.encode("utf-8"),
        headers={"Content-Type": content_type},
    )


def run(coroutine):
    return asyncio.run(coroutine)


def test_async_fetch_returns_success():
    client = SimpleNamespace(get=AsyncMock(return_value=response(200, "GPU")))

    result = run(httpx_client.async_fetch(client, "https://example.com/gpu"))

    client.get.assert_awaited_once_with("https://example.com/gpu")
    assert result["status"] == "success"
    assert result["status_code"] == 200
    assert result["content"] == "GPU"
    assert result["content_length"] == 3
    assert result["content_type"] == "text/html"
    assert result["retry_count"] == 0
    assert result["error"] is None


@pytest.mark.parametrize(
    ("status_code", "error"),
    [
        (403, "Client error: HTTP 403"),
        (302, "Unexpected HTTP status: 302"),
    ],
)
def test_async_fetch_classifies_non_retryable_statuses(status_code, error):
    client = SimpleNamespace(get=AsyncMock(return_value=response(status_code)))

    result = run(httpx_client.async_fetch(client, "https://example.com"))

    assert result["status"] == "failed"
    assert result["status_code"] == status_code
    assert result["content"] is None
    assert result["content_length"] == 0
    assert result["retry_count"] == 0
    assert result["error"] == error


def test_async_fetch_retries_server_errors(monkeypatch):
    client = SimpleNamespace(get=AsyncMock(return_value=response(503)))
    sleep = AsyncMock()
    monkeypatch.setattr(httpx_client.asyncio, "sleep", sleep)

    result = run(httpx_client.async_fetch(client, "https://example.com"))

    assert client.get.await_count == httpx_client.MAX_RETRIES
    assert sleep.await_count == httpx_client.MAX_RETRIES - 1
    assert result["status_code"] == 503
    assert result["retry_count"] == 2
    assert result["error"] == "Server error: HTTP 503"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (httpx.TimeoutException("slow"), "Request timed out"),
        (httpx.ConnectError("offline"), "Connection failed: offline"),
    ],
)
def test_async_fetch_retries_transient_errors(
    monkeypatch, exception, expected_error
):
    client = SimpleNamespace(get=AsyncMock(side_effect=exception))
    sleep = AsyncMock()
    monkeypatch.setattr(httpx_client.asyncio, "sleep", sleep)

    result = run(httpx_client.async_fetch(client, "https://example.com"))

    assert client.get.await_count == httpx_client.MAX_RETRIES
    assert sleep.await_count == httpx_client.MAX_RETRIES - 1
    assert result["status"] == "failed"
    assert result["status_code"] is None
    assert result["retry_count"] == 2
    assert result["error"] == expected_error


def test_async_fetch_does_not_retry_invalid_url():
    client = SimpleNamespace(
        get=AsyncMock(side_effect=httpx.InvalidURL("missing protocol"))
    )

    result = run(httpx_client.async_fetch(client, "bad-url"))

    client.get.assert_awaited_once()
    assert result["status"] == "failed"
    assert result["retry_count"] == 0
    assert result["error"] == "Invalid URL: missing protocol"


def test_async_fetch_handles_other_http_errors():
    client = SimpleNamespace(
        get=AsyncMock(side_effect=httpx.DecodingError("bad encoding"))
    )

    result = run(httpx_client.async_fetch(client, "https://example.com"))

    assert result["status"] == "failed"
    assert result["status_code"] is None
    assert result["retry_count"] == 0
    assert result["error"] == "bad encoding"
