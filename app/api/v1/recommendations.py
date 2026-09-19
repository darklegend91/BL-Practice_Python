"""Recommendation endpoints (guide section 9).

The recommendation path never waits for a live crawl; it reads only published
catalog data. A valid calculation with no suitable candidate returns ``200``
with a typed domain status, not a server error.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, Response, status

from app.api.deps import PaginationDep, PrincipalDep, SessionDep
from app.api.ratelimit import enforce_rate_limit
from app.config import get_settings
from app.schemas.common import StrictModel
from app.schemas.result import RecommendationResult
from app.services import idempotency, recommendations, reporting, scenarios

router = APIRouter(prefix="/v1/recommendations", tags=["recommendations"])

ROUTE = "POST /v1/recommendations"


class CalculateRequest(StrictModel):
    scenario_id: uuid.UUID


class RecommendationResponse(StrictModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    created_at: str
    result: RecommendationResult


class RecommendationSummary(StrictModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    status: str
    policy_version: str
    app_version: str
    created_at: str


@router.post("", response_model=RecommendationResponse, status_code=status.HTTP_201_CREATED)
def calculate(
    request: Request,
    body: CalculateRequest,
    principal: PrincipalDep,
    session: SessionDep,
    response: Response,
    idempotency_key: Annotated[str | None, Header()] = None,
):
    """Calculate and store a recommendation against the published catalog."""
    enforce_rate_limit(
        request, "recommendations.write", get_settings().write_rate_limit_per_minute
    )
    organization_id = principal.require_analyst()
    request_body = body.model_dump_json().encode("utf-8")

    if idempotency_key:
        replay = idempotency.look_up(
            session,
            organization_id=organization_id,
            route=ROUTE,
            key=idempotency_key,
            request_body=request_body,
        )
        if replay is not None:
            stored, status_code = replay
            response.status_code = status_code
            return RecommendationResponse.model_validate(stored)

    revision = scenarios.get(session, principal, body.scenario_id)
    run, result = recommendations.calculate_and_save(
        session,
        principal,
        scenario_revision_id=revision.id,
        scenario=scenarios.load_input(revision),
    )
    session.flush()

    payload = RecommendationResponse(
        id=run.id,
        scenario_id=revision.id,
        created_at=result.created_at.isoformat(),
        result=result,
    )

    if idempotency_key:
        idempotency.remember(
            session,
            organization_id=organization_id,
            route=ROUTE,
            key=idempotency_key,
            request_body=request_body,
            outcome=payload.model_dump(mode="json"),
            status_code=status.HTTP_201_CREATED,
        )
    return payload


@router.get("", response_model=list[RecommendationSummary])
def list_runs(principal: PrincipalDep, session: SessionDep, pagination: PaginationDep):
    limit, offset = pagination
    runs = recommendations.list_for_workspace(session, principal, limit=limit, offset=offset)
    return [
        RecommendationSummary(
            id=run.id,
            scenario_id=run.scenario_revision_id,
            status=run.outputs.get("status", "unknown"),
            policy_version=run.policy_version,
            app_version=run.app_version,
            created_at=run.created_at.isoformat(),
        )
        for run in runs
    ]


@router.get("/{run_id}", response_model=RecommendationResponse)
def get_run(run_id: uuid.UUID, principal: PrincipalDep, session: SessionDep):
    """Return the stored result exactly as it was computed."""
    run = recommendations.get(session, principal, run_id)
    result = recommendations.stored_result(run)
    return RecommendationResponse(
        id=run.id,
        scenario_id=run.scenario_revision_id,
        created_at=run.created_at.isoformat(),
        result=result,
    )


@router.get("/{run_id}/export")
def export(
    request: Request,
    run_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    fmt: Annotated[str, Query(pattern="^(json|csv)$", alias="format")] = "json",
):
    enforce_rate_limit(request, "recommendations.export", get_settings().write_rate_limit_per_minute)
    run = recommendations.get(session, principal, run_id)
    result = recommendations.stored_result(run)
    if fmt == "csv":
        return Response(
            content=reporting.to_csv(result),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="recommendation-{run_id}.csv"'
            },
        )
    return reporting.to_json(result)
