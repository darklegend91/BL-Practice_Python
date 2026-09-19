"""Review tasks raised by a page change (guide section 5).

A changed page produces a review task. It never publishes anything by itself,
and it does not assert which field changed.
"""

from __future__ import annotations

import datetime as dt
import enum

from app.collection.snapshots import change_ratio, diff
from app.schemas.common import StrictModel


class ChangeOutcome(str, enum.Enum):
    FIRST_SNAPSHOT = "first_snapshot"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class ReviewTask(StrictModel):
    source_url: str
    outcome: ChangeOutcome
    detected_at: dt.datetime
    change_ratio: float = 0.0
    diff_text: str = ""
    note: str = ""


def evaluate(
    source_url: str,
    previous_markdown: str | None,
    current_markdown: str,
    detected_at: dt.datetime,
) -> ReviewTask:
    if previous_markdown is None:
        return ReviewTask(
            source_url=source_url,
            outcome=ChangeOutcome.FIRST_SNAPSHOT,
            detected_at=detected_at,
            note="First snapshot for this source. An editor must enter typed values.",
        )

    difference = diff(previous_markdown, current_markdown)
    if not difference:
        return ReviewTask(
            source_url=source_url,
            outcome=ChangeOutcome.UNCHANGED,
            detected_at=detected_at,
            note=(
                "Content is unchanged. This confirms the page was fetched; it does "
                "not independently verify any structured claim."
            ),
        )

    return ReviewTask(
        source_url=source_url,
        outcome=ChangeOutcome.CHANGED,
        detected_at=detected_at,
        change_ratio=change_ratio(previous_markdown, current_markdown),
        diff_text=difference,
        note=(
            "The page changed and needs review. A change does not prove that a "
            "particular price or specification changed."
        ),
    )
