"""One PostgreSQL database, five tables, no row-level security, no tenants.

* ``sources``  - the pages the crawler should visit.
* ``pages``    - what it found last time, as Markdown.
* ``hardware`` / ``models`` / ``plans`` - the catalog the engine reads.

Money is ``NUMERIC``, never float. Timestamps carry a timezone. A ``NULL``
means unknown and the engine treats it that way.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Integer, MetaData, Numeric, String, Text,
    UniqueConstraint, create_engine, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings

MONEY = Numeric(14, 4)
AMOUNT = Numeric(12, 3)

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


def _updated() -> Mapped[dt.datetime]:
    return mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Source(Base):
    """A page the crawler visits. Add one, run the crawler, and it appears."""

    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = _pk()
    url: Mapped[str] = mapped_column(Text, unique=True)
    label: Mapped[str] = mapped_column(String(200), server_default=text("''"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[dt.datetime] = _updated()


class Page(Base):
    """The last Markdown the crawler got from a source, and when."""

    __tablename__ = "pages"

    id: Mapped[uuid.UUID] = _pk()
    url: Mapped[str] = mapped_column(Text, unique=True)
    markdown: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    changed: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    rows_found: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    fetched_at: Mapped[dt.datetime] = _updated()


class Hardware(Base):
    __tablename__ = "hardware"

    id: Mapped[uuid.UUID] = _pk()
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    vram_gb: Mapped[float | None] = mapped_column(AMOUNT, nullable=True)
    ram_gb: Mapped[float | None] = mapped_column(AMOUNT, nullable=True)
    active_watts: Mapped[float | None] = mapped_column(AMOUNT, nullable=True)
    idle_watts: Mapped[float | None] = mapped_column(AMOUNT, nullable=True)
    price: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    region: Mapped[str | None] = mapped_column(String(2), nullable=True)
    setup_hours: Mapped[float] = mapped_column(AMOUNT, server_default=text("2"))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[dt.datetime] = _updated()

    __table_args__ = (
        CheckConstraint("role in ('gpu','system')", name="role_known"),
        CheckConstraint("price is null or price >= 0", name="price_not_negative"),
    )


class Model(Base):
    """A downloadable model you would run yourself."""

    __tablename__ = "models"

    id: Mapped[uuid.UUID] = _pk()
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    params_b: Mapped[float | None] = mapped_column(AMOUNT, nullable=True)
    quantization: Mapped[str | None] = mapped_column(String(40), nullable=True)
    weights_gb: Mapped[float | None] = mapped_column(AMOUNT, nullable=True)
    max_context: Mapped[int | None] = mapped_column(Integer, nullable=True)
    layers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kv_heads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    head_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commercial_use: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    suitable_for: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    setup_hours: Mapped[float] = mapped_column(AMOUNT, server_default=text("3"))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[dt.datetime] = _updated()


class Plan(Base):
    """A paid subscription you would buy instead."""

    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = _pk()
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    provider: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    billing_interval: Mapped[str] = mapped_column(String(10), server_default=text("'monthly'"))
    min_seats: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    regions: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    max_context: Mapped[int | None] = mapped_column(Integer, nullable=True)
    messages_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supports_api: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    commercial_use: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    suitable_for: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    setup_hours: Mapped[float] = mapped_column(AMOUNT, server_default=text("1"))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[dt.datetime] = _updated()

    __table_args__ = (
        CheckConstraint(
            "billing_interval in ('monthly','annual')", name="billing_interval_known"
        ),
        CheckConstraint("min_seats >= 1", name="min_seats_at_least_one"),
        UniqueConstraint("provider", "name"),
    )


_engine = None
_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True, future=True)
    return _engine


def get_sessionmaker():
    global _factory
    if _factory is None:
        _factory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """One transaction: commit on success, roll back on any error."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: a session per request."""
    with session_scope() as session:
        yield session
