"""The draft to published workflow (guide section 5).

``draft -> pending_review -> published``, with ``rejected`` and ``superseded``
outcomes. Publication writes the revision, its claims, the supersession of the
previous revision and the audit event in one transaction. An editor may not
approve their own change.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, CatalogItem, CatalogRevision, EvidenceClaim, Review
from app.schemas.common import ReviewStatus, utc_now
from app.security.authz import Principal, check_independent_review


class WorkflowError(RuntimeError):
    """An operation that the workflow state does not allow."""


class EditConflict(RuntimeError):
    """Another editor changed this draft first (optimistic revision check)."""


class ClaimInput:
    def __init__(self, field_name: str, value_text: str, snapshot_id: uuid.UUID | None,
                 excerpt: str) -> None:
        self.field_name = field_name
        self.value_text = value_text
        self.snapshot_id = snapshot_id
        self.excerpt = excerpt


def create_draft(
    session: Session,
    principal: Principal,
    *,
    kind: str,
    slug: str,
    schema_version: str,
    attributes: dict,
    claims: list[ClaimInput],
) -> CatalogRevision:
    """Create a typed draft with its supporting evidence."""
    principal.require_catalog_editor()

    item = session.scalars(
        select(CatalogItem).where(CatalogItem.kind == kind, CatalogItem.slug == slug)
    ).first()
    if item is None:
        item = CatalogItem(kind=kind, slug=slug)
        session.add(item)
        session.flush()

    revision = CatalogRevision(
        item_id=item.id,
        schema_version=schema_version,
        attributes=attributes,
        review_status=ReviewStatus.DRAFT,
        author_id=principal.user_id,
        lock_version=1,
    )
    session.add(revision)
    session.flush()

    for claim in claims:
        session.add(
            EvidenceClaim(
                revision_id=revision.id,
                field_name=claim.field_name,
                value_text=claim.value_text,
                snapshot_id=claim.snapshot_id,
                excerpt=claim.excerpt,
                review_status=ReviewStatus.DRAFT,
            )
        )

    _audit(session, principal, "catalog.draft_created", "catalog_revision", revision.id,
           {"kind": kind, "slug": slug})
    return revision


def update_draft(
    session: Session,
    principal: Principal,
    revision_id: uuid.UUID,
    *,
    expected_lock_version: int,
    attributes: dict,
) -> CatalogRevision:
    """Revise a draft, refusing the write if someone else changed it first."""
    principal.require_catalog_editor()
    revision = _load(session, revision_id)
    if revision.review_status not in (ReviewStatus.DRAFT, ReviewStatus.PENDING_REVIEW):
        raise WorkflowError(f"a {revision.review_status.value} revision cannot be edited")

    changed = session.execute(
        update(CatalogRevision)
        .where(
            CatalogRevision.id == revision_id,
            CatalogRevision.lock_version == expected_lock_version,
        )
        .values(
            attributes=attributes,
            lock_version=expected_lock_version + 1,
            review_status=ReviewStatus.DRAFT,
        )
    ).rowcount
    if changed == 0:
        raise EditConflict(
            f"revision {revision_id} was modified by another editor; reload and retry"
        )
    session.expire(revision)
    _audit(session, principal, "catalog.draft_updated", "catalog_revision", revision_id, {})
    return _load(session, revision_id)


def submit_for_review(
    session: Session, principal: Principal, revision_id: uuid.UUID
) -> CatalogRevision:
    principal.require_catalog_editor()
    revision = _load(session, revision_id)
    if revision.review_status is not ReviewStatus.DRAFT:
        raise WorkflowError(f"only a draft can be submitted, not {revision.review_status.value}")
    revision.review_status = ReviewStatus.PENDING_REVIEW
    revision.submitted_at = utc_now()
    _audit(session, principal, "catalog.submitted", "catalog_revision", revision_id, {})
    return revision


def reject(
    session: Session, principal: Principal, revision_id: uuid.UUID, notes: str
) -> CatalogRevision:
    principal.require_catalog_reviewer()
    revision = _load(session, revision_id)
    if revision.review_status is not ReviewStatus.PENDING_REVIEW:
        raise WorkflowError("only a revision pending review can be rejected")
    check_independent_review(revision.author_id, principal.user_id)
    revision.review_status = ReviewStatus.REJECTED
    session.add(
        Review(
            revision_id=revision_id,
            reviewer_id=principal.user_id,
            decision="rejected",
            notes=notes,
        )
    )
    _audit(session, principal, "catalog.rejected", "catalog_revision", revision_id, {})
    return revision


def approve_and_publish(
    session: Session,
    principal: Principal,
    revision_id: uuid.UUID,
    *,
    notes: str = "",
    now: dt.datetime | None = None,
) -> CatalogRevision:
    """Publish atomically: revision, claims, current pointer and audit event.

    The caller's transaction commits all of it or none of it.
    """
    principal.require_catalog_reviewer()
    revision = _load(session, revision_id)
    if revision.review_status is not ReviewStatus.PENDING_REVIEW:
        raise WorkflowError(
            f"only a revision pending review can be published, not "
            f"{revision.review_status.value}"
        )
    check_independent_review(revision.author_id, principal.user_id)

    moment = now or utc_now()
    item = session.get(CatalogItem, revision.item_id)
    if item is None:  # pragma: no cover - foreign key makes this unreachable
        raise WorkflowError("the catalog item no longer exists")

    if item.current_revision_id is not None:
        session.execute(
            update(CatalogRevision)
            .where(CatalogRevision.id == item.current_revision_id)
            .values(review_status=ReviewStatus.SUPERSEDED, superseded_at=moment)
        )

    revision.review_status = ReviewStatus.PUBLISHED
    revision.published_at = moment
    revision.specs_reviewed_at = moment
    session.execute(
        update(EvidenceClaim)
        .where(EvidenceClaim.revision_id == revision_id)
        .values(review_status=ReviewStatus.PUBLISHED, reviewed_at=moment)
    )
    item.current_revision_id = revision.id

    session.add(
        Review(
            revision_id=revision_id,
            reviewer_id=principal.user_id,
            decision="approved",
            notes=notes,
        )
    )
    _audit(
        session,
        principal,
        "catalog.published",
        "catalog_revision",
        revision_id,
        {"item_id": str(item.id), "kind": item.kind, "slug": item.slug},
    )
    return revision


def _load(session: Session, revision_id: uuid.UUID) -> CatalogRevision:
    revision = session.get(CatalogRevision, revision_id)
    if revision is None:
        raise WorkflowError(f"revision {revision_id} does not exist")
    return revision


def _audit(
    session: Session,
    principal: Principal,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    details: dict,
) -> None:
    session.add(
        AuditEvent(
            actor_id=principal.user_id,
            organization_id=None,  # platform catalog actions are not workspace-scoped
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
    )
