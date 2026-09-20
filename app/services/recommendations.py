"""Calculating and storing recommendations (guide sections 6, 8 and 9).

The catalog is read inside one repeatable-read transaction, the pure engine is
called outside any database work, and the exact revisions used are persisted
alongside the immutable result.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog import snapshot_builder
from app.db.models import AuditEvent, RecommendationEvidence, RecommendationRun
from app.engine.policy import DEFAULT_POLICY, Policy
from app.engine.recommend import recommend
from app.schemas.result import RecommendationResult
from app.schemas.scenario import ScenarioInput, expand
from app.security.authz import Principal
from app.services.scenarios import NotFound
from app.version import APP_VERSION


def calculate_and_save(
    session: Session,
    principal: Principal,
    *,
    scenario_revision_id: uuid.UUID,
    scenario: ScenarioInput,
    policy: Policy = DEFAULT_POLICY,
    now: dt.datetime | None = None,
) -> tuple[RecommendationRun, RecommendationResult]:
    """Run the engine and persist the result immutably."""
    organization_id = principal.require_analyst()
    expanded = expand(scenario)

    # One consistent set of published revisions; the caller holds the
    # repeatable-read transaction that this session belongs to.
    snapshot = snapshot_builder.build(
        session, currency=scenario.currency, region=scenario.region
    )

    result = recommend(expanded, snapshot, policy, as_of=now, created_at=now)

    run = RecommendationRun(
        organization_id=organization_id,
        scenario_revision_id=scenario_revision_id,
        created_by=principal.user_id,
        policy_version=result.policy_version,
        app_version=APP_VERSION,
        catalog_snapshot_id=result.catalog_snapshot_id,
        inputs=expanded.model_dump(mode="json"),
        outputs=result.model_dump(mode="json"),
    )
    session.add(run)
    session.flush()

    # Provenance: the exact revisions this decision rests on cannot be deleted.
    for revision_id in dict.fromkeys(result.catalog_revision_ids):
        session.add(
            RecommendationEvidence(
                organization_id=organization_id,
                run_id=run.id,
                revision_id=revision_id,
            )
        )

    session.add(
        AuditEvent(
            actor_id=principal.user_id,
            organization_id=organization_id,
            action="recommendation.created",
            target_type="recommendation_run",
            target_id=run.id,
            details={"status": result.status.value, "policy": result.policy_version},
        )
    )
    return run, result


def get(session: Session, principal: Principal, run_id: uuid.UUID) -> RecommendationRun:
    """Fetch a stored result. This never recomputes against today's prices."""
    organization_id = principal.require_member()
    run = session.scalars(
        select(RecommendationRun).where(
            RecommendationRun.id == run_id,
            RecommendationRun.organization_id == organization_id,
        )
    ).first()
    if run is None:
        raise NotFound(f"recommendation {run_id} was not found")
    return run


def stored_result(run: RecommendationRun) -> RecommendationResult:
    return RecommendationResult.model_validate(run.outputs)


def list_for_workspace(
    session: Session, principal: Principal, *, limit: int, offset: int
) -> list[RecommendationRun]:
    organization_id = principal.require_member()
    return list(
        session.scalars(
            select(RecommendationRun)
            .where(RecommendationRun.organization_id == organization_id)
            .order_by(RecommendationRun.created_at.desc(), RecommendationRun.id)
            .limit(limit)
            .offset(offset)
        ).all()
    )
