"""The collector worker loop (guide sections 7 and 10).

Runs as its own process so browser work can never block a user request. Browser
concurrency and per-domain request frequency are bounded, no database lock is
held while a page renders, and browser resources are closed on timeout and
shutdown.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import signal
import uuid
from collections import defaultdict
from urllib.parse import urlsplit

from sqlalchemy import select

from app.collection.adapter import CollectionBackend, CollectionError, get_backend
from app.collection.changes import ChangeOutcome, evaluate
from app.collection.snapshots import PageSnapshot
from app.config import get_settings
from app.db.models import Source, SourceSnapshot
from app.db.session import unit_of_work
from app.security.net_guard import DestinationRefused, check_url
from app.workers import queue

log = logging.getLogger("llmfit.crawler")


class DomainRateLimiter:
    """Keeps a minimum interval between requests to the same host."""

    def __init__(self, minimum_interval_seconds: float) -> None:
        self._interval = minimum_interval_seconds
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last: dict[str, float] = {}

    async def wait(self, url: str) -> None:
        host = urlsplit(url).hostname or ""
        async with self._locks[host]:
            loop = asyncio.get_running_loop()
            elapsed = loop.time() - self._last.get(host, float("-inf"))
            if elapsed < self._interval:
                await asyncio.sleep(self._interval - elapsed)
            self._last[host] = loop.time()


class CrawlerWorker:
    def __init__(self, backend: CollectionBackend | None = None) -> None:
        self.settings = get_settings()
        self.backend = backend or get_backend()
        self.limiter = DomainRateLimiter(
            self.settings.crawl_per_domain_min_interval_seconds
        )
        self.browser_slots = asyncio.Semaphore(self.settings.crawl_browser_concurrency)
        self._stopping = asyncio.Event()

    # --- lifecycle ---------------------------------------------------------

    def request_stop(self) -> None:
        self._stopping.set()

    async def run(self, poll_interval_seconds: float = 2.0) -> None:
        log.info("crawler worker started (backend=%s)", self.backend.version)
        while not self._stopping.is_set():
            did_work = await self.run_once()
            if not did_work:
                try:
                    await asyncio.wait_for(
                        self._stopping.wait(), timeout=poll_interval_seconds
                    )
                except TimeoutError:
                    pass
        log.info("crawler worker stopped")

    # --- one job -----------------------------------------------------------

    async def run_once(self) -> bool:
        """Claim and process at most one job. Returns whether work was done."""
        # Short transaction: claim, commit, then release the connection.
        with unit_of_work() as session:
            lease = queue.claim(session, self.settings.crawl_lease_seconds)
            if lease is None:
                return False
            source = session.get(Source, lease.source_id)
            if source is None or not source.enabled:
                queue.fail_permanently(session, lease, "source is missing or disabled")
                return True
            request = _SourceRequest.from_row(source)

        # No database lock is held while the page renders.
        try:
            snapshot = await self._collect(request)
        except DestinationRefused as refusal:
            with unit_of_work() as session:
                queue.fail_permanently(session, lease, f"destination refused: {refusal}")
            return True
        except CollectionError as error:
            with unit_of_work() as session:
                if error.permanent:
                    queue.fail_permanently(session, lease, str(error))
                else:
                    queue.retry_later(
                        session, lease, str(error), queue.backoff_seconds(lease.attempts)
                    )
            return True

        with unit_of_work() as session:
            self._store(session, request, snapshot)
            queue.succeed(session, lease)
        return True

    async def _collect(self, request: "_SourceRequest") -> PageSnapshot:
        check_url(request.url, request.allowed_hosts)
        await self.limiter.wait(request.url)
        async with self.browser_slots:
            try:
                return await asyncio.wait_for(
                    self.backend.fetch(
                        request.url,
                        allowed_hosts=request.allowed_hosts,
                        timeout_seconds=request.timeout_seconds,
                        max_bytes=request.max_page_bytes,
                    ),
                    timeout=request.timeout_seconds + 5,
                )
            except TimeoutError as error:
                # The adapter closes its own browser resources on the way out.
                raise CollectionError(f"timed out collecting {request.url}") from error

    def _store(self, session, request: "_SourceRequest", snapshot: PageSnapshot) -> None:
        """Write the snapshot and record what review it implies.

        Execution is at least once, so an identical snapshot is not written twice.
        """
        previous = session.scalars(
            select(SourceSnapshot)
            .where(SourceSnapshot.source_id == request.source_id)
            .order_by(SourceSnapshot.fetched_at.desc())
            .limit(1)
        ).first()

        task = evaluate(
            request.url,
            previous.markdown if previous else None,
            snapshot.markdown,
            snapshot.fetched_at,
        )
        if task.outcome is ChangeOutcome.UNCHANGED:
            log.info("source %s unchanged", request.url)
            return

        session.add(
            SourceSnapshot(
                source_id=request.source_id,
                fetched_at=snapshot.fetched_at,
                final_url=snapshot.final_url,
                http_status=snapshot.http_status,
                content_hash=snapshot.content_hash,
                markdown=snapshot.markdown,
                byte_size=snapshot.byte_size,
                crawler_version=snapshot.crawler_version,
            )
        )
        log.info(
            "source %s %s (change ratio %.4f) - queued for editor review",
            request.url,
            task.outcome.value,
            task.change_ratio,
        )


class _SourceRequest:
    """Plain copy of a source row, so no ORM object outlives its session."""

    def __init__(self, source_id: uuid.UUID, url: str, allowed_hosts: list[str],
                 timeout_seconds: int, max_page_bytes: int) -> None:
        self.source_id = source_id
        self.url = url
        self.allowed_hosts = allowed_hosts
        self.timeout_seconds = timeout_seconds
        self.max_page_bytes = max_page_bytes

    @classmethod
    def from_row(cls, source: Source) -> "_SourceRequest":
        return cls(
            source.id,
            source.url,
            list(source.allowed_hosts or []),
            source.timeout_seconds,
            source.max_page_bytes,
        )


async def main() -> None:  # pragma: no cover - process entry point
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    worker = CrawlerWorker()
    loop = asyncio.get_running_loop()
    for received in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(received, worker.request_stop)
    await worker.run()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
