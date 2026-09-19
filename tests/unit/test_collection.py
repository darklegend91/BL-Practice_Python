"""Collection boundary, change review and discovery (guide sections 5 and 13).

Every test here uses saved page fixtures; none touches a live vendor site.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

import pytest

from app.collection.adapter import CollectionError, FixtureBackend
from app.collection.changes import ChangeOutcome, evaluate
from app.collection.discovery import DiscoveryBudget, candidates_from_links, candidates_from_sitemap
from app.collection.snapshots import change_ratio, content_hash, diff, has_changed, normalize

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "pages"
PAGE = FIXTURES / "vendor.example.invalid" / "accelerators.md"
CHANGED_PAGE = FIXTURES / "vendor.example.invalid" / "accelerators-changed.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Hashing and change detection
# --------------------------------------------------------------------------- #


def test_whitespace_churn_is_not_a_change():
    """Reindentation and line-ending changes must not look like a price change."""
    original = "Price: 430.00 EUR\nStock: yes"
    reformatted = "\n\nPrice:   430.00 EUR  \r\nStock:\tyes\n\n"
    assert content_hash(original) == content_hash(reformatted)
    assert has_changed(original, reformatted) is False


def test_a_real_price_change_is_detected():
    assert has_changed(read(PAGE), read(CHANGED_PAGE)) is True


def test_an_identical_page_is_not_a_change():
    assert has_changed(read(PAGE), read(PAGE)) is False


def test_the_diff_shows_what_an_editor_must_review():
    text = diff(read(PAGE), read(CHANGED_PAGE))
    assert "-- Price (SampleRetailerA, DE): 430.00 EUR, in stock" in text
    assert "+- Price (SampleRetailerA, DE): 459.00 EUR, in stock" in text


def test_change_ratio_orders_the_review_queue():
    assert 0.0 < change_ratio(read(PAGE), read(CHANGED_PAGE)) < 1.0


# --------------------------------------------------------------------------- #
# Review tasks
# --------------------------------------------------------------------------- #


def test_a_first_snapshot_asks_an_editor_for_typed_values():
    task = evaluate("https://vendor.example.invalid/x", None, read(PAGE), dt.datetime.now(dt.timezone.utc))
    assert task.outcome is ChangeOutcome.FIRST_SNAPSHOT
    assert "typed values" in task.note


def test_an_unchanged_fetch_does_not_verify_any_claim():
    task = evaluate(
        "https://vendor.example.invalid/x", read(PAGE), read(PAGE),
        dt.datetime.now(dt.timezone.utc),
    )
    assert task.outcome is ChangeOutcome.UNCHANGED
    assert "does not independently verify" in task.note


def test_a_change_raises_review_without_asserting_which_field_changed():
    task = evaluate(
        "https://vendor.example.invalid/x", read(PAGE), read(CHANGED_PAGE),
        dt.datetime.now(dt.timezone.utc),
    )
    assert task.outcome is ChangeOutcome.CHANGED
    assert "does not prove" in task.note
    assert task.diff_text


# --------------------------------------------------------------------------- #
# The collection backend
# --------------------------------------------------------------------------- #


def test_the_fixture_backend_returns_a_bounded_snapshot():
    backend = FixtureBackend(FIXTURES)
    snapshot = asyncio.run(
        backend.fetch(
            "https://vendor.example.invalid/accelerators",
            allowed_hosts=["vendor.example.invalid"],
            timeout_seconds=5,
            max_bytes=512 * 1024,
        )
    )
    assert "Accelerator 16G" in snapshot.markdown
    assert snapshot.content_hash == content_hash(snapshot.markdown)
    assert snapshot.byte_size > 0


def test_the_maximum_page_size_is_a_hard_stop():
    backend = FixtureBackend(FIXTURES)
    snapshot = asyncio.run(
        backend.fetch(
            "https://vendor.example.invalid/accelerators",
            allowed_hosts=["vendor.example.invalid"],
            timeout_seconds=5,
            max_bytes=64,
        )
    )
    assert snapshot.byte_size <= 64


def test_a_missing_saved_page_is_a_permanent_failure():
    backend = FixtureBackend(FIXTURES)
    with pytest.raises(CollectionError) as failure:
        asyncio.run(
            backend.fetch(
                "https://vendor.example.invalid/nothing-here",
                allowed_hosts=["vendor.example.invalid"],
                timeout_seconds=5,
                max_bytes=1024,
            )
        )
    assert failure.value.permanent is True


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #


def test_discovery_stays_inside_the_approved_domains():
    found = candidates_from_links(
        [
            "/accelerators/16g",
            "https://vendor.example.invalid/accelerators/24g",
            "https://somewhere-else.example.com/deal",
        ],
        base_url="https://vendor.example.invalid/accelerators",
        allowed_hosts=["vendor.example.invalid"],
        depth=1,
        budget=DiscoveryBudget(),
    )
    assert [candidate.url for candidate in found] == [
        "https://vendor.example.invalid/accelerators/16g",
        "https://vendor.example.invalid/accelerators/24g",
    ]


def test_discovery_respects_the_page_budget():
    links = [f"/page-{index}" for index in range(100)]
    found = candidates_from_links(
        links,
        base_url="https://vendor.example.invalid/",
        allowed_hosts=["vendor.example.invalid"],
        depth=1,
        budget=DiscoveryBudget(max_pages=5),
    )
    assert len(found) == 5


def test_discovery_respects_the_depth_budget():
    found = candidates_from_links(
        ["/deep"],
        base_url="https://vendor.example.invalid/",
        allowed_hosts=["vendor.example.invalid"],
        depth=5,
        budget=DiscoveryBudget(max_depth=2),
    )
    assert found == []


def test_a_sitemap_is_parsed_with_the_standard_xml_parser():
    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://vendor.example.invalid/a</loc></url>
      <url><loc>https://vendor.example.invalid/b</loc></url>
      <url><loc>https://elsewhere.example.com/c</loc></url>
    </urlset>"""
    found = candidates_from_sitemap(
        sitemap,
        sitemap_url="https://vendor.example.invalid/sitemap.xml",
        allowed_hosts=["vendor.example.invalid"],
        budget=DiscoveryBudget(),
    )
    assert [candidate.url for candidate in found] == [
        "https://vendor.example.invalid/a",
        "https://vendor.example.invalid/b",
    ]


def test_a_malformed_sitemap_yields_nothing_rather_than_raising():
    assert (
        candidates_from_sitemap(
            "not xml at all",
            sitemap_url="https://vendor.example.invalid/sitemap.xml",
            allowed_hosts=["vendor.example.invalid"],
            budget=DiscoveryBudget(),
        )
        == []
    )
