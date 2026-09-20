"""Deterministic ordering of feasible candidates (guide section 6, step 7).

Ranking uses the user's selected priority with documented tie-breakers, so the
same scenario, catalog and policy always yield the same order.
"""

from __future__ import annotations

from decimal import Decimal

from app.schemas.common import DeploymentKind, Priority
from app.schemas.result import CandidateResult

TIE_BREAKERS = (
    "lower total horizon cash cost",
    "lower upfront cash cost",
    "fewer setup hours",
    "candidate identifier, ascending",
)

_OFFLINE_RANK = {
    DeploymentKind.EXISTING_LOCAL: 0,
    DeploymentKind.LOCAL_UPGRADE: 1,
    DeploymentKind.NEW_LOCAL_MACHINE: 2,
    DeploymentKind.HOSTED_SUBSCRIPTION: 3,
}

_HUGE = Decimal("1e18")


def _horizon(candidate: CandidateResult) -> Decimal:
    return candidate.cost.horizon_total.amount if candidate.cost else _HUGE


def _upfront(candidate: CandidateResult) -> Decimal:
    return candidate.cost.upfront.amount if candidate.cost else _HUGE


def _setup(candidate: CandidateResult) -> Decimal:
    return candidate.setup_hours if candidate.setup_hours is not None else _HUGE


def sort_key(candidate: CandidateResult, priority: Priority) -> tuple:
    tail = (_horizon(candidate), _upfront(candidate), _setup(candidate), candidate.candidate_id)
    if priority is Priority.LOWEST_CASH_COST:
        return tail
    if priority is Priority.LEAST_SETUP:
        return (_setup(candidate), *tail)
    return (_OFFLINE_RANK[candidate.deployment], *tail)


def rank(candidates: list[CandidateResult], priority: Priority) -> list[CandidateResult]:
    return sorted(candidates, key=lambda candidate: sort_key(candidate, priority))
