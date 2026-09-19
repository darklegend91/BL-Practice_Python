"""Saved scenarios (guide section 9).

A scenario revision is immutable; changing inputs creates a new revision so a
historical result always refers to the exact inputs it was computed from.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ScenarioRevision
from app.schemas.scenario import ScenarioInput
from app.security.authz import Forbidden, Principal
from app.version import PRESET_VERSION, SCENARIO_SCHEMA_VERSION


class NotFound(Exception):
    """The record does not exist, or does not belong to this workspace.

    Both cases raise the same error so existence is not revealed across
    workspaces (guide section 9).
    """


def save(
    session: Session, principal: Principal, *, label: str, scenario: ScenarioInput
) -> ScenarioRevision:
    organization_id = principal.require_analyst()
    revision = ScenarioRevision(
        organization_id=organization_id,
        created_by=principal.user_id,
        label=label,
        schema_version=SCENARIO_SCHEMA_VERSION,
        preset_version=PRESET_VERSION,
        inputs=scenario.model_dump(mode="json"),
    )
    session.add(revision)
    session.add(
        AuditEvent(
            actor_id=principal.user_id,
            organization_id=organization_id,
            action="scenario.saved",
            target_type="scenario_revision",
            details={"label": label},
        )
    )
    session.flush()
    return revision


def get(session: Session, principal: Principal, scenario_id: uuid.UUID) -> ScenarioRevision:
    organization_id = principal.require_member()
    revision = session.scalars(
        select(ScenarioRevision).where(
            ScenarioRevision.id == scenario_id,
            ScenarioRevision.organization_id == organization_id,
        )
    ).first()
    if revision is None:
        raise NotFound(f"scenario {scenario_id} was not found")
    return revision


def load_input(revision: ScenarioRevision) -> ScenarioInput:
    return ScenarioInput.model_validate(revision.inputs)


def list_for_workspace(
    session: Session, principal: Principal, *, limit: int, offset: int
) -> list[ScenarioRevision]:
    organization_id = principal.require_member()
    return list(
        session.scalars(
            select(ScenarioRevision)
            .where(ScenarioRevision.organization_id == organization_id)
            .order_by(ScenarioRevision.created_at.desc(), ScenarioRevision.id)
            .limit(limit)
            .offset(offset)
        ).all()
    )
