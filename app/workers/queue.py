"""The PostgreSQL job queue (guide section 10).

Claiming is a short transaction that writes a lease token and commits *before*
any browser work starts. Every later write must match that lease token, so a
worker that stalled and lost its lease cannot overwrite a newer attempt.
``SKIP LOCKED`` is used only for queue-like claiming, not as a general reading
strategy.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import CrawlJob

CLAIM_SQL = text(
    """
    WITH claimed AS (
        SELECT id
        FROM crawl_jobs
        WHERE run_after <= now()
          AND attempts < max_attempts
          AND (
                state = 'queued'
                OR (state = 'running' AND lease_expires_at < now())
              )
        ORDER BY run_after
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    UPDATE crawl_jobs AS job
    SET state = 'running',
        lease_token = :lease_token,
        lease_expires_at = now() + make_interval(secs => :lease_seconds),
        heartbeat_at = now(),
        attempts = job.attempts + 1,
        updated_at = now()
    FROM claimed
    WHERE job.id = claimed.id
    RETURNING job.id, job.source_id, job.attempts, job.max_attempts
    """
)


class Lease:
    """Proof that this worker currently owns a job."""

    def __init__(self, job_id: uuid.UUID, source_id: uuid.UUID, token: uuid.UUID,
                 attempts: int, max_attempts: int) -> None:
        self.job_id = job_id
        self.source_id = source_id
        self.token = token
        self.attempts = attempts
        self.max_attempts = max_attempts

    @property
    def attempts_remaining(self) -> int:
        return max(0, self.max_attempts - self.attempts)


class LeaseLost(RuntimeError):
    """The job was reclaimed by another worker while this one was running."""


def enqueue(
    session: Session,
    source_id: uuid.UUID,
    dedupe_key: str,
    *,
    run_after: dt.datetime | None = None,
    max_attempts: int = 5,
) -> uuid.UUID | None:
    """Queue a refresh, ignoring a duplicate for the same schedule slot.

    Returns the job id, or ``None`` when an equivalent job already exists.
    """
    result = session.execute(
        text(
            """
            INSERT INTO crawl_jobs (source_id, dedupe_key, run_after, max_attempts)
            VALUES (:source_id, :dedupe_key, coalesce(:run_after, now()), :max_attempts)
            ON CONFLICT (dedupe_key) DO NOTHING
            RETURNING id
            """
        ),
        {
            "source_id": source_id,
            "dedupe_key": dedupe_key,
            "run_after": run_after,
            "max_attempts": max_attempts,
        },
    )
    row = result.first()
    return row[0] if row else None


def claim(session: Session, lease_seconds: int) -> Lease | None:
    """Take one eligible job. Commit before starting any browser work."""
    token = uuid.uuid4()
    row = session.execute(
        CLAIM_SQL, {"lease_token": token, "lease_seconds": lease_seconds}
    ).first()
    if row is None:
        return None
    return Lease(row[0], row[1], token, row[2], row[3])


def heartbeat(session: Session, lease: Lease, lease_seconds: int) -> None:
    """Extend a long job's lease. Fails if the lease was already reclaimed."""
    updated = session.execute(
        text(
            """
            UPDATE crawl_jobs
            SET heartbeat_at = now(),
                lease_expires_at = now() + make_interval(secs => :lease_seconds),
                updated_at = now()
            WHERE id = :job_id AND lease_token = :lease_token
            """
        ),
        {"job_id": lease.job_id, "lease_token": lease.token, "lease_seconds": lease_seconds},
    ).rowcount
    if updated == 0:
        raise LeaseLost(f"lease for job {lease.job_id} is no longer held")


def _finish(session: Session, lease: Lease, **values) -> None:
    assignments = ", ".join(f"{name} = :{name}" for name in values)
    updated = session.execute(
        text(
            f"""
            UPDATE crawl_jobs
            SET {assignments}, lease_token = NULL, lease_expires_at = NULL,
                updated_at = now()
            WHERE id = :job_id AND lease_token = :lease_token
            """
        ),
        {**values, "job_id": lease.job_id, "lease_token": lease.token},
    ).rowcount
    if updated == 0:
        raise LeaseLost(f"lease for job {lease.job_id} is no longer held")


def succeed(session: Session, lease: Lease) -> None:
    _finish(session, lease, state="succeeded", last_error=None)


def fail_permanently(session: Session, lease: Lease, error: str) -> None:
    _finish(session, lease, state="failed", last_error=error[:2000])


def retry_later(session: Session, lease: Lease, error: str, backoff_seconds: int) -> None:
    """Reschedule a transient failure, or give up once attempts are exhausted."""
    if lease.attempts_remaining == 0:
        fail_permanently(session, lease, f"{error} (no attempts remaining)")
        return
    updated = session.execute(
        text(
            """
            UPDATE crawl_jobs
            SET state = 'queued',
                run_after = now() + make_interval(secs => :backoff),
                last_error = :error,
                lease_token = NULL,
                lease_expires_at = NULL,
                updated_at = now()
            WHERE id = :job_id AND lease_token = :lease_token
            """
        ),
        {
            "job_id": lease.job_id,
            "lease_token": lease.token,
            "backoff": backoff_seconds,
            "error": error[:2000],
        },
    ).rowcount
    if updated == 0:
        raise LeaseLost(f"lease for job {lease.job_id} is no longer held")


def backoff_seconds(attempt: int, *, base: int = 30, ceiling: int = 3600) -> int:
    """Bounded exponential backoff."""
    return min(ceiling, base * (2 ** max(0, attempt - 1)))
