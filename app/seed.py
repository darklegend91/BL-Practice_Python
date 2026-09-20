"""Registers the example sources so there is something to crawl.

Run it once with ``python -m app.seed``, then run the crawler. It only adds
sources; the catalog itself is filled by the crawler, exactly as it would be
for a real page.

The example pages describe invented products at ``.invalid`` addresses, which
can never resolve. They exist so the app works end to end before you have any
real sources of your own.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db import Source, session_scope

EXAMPLE_SOURCES = [
    ("https://sample-vendor.example.invalid/gpus", "Example hardware prices"),
    ("https://sample-models.example.invalid/open-models", "Example downloadable models"),
    ("https://sample-host.example.invalid/plans", "Example subscription plans"),
]


def add_examples(session) -> int:
    """Add any example source that is not registered yet. Safe to run twice."""
    added = 0
    for url, label in EXAMPLE_SOURCES:
        if session.scalars(select(Source).where(Source.url == url)).first() is None:
            session.add(Source(url=url, label=label))
            added += 1
    return added


def main() -> None:  # pragma: no cover - command line entry point
    with session_scope() as session:
        added = add_examples(session)
    print(f"Added {added} example source(s).")
    print("Now run: python -m app.crawler")


if __name__ == "__main__":  # pragma: no cover
    main()
