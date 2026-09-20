"""Platform catalog administration (guide section 9).

These routes use platform catalog roles, which are separate from workspace
roles: a customer workspace administrator cannot publish shared catalog prices.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request, status
from pydantic import Field

from app.api.deps import PrincipalDep, SessionDep
from app.api.ratelimit import enforce_rate_limit
from app.catalog import freshness, publication
from app.config import get_settings
from app.db.models import CrawlJob, Source
from app.schemas.common import ReviewStatus, StrictModel
from app.security.net_guard import check_url_shape
from app.services import idempotency
from app.services.scenarios import NotFound
from app.workers import queue, scheduler

router = APIRouter(prefix="/v1/admin", tags=["admin"])

ENQUEUE_ROUTE = "POST /v1/admin/crawl-jobs"


# --------------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------------- #


class RegisterSourceRequest(StrictModel):
    url: str = Field(min_length=1, max_length=2048)
    allowed_hosts: list[str] = Field(default_factory=list, max_length=20)
    category: str
    owner: str = Field(min_length=1, max_length=200)
    refresh_interval_seconds: int = Field(ge=60, le=30 * 24 * 3600)
    max_page_bytes: int = Field(default=512 * 1024, ge=1024, le=8 * 1024 * 1024)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    crawl_permission_notes: str = ""


class SourceResponse(StrictModel):
    id: uuid.UUID
    url: str
    category: str
    enabled: bool


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def register_source(
    body: RegisterSourceRequest, principal: PrincipalDep, session: SessionDep
):
    principal.require_catalog_admin()
    # Shape is validated here; the host is resolved and re-checked at the
    # moment of collection, which is the check that actually protects egress.
    check_url_shape(body.url, body.allowed_hosts)
    source = Source(
        url=body.url,
        allowed_hosts=body.allowed_hosts,
        category=body.category,
        owner=body.owner,
        refresh_interval_seconds=body.refresh_interval_seconds,
        max_page_bytes=body.max_page_bytes,
        timeout_seconds=body.timeout_seconds,
        crawl_permission_notes=body.crawl_permission_notes,
    )
    session.add(source)
    session.flush()
    return SourceResponse(
        id=source.id, url=source.url, category=source.category, enabled=source.enabled
    )


# --------------------------------------------------------------------------- #
# Crawl jobs
# --------------------------------------------------------------------------- #


class EnqueueRequest(StrictModel):
    source_id: uuid.UUID


class CrawlJobResponse(StrictModel):
    id: uuid.UUID | None
    source_id: uuid.UUID
    state: str
    attempts: int
    run_after: str
    last_error: str | None = None


@router.post(
    "/crawl-jobs", response_model=CrawlJobResponse, status_code=status.HTTP_202_ACCEPTED
)
def enqueue_refresh(
    request: Request,
    body: EnqueueRequest,
    principal: PrincipalDep,
    session: SessionDep,
    idempotency_key: Annotated[str | None, Header()] = None,
):
    """Queue a refresh of a registered source. Accepted, not performed inline."""
    principal.require_catalog_editor()
    enforce_rate_limit(request, "admin.enqueue", get_settings().write_rate_limit_per_minute)

    source = session.get(Source, body.source_id)
    if source is None:
        raise NotFound(f"source {body.source_id} was not found")

    organization_id = principal.organization_id
    request_body = body.model_dump_json().encode("utf-8")
    if idempotency_key and organization_id is not None:
        replay = idempotency.look_up(
            session,
            organization_id=organization_id,
            route=ENQUEUE_ROUTE,
            key=idempotency_key,
            request_body=request_body,
        )
        if replay is not None:
            return CrawlJobResponse.model_validate(replay[0])

    import datetime as dt

    slot = scheduler.schedule_slot(
        dt.datetime.now(dt.timezone.utc), source.refresh_interval_seconds
    )
    job_id = queue.enqueue(session, source.id, scheduler.dedupe_key(source.id, slot))
    session.flush()

    if job_id is None:
        # A refresh for this slot is already queued; deduplication is the point.
        existing = session.get(CrawlJob, job_id) if job_id else None
        payload = CrawlJobResponse(
            id=existing.id if existing else None,
            source_id=source.id,
            state="already_queued",
            attempts=0,
            run_after=dt.datetime.now(dt.timezone.utc).isoformat(),
        )
    else:
        job = session.get(CrawlJob, job_id)
        payload = CrawlJobResponse(
            id=job.id,
            source_id=job.source_id,
            state=job.state,
            attempts=job.attempts,
            run_after=job.run_after.isoformat(),
        )

    if idempotency_key and organization_id is not None:
        idempotency.remember(
            session,
            organization_id=organization_id,
            route=ENQUEUE_ROUTE,
            key=idempotency_key,
            request_body=request_body,
            outcome=payload.model_dump(mode="json"),
            status_code=status.HTTP_202_ACCEPTED,
        )
    return payload


@router.get("/crawl-jobs/{job_id}", response_model=CrawlJobResponse)
def inspect_job(job_id: uuid.UUID, principal: PrincipalDep, session: SessionDep):
    principal.require_catalog_editor()
    job = session.get(CrawlJob, job_id)
    if job is None:
        raise NotFound(f"crawl job {job_id} was not found")
    return CrawlJobResponse(
        id=job.id,
        source_id=job.source_id,
        state=job.state,
        attempts=job.attempts,
        run_after=job.run_after.isoformat(),
        last_error=job.last_error,
    )


# --------------------------------------------------------------------------- #
# Catalog drafts
# --------------------------------------------------------------------------- #


class ClaimBody(StrictModel):
    field_name: str = Field(min_length=1, max_length=120)
    value_text: str = Field(max_length=4000)
    snapshot_id: uuid.UUID | None = None
    excerpt: str = Field(default="", max_length=2000)


class CreateDraftRequest(StrictModel):
    kind: str
    slug: str = Field(min_length=1, max_length=200)
    schema_version: str
    attributes: dict
    claims: list[ClaimBody] = Field(default_factory=list)


class UpdateDraftRequest(StrictModel):
    expected_lock_version: int = Field(ge=1)
    attributes: dict


class ReviewRequest(StrictModel):
    notes: str = Field(default="", max_length=4000)


class DraftResponse(StrictModel):
    revision_id: uuid.UUID
    item_id: uuid.UUID
    review_status: ReviewStatus
    lock_version: int


def _draft_response(revision) -> DraftResponse:
    return DraftResponse(
        revision_id=revision.id,
        item_id=revision.item_id,
        review_status=revision.review_status,
        lock_version=revision.lock_version,
    )


@router.post(
    "/catalog/drafts", response_model=DraftResponse, status_code=status.HTTP_201_CREATED
)
def create_draft(body: CreateDraftRequest, principal: PrincipalDep, session: SessionDep):
    revision = publication.create_draft(
        session,
        principal,
        kind=body.kind,
        slug=body.slug,
        schema_version=body.schema_version,
        attributes=body.attributes,
        claims=[
            publication.ClaimInput(
                claim.field_name, claim.value_text, claim.snapshot_id, claim.excerpt
            )
            for claim in body.claims
        ],
    )
    session.flush()
    return _draft_response(revision)


@router.patch("/catalog/drafts/{revision_id}", response_model=DraftResponse)
def update_draft(
    revision_id: uuid.UUID,
    body: UpdateDraftRequest,
    principal: PrincipalDep,
    session: SessionDep,
):
    revision = publication.update_draft(
        session,
        principal,
        revision_id,
        expected_lock_version=body.expected_lock_version,
        attributes=body.attributes,
    )
    return _draft_response(revision)


@router.post("/catalog/drafts/{revision_id}/submit", response_model=DraftResponse)
def submit(revision_id: uuid.UUID, principal: PrincipalDep, session: SessionDep):
    return _draft_response(publication.submit_for_review(session, principal, revision_id))


@router.post("/catalog/drafts/{revision_id}/approve", response_model=DraftResponse)
def approve(
    revision_id: uuid.UUID,
    body: ReviewRequest,
    principal: PrincipalDep,
    session: SessionDep,
):
    """Publish. The reviewer must be someone other than the draft's author."""
    return _draft_response(
        publication.approve_and_publish(session, principal, revision_id, notes=body.notes)
    )


@router.post("/catalog/drafts/{revision_id}/reject", response_model=DraftResponse)
def reject(
    revision_id: uuid.UUID,
    body: ReviewRequest,
    principal: PrincipalDep,
    session: SessionDep,
):
    return _draft_response(
        publication.reject(session, principal, revision_id, body.notes)
    )


# --------------------------------------------------------------------------- #
# Review dashboard
# --------------------------------------------------------------------------- #


@router.get("/freshness/sources")
def source_freshness(principal: PrincipalDep, session: SessionDep):
    principal.require_catalog_editor()
    return [entry.model_dump(mode="json") for entry in freshness.source_report(session)]


@router.get("/freshness/catalog")
def catalog_freshness(principal: PrincipalDep, session: SessionDep):
    principal.require_catalog_editor()
    return [entry.model_dump(mode="json") for entry in freshness.catalog_report(session)]
