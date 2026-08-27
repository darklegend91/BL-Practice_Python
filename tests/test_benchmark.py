import asyncio

import pytest

import benchmark


def test_fetch_sequential_collects_results_and_elapsed_time(monkeypatch):
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return {"url": url}

    times = iter([10.0, 13.5])
    monkeypatch.setattr(benchmark, "fetch_page", fake_fetch)
    monkeypatch.setattr(benchmark.time, "perf_counter", lambda: next(times))

    results, elapsed = benchmark.fetch_sequential(["one", "two"])

    assert calls == ["one", "two"]
    assert results == [{"url": "one"}, {"url": "two"}]
    assert elapsed == 3.5


def test_fetch_concurrent_delegates_to_async_client(monkeypatch):
    async def fake_fetch_many(urls):
        return [{"url": url} for url in urls]

    times = iter([2.0, 2.75])
    monkeypatch.setattr(benchmark, "async_fetch_many", fake_fetch_many)
    monkeypatch.setattr(benchmark.time, "perf_counter", lambda: next(times))

    results, elapsed = asyncio.run(benchmark.fetch_concurrent(["one", "two"]))

    assert results == [{"url": "one"}, {"url": "two"}]
    assert elapsed == 0.75


@pytest.mark.parametrize(
    ("sequential", "asynchronous", "expected"),
    [
        (10, 4, 60),
        (10, 10, 0),
        (10, 12, -20),
        (0, 1, 0),
    ],
)
def test_calculate_improvement(sequential, asynchronous, expected):
    assert benchmark.calculate_improvement(sequential, asynchronous) == expected
