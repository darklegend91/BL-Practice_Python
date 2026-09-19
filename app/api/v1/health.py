"""Health endpoints (guide sections 9 and 12).

Liveness reports the process. Readiness reports dependencies. Neither says
anything about catalog freshness: a healthy API does not imply a fresh catalog,
and those states are shown separately.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import SessionDep
from app.version import APP_VERSION

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict:
    return {"status": "live", "app_version": APP_VERSION}


@router.get("/health/ready")
def ready(session: SessionDep, response: Response) -> dict:
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": "unavailable"}
    return {"status": "ready", "database": "ok"}
