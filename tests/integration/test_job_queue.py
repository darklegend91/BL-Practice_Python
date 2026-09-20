"""Durable job behaviour: claiming, leases, fencing and retries (guide section 10)."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import text

from app.workers import queue
from tests.integration.conftest import requires_postgres

pytestmark = requires_postgres


def _source(session, url: str = "https://vendor.example.invalid/page") -> uuid.UUID:
    source_id = uuid.uuid4()
    session.execute(
        text(
            """
            INSERT INTO sources
              (id, url, allowed_hosts, category, owner, refresh_interval_seconds,
               max_page_bytes, timeout_seconds)
            VALUES (:id,:url,'["vendor.example.invalid"]'::jsonb,'manufacturer','ops',
                    3600, 524288, 30)
            """
        ),
        {"id": source_id, "url": f"{url}/{source_id}"},
    )
    return source_id


def test_enqueue_deduplicates_the_same_schedule_slot(owner_session):
    source_id = _source(owner_session)
    first = queue.enqueue(owner_session, source_id, "slot-1")
    second = queue.enqueue(owner_session, source_id, "slot-1")
    assert first is not None
    assert second is None  # two schedulers cannot queue one refresh twice


def test_claiming_marks_the_job_running_and_takes_a_lease(owner_session):
    source_id = _source(owner_session)
    queue.enqueue(owner_session, source_id, "slot-claim")
    lease = queue.claim(owner_session, lease_seconds=300)
    assert lease is not None
    state, token = owner_session.execute(
        text("SELECT state, lease_token FROM crawl_jobs WHERE id = :id"),
        {"id": lease.job_id},
    ).one()
    assert state == "running"
    assert token == lease.token


def test_a_claimed_job_is_not_handed_to_a_second_worker(owner_session):
    source_id = _source(owner_session)
    queue.enqueue(owner_session, source_id, "slot-once")
    assert queue.claim(owner_session, lease_seconds=300) is not None
    assert queue.claim(owner_session, lease_seconds=300) is None


def test_an_expired_lease_is_reclaimed(owner_session):
    """A killed worker's job returns to the queue without losing its history."""
    source_id = _source(owner_session)
    queue.enqueue(owner_session, source_id, "slot-expire")
    first = queue.claim(owner_session, lease_seconds=300)
    assert first is not None

    owner_session.execute(
        text("UPDATE crawl_jobs SET lease_expires_at = now() - interval '1 minute' "
             "WHERE id = :id"),
        {"id": first.job_id},
    )
    second = queue.claim(owner_session, lease_seconds=300)
    assert second is not None
    assert second.job_id == first.job_id
    assert second.token != first.token
    assert second.attempts == 2  # attempt history is preserved


def test_a_stale_worker_cannot_overwrite_the_new_attempt(owner_session):
    """Lease fencing: every completion must match the current lease token."""
    source_id = _source(owner_session)
    queue.enqueue(owner_session, source_id, "slot-fence")
    stale = queue.claim(owner_session, lease_seconds=300)
    owner_session.execute(
        text("UPDATE crawl_jobs SET lease_expires_at = now() - interval '1 minute' "
             "WHERE id = :id"),
        {"id": stale.job_id},
    )
    fresh = queue.claim(owner_session, lease_seconds=300)

    with pytest.raises(queue.LeaseLost):
        queue.succeed(owner_session, stale)

    queue.succeed(owner_session, fresh)
    state = owner_session.execute(
        text("SELECT state FROM crawl_jobs WHERE id = :id"), {"id": fresh.job_id}
    ).scalar()
    assert state == "succeeded"


def test_heartbeat_extends_a_held_lease_and_fails_on_a_lost_one(owner_session):
    source_id = _source(owner_session)
    queue.enqueue(owner_session, source_id, "slot-heartbeat")
    lease = queue.claim(owner_session, lease_seconds=60)
    queue.heartbeat(owner_session, lease, lease_seconds=600)

    owner_session.execute(
        text("UPDATE crawl_jobs SET lease_token = :other WHERE id = :id"),
        {"other": uuid.uuid4(), "id": lease.job_id},
    )
    with pytest.raises(queue.LeaseLost):
        queue.heartbeat(owner_session, lease, lease_seconds=600)


def test_a_transient_failure_is_retried_with_backoff(owner_session):
    source_id = _source(owner_session)
    queue.enqueue(owner_session, source_id, "slot-retry")
    lease = queue.claim(owner_session, lease_seconds=300)
    queue.retry_later(owner_session, lease, "temporary network error", backoff_seconds=120)

    state, run_after, error = owner_session.execute(
        text("SELECT state, run_after, last_error FROM crawl_jobs WHERE id = :id"),
        {"id": lease.job_id},
    ).one()
    assert state == "queued"
    assert run_after > dt.datetime.now(dt.timezone.utc)
    assert "temporary network error" in error


def test_retries_stop_once_attempts_are_exhausted(owner_session):
    source_id = _source(owner_session)
    job_id = queue.enqueue(owner_session, source_id, "slot-exhaust")
    owner_session.execute(
        text("UPDATE crawl_jobs SET max_attempts = 1 WHERE id = :id"), {"id": job_id}
    )
    lease = queue.claim(owner_session, lease_seconds=300)
    queue.retry_later(owner_session, lease, "still failing", backoff_seconds=60)

    state = owner_session.execute(
        text("SELECT state FROM crawl_jobs WHERE id = :id"), {"id": job_id}
    ).scalar()
    assert state == "failed"


def test_backoff_is_bounded():
    values = [queue.backoff_seconds(attempt) for attempt in range(1, 12)]
    assert values == sorted(values)
    assert max(values) <= 3600
