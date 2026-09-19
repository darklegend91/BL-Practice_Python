"""Relational mappings for the tables listed in guide section 8.

Conventions applied throughout:

* UUID primary keys and explicit foreign keys.
* ``TIMESTAMPTZ`` for every timestamp; units are named in the column.
* ``NUMERIC`` with documented precision for money; never float.
* ``organization_id`` on every private business record.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    CheckConstraint,
    Enum as SAEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, nonnegative, utc_column, uuid_pk
from app.schemas.common import BillingInterval, ReviewStatus

MONEY = Numeric(18, 4)
"""Documented money precision: 18 significant digits, 4 decimal places."""

QUANTITY = Numeric(12, 3)


def _uuid_fk(target: str, **kwargs) -> Mapped[uuid.UUID]:
    return mapped_column(PgUUID(as_uuid=True), ForeignKey(target, ondelete="RESTRICT"), **kwargs)


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(Text)
    """Argon2id encoded hash. The plaintext password is never stored or logged."""
    platform_role: Mapped[str] = mapped_column(String(40), server_default=text("'none'"))
    """Platform catalog role: none | catalog_editor | catalog_reviewer | catalog_admin."""
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))

    __table_args__ = (
        CheckConstraint(
            "platform_role in ('none','catalog_editor','catalog_reviewer','catalog_admin')",
            name="platform_role_known",
        ),
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = _uuid_fk("users.id", index=True)
    token_digest: Mapped[str] = mapped_column(String(128), unique=True)
    """Only the digest is stored; the opaque token itself is never persisted."""
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))
    expires_at: Mapped[dt.datetime] = utc_column()
    revoked_at: Mapped[dt.datetime | None] = utc_column(nullable=True)

    user: Mapped[User] = relationship()

    __table_args__ = (Index("ix_sessions_expires_at", "expires_at"),)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), unique=True)
    default_region: Mapped[str] = mapped_column(String(2))
    default_currency: Mapped[str] = mapped_column(String(3))
    default_electricity_tariff: Mapped[float | None] = mapped_column(MONEY, nullable=True)
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = _uuid_fk("organizations.id", index=True)
    user_id: Mapped[uuid.UUID] = _uuid_fk("users.id", index=True)
    role: Mapped[str] = mapped_column(String(20))
    """Workspace role: owner | analyst | viewer."""
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id"),
        CheckConstraint("role in ('owner','analyst','viewer')", name="role_known"),
    )


# --------------------------------------------------------------------------- #
# Collection
# --------------------------------------------------------------------------- #


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = uuid_pk()
    url: Mapped[str] = mapped_column(Text, unique=True)
    allowed_hosts: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    category: Mapped[str] = mapped_column(String(40))
    """manufacturer | retailer | publisher | provider_plan."""
    owner: Mapped[str] = mapped_column(String(200))
    refresh_interval_seconds: Mapped[int] = mapped_column(Integer)
    max_page_bytes: Mapped[int] = mapped_column(Integer)
    timeout_seconds: Mapped[int] = mapped_column(Integer)
    crawl_permission_notes: Mapped[str] = mapped_column(Text, server_default=text("''"))
    enabled: Mapped[bool] = mapped_column(server_default=text("true"))
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))

    __table_args__ = (
        CheckConstraint(
            "category in ('manufacturer','retailer','publisher','provider_plan')",
            name="category_known",
        ),
        nonnegative("refresh_interval_seconds"),
        nonnegative("max_page_bytes"),
        nonnegative("timeout_seconds"),
    )


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = _uuid_fk("sources.id", index=True)
    state: Mapped[str] = mapped_column(String(20), server_default=text("'queued'"))
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    """Source plus schedule slot, so two schedulers cannot enqueue one refresh twice."""
    run_after: Mapped[dt.datetime] = utc_column(server_default=text("now()"))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, server_default=text("5"))
    lease_token: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    lease_expires_at: Mapped[dt.datetime | None] = utc_column(nullable=True)
    heartbeat_at: Mapped[dt.datetime | None] = utc_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))
    updated_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))

    __table_args__ = (
        CheckConstraint(
            "state in ('queued','running','succeeded','failed')", name="state_known"
        ),
        nonnegative("attempts"),
        Index("ix_crawl_jobs_due", "state", "run_after"),
    )


class SourceSnapshot(Base):
    __tablename__ = "source_snapshots"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = _uuid_fk("sources.id", index=True)
    fetched_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))
    final_url: Mapped[str] = mapped_column(Text)
    http_status: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    markdown: Mapped[str] = mapped_column(Text)
    """Bounded Markdown. Treated as untrusted content everywhere it is displayed."""
    byte_size: Mapped[int] = mapped_column(Integer)
    crawler_version: Mapped[str] = mapped_column(String(80))

    __table_args__ = (
        # At-least-once execution: one snapshot per source per content version.
        UniqueConstraint("source_id", "content_hash", "fetched_at"),
        Index("ix_source_snapshots_history", "source_id", "fetched_at"),
        nonnegative("byte_size"),
    )


# --------------------------------------------------------------------------- #
# Catalog
# --------------------------------------------------------------------------- #


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[str] = mapped_column(String(20))
    """hardware | model | plan."""
    slug: Mapped[str] = mapped_column(String(200))
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("kind", "slug"),
        CheckConstraint("kind in ('hardware','model','plan')", name="kind_known"),
        Index("ix_catalog_items_kind", "kind"),
    )


class CatalogRevision(Base):
    __tablename__ = "catalog_revisions"

    id: Mapped[uuid.UUID] = uuid_pk()
    item_id: Mapped[uuid.UUID] = _uuid_fk("catalog_items.id", index=True)
    schema_version: Mapped[str] = mapped_column(String(40))
    attributes: Mapped[dict] = mapped_column(JSONB)
    """Validated typed attributes; the Pydantic contract is the source of truth."""
    review_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, name="review_status", values_callable=lambda e: [m.value for m in e])
    )
    author_id: Mapped[uuid.UUID] = _uuid_fk("users.id")
    lock_version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    """Optimistic check: editing a draft someone else changed returns a conflict."""
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))
    submitted_at: Mapped[dt.datetime | None] = utc_column(nullable=True)
    published_at: Mapped[dt.datetime | None] = utc_column(nullable=True)
    superseded_at: Mapped[dt.datetime | None] = utc_column(nullable=True)
    specs_reviewed_at: Mapped[dt.datetime | None] = utc_column(nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(review_status <> 'published') or (published_at is not null)",
            name="published_has_timestamp",
        ),
        Index("ix_catalog_revisions_status", "item_id", "review_status"),
    )


class EvidenceClaim(Base):
    __tablename__ = "evidence_claims"

    id: Mapped[uuid.UUID] = uuid_pk()
    revision_id: Mapped[uuid.UUID] = _uuid_fk("catalog_revisions.id", index=True)
    field_name: Mapped[str] = mapped_column(String(120))
    value_text: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("source_snapshots.id", ondelete="RESTRICT"), nullable=True
    )
    excerpt: Mapped[str] = mapped_column(Text, server_default=text("''"))
    review_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(
            ReviewStatus,
            name="review_status",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    reviewed_at: Mapped[dt.datetime | None] = utc_column(nullable=True)

    __table_args__ = (UniqueConstraint("revision_id", "field_name"),)


class PriceObservationRow(Base):
    __tablename__ = "price_observations"

    id: Mapped[uuid.UUID] = uuid_pk()
    revision_id: Mapped[uuid.UUID] = _uuid_fk("catalog_revisions.id", index=True)
    seller: Mapped[str] = mapped_column(String(200))
    region: Mapped[str] = mapped_column(String(2))
    currency: Mapped[str] = mapped_column(String(3))
    amount: Mapped[float] = mapped_column(MONEY)
    tax_included: Mapped[bool] = mapped_column()
    billing_interval: Mapped[BillingInterval | None] = mapped_column(
        SAEnum(
            BillingInterval,
            name="billing_interval",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    in_stock: Mapped[str] = mapped_column(String(12), server_default=text("'unknown'"))
    observed_at: Mapped[dt.datetime] = utc_column()
    reviewed_at: Mapped[dt.datetime | None] = utc_column(nullable=True)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("source_snapshots.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        # One seller's offer never overwrites another's under the same identity.
        UniqueConstraint("revision_id", "seller", "region", "observed_at"),
        Index("ix_price_observations_region_currency", "region", "currency"),
        nonnegative("amount"),
    )


class PlanModelAccessRow(Base):
    __tablename__ = "plan_model_access"

    id: Mapped[uuid.UUID] = uuid_pk()
    plan_revision_id: Mapped[uuid.UUID] = _uuid_fk("catalog_revisions.id", index=True)
    model_revision_id: Mapped[uuid.UUID] = _uuid_fk("catalog_revisions.id")
    conditions: Mapped[str] = mapped_column(Text, server_default=text("''"))
    reviewed_at: Mapped[dt.datetime | None] = utc_column(nullable=True)

    __table_args__ = (UniqueConstraint("plan_revision_id", "model_revision_id"),)


class BenchmarkObservationRow(Base):
    __tablename__ = "benchmark_observations"

    id: Mapped[uuid.UUID] = uuid_pk()
    model_revision_id: Mapped[uuid.UUID] = _uuid_fk("catalog_revisions.id", index=True)
    quantization: Mapped[str] = mapped_column(String(40))
    gpu_model: Mapped[str] = mapped_column(String(120))
    runtime: Mapped[str] = mapped_column(String(60))
    context_tokens: Mapped[int] = mapped_column(Integer)
    concurrency: Mapped[int] = mapped_column(Integer)
    tokens_per_second: Mapped[float] = mapped_column(QUANTITY)
    measured_at: Mapped[dt.datetime] = utc_column()
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("source_snapshots.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        nonnegative("tokens_per_second"),
        CheckConstraint("context_tokens > 0", name="context_tokens_positive"),
        CheckConstraint("concurrency > 0", name="concurrency_positive"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = uuid_pk()
    revision_id: Mapped[uuid.UUID] = _uuid_fk("catalog_revisions.id", index=True)
    reviewer_id: Mapped[uuid.UUID] = _uuid_fk("users.id")
    decision: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str] = mapped_column(Text, server_default=text("''"))
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("decision in ('approved','rejected')", name="decision_known"),
    )


# --------------------------------------------------------------------------- #
# Workspace-private records
# --------------------------------------------------------------------------- #


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = _uuid_fk("organizations.id", index=True)
    label: Mapped[str] = mapped_column(String(200))
    configuration: Mapped[dict] = mapped_column(JSONB)
    quantity: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    owned: Mapped[bool] = mapped_column(server_default=text("true"))
    dedicated: Mapped[bool] = mapped_column(server_default=text("true"))
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("organization_id", "label"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )


class ScenarioRevision(Base):
    __tablename__ = "scenario_revisions"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = _uuid_fk("organizations.id", index=True)
    created_by: Mapped[uuid.UUID] = _uuid_fk("users.id")
    label: Mapped[str] = mapped_column(String(200))
    schema_version: Mapped[str] = mapped_column(String(40))
    preset_version: Mapped[str] = mapped_column(String(40))
    inputs: Mapped[dict] = mapped_column(JSONB)
    """Immutable validated input. A change creates a new revision."""
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))

    __table_args__ = (
        Index("ix_scenario_revisions_org_created", "organization_id", "created_at"),
        UniqueConstraint("id", "organization_id"),
    )


class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = _uuid_fk("organizations.id", index=True)
    scenario_revision_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = _uuid_fk("users.id")
    policy_version: Mapped[str] = mapped_column(String(40))
    app_version: Mapped[str] = mapped_column(String(40))
    catalog_snapshot_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True))
    inputs: Mapped[dict] = mapped_column(JSONB)
    outputs: Mapped[dict] = mapped_column(JSONB)
    """Immutable stored result. Viewing it never recomputes against today's prices."""
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))

    __table_args__ = (
        # Compound foreign key: a run can only reference a scenario in its own workspace.
        ForeignKeyConstraint(
            ["scenario_revision_id", "organization_id"],
            ["scenario_revisions.id", "scenario_revisions.organization_id"],
            ondelete="RESTRICT",
            name="scenario_same_organization",
        ),
        UniqueConstraint("id", "organization_id"),
        Index("ix_recommendation_runs_org_created", "organization_id", "created_at"),
    )


class RecommendationEvidence(Base):
    __tablename__ = "recommendation_evidence"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = _uuid_fk("organizations.id", index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True))
    revision_id: Mapped[uuid.UUID] = _uuid_fk("catalog_revisions.id")
    """Referenced revisions may be superseded but never deleted."""
    observation_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "organization_id"],
            ["recommendation_runs.id", "recommendation_runs.organization_id"],
            ondelete="CASCADE",
            name="run_same_organization",
        ),
        UniqueConstraint("run_id", "revision_id", "observation_id"),
    )


# --------------------------------------------------------------------------- #
# Operations
# --------------------------------------------------------------------------- #


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    """Redacted change details. Account secrets and private scenarios stay out."""
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))

    __table_args__ = (Index("ix_audit_events_created", "created_at"),)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = _uuid_fk("organizations.id", index=True)
    route: Mapped[str] = mapped_column(String(200))
    key_digest: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(128))
    outcome: Mapped[dict] = mapped_column(JSONB)
    status_code: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = utc_column(server_default=text("now()"))
    expires_at: Mapped[dt.datetime] = utc_column()

    __table_args__ = (
        UniqueConstraint("organization_id", "route", "key_digest"),
        Index("ix_idempotency_keys_expires", "expires_at"),
    )
