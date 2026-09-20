"""Result export (guide sections 9 and 11).

JSON export is the stored result verbatim. CSV export flattens the comparison
and neutralises any user-controlled string so a spreadsheet cannot treat it as
a formula.
"""

from __future__ import annotations

import csv
import io

from app.schemas.result import CandidateResult, RecommendationResult
from app.security.csv_safe import neutralize

CSV_COLUMNS = [
    "candidate_id",
    "label",
    "deployment",
    "outcome",
    "evidence_quality",
    "currency",
    "upfront",
    "horizon_total",
    "optional_time_cost",
    "setup_hours",
    "blocking_reasons",
    "uncertainty_reasons",
]


def to_json(result: RecommendationResult) -> dict:
    return result.model_dump(mode="json")


def _row(candidate: CandidateResult, outcome: str) -> list:
    blocking = ";".join(code.value for code in candidate.blocking_reasons)
    uncertainty = ";".join(
        finding.code.value for finding in candidate.findings if not finding.blocking
    )
    cost = candidate.cost
    return [
        neutralize(candidate.candidate_id),
        neutralize(candidate.label),
        candidate.deployment.value,
        outcome,
        candidate.evidence_quality.value,
        cost.currency if cost else "",
        str(cost.upfront.amount) if cost else "",
        str(cost.horizon_total.amount) if cost else "",
        str(cost.optional_time_cost.amount) if cost and cost.optional_time_cost else "",
        str(candidate.setup_hours) if candidate.setup_hours is not None else "",
        neutralize(blocking),
        neutralize(uncertainty),
    ]


def to_csv(result: RecommendationResult) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    if result.selected is not None:
        writer.writerow(_row(result.selected, "selected"))
    for candidate in result.alternatives:
        writer.writerow(_row(candidate, "alternative"))
    for candidate in result.uncertain:
        writer.writerow(_row(candidate, "uncertain"))
    for candidate in result.ruled_out:
        writer.writerow(_row(candidate, "ruled_out"))
    return buffer.getvalue()
