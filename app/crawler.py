"""Visits every enabled source, stores the page, and updates the catalog.

The whole thing is one pass with no queue, no worker process and no retries to
reason about: you run it, it finishes, and it tells you what it found. Run it
from the command line with ``python -m app.crawler`` or by calling
``POST /crawl``.

Two backends. ``fixture`` reads saved pages from disk and is what the tests
use, so nothing in the test suite touches the internet. ``crawl4ai`` drives a
real browser against the registered URLs.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from contextlib import asynccontextmanager
import hashlib
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import adapters, netguard, robots
from app.config import get_settings
from app.db import Hardware as HardwareRow, Model as ModelRow, Page, Plan as PlanRow, Source


class CrawlError(RuntimeError):
    """One source could not be fetched. The others still run."""


# --------------------------------------------------------------------------- #
# Page identity
# --------------------------------------------------------------------------- #


def tidy(text: str) -> str:
    """Ignore indentation and line-ending noise when deciding if a page changed."""
    unified = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(" ".join(line.split()) for line in unified.split("\n")).strip()


def fingerprint(text: str) -> str:
    return hashlib.sha256(tidy(text).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Fetching
# --------------------------------------------------------------------------- #


async def fetch_fixture(url: str) -> str:
    """Read a saved page. The filename mirrors the host and path."""
    settings = get_settings()
    parts = urlsplit(url)
    name = (parts.path or "/").strip("/").replace("/", "__") or "index"
    path = Path(settings.fixture_dir) / parts.netloc / f"{name}.md"
    if not path.exists():
        raise CrawlError(f"no saved page at {path}")
    return path.read_text(encoding="utf-8")


@asynccontextmanager
async def browser():
    """Open one browser for the whole run, or nothing if none is needed.

    Starting a browser costs a few seconds, so opening one per page made a
    five-source run take minutes. One browser, reused, makes it seconds.
    """
    if get_settings().crawler != "crawl4ai":
        yield None
        return

    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig
    except ImportError as error:
        raise CrawlError(
            "crawl4ai is not installed. Either 'pip install -r "
            "requirements-crawler.txt' or set LLMFIT_CRAWLER=fixture."
        ) from error

    async with AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False)) as opened:
        yield opened


async def fetch_crawl4ai(url: str, opened=None) -> str:
    """Fetch the page with a real browser and keep the Markdown it produces."""
    try:
        from crawl4ai import CrawlerRunConfig
    except ImportError as error:
        raise CrawlError(
            "crawl4ai is not installed. Either 'pip install -r "
            "requirements-crawler.txt' or set LLMFIT_CRAWLER=fixture."
        ) from error

    settings = get_settings()
    netguard.check(url)
    run = CrawlerRunConfig(page_timeout=settings.crawl_timeout_seconds * 1000)
    try:
        if opened is not None:
            outcome = await opened.arun(url=url, config=run)
        else:
            async with browser() as one_off:
                outcome = await one_off.arun(url=url, config=run)
    except CrawlError:
        raise
    except Exception as error:
        raise CrawlError(f"could not fetch {url}: {error}") from error

    if not getattr(outcome, "success", False):
        raise CrawlError(f"could not fetch {url}: {getattr(outcome, 'error_message', 'unknown')}")

    landed = getattr(outcome, "url", url) or url
    if landed != url:
        netguard.check(landed)  # a redirect is a new request, so check it again

    return str(getattr(outcome, "markdown", "") or "")


async def fetch(url: str, opened=None) -> str:
    settings = get_settings()
    markdown = await (
        fetch_crawl4ai(url, opened) if settings.crawler == "crawl4ai"
        else fetch_fixture(url)
    )
    encoded = markdown.encode("utf-8")
    if len(encoded) > settings.max_page_bytes:
        markdown = encoded[: settings.max_page_bytes].decode("utf-8", errors="ignore")
    return markdown


# --------------------------------------------------------------------------- #
# Saving
# --------------------------------------------------------------------------- #


def _save_rows(session: Session, found) -> None:
    """Write catalog rows, replacing any earlier version of the same slug."""
    for row in found.hardware:
        session.execute(_upsert(HardwareRow, row.model_dump(exclude={"updated_at"})))
    for row in found.models:
        payload = row.model_dump(exclude={"updated_at"})
        payload["suitable_for"] = [w.value for w in row.suitable_for]
        session.execute(_upsert(ModelRow, payload))
    for row in found.plans:
        payload = row.model_dump(exclude={"updated_at"})
        payload["suitable_for"] = [w.value for w in row.suitable_for]
        payload["billing_interval"] = row.billing_interval.value
        session.execute(_upsert(PlanRow, payload))


def _upsert(table, payload: dict):
    """Insert, or overwrite the existing row with the same slug."""
    payload = {**payload, "updated_at": dt.datetime.now(dt.timezone.utc)}
    statement = insert(table).values(**payload)
    return statement.on_conflict_do_update(
        index_elements=["slug"],
        set_={key: statement.excluded[key] for key in payload if key != "slug"},
    )


class Report:
    """What one run did, in the order it happened."""

    def __init__(self) -> None:
        self.visited: list[dict] = []

    @property
    def rows(self) -> int:
        return sum(entry.get("rows_found", 0) for entry in self.visited)

    @property
    def failures(self) -> int:
        return sum(1 for entry in self.visited if entry.get("error"))

    @property
    def skipped(self) -> int:
        return sum(1 for entry in self.visited if entry.get("skipped"))

    def as_dict(self) -> dict:
        return {
            "sources_visited": len(self.visited),
            "catalog_rows_written": self.rows,
            "failures": self.failures,
            "skipped": self.skipped,
            "details": self.visited,
        }


async def crawl_all(session: Session) -> Report:
    """Visit every enabled source once. One failure does not stop the rest."""
    report = Report()
    sources = session.scalars(select(Source).where(Source.enabled.is_(True))).all()
    if not sources:
        return report

    async with browser() as opened:
        await _visit_each(session, sources, opened, report)
    return report


async def _visit_each(session: Session, sources, opened, report: "Report") -> None:
    live = get_settings().crawler == "crawl4ai"

    for source in sources:
        entry: dict = {"url": source.url}

        # .invalid is reserved by RFC 2606 and can never resolve, so these are
        # the bundled example pages. Reporting them as failures every time you
        # crawl for real would be noise about something working as intended.
        if live and (urlsplit(source.url).hostname or "").endswith(".invalid"):
            entry["skipped"] = "an example page, only readable with LLMFIT_CRAWLER=fixture"
            report.visited.append(entry)
            continue

        try:
            # Shape only here: the fixture backend reads a local file, and the
            # crawl4ai backend runs the full check itself just before fetching.
            netguard.check_shape(source.url)
            if get_settings().crawler == "crawl4ai":
                # Only ask about robots.txt when we are really going to visit.
                robots.check(source.url)
            markdown = await fetch(source.url, opened)
        except (netguard.Blocked, robots.Disallowed, CrawlError) as error:
            entry["error"] = str(error)
            report.visited.append(entry)
            continue

        digest = fingerprint(markdown)
        previous = session.scalars(select(Page).where(Page.url == source.url)).first()
        changed = previous is None or previous.content_hash != digest

        try:
            found = adapters.read(
                source.adapter, markdown, source.url, dict(source.config or {})
            )
        except adapters.UnknownAdapter as error:
            entry["error"] = str(error)
            report.visited.append(entry)
            continue
        _save_rows(session, found)

        if previous is None:
            session.add(Page(
                url=source.url, markdown=markdown, content_hash=digest,
                changed=True, rows_found=found.count,
            ))
        else:
            previous.markdown = markdown
            previous.content_hash = digest
            previous.changed = changed
            previous.rows_found = found.count
            previous.fetched_at = dt.datetime.now(dt.timezone.utc)

        entry.update({
            "adapter": source.adapter,
            "changed": changed,
            "rows_found": found.count,
        })
        if found.notes:
            entry["notes"] = found.notes
        report.visited.append(entry)


def run() -> dict:  # pragma: no cover - command line entry point
    from app.db import session_scope

    with session_scope() as session:
        report = asyncio.run(crawl_all(session))
    return report.as_dict()


if __name__ == "__main__":  # pragma: no cover
    import json

    outcome = run()
    print(json.dumps(outcome, indent=2))
    print(
        f"\nVisited {outcome['sources_visited']} source(s), "
        f"wrote {outcome['catalog_rows_written']} catalog row(s), "
        f"{outcome['failures']} failure(s)."
    )
