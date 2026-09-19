"""Local sessions (guide section 11).

The opaque token is returned once and never stored. Authorization decisions are
made here, in the service layer, so worker and import paths use the same rules.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.config import get_settings
from app.db.models import AuditEvent, Membership, Session, User
from app.db.session import set_tenant
from app.schemas.common import utc_now
from app.security.authz import NotAuthenticated, PlatformRole, Principal, WorkspaceRole
from app.security.passwords import hash_password, needs_rehash, verify_password
from app.security.tokens import digest_token, issue_token


class AuthenticationFailed(Exception):
    """Wrong credentials, a disabled account, or an expired session.

    The message is deliberately identical in every case so it cannot be used to
    discover which email addresses exist.
    """

    def __init__(self) -> None:
        super().__init__("invalid credentials")


def create_user(
    session: DbSession,
    *,
    email: str,
    display_name: str,
    password: str,
    platform_role: PlatformRole = PlatformRole.NONE,
) -> User:
    user = User(
        email=email.strip().lower(),
        display_name=display_name,
        password_hash=hash_password(password),
        platform_role=platform_role.value,
    )
    session.add(user)
    session.flush()
    return user


def log_in(session: DbSession, *, email: str, password: str) -> tuple[str, Session]:
    """Return the one-time token and its stored session row."""
    user = session.scalars(select(User).where(User.email == email.strip().lower())).first()
    if user is None or not user.is_active:
        # Still spend the hashing time so timing does not reveal the account.
        verify_password("$argon2id$v=19$m=65536,t=3,p=4$" + "A" * 22 + "$" + "A" * 43, password)
        raise AuthenticationFailed()
    if not verify_password(user.password_hash, password):
        raise AuthenticationFailed()
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    settings = get_settings()
    token, token_digest = issue_token()
    record = Session(
        user_id=user.id,
        token_digest=token_digest,
        expires_at=utc_now() + dt.timedelta(seconds=settings.session_ttl_seconds),
    )
    session.add(record)
    session.add(
        AuditEvent(
            actor_id=user.id, action="auth.login", target_type="session", details={}
        )
    )
    session.flush()
    return token, record


def log_out(session: DbSession, token: str) -> None:
    record = session.scalars(
        select(Session).where(Session.token_digest == digest_token(token))
    ).first()
    if record is not None and record.revoked_at is None:
        record.revoked_at = utc_now()
        session.add(
            AuditEvent(
                actor_id=record.user_id,
                action="auth.logout",
                target_type="session",
                target_id=record.id,
                details={},
            )
        )


def authenticate(
    session: DbSession, token: str, organization_id: uuid.UUID | None = None
) -> Principal:
    """Resolve an opaque token into a verified principal.

    Memberships are themselves workspace-private, so the requested workspace is
    applied to the transaction *before* the membership is read. Row security
    then returns the row only if it really belongs to that workspace, and the
    user identity is checked here as well. A request that names no workspace, or
    names one the user does not belong to, yields a principal with no workspace
    role at all, and workspace routes refuse it.
    """
    record = session.scalars(
        select(Session).where(Session.token_digest == digest_token(token))
    ).first()
    if record is None or record.revoked_at is not None or record.expires_at <= utc_now():
        raise NotAuthenticated("session is invalid or expired")

    user = session.get(User, record.user_id)
    if user is None or not user.is_active:
        raise NotAuthenticated("account is not active")

    workspace_role: WorkspaceRole | None = None
    if organization_id is not None:
        set_tenant(session, organization_id)
        membership = session.scalars(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.organization_id == organization_id,
            )
        ).first()
        if membership is not None:
            workspace_role = WorkspaceRole(membership.role)
        else:
            # Not a member: drop the context again so nothing private is visible.
            set_tenant(session, None)

    return Principal(
        user_id=user.id,
        organization_id=organization_id if workspace_role else None,
        workspace_role=workspace_role,
        platform_role=PlatformRole(user.platform_role),
    )
