"""Request-scoped dependencies.

Each request gets its own SQLAlchemy session with an explicit transaction
boundary, and the verified organization is applied transaction-locally so a
pooled connection cannot carry it into the next request.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_sessionmaker, set_tenant
from app.security.authz import NotAuthenticated, Principal
from app.services import auth

ORGANIZATION_HEADER = "X-Organization-Id"


def db_session() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def settings() -> Settings:
    return get_settings()


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise NotAuthenticated("a bearer session token is required")
    token = authorization[7:].strip()
    if not token:
        raise NotAuthenticated("a bearer session token is required")
    return token


def current_principal(
    request: Request,
    session: Annotated[Session, Depends(db_session)],
    authorization: Annotated[str | None, Header()] = None,
    x_organization_id: Annotated[str | None, Header()] = None,
) -> Principal:
    """Authenticate, then apply the verified workspace to this transaction."""
    token = _bearer_token(authorization)

    organization_id: uuid.UUID | None = None
    if x_organization_id:
        try:
            organization_id = uuid.UUID(x_organization_id)
        except ValueError as error:
            raise NotAuthenticated("organization header is not a valid identifier") from error

    principal = auth.authenticate(session, token, organization_id)
    # Row-level security fails closed when this is absent, so it is set only
    # after the membership has actually been verified above.
    set_tenant(session, principal.organization_id)
    request.state.principal = principal
    return principal


SessionDep = Annotated[Session, Depends(db_session)]
PrincipalDep = Annotated[Principal, Depends(current_principal)]
SettingsDep = Annotated[Settings, Depends(settings)]


def pagination(
    limit: int | None = None, offset: int = 0
) -> tuple[int, int]:
    """Bounded pagination with a stable maximum page size."""
    configured = get_settings()
    chosen = limit if limit is not None else configured.default_page_size
    chosen = max(1, min(chosen, configured.max_page_size))
    return chosen, max(0, offset)


PaginationDep = Annotated[tuple[int, int], Depends(pagination)]
