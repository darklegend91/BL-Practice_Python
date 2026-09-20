"""The crawler: fetch a page, store it, and fill the catalog from it.

Uses saved pages, so no test here touches the internet.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select, text

from app import crawler, netguard
from app.config import Settings
from app.db import Hardware, Model, Page, Plan, Source
from tests.conftest import FIXTURE_PAGES, needs_database

pytestmark = needs_database

VENDOR = "https://sample-vendor.example.invalid/gpus"
MODELS = "https://sample-models.example.invalid/open-models"
PLANS = "https://sample-host.example.invalid/plans"


@pytest.fixture(autouse=True)
def fixture_backend(monkeypatch):
    settings = Settings(crawler="fixture", fixture_dir=str(FIXTURE_PAGES))
    monkeypatch.setattr("app.crawler.get_settings", lambda: settings)
    monkeypatch.setattr("app.netguard.get_settings", lambda: settings)


def add_source(session, url: str) -> None:
    session.add(Source(url=url))
    session.flush()


def run(session):
    return asyncio.run(crawler.crawl_all(session))


def test_crawling_fills_the_catalog(session):
    for url in (VENDOR, MODELS, PLANS):
        add_source(session, url)

    report = run(session)
    session.flush()

    assert report.failures == 0
    assert report.rows == 7  # 3 hardware, 2 models, 2 plans
    assert len(session.scalars(select(Hardware)).all()) == 3
    assert len(session.scalars(select(Model)).all()) == 2
    assert len(session.scalars(select(Plan)).all()) == 2


def test_the_page_itself_is_kept_so_you_can_check_it(session):
    add_source(session, VENDOR)
    run(session)
    session.flush()

    page = session.scalars(select(Page).where(Page.url == VENDOR)).first()
    assert page is not None
    assert "Accelerator 16G" in page.markdown
    assert page.rows_found == 3
    assert page.content_hash


def test_values_land_in_the_right_columns(session):
    add_source(session, VENDOR)
    run(session)
    session.flush()

    card = session.scalars(select(Hardware).where(Hardware.slug == "gpu-16g")).first()
    assert float(card.vram_gb) == 16.0
    assert float(card.price) == 430.0
    assert card.currency == "EUR"
    assert card.source_url == VENDOR


def test_crawling_twice_updates_rather_than_duplicates(session):
    add_source(session, VENDOR)
    run(session)
    session.flush()
    run(session)
    session.flush()

    assert len(session.scalars(select(Hardware)).all()) == 3
    assert len(session.scalars(select(Page)).all()) == 1


def test_an_unchanged_page_is_reported_as_unchanged(session):
    add_source(session, VENDOR)
    first = run(session)
    session.flush()
    second = run(session)
    session.flush()

    assert first.visited[0]["changed"] is True
    assert second.visited[0]["changed"] is False


def test_a_changed_price_is_picked_up(session):
    add_source(session, VENDOR)
    run(session)
    session.flush()

    session.execute(text("UPDATE pages SET content_hash = 'something else'"))
    session.execute(text("UPDATE hardware SET price = 999 WHERE slug = 'gpu-16g'"))
    session.flush()

    run(session)
    session.flush()

    card = session.scalars(select(Hardware).where(Hardware.slug == "gpu-16g")).first()
    assert float(card.price) == 430.0  # back to what the page says


def test_a_missing_page_is_reported_and_does_not_stop_the_rest(session):
    add_source(session, "https://sample-vendor.example.invalid/does-not-exist")
    add_source(session, VENDOR)

    report = run(session)
    session.flush()

    assert report.failures == 1
    assert report.rows == 3  # the good source still ran
    failed = next(entry for entry in report.visited if "error" in entry)
    assert "no saved page" in failed["error"]


def test_a_disabled_source_is_skipped(session):
    add_source(session, VENDOR)
    session.execute(text("UPDATE sources SET enabled = false"))
    session.flush()

    assert run(session).visited == []


def test_an_unsafe_source_url_is_refused_not_fetched(session):
    session.add(Source(url="http://127.0.0.1/admin"))
    session.flush()

    report = run(session)
    assert report.failures == 1
    assert "not a public address" in report.visited[0]["error"]


def test_whitespace_changes_do_not_count_as_a_change():
    first = "- price: 430.00 EUR\n- region: DE"
    second = "\n\n-   price:   430.00 EUR  \r\n- region:\tDE\n\n"
    assert crawler.fingerprint(first) == crawler.fingerprint(second)


def test_a_real_change_changes_the_fingerprint():
    assert crawler.fingerprint("- price: 430.00 EUR") != crawler.fingerprint(
        "- price: 459.00 EUR"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1/admin",
        "http://10.0.0.1/internal",
        "file:///etc/passwd",
        "http://user:secret@example.com/",
        "http://example.com:22/",
    ],
)
def test_the_guard_refuses_what_it_should(url):
    with pytest.raises(netguard.Blocked):
        netguard.check_shape(url)


def test_the_guard_allows_an_ordinary_public_page():
    assert netguard.check_shape("https://vendor.example.com/gpus")
