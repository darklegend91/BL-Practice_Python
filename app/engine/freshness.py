"""Age checks over reviewed evidence (guide section 5).

Fetch age and review age are different things; only review age decides whether a
fact may support a confident recommendation.
"""

from __future__ import annotations

import datetime as dt


def review_age_days(reviewed_at: dt.datetime | None, as_of: dt.datetime) -> int | None:
    if reviewed_at is None:
        return None
    if reviewed_at.tzinfo is None:
        reviewed_at = reviewed_at.replace(tzinfo=dt.timezone.utc)
    return max((as_of - reviewed_at).days, 0)


def is_stale(reviewed_at: dt.datetime | None, as_of: dt.datetime, max_age_days: int) -> bool:
    """Never reviewed counts as stale; absence of a review is not freshness."""
    age = review_age_days(reviewed_at, as_of)
    return age is None or age > max_age_days
