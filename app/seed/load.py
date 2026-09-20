"""Loads the sample catalog into PostgreSQL through the real review workflow.

Nothing is inserted as already-published: each record is drafted by an editor
and approved by a separate reviewer, so seeded data cannot be more trusted than
data a real editor enters (guide section 14, stage 1).
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.publication import ClaimInput, approve_and_publish, create_draft, submit_for_review
from app.db.session import set_tenant
from app.db.models import (
    BenchmarkObservationRow,
    Membership,
    Organization,
    PriceObservationRow,
    Source,
    User,
)
from app.schemas.catalog import HardwareRevision, ModelRevision, PlanRevision
from app.schemas.common import ReviewStatus
from app.security.authz import PlatformRole, Principal, WorkspaceRole
from app.seed import dataset
from app.services.auth import create_user
from app.version import CATALOG_SCHEMA_VERSION

EDITOR_EMAIL = "editor@example.invalid"
REVIEWER_EMAIL = "reviewer@example.invalid"
ANALYST_EMAIL = "analyst@example.invalid"
DEFAULT_PASSWORD = "development-only-password"


class SeedResult:
    def __init__(self, organization_id: uuid.UUID, editor_id: uuid.UUID,
                 reviewer_id: uuid.UUID, analyst_id: uuid.UUID, published: int) -> None:
        self.organization_id = organization_id
        self.editor_id = editor_id
        self.reviewer_id = reviewer_id
        self.analyst_id = analyst_id
        self.published = published


def _principal(user: User, organization_id: uuid.UUID | None,
               workspace_role: WorkspaceRole | None) -> Principal:
    return Principal(
        user_id=user.id,
        organization_id=organization_id,
        workspace_role=workspace_role,
        platform_role=PlatformRole(user.platform_role),
    )


def _attributes(revision) -> dict:
    """Strip the header; it is rebuilt from the database row on read."""
    payload = revision.model_dump(mode="json")
    payload.pop("header", None)
    return payload


def _claims(revision) -> list[ClaimInput]:
    """One claim per evidenced field that actually carries evidence."""
    claims: list[ClaimInput] = []
    for field_name, value in revision.model_dump(mode="json").items():
        if not isinstance(value, dict) or "evidence" not in value:
            continue
        evidence = value.get("evidence")
        if not evidence:
            continue
        claims.append(
            ClaimInput(
                field_name=field_name,
                value_text=str(value.get("value")),
                snapshot_id=None,
                excerpt=evidence.get("excerpt", ""),
            )
        )
    return claims


def _publish(session: Session, editor: Principal, reviewer: Principal, kind: str,
             slug: str, revision, now: dt.datetime) -> uuid.UUID:
    draft = create_draft(
        session,
        editor,
        kind=kind,
        slug=slug,
        schema_version=CATALOG_SCHEMA_VERSION,
        attributes=_attributes(revision),
        claims=_claims(revision),
    )
    submit_for_review(session, editor, draft.id)
    approve_and_publish(session, reviewer, draft.id, notes="seeded sample data", now=now)
    return draft.id


def seed(session: Session, *, as_of: dt.datetime | None = None) -> SeedResult:
    """Idempotent: running it twice does not duplicate anything."""
    moment = as_of or dataset.SEED_EPOCH

    existing = session.scalars(select(User).where(User.email == EDITOR_EMAIL)).first()
    if existing is not None:
        organization = session.scalars(select(Organization)).first()
        reviewer = session.scalars(select(User).where(User.email == REVIEWER_EMAIL)).first()
        analyst = session.scalars(select(User).where(User.email == ANALYST_EMAIL)).first()
        return SeedResult(organization.id, existing.id, reviewer.id, analyst.id, 0)

    editor_user = create_user(
        session, email=EDITOR_EMAIL, display_name="Sample Editor",
        password=DEFAULT_PASSWORD, platform_role=PlatformRole.CATALOG_EDITOR,
    )
    reviewer_user = create_user(
        session, email=REVIEWER_EMAIL, display_name="Sample Reviewer",
        password=DEFAULT_PASSWORD, platform_role=PlatformRole.CATALOG_ADMIN,
    )
    analyst_user = create_user(
        session, email=ANALYST_EMAIL, display_name="Sample Analyst",
        password=DEFAULT_PASSWORD, platform_role=PlatformRole.NONE,
    )

    organization = Organization(
        name="Sample Workspace", default_region="DE", default_currency="EUR"
    )
    session.add(organization)
    session.flush()
    # Memberships are workspace-private, so the tenant context must name the
    # workspace being created before they can be written.
    set_tenant(session, organization.id)
    session.add(
        Membership(
            organization_id=organization.id,
            user_id=analyst_user.id,
            role=WorkspaceRole.ANALYST.value,
        )
    )
    session.add(
        Membership(
            organization_id=organization.id,
            user_id=reviewer_user.id,
            role=WorkspaceRole.OWNER.value,
        )
    )

    editor = _principal(editor_user, None, None)
    reviewer = _principal(reviewer_user, None, None)

    session.add(
        Source(
            url="https://sample-vendor.example.invalid/accelerators",
            allowed_hosts=["sample-vendor.example.invalid"],
            category="manufacturer",
            owner="Catalog operations",
            refresh_interval_seconds=86_400,
            max_page_bytes=512 * 1024,
            timeout_seconds=30,
            crawl_permission_notes="Sample source for development only.",
        )
    )

    published = 0
    revision_ids: dict[str, uuid.UUID] = {}

    for item in dataset.build_hardware(moment):
        slug = f"{item.vendor}-{item.model_name}".lower().replace(" ", "-")
        revision_ids[item.model_name] = _publish(
            session, editor, reviewer, "hardware", slug, item, moment
        )
        published += 1

    for model in dataset.build_models(moment):
        slug = f"{model.family}-{model.variant_name}".lower().replace(" ", "-").replace("_", "-")
        revision_ids[model.variant_name] = _publish(
            session, editor, reviewer, "model", slug, model, moment
        )
        published += 1

    for plan in dataset.build_plans(moment):
        slug = f"{plan.provider}-{plan.plan_name}".lower().replace(" ", "-")
        revision_ids[plan.plan_name] = _publish(
            session, editor, reviewer, "plan", slug, plan, moment
        )
        published += 1

    hardware = dataset.build_hardware(moment)
    for observation in dataset.build_prices(hardware, moment):
        item = next(
            entry for entry in hardware
            if entry.header.revision_id == observation.revision_id
        )
        session.add(
            PriceObservationRow(
                revision_id=revision_ids[item.model_name],
                seller=observation.seller,
                region=observation.region,
                currency=observation.price.currency,
                amount=observation.price.amount,
                tax_included=observation.tax_included,
                in_stock=observation.in_stock.value,
                observed_at=observation.observed_at,
                reviewed_at=observation.reviewed_at,
            )
        )

    models = dataset.build_models(moment)
    for benchmark in dataset.build_benchmarks(models, moment):
        model = next(
            entry for entry in models
            if entry.header.revision_id == benchmark.model_revision_id
        )
        session.add(
            BenchmarkObservationRow(
                model_revision_id=revision_ids[model.variant_name],
                quantization=benchmark.quantization,
                gpu_model=benchmark.gpu_model,
                runtime=benchmark.runtime,
                context_tokens=benchmark.context_tokens,
                concurrency=benchmark.concurrency,
                tokens_per_second=benchmark.tokens_per_second,
                measured_at=benchmark.measured_at,
            )
        )

    session.flush()
    return SeedResult(
        organization.id, editor_user.id, reviewer_user.id, analyst_user.id, published
    )


def main() -> None:  # pragma: no cover - development entry point
    from app.db.session import unit_of_work

    with unit_of_work() as session:
        result = seed(session)
    print(f"{dataset.SAMPLE_DATA_NOTICE}\nPublished {result.published} catalog revisions.")


if __name__ == "__main__":  # pragma: no cover
    main()
