"""Idempotency for crawl enqueueing and saved calculations (guide section 9).

Keys are scoped to organization and route. The same key with the same request
replays the stored outcome; the same key with a different request is a conflict.
Entries expire after the configured retention window.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import IdempotencyKey
from app.schemas.common import utc_now
from app.security.tokens import digest_idempotency_key, hash_request_body


class IdempotencyConflict(Exception):
    """The key was already used for a different request body."""


def look_up(
    session: Session,
    *,
    organization_id: uuid.UUID,
    route: str,
    key: str,
    request_body: bytes,
) -> tuple[dict, int] | None:
    """Return the stored ``(outcome, status_code)`` for a replay, if any."""
    record = session.scalars(
        select(IdempotencyKey).where(
            IdempotencyKey.organization_id == organization_id,
            IdempotencyKey.route == route,
            IdempotencyKey.key_digest == digest_idempotency_key(key),
        )
    ).first()
    if record is None:
        return None
    if record.expires_at <= utc_now():
        session.delete(record)
        return None
    if record.request_hash != hash_request_body(request_body):
        raise IdempotencyConflict(
            "this idempotency key was already used with a different request"
        )
    return record.outcome, record.status_code


def remember(
    session: Session,
    *,
    organization_id: uuid.UUID,
    route: str,
    key: str,
    request_body: bytes,
    outcome: dict,
    status_code: int,
) -> None:
    settings = get_settings()
    session.add(
        IdempotencyKey(
            organization_id=organization_id,
            route=route,
            key_digest=digest_idempotency_key(key),
            request_hash=hash_request_body(request_body),
            outcome=outcome,
            status_code=status_code,
            expires_at=utc_now()
            + dt.timedelta(seconds=settings.idempotency_retention_seconds),
        )
    )


def purge_expired(session: Session) -> int:
    return session.execute(
        delete(IdempotencyKey).where(IdempotencyKey.expires_at <= utc_now())
    ).rowcount
