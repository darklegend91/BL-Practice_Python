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
import hashlib
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import netguard
from app.config import get_settings
from app.db import Hardware as HardwareRow, Model as ModelRow, Page, Plan as PlanRow, Source
from app.extract import read_page


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


async def fetch_crawl4ai(url: str) -> str:
    """Fetch the page with a real browser and keep the Markdown it produces."""
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    except ImportError as error:
        raise CrawlError(
            "crawl4ai is not installed. Either 'pip install -r "
            "requirements-crawler.txt' or set LLMFIT_CRAWLER=fixture."
        ) from error

    settings = get_settings()
    netguard.check(url)
    try:
        async with AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False)) as crawler:
            outcome = await crawler.arun(
                url=url,
                config=CrawlerRunConfig(page_timeout=settings.crawl_timeout_seconds * 1000),
            )
    except Exception as error:
        raise CrawlError(f"could not fetch {url}: {error}") from error

    if not getattr(outcome, "success", False):
        raise CrawlError(f"could not fetch {url}: {getattr(outcome, 'error_message', 'unknown')}")

    landed = getattr(outcome, "url", url) or url
    if landed != url:
        netguard.check(landed)  # a redirect is a new request, so check it again

    return str(getattr(outcome, "markdown", "") or "")


async def fetch(url: str) -> str:
    settings = get_settings()
    markdown = await (
        fetch_crawl4ai(url) if settings.crawler == "crawl4ai" else fetch_fixture(url)
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

    def as_dict(self) -> dict:
        return {
            "sources_visited": len(self.visited),
            "catalog_rows_written": self.rows,
            "failures": self.failures,
            "details": self.visited,
        }


async def crawl_all(session: Session) -> Report:
    """Visit every enabled source once. One failure does not stop the rest."""
    report = Report()
    sources = session.scalars(select(Source).where(Source.enabled.is_(True))).all()

    for source in sources:
        entry: dict = {"url": source.url}
        try:
            # Shape only here: the fixture backend reads a local file, and the
            # crawl4ai backend runs the full check itself just before fetching.
            netguard.check_shape(source.url)
            markdown = await fetch(source.url)
        except (netguard.Blocked, CrawlError) as error:
            entry["error"] = str(error)
            report.visited.append(entry)
            continue

        digest = fingerprint(markdown)
        previous = session.scalars(select(Page).where(Page.url == source.url)).first()
        changed = previous is None or previous.content_hash != digest

        found = read_page(markdown, source.url)
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

        entry.update({"changed": changed, "rows_found": found.count})
        report.visited.append(entry)

    return report


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
