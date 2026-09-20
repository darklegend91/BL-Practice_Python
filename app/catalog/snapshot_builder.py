"""Selects one consistent set of published revisions for a recommendation.

Read inside a repeatable-read transaction so every revision comes from the same
database version, then persisted by reference so the result can be reproduced
(guide section 8).
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    BenchmarkObservationRow,
    CatalogItem,
    CatalogRevision,
    EvidenceClaim,
    PlanModelAccessRow,
    PriceObservationRow,
)
from app.schemas.catalog import (
    BenchmarkObservation,
    CatalogSnapshot,
    HardwareRevision,
    ModelRevision,
    PlanModelAccess,
    PlanRevision,
    PriceObservation,
    RevisionHeader,
)
from app.schemas.common import Claimed, EvidenceRef, ReviewStatus, utc_now

_MODEL_FOR_KIND = {
    "hardware": HardwareRevision,
    "model": ModelRevision,
    "plan": PlanRevision,
}


def _header(item: CatalogItem, revision: CatalogRevision) -> RevisionHeader:
    return RevisionHeader(
        item_id=item.id,
        revision_id=revision.id,
        schema_version=revision.schema_version,
        review_status=ReviewStatus.PUBLISHED,
        published_at=revision.published_at,
        specs_reviewed_at=revision.specs_reviewed_at,
    )


def _claims_by_field(session: Session, revision_id: uuid.UUID) -> dict[str, EvidenceClaim]:
    rows = session.scalars(
        select(EvidenceClaim).where(EvidenceClaim.revision_id == revision_id)
    ).all()
    return {row.field_name: row for row in rows}


def _attach_evidence(attributes: dict, claims: dict[str, EvidenceClaim]) -> dict:
    """Fill each ``Evidenced`` field's ``evidence`` from its stored claim."""
    enriched = dict(attributes)
    for field_name, claim in claims.items():
        current = enriched.get(field_name)
        if not isinstance(current, dict) or "value" not in current:
            continue
        enriched[field_name] = {
            **current,
            "evidence": EvidenceRef(
                claim_id=claim.id,
                field_name=field_name,
                snapshot_id=claim.snapshot_id,
                excerpt=claim.excerpt,
                review_status=claim.review_status,
                reviewed_at=claim.reviewed_at,
            ).model_dump(mode="json"),
        }
    return enriched


def build(
    session: Session,
    *,
    currency: str,
    region: str,
    snapshot_id: uuid.UUID | None = None,
    taken_at: dt.datetime | None = None,
) -> CatalogSnapshot:
    """Assemble the published catalog into an immutable snapshot."""
    published = session.execute(
        select(CatalogItem, CatalogRevision)
        .join(CatalogRevision, CatalogRevision.id == CatalogItem.current_revision_id)
        .where(CatalogRevision.review_status == ReviewStatus.PUBLISHED)
        .order_by(CatalogItem.kind, CatalogItem.slug)
    ).all()

    hardware: list[HardwareRevision] = []
    models: list[ModelRevision] = []
    plans: list[PlanRevision] = []
    revision_ids: list[uuid.UUID] = []

    for item, revision in published:
        contract = _MODEL_FOR_KIND.get(item.kind)
        if contract is None:  # pragma: no cover - guarded by a check constraint
            continue
        payload = _attach_evidence(revision.attributes, _claims_by_field(session, revision.id))
        payload["header"] = _header(item, revision).model_dump(mode="json")
        parsed = contract.model_validate(payload)
        revision_ids.append(revision.id)
        if item.kind == "hardware":
            hardware.append(parsed)
        elif item.kind == "model":
            models.append(parsed)
        else:
            plans.append(parsed)

    prices = [
        PriceObservation(
            observation_id=row.id,
            revision_id=row.revision_id,
            seller=row.seller,
            region=row.region,
            price={"amount": row.amount, "currency": row.currency},
            tax_included=row.tax_included,
            billing_interval=row.billing_interval,
            in_stock=Claimed(row.in_stock),
            observed_at=row.observed_at,
            reviewed_at=row.reviewed_at,
        )
        for row in session.scalars(
            select(PriceObservationRow).where(
                PriceObservationRow.revision_id.in_(revision_ids),
                PriceObservationRow.region == region,
                PriceObservationRow.currency == currency,
            )
        ).all()
    ]

    benchmarks = [
        BenchmarkObservation(
            observation_id=row.id,
            model_revision_id=row.model_revision_id,
            quantization=row.quantization,
            gpu_model=row.gpu_model,
            runtime=row.runtime,
            context_tokens=row.context_tokens,
            concurrency=row.concurrency,
            tokens_per_second=row.tokens_per_second,
            measured_at=row.measured_at,
        )
        for row in session.scalars(
            select(BenchmarkObservationRow).where(
                BenchmarkObservationRow.model_revision_id.in_(revision_ids)
            )
        ).all()
    ]

    access = [
        PlanModelAccess(
            plan_revision_id=row.plan_revision_id,
            model_revision_id=row.model_revision_id,
            conditions=row.conditions,
            reviewed_at=row.reviewed_at,
        )
        for row in session.scalars(
            select(PlanModelAccessRow).where(
                PlanModelAccessRow.plan_revision_id.in_(revision_ids)
            )
        ).all()
    ]

    return CatalogSnapshot(
        snapshot_id=snapshot_id or uuid.uuid4(),
        taken_at=taken_at or utc_now(),
        currency=currency,
        hardware=hardware,
        models=models,
        plans=plans,
        prices=prices,
        benchmarks=benchmarks,
        plan_model_access=access,
    )
