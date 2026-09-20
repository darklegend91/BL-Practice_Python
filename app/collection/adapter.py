"""The collection boundary.

Two backends implement one interface so the deterministic test suite never
touches a live vendor site (guide section 13):

``FixtureBackend``  reads saved pages from disk.
``Crawl4AIBackend`` drives Crawl4AI's default Markdown generator.

Application code here performs no CSS-selector, XPath or regular-expression
extraction; it stores the Markdown that Crawl4AI returns and leaves structured
values to a human editor (guide section 1). Crawl4AI's own browser and
HTML-to-Markdown internals are a third-party dependency and this module makes no
claim about how they work internally.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from app.collection.snapshots import PageSnapshot, content_hash
from app.config import get_settings
from app.security.net_guard import check_url

FIXTURE_VERSION = "fixture-backend/1"


class CollectionError(RuntimeError):
    """A collection attempt failed. Transient unless marked permanent."""

    def __init__(self, message: str, *, permanent: bool = False) -> None:
        super().__init__(message)
        self.permanent = permanent


class CollectionBackend(Protocol):
    version: str

    async def fetch(self, url: str, *, allowed_hosts: list[str], timeout_seconds: int,
                    max_bytes: int) -> PageSnapshot: ...


def _snapshot(
    url: str,
    final_url: str,
    markdown: str,
    status: int,
    version: str,
    links: list[str],
    max_bytes: int,
) -> PageSnapshot:
    encoded = markdown.encode("utf-8")
    if len(encoded) > max_bytes:
        # Bounded snapshots: the configured maximum is a hard stop, not a hint.
        encoded = encoded[:max_bytes]
        markdown = encoded.decode("utf-8", errors="ignore")
    return PageSnapshot(
        source_url=url,
        final_url=final_url,
        http_status=status,
        markdown=markdown,
        content_hash=content_hash(markdown),
        byte_size=len(encoded),
        fetched_at=dt.datetime.now(dt.timezone.utc),
        crawler_version=version,
        discovered_links=links,
    )


class FixtureBackend:
    """Serves saved pages from disk, keyed by host and path."""

    version = FIXTURE_VERSION

    def __init__(self, directory: str | Path | None = None) -> None:
        self.directory = Path(directory or get_settings().crawl_fixture_dir)

    def _path_for(self, url: str) -> Path:
        parts = urlsplit(url)
        name = (parts.path or "/").strip("/").replace("/", "__") or "index"
        return self.directory / parts.netloc / f"{name}.md"

    async def fetch(
        self, url: str, *, allowed_hosts: list[str], timeout_seconds: int, max_bytes: int
    ) -> PageSnapshot:
        path = self._path_for(url)
        if not path.exists():
            raise CollectionError(f"no saved page for {url}", permanent=True)
        markdown = path.read_text(encoding="utf-8")
        return _snapshot(url, url, markdown, 200, self.version, [], max_bytes)


class Crawl4AIBackend:
    """Collects a page with Crawl4AI's default Markdown generator.

    Crawl4AI is imported lazily so that the API process, the test suite and a
    development machine without a browser installation all work without it.
    """

    version = "crawl4ai-backend/1"

    async def fetch(
        self, url: str, *, allowed_hosts: list[str], timeout_seconds: int, max_bytes: int
    ) -> PageSnapshot:
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
        except ImportError as error:  # pragma: no cover - optional dependency
            raise CollectionError(
                "crawl4ai is not installed; install the 'collect' extra or use the "
                "fixture backend",
                permanent=True,
            ) from error

        check_url(url, allowed_hosts)

        browser = BrowserConfig(headless=True, verbose=False)
        run = CrawlerRunConfig(page_timeout=timeout_seconds * 1000)
        try:
            async with AsyncWebCrawler(config=browser) as crawler:
                outcome = await crawler.arun(url=url, config=run)
        except Exception as error:  # pragma: no cover - needs a live browser
            raise CollectionError(f"collection failed for {url}: {error}") from error

        if not getattr(outcome, "success", False):
            raise CollectionError(
                f"collection failed for {url}: {getattr(outcome, 'error_message', 'unknown')}"
            )

        final_url = getattr(outcome, "url", url) or url
        # A redirect is a new request and is checked again before it is trusted.
        if final_url != url:
            check_url(final_url, allowed_hosts)

        markdown = str(getattr(outcome, "markdown", "") or "")
        links = _links_from(outcome)
        return _snapshot(
            url, final_url, markdown, getattr(outcome, "status_code", 200) or 200,
            self.version, links, max_bytes,
        )


def _links_from(outcome: object) -> list[str]:
    """Read Crawl4AI's returned link list without parsing any HTML ourselves."""
    links = getattr(outcome, "links", None)
    if not isinstance(links, dict):
        return []
    found: list[str] = []
    for group in ("internal", "external"):
        for entry in links.get(group, []) or []:
            href = entry.get("href") if isinstance(entry, dict) else entry
            if isinstance(href, str):
                found.append(href)
    return found


def get_backend(name: str | None = None) -> CollectionBackend:
    chosen = name or get_settings().crawl_backend
    if chosen == "crawl4ai":
        return Crawl4AIBackend()
    return FixtureBackend()
