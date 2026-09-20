"""Security unit tests (guide sections 11 and 13)."""

from __future__ import annotations

import pytest

from app.security import csv_safe, markdown_safe, net_guard, passwords, tokens
from app.security.authz import (
    Forbidden,
    PlatformRole,
    Principal,
    SelfApprovalRefused,
    WorkspaceRole,
    check_independent_review,
)
import uuid


# --------------------------------------------------------------------------- #
# Passwords and tokens
# --------------------------------------------------------------------------- #


def test_passwords_are_hashed_with_argon2id_and_salted():
    first = passwords.hash_password("a-sufficiently-long-password")
    second = passwords.hash_password("a-sufficiently-long-password")
    assert first.startswith("$argon2id$")
    assert first != second  # distinct salts
    assert passwords.verify_password(first, "a-sufficiently-long-password")
    assert not passwords.verify_password(first, "a-sufficiently-long-passwore")


def test_a_short_password_is_refused():
    with pytest.raises(passwords.WeakPassword):
        passwords.hash_password("short")


def test_a_corrupt_hash_never_verifies():
    assert passwords.verify_password("not-a-hash", "anything") is False


def test_session_tokens_are_high_entropy_and_stored_only_as_a_digest():
    token, digest = tokens.issue_token()
    assert len(token) >= 32
    assert token not in digest
    assert tokens.tokens_match(token, digest)
    assert not tokens.tokens_match(token + "x", digest)


def test_two_issued_tokens_never_collide():
    issued = {tokens.issue_token()[0] for _ in range(200)}
    assert len(issued) == 200


# --------------------------------------------------------------------------- #
# Authorization
# --------------------------------------------------------------------------- #


def _principal(workspace_role=None, platform_role=PlatformRole.NONE, organization_id=None):
    return Principal(
        user_id=uuid.uuid4(),
        organization_id=organization_id,
        workspace_role=workspace_role,
        platform_role=platform_role,
    )


def test_a_viewer_cannot_create_scenarios():
    viewer = _principal(WorkspaceRole.VIEWER, organization_id=uuid.uuid4())
    with pytest.raises(Forbidden):
        viewer.require_analyst()


def test_an_analyst_is_not_a_workspace_owner():
    analyst = _principal(WorkspaceRole.ANALYST, organization_id=uuid.uuid4())
    analyst.require_analyst()
    with pytest.raises(Forbidden):
        analyst.require_owner()


def test_a_workspace_owner_is_not_a_catalog_publisher():
    """Workspace roles and platform catalog roles are deliberately separate."""
    owner = _principal(WorkspaceRole.OWNER, organization_id=uuid.uuid4())
    owner.require_owner()
    with pytest.raises(Forbidden):
        owner.require_catalog_editor()
    with pytest.raises(Forbidden):
        owner.require_catalog_reviewer()


def test_a_catalog_editor_cannot_approve():
    editor = _principal(platform_role=PlatformRole.CATALOG_EDITOR)
    editor.require_catalog_editor()
    with pytest.raises(Forbidden):
        editor.require_catalog_reviewer()


def test_a_principal_with_no_workspace_cannot_read_workspace_data():
    with pytest.raises(Forbidden):
        _principal().require_member()


def test_self_approval_is_refused():
    author = uuid.uuid4()
    check_independent_review(author, uuid.uuid4())
    with pytest.raises(SelfApprovalRefused):
        check_independent_review(author, author)


# --------------------------------------------------------------------------- #
# Egress control
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # AWS/GCP/Azure metadata
        "http://100.100.100.200/latest/meta-data/",  # Alibaba metadata
        "http://127.0.0.1:8080/admin",
        "http://10.0.0.5/internal",
        "http://192.168.1.1/router",
        "http://172.16.0.9/private",
        "http://[::1]/loopback",
        "http://0.0.0.0/",
    ],
)
def test_internal_destinations_are_refused(url):
    with pytest.raises(net_guard.DestinationRefused):
        net_guard.check_url_shape(url)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://vendor.example.com/",
        "ftp://vendor.example.com/",
        "http://vendor.example.com:22/",
        "http://user:secret@vendor.example.com/",
    ],
)
def test_unsupported_schemes_ports_and_credentials_are_refused(url):
    with pytest.raises(net_guard.DestinationRefused):
        net_guard.check_url_shape(url)


def test_a_host_outside_the_approved_domains_is_refused():
    with pytest.raises(net_guard.DestinationRefused):
        net_guard.check_url_shape(
            "https://lookalike.example.com/page", ["vendor.example.com"]
        )


def test_a_subdomain_of_an_approved_domain_is_allowed():
    net_guard.check_url_shape(
        "https://shop.vendor.example.com/page", ["vendor.example.com"]
    )


def test_a_redirect_is_checked_as_a_new_request():
    """A redirect target gets the full check, not a pass because it followed one."""
    with pytest.raises(net_guard.DestinationRefused):
        net_guard.check_redirect(
            "https://vendor.example.com/a",
            "http://169.254.169.254/latest/meta-data/",
            ["vendor.example.com"],
        )


# --------------------------------------------------------------------------- #
# Untrusted content and exports
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("payload", ["=SUM(A1)", "+1+1", "-2+3", "@SUM(1)", "\tcmd", "\rcmd"])
def test_formula_prefixes_are_neutralised_in_csv_cells(payload):
    assert csv_safe.neutralize(payload).startswith("'")


def test_ordinary_values_are_left_alone():
    assert csv_safe.neutralize("SampleVendor 16G") == "SampleVendor 16G"
    assert csv_safe.neutralize(42) == 42


def test_collected_markdown_is_escaped_not_executed():
    hostile = '<script>fetch("https://attacker.example.com")</script>'
    rendered = markdown_safe.as_escaped_text(hostile)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_displayed_content_is_bounded():
    assert len(markdown_safe.as_escaped_text("a" * 10_000, limit=100)) == 100


def test_an_excerpt_is_found_without_regular_expressions():
    page = "Specifications\n\nMemory: 16 GB GDDR6\n\nPower: 220 W"
    excerpt = markdown_safe.excerpt_around(page, "16 GB GDDR6")
    assert "16 GB GDDR6" in excerpt
    assert markdown_safe.excerpt_around(page, "not present") == ""
