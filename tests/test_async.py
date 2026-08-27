import asyncio
import json

from http_methods import httpx_client

class FakeAsyncClient:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.entered = False
        self.exited = False
        self.__class__.instances.append(self)

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.exited = True


def test_async_fetch_many_preserves_order_and_wraps_unexpected_errors(
    monkeypatch,
):
    FakeAsyncClient.instances.clear()
    monkeypatch.setattr(httpx_client.httpx, "AsyncClient", FakeAsyncClient)

    async def fake_fetch(client, url):
        await asyncio.sleep(0)
        if url == "broken":
            raise RuntimeError("escaped")
        return {"url": url, "status": "success"}

    monkeypatch.setattr(httpx_client, "async_fetch", fake_fetch)

    results = asyncio.run(
        httpx_client.async_fetch_many(["first", "broken", "last"])
    )

    assert [result["url"] for result in results] == [
        "first",
        "broken",
        "last",
    ]
    assert results[0] == {"url": "first", "status": "success"}
    assert results[1] == {
        "url": "broken",
        "status": "failed",
        "status_code": None,
        "content": None,
        "content_length": 0,
        "content_type": None,
        "elapsed_time": 0,
        "retry_count": 0,
        "error": "Unexpected error: escaped",
    }
    assert results[2] == {"url": "last", "status": "success"}

    instance = FakeAsyncClient.instances[0]
    assert instance.entered and instance.exited
    assert instance.kwargs["headers"] == httpx_client.HEADERS
    assert instance.kwargs["follow_redirects"] is True


def test_async_fetch_many_accepts_empty_input(monkeypatch):
    FakeAsyncClient.instances.clear()
    monkeypatch.setattr(httpx_client.httpx, "AsyncClient", FakeAsyncClient)

    assert asyncio.run(httpx_client.async_fetch_many([])) == []


def test_save_async_results_to_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "output" / "async.json"
    results = [{"url": "one", "status": "success"}]

    httpx_client.save_results_to_file(results, str(target))

    assert json.loads(target.read_text(encoding="utf-8")) == results
