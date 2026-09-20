"""The worker end to end: claim, collect from a fixture, store, review.

The crawl boundary is mocked with saved pages, so nothing here reaches a live
vendor site (guide section 13).
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.collection.adapter import CollectionError, FixtureBackend
from app.collection.snapshots import PageSnapshot
from app.workers import queue, scheduler
from app.workers.crawler import CrawlerWorker, DomainRateLimiter
from tests.integration.conftest import requires_postgres

pytestmark = requires_postgres

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "pages"
SOURCE_URL = "https://vendor.example.invalid/accelerators"


@pytest.fixture
def worker_session_factory(owner_engine, monkeypatch):
    """Point the worker's own unit_of_work at the test database."""
    factory = sessionmaker(bind=owner_engine, expire_on_commit=False, future=True)
    monkeypatch.setattr("app.db.session.get_sessionmaker", lambda: factory)
    return factory


@pytest.fixture
def registered_source(owner_engine) -> uuid.UUID:
    source_id = uuid.uuid4()
    with owner_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO sources
                  (id, url, allowed_hosts, category, owner, refresh_interval_seconds,
                   max_page_bytes, timeout_seconds)
                VALUES (:id,:url,'["vendor.example.invalid"]'::jsonb,'manufacturer','ops',
                        3600, 524288, 10)
                """
            ),
            {"id": source_id, "url": SOURCE_URL},
        )
    return source_id


@pytest.fixture
def worker(monkeypatch):
    # The egress guard's resolution step cannot reach a .invalid host, and this
    # test is about the worker, not the guard - the guard has its own tests.
    monkeypatch.setattr("app.workers.crawler.check_url", lambda url, hosts: url)
    return CrawlerWorker(backend=FixtureBackend(FIXTURES))


def _snapshots(engine, source_id) -> list[tuple[str, str]]:
    with engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT content_hash, markdown FROM source_snapshots "
                "WHERE source_id = :id ORDER BY fetched_at"
            ),
            {"id": source_id},
        ).all()


def test_a_queued_job_is_collected_and_stored(
    owner_engine, worker_session_factory, registered_source, worker
):
    with owner_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO crawl_jobs (source_id, dedupe_key) VALUES (:source,'slot-a')"
            ),
            {"source": registered_source},
        )

    assert asyncio.run(worker.run_once()) is True

    stored = _snapshots(owner_engine, registered_source)
    assert len(stored) == 1
    assert "Accelerator 16G" in stored[0][1]

    with owner_engine.begin() as connection:
        state = connection.execute(
            text("SELECT state FROM crawl_jobs WHERE source_id = :id"),
            {"id": registered_source},
        ).scalar()
    assert state == "succeeded"


def test_an_unchanged_page_is_not_stored_twice(
    owner_engine, worker_session_factory, registered_source, worker
):
    """At-least-once execution must not create duplicate snapshots."""
    with owner_engine.begin() as connection:
        for slot in ("slot-1", "slot-2"):
            connection.execute(
                text(
                    "INSERT INTO crawl_jobs (source_id, dedupe_key) VALUES (:source,:slot)"
                ),
                {"source": registered_source, "slot": slot},
            )

    asyncio.run(worker.run_once())
    asyncio.run(worker.run_once())

    assert len(_snapshots(owner_engine, registered_source)) == 1


def test_a_changed_page_creates_a_new_snapshot_for_review(
    owner_engine, worker_session_factory, registered_source, worker, monkeypatch
):
    with owner_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO crawl_jobs (source_id, dedupe_key) VALUES (:s,'slot-1')"),
            {"s": registered_source},
        )
    asyncio.run(worker.run_once())

    # The vendor page changes its price.
    changed = (FIXTURES / "vendor.example.invalid" / "accelerators-changed.md").read_text()

    async def fetch_changed(url, **kwargs):
        import datetime as dt
        from app.collection.snapshots import content_hash

        return PageSnapshot(
            source_url=url,
            final_url=url,
            http_status=200,
            markdown=changed,
            content_hash=content_hash(changed),
            byte_size=len(changed.encode()),
            fetched_at=dt.datetime.now(dt.timezone.utc),
            crawler_version="fixture-backend/1",
        )

    monkeypatch.setattr(worker.backend, "fetch", fetch_changed)
    with owner_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO crawl_jobs (source_id, dedupe_key) VALUES (:s,'slot-2')"),
            {"s": registered_source},
        )
    asyncio.run(worker.run_once())

    stored = _snapshots(owner_engine, registered_source)
    assert len(stored) == 2
    assert stored[0][0] != stored[1][0]


def test_a_page_change_cannot_publish_anything_by_itself(
    owner_engine, worker_session_factory, registered_source, worker
):
    """Collection never touches the catalog; an editor still has to act."""
    with owner_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO crawl_jobs (source_id, dedupe_key) VALUES (:s,'slot-1')"),
            {"s": registered_source},
        )
    asyncio.run(worker.run_once())

    with owner_engine.begin() as connection:
        published = connection.execute(
            text("SELECT count(*) FROM catalog_revisions WHERE review_status='published'")
        ).scalar()
        prices = connection.execute(text("SELECT count(*) FROM price_observations")).scalar()
    assert published == 0
    assert prices == 0


def test_a_permanent_failure_does_not_retry(
    owner_engine, worker_session_factory, registered_source, worker, monkeypatch
):
    async def refuse(url, **kwargs):
        raise CollectionError("source format is not supported", permanent=True)

    monkeypatch.setattr(worker.backend, "fetch", refuse)
    with owner_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO crawl_jobs (source_id, dedupe_key) VALUES (:s,'slot-1')"),
            {"s": registered_source},
        )
    asyncio.run(worker.run_once())

    with owner_engine.begin() as connection:
        state, error = connection.execute(
            text("SELECT state, last_error FROM crawl_jobs WHERE source_id = :id"),
            {"id": registered_source},
        ).one()
    assert state == "failed"
    assert "not supported" in error


def test_a_transient_failure_is_requeued(
    owner_engine, worker_session_factory, registered_source, worker, monkeypatch
):
    async def stumble(url, **kwargs):
        raise CollectionError("temporary network problem")

    monkeypatch.setattr(worker.backend, "fetch", stumble)
    with owner_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO crawl_jobs (source_id, dedupe_key) VALUES (:s,'slot-1')"),
            {"s": registered_source},
        )
    asyncio.run(worker.run_once())

    with owner_engine.begin() as connection:
        state, attempts = connection.execute(
            text("SELECT state, attempts FROM crawl_jobs WHERE source_id = :id"),
            {"id": registered_source},
        ).one()
    assert state == "queued"
    assert attempts == 1


def test_a_disabled_source_fails_the_job_permanently(
    owner_engine, worker_session_factory, registered_source, worker
):
    with owner_engine.begin() as connection:
        connection.execute(
            text("UPDATE sources SET enabled = false WHERE id = :id"),
            {"id": registered_source},
        )
        connection.execute(
            text("INSERT INTO crawl_jobs (source_id, dedupe_key) VALUES (:s,'slot-1')"),
            {"s": registered_source},
        )
    asyncio.run(worker.run_once())

    with owner_engine.begin() as connection:
        state = connection.execute(
            text("SELECT state FROM crawl_jobs WHERE source_id = :id"),
            {"id": registered_source},
        ).scalar()
    assert state == "failed"


def test_an_empty_queue_is_not_an_error(owner_engine, worker_session_factory, worker):
    assert asyncio.run(worker.run_once()) is False


def test_the_scheduler_queues_one_job_per_slot(
    owner_engine, worker_session_factory, registered_source
):
    assert scheduler.enqueue_due() == 1
    assert scheduler.enqueue_due() == 0  # same slot, already queued


def test_requests_to_one_host_are_spaced_apart():
    async def timed() -> float:
        limiter = DomainRateLimiter(minimum_interval_seconds=0.2)
        loop = asyncio.get_running_loop()
        start = loop.time()
        await limiter.wait("https://vendor.example.invalid/a")
        await limiter.wait("https://vendor.example.invalid/b")
        return loop.time() - start

    assert asyncio.run(timed()) >= 0.2
