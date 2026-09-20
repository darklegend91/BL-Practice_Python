"""Read-only catalog browsing for workspace members (guide section 9).

Only published revisions are visible here. Draft data can never reach a
production recommendation.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import PaginationDep, PrincipalDep, SessionDep
from app.db.models import CatalogItem, CatalogRevision, EvidenceClaim
from app.schemas.common import ReviewStatus, StrictModel
from app.services.scenarios import NotFound

router = APIRouter(prefix="/v1/catalog", tags=["catalog"])


class CatalogEntry(StrictModel):
    item_id: uuid.UUID
    revision_id: uuid.UUID
    kind: str
    slug: str
    schema_version: str
    attributes: dict
    published_at: str | None
    specs_reviewed_at: str | None


class CatalogPage(StrictModel):
    items: list[CatalogEntry]
    limit: int
    offset: int


class HistoryEntry(StrictModel):
    revision_id: uuid.UUID
    review_status: ReviewStatus
    published_at: str | None
    superseded_at: str | None
    claims: list[dict]


def _page(session, kind: str, pagination: tuple[int, int]) -> CatalogPage:
    limit, offset = pagination
    rows = session.execute(
        select(CatalogItem, CatalogRevision)
        .join(CatalogRevision, CatalogRevision.id == CatalogItem.current_revision_id)
        .where(
            CatalogItem.kind == kind,
            CatalogRevision.review_status == ReviewStatus.PUBLISHED,
        )
        .order_by(CatalogItem.slug, CatalogItem.id)  # stable ordering
        .limit(limit)
        .offset(offset)
    ).all()
    return CatalogPage(
        items=[
            CatalogEntry(
                item_id=item.id,
                revision_id=revision.id,
                kind=item.kind,
                slug=item.slug,
                schema_version=revision.schema_version,
                attributes=revision.attributes,
                published_at=revision.published_at.isoformat() if revision.published_at else None,
                specs_reviewed_at=(
                    revision.specs_reviewed_at.isoformat()
                    if revision.specs_reviewed_at
                    else None
                ),
            )
            for item, revision in rows
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/hardware", response_model=CatalogPage)
def hardware(principal: PrincipalDep, session: SessionDep, pagination: PaginationDep):
    principal.require_member()
    return _page(session, "hardware", pagination)


@router.get("/models", response_model=CatalogPage)
def models(principal: PrincipalDep, session: SessionDep, pagination: PaginationDep):
    principal.require_member()
    return _page(session, "model", pagination)


@router.get("/plans", response_model=CatalogPage)
def plans(principal: PrincipalDep, session: SessionDep, pagination: PaginationDep):
    principal.require_member()
    return _page(session, "plan", pagination)


@router.get("/items/{item_id}/history", response_model=list[HistoryEntry])
def history(item_id: uuid.UUID, principal: PrincipalDep, session: SessionDep):
    """Published history and the evidence behind each revision."""
    principal.require_member()
    if session.get(CatalogItem, item_id) is None:
        raise NotFound(f"catalog item {item_id} was not found")

    revisions = session.scalars(
        select(CatalogRevision)
        .where(
            CatalogRevision.item_id == item_id,
            CatalogRevision.review_status.in_(
                [ReviewStatus.PUBLISHED, ReviewStatus.SUPERSEDED]
            ),
        )
        .order_by(CatalogRevision.published_at.desc())
    ).all()

    entries: list[HistoryEntry] = []
    for revision in revisions:
        claims = session.scalars(
            select(EvidenceClaim).where(EvidenceClaim.revision_id == revision.id)
        ).all()
        entries.append(
            HistoryEntry(
                revision_id=revision.id,
                review_status=revision.review_status,
                published_at=revision.published_at.isoformat() if revision.published_at else None,
                superseded_at=(
                    revision.superseded_at.isoformat() if revision.superseded_at else None
                ),
                claims=[
                    {
                        "field_name": claim.field_name,
                        "value_text": claim.value_text,
                        "excerpt": claim.excerpt,
                        "reviewed_at": (
                            claim.reviewed_at.isoformat() if claim.reviewed_at else None
                        ),
                    }
                    for claim in claims
                ],
            )
        )
    return entries
