"""Declarative base and shared column conventions (guide section 8)."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, DateTime, MetaData, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}

# Tables holding data private to one workspace. Row-level security is enabled on
# each of these by the migration, and every row carries organization_id.
TENANT_TABLES: tuple[str, ...] = (
    "memberships",
    "inventory_items",
    "scenario_revisions",
    "recommendation_runs",
    "recommendation_evidence",
    "idempotency_keys",
)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )


def utc_column(**kwargs) -> Mapped[dt.datetime]:
    return mapped_column(DateTime(timezone=True), **kwargs)


def nonnegative(column_name: str) -> CheckConstraint:
    return CheckConstraint(f"{column_name} >= 0", name=f"{column_name}_nonnegative")
