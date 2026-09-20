"""Page snapshot identity and change detection (guide section 5).

Text is normalised before hashing so that whitespace churn does not look like a
price change. A changed hash means *review this*; it never proves that a
particular field changed, and an unchanged fetch does not verify any claim.
"""

from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import unicodedata

from app.schemas.common import StrictModel


class PageSnapshot(StrictModel):
    """One immutable collection result."""

    source_url: str
    final_url: str
    http_status: int
    markdown: str
    content_hash: str
    byte_size: int
    fetched_at: dt.datetime
    crawler_version: str
    discovered_links: list[str] = []


def normalize(text: str) -> str:
    """Collapse presentation noise without touching the words themselves."""
    unified = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in unified.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def has_changed(previous_markdown: str | None, current_markdown: str) -> bool:
    if previous_markdown is None:
        return True
    return content_hash(previous_markdown) != content_hash(current_markdown)


def diff(previous_markdown: str, current_markdown: str, context_lines: int = 3) -> str:
    """A readable textual review of what changed between two snapshots."""
    return "\n".join(
        difflib.unified_diff(
            normalize(previous_markdown).splitlines(),
            normalize(current_markdown).splitlines(),
            fromfile="previous snapshot",
            tofile="current snapshot",
            lineterm="",
            n=context_lines,
        )
    )


def change_ratio(previous_markdown: str, current_markdown: str) -> float:
    """How much of the page changed, for ordering the review queue."""
    matcher = difflib.SequenceMatcher(
        None, normalize(previous_markdown), normalize(current_markdown)
    )
    return round(1.0 - matcher.quick_ratio(), 4)
