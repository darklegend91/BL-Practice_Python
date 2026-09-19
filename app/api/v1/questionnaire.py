"""The questionnaire endpoint (guide section 9)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import PrincipalDep
from app.schemas.questionnaire import Questionnaire, build_questionnaire

router = APIRouter(prefix="/v1", tags=["questionnaire"])


@router.get("/questionnaire", response_model=Questionnaire)
def questionnaire(principal: PrincipalDep) -> Questionnaire:
    """Options, units, ranges and the preset version currently in force."""
    principal.require_member()
    return build_questionnaire()
