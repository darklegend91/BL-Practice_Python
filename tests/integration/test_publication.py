"""Draft, review and publication workflow (guide sections 5 and 13)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.catalog import publication
from app.catalog.publication import ClaimInput, EditConflict, WorkflowError
from app.db.models import CatalogItem, CatalogRevision
from app.schemas.common import ReviewStatus
from app.security.authz import Forbidden, PlatformRole, Principal, SelfApprovalRefused
from app.services.auth import create_user
from tests.integration.conftest import requires_postgres

pytestmark = requires_postgres


def _principal(session, email: str, role: PlatformRole) -> Principal:
    user = create_user(
        session,
        email=email,
        display_name=email,
        password="development-only-password",
        platform_role=role,
    )
    return Principal(
        user_id=user.id, organization_id=None, workspace_role=None, platform_role=role
    )


@pytest.fixture
def editor(owner_session):
    return _principal(owner_session, "editor@example.invalid", PlatformRole.CATALOG_EDITOR)


@pytest.fixture
def reviewer(owner_session):
    return _principal(
        owner_session, "reviewer@example.invalid", PlatformRole.CATALOG_REVIEWER
    )


def _draft(session, principal, slug="sample-gpu", attributes=None):
    return publication.create_draft(
        session,
        principal,
        kind="hardware",
        slug=slug,
        schema_version="catalog-test",
        attributes=attributes or {"component_role": "gpu", "vendor": "SampleVendor"},
        claims=[ClaimInput("vram_gb", "16", None, "16 GB GDDR6")],
    )


def test_a_draft_starts_unpublished_with_its_evidence(owner_session, editor):
    draft = _draft(owner_session, editor)
    owner_session.flush()
    assert draft.review_status is ReviewStatus.DRAFT
    claims = owner_session.execute(
        text("SELECT field_name, excerpt FROM evidence_claims WHERE revision_id = :id"),
        {"id": draft.id},
    ).all()
    assert claims == [("vram_gb", "16 GB GDDR6")]


def test_a_viewer_without_the_editor_role_cannot_draft(owner_session):
    outsider = _principal(owner_session, "nobody@example.invalid", PlatformRole.NONE)
    with pytest.raises(Forbidden):
        _draft(owner_session, outsider)


def test_the_author_cannot_approve_their_own_change(owner_session, editor):
    """A small organization still needs two authorized people."""
    draft = _draft(owner_session, editor)
    publication.submit_for_review(owner_session, editor, draft.id)
    self_approving = Principal(
        user_id=editor.user_id,
        organization_id=None,
        workspace_role=None,
        platform_role=PlatformRole.CATALOG_ADMIN,
    )
    with pytest.raises(SelfApprovalRefused):
        publication.approve_and_publish(owner_session, self_approving, draft.id)


def test_publication_sets_the_current_revision_and_publishes_its_claims(
    owner_session, editor, reviewer
):
    draft = _draft(owner_session, editor)
    publication.submit_for_review(owner_session, editor, draft.id)
    publication.approve_and_publish(owner_session, reviewer, draft.id)
    owner_session.flush()

    item = owner_session.get(CatalogItem, draft.item_id)
    assert item.current_revision_id == draft.id
    assert draft.review_status is ReviewStatus.PUBLISHED
    assert draft.published_at is not None

    statuses = owner_session.execute(
        text("SELECT DISTINCT review_status FROM evidence_claims WHERE revision_id = :id"),
        {"id": draft.id},
    ).scalars().all()
    assert statuses == ["published"]


def test_publishing_supersedes_the_previous_revision(owner_session, editor, reviewer):
    first = _draft(owner_session, editor)
    publication.submit_for_review(owner_session, editor, first.id)
    publication.approve_and_publish(owner_session, reviewer, first.id)

    second = _draft(
        owner_session, editor, attributes={"component_role": "gpu", "vendor": "Revised"}
    )
    publication.submit_for_review(owner_session, editor, second.id)
    publication.approve_and_publish(owner_session, reviewer, second.id)
    owner_session.flush()

    owner_session.refresh(first)
    assert first.review_status is ReviewStatus.SUPERSEDED
    assert first.superseded_at is not None
    item = owner_session.get(CatalogItem, second.item_id)
    assert item.current_revision_id == second.id


def test_a_draft_cannot_be_published_without_review(owner_session, editor, reviewer):
    draft = _draft(owner_session, editor)
    with pytest.raises(WorkflowError):
        publication.approve_and_publish(owner_session, reviewer, draft.id)


def test_a_concurrent_edit_returns_a_conflict(owner_session, editor):
    draft = _draft(owner_session, editor)
    owner_session.flush()
    publication.update_draft(
        owner_session, editor, draft.id, expected_lock_version=1, attributes={"v": 2}
    )
    with pytest.raises(EditConflict):
        publication.update_draft(
            owner_session, editor, draft.id, expected_lock_version=1, attributes={"v": 3}
        )


def test_a_published_revision_cannot_be_edited(owner_session, editor, reviewer):
    draft = _draft(owner_session, editor)
    publication.submit_for_review(owner_session, editor, draft.id)
    publication.approve_and_publish(owner_session, reviewer, draft.id)
    owner_session.flush()
    with pytest.raises(WorkflowError):
        publication.update_draft(
            owner_session, editor, draft.id, expected_lock_version=draft.lock_version,
            attributes={"v": 9},
        )


def test_publication_writes_an_audit_event(owner_session, editor, reviewer):
    draft = _draft(owner_session, editor)
    publication.submit_for_review(owner_session, editor, draft.id)
    publication.approve_and_publish(owner_session, reviewer, draft.id)
    owner_session.flush()

    actions = owner_session.execute(
        text("SELECT action FROM audit_events WHERE target_id = :id ORDER BY created_at"),
        {"id": draft.id},
    ).scalars().all()
    assert "catalog.published" in actions


def test_a_rejected_revision_is_not_published(owner_session, editor, reviewer):
    draft = _draft(owner_session, editor)
    publication.submit_for_review(owner_session, editor, draft.id)
    publication.reject(owner_session, reviewer, draft.id, "price could not be confirmed")
    owner_session.flush()
    assert draft.review_status is ReviewStatus.REJECTED
    item = owner_session.get(CatalogItem, draft.item_id)
    assert item.current_revision_id is None
