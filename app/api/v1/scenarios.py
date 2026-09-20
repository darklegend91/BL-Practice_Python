"""Scenario endpoints (guide section 9)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from pydantic import Field

from app.api.deps import PaginationDep, PrincipalDep, SessionDep
from app.schemas.common import StrictModel
from app.schemas.scenario import ScenarioInput
from app.services import scenarios

router = APIRouter(prefix="/v1/scenarios", tags=["scenarios"])


class SaveScenarioRequest(StrictModel):
    label: str = Field(min_length=1, max_length=200)
    scenario: ScenarioInput


class ScenarioResponse(StrictModel):
    id: uuid.UUID
    label: str
    schema_version: str
    preset_version: str
    created_at: str
    scenario: ScenarioInput


class ScenarioPage(StrictModel):
    items: list[ScenarioResponse]
    limit: int
    offset: int


def _response(revision) -> ScenarioResponse:
    return ScenarioResponse(
        id=revision.id,
        label=revision.label,
        schema_version=revision.schema_version,
        preset_version=revision.preset_version,
        created_at=revision.created_at.isoformat(),
        scenario=scenarios.load_input(revision),
    )


@router.post("", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
def save(body: SaveScenarioRequest, principal: PrincipalDep, session: SessionDep):
    revision = scenarios.save(session, principal, label=body.label, scenario=body.scenario)
    return _response(revision)


@router.get("", response_model=ScenarioPage)
def list_scenarios(principal: PrincipalDep, session: SessionDep, pagination: PaginationDep):
    limit, offset = pagination
    found = scenarios.list_for_workspace(session, principal, limit=limit, offset=offset)
    return ScenarioPage(
        items=[_response(revision) for revision in found], limit=limit, offset=offset
    )


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(scenario_id: uuid.UUID, principal: PrincipalDep, session: SessionDep):
    return _response(scenarios.get(session, principal, scenario_id))
