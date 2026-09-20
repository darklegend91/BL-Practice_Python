"""Enqueues due refreshes (guide section 10).

The deduplication key is the source plus its schedule slot, so two schedulers
running at once cannot enqueue the same refresh twice.
"""

from __future__ import annotations

import datetime as dt
import logging
import time

from sqlalchemy import select

from app.db.models import Source
from app.db.session import unit_of_work
from app.workers import queue

log = logging.getLogger("llmfit.scheduler")


def schedule_slot(now: dt.datetime, interval_seconds: int) -> int:
    """The slot number this moment belongs to, for a given refresh interval."""
    return int(now.timestamp()) // max(1, interval_seconds)


def dedupe_key(source_id, slot: int) -> str:
    return f"{source_id}:{slot}"


def enqueue_due(now: dt.datetime | None = None) -> int:
    """Queue one refresh per enabled source per schedule slot."""
    moment = now or dt.datetime.now(dt.timezone.utc)
    queued = 0
    with unit_of_work() as session:
        sources = session.scalars(select(Source).where(Source.enabled.is_(True))).all()
        for source in sources:
            slot = schedule_slot(moment, source.refresh_interval_seconds)
            if queue.enqueue(session, source.id, dedupe_key(source.id, slot)) is not None:
                queued += 1
    return queued


def main(interval_seconds: int = 60) -> None:  # pragma: no cover - entry point
    logging.basicConfig(level=logging.INFO)
    while True:
        queued = enqueue_due()
        if queued:
            log.info("queued %d refresh job(s)", queued)
        time.sleep(interval_seconds)


if __name__ == "__main__":  # pragma: no cover
    main()
