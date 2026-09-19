"""Session endpoints (guide section 9)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request, status
from pydantic import Field

from app.api.deps import SessionDep
from app.api.ratelimit import enforce_rate_limit
from app.config import get_settings
from app.schemas.common import StrictModel
from app.services import auth

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginRequest(StrictModel):
    # Bounded, not format-validated: login looks the identifier up, and a
    # rejection here would reveal an opinion about which addresses exist.
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(StrictModel):
    token: str
    expires_at: str


@router.post("/login", response_model=LoginResponse)
def login(request: Request, body: LoginRequest, session: SessionDep) -> LoginResponse:
    enforce_rate_limit(
        request, "auth.login", get_settings().login_rate_limit_per_minute
    )
    token, record = auth.log_in(session, email=body.email, password=body.password)
    return LoginResponse(token=token, expires_at=record.expires_at.isoformat())


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    session: SessionDep, authorization: Annotated[str | None, Header()] = None
) -> None:
    if authorization and authorization.lower().startswith("bearer "):
        auth.log_out(session, authorization[7:].strip())
