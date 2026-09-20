"""Freshness reporting for the review dashboard (guide section 5).

Fetch age and review age are shown separately: a successful fetch is not a
review, and a source that has never been reviewed is stale rather than fresh.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import CatalogItem, CatalogRevision, PriceObservationRow, Source, SourceSnapshot
from app.engine.freshness import review_age_days
from app.schemas.common import ReviewStatus, StrictModel, utc_now


class SourceFreshness(StrictModel):
    source_url: str
    last_fetch_age_days: int | None
    enabled: bool


class CatalogFreshness(StrictModel):
    kind: str
    slug: str
    spec_review_age_days: int | None
    price_review_age_days: int | None
    specs_stale: bool
    prices_stale: bool


def source_report(session: Session, now: dt.datetime | None = None) -> list[SourceFreshness]:
    moment = now or utc_now()
    latest = (
        select(
            SourceSnapshot.source_id.label("source_id"),
            func.max(SourceSnapshot.fetched_at).label("fetched_at"),
        )
        .group_by(SourceSnapshot.source_id)
        .subquery()
    )
    rows = session.execute(
        select(Source, latest.c.fetched_at).join(
            latest, latest.c.source_id == Source.id, isouter=True
        )
    ).all()
    return [
        SourceFreshness(
            source_url=source.url,
            last_fetch_age_days=review_age_days(fetched_at, moment),
            enabled=source.enabled,
        )
        for source, fetched_at in rows
    ]


def catalog_report(session: Session, now: dt.datetime | None = None) -> list[CatalogFreshness]:
    settings = get_settings()
    moment = now or utc_now()

    rows = session.execute(
        select(CatalogItem, CatalogRevision)
        .join(CatalogRevision, CatalogRevision.id == CatalogItem.current_revision_id)
        .where(CatalogRevision.review_status == ReviewStatus.PUBLISHED)
    ).all()

    report: list[CatalogFreshness] = []
    for item, revision in rows:
        newest_price = session.scalar(
            select(func.max(PriceObservationRow.reviewed_at)).where(
                PriceObservationRow.revision_id == revision.id
            )
        )
        spec_age = review_age_days(revision.specs_reviewed_at, moment)
        price_age = review_age_days(newest_price, moment)
        report.append(
            CatalogFreshness(
                kind=item.kind,
                slug=item.slug,
                spec_review_age_days=spec_age,
                price_review_age_days=price_age,
                specs_stale=spec_age is None or spec_age > settings.spec_freshness_days,
                prices_stale=price_age is None or price_age > settings.price_freshness_days,
            )
        )
    return report
