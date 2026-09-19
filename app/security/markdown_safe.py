"""Collected page content is untrusted (guide section 11).

Markdown gathered from a vendor page is never executed or rendered as HTML by
the review application. It is escaped to plain text before display.
"""

from __future__ import annotations

import html

MAX_DISPLAY_CHARS = 200_000


def as_escaped_text(markdown: str, limit: int = MAX_DISPLAY_CHARS) -> str:
    """Escape collected content for display and bound its size."""
    clipped = markdown[:limit]
    return html.escape(clipped, quote=True)


def excerpt_around(markdown: str, needle: str, window: int = 240) -> str:
    """A short supporting excerpt for an evidence claim, escaped for display.

    Uses plain string search - no regular expressions, in line with the
    extraction restriction in guide section 1.
    """
    position = markdown.find(needle)
    if position < 0:
        return ""
    start = max(0, position - window // 2)
    end = min(len(markdown), position + len(needle) + window // 2)
    return as_escaped_text(markdown[start:end])
