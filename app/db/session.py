"""Session management and the transaction-local tenant context.

Each request or worker unit gets its own session; a session is never shared
across concurrent tasks. Organization context is set transaction-locally with
``SET LOCAL`` so a pooled connection cannot leak it into the next user's work
(guide sections 7 and 8).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None

TENANT_SETTING = "app.organization_id"


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            future=True,
            connect_args={
                "options": f"-c statement_timeout={settings.db_statement_timeout_ms}"
            },
        )
        _install_tenant_reset(_engine)
    return _engine


def _install_tenant_reset(engine: Engine) -> None:
    """Clear tenant context when a connection returns to the pool.

    ``SET LOCAL`` already ends with the transaction; this is the belt-and-braces
    guard the guide asks for against connection reuse.
    """

    @event.listens_for(engine, "reset")
    def _reset(dbapi_connection, connection_record, reset_state) -> None:  # noqa: ANN001
        try:
            with dbapi_connection.cursor() as cursor:
                cursor.execute(f"SELECT set_config('{TENANT_SETTING}', '', false)")
        except Exception:  # pragma: no cover - connection already broken
            pass


def get_sessionmaker() -> sessionmaker[Session]:
    global _factory
    if _factory is None:
        _factory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _factory


class TenantContextMissing(RuntimeError):
    """Raised when workspace-private work is attempted with no verified context."""


def set_tenant(session: Session, organization_id: uuid.UUID | None) -> None:
    """Apply the verified organization for the current transaction only.

    Row-level security policies fail closed when the setting is empty, so an
    unauthenticated or unscoped transaction simply sees no private rows.
    """
    value = str(organization_id) if organization_id is not None else ""
    session.execute(
        text(f"SELECT set_config('{TENANT_SETTING}', :value, true)"), {"value": value}
    )


def current_tenant(session: Session) -> uuid.UUID | None:
    value = session.execute(
        text(f"SELECT current_setting('{TENANT_SETTING}', true)")
    ).scalar()
    return uuid.UUID(value) if value else None


@contextmanager
def unit_of_work(organization_id: uuid.UUID | None = None) -> Iterator[Session]:
    """One explicit transaction boundary, closed promptly."""
    session = get_sessionmaker()()
    try:
        set_tenant(session, organization_id)
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def repeatable_read(organization_id: uuid.UUID | None = None) -> Iterator[Session]:
    """A single-version read used to select a consistent catalog snapshot.

    Guide section 8 requires that recommendation inputs come from one consistent
    database snapshot before the exact revisions are persisted.
    """
    session = get_sessionmaker()()
    try:
        session.connection(
            execution_options={"isolation_level": "REPEATABLE READ"}
        )
        set_tenant(session, organization_id)
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
