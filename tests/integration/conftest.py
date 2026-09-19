"""Integration fixtures.

These tests run against a real PostgreSQL database, never SQLite: they exist to
verify migrations, transactions, row-level security, lease fencing and the
immutability triggers, none of which SQLite can represent (guide section 13).
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = os.environ.get(
    "LLMFIT_TEST_DATABASE_URL",
    "postgresql+psycopg://llmfit_app:llmfit_app@localhost:5432/llmfit_test",
)
TEST_MIGRATION_URL = os.environ.get(
    "LLMFIT_TEST_MIGRATION_DATABASE_URL",
    "postgresql+psycopg://llmfit_migrate:llmfit_migrate@localhost:5432/llmfit_test",
)


def _database_available() -> bool:
    try:
        engine = create_engine(TEST_MIGRATION_URL)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


requires_postgres = pytest.mark.skipif(
    not _database_available(),
    reason=(
        "no PostgreSQL test database; set LLMFIT_TEST_DATABASE_URL and "
        "LLMFIT_TEST_MIGRATION_DATABASE_URL"
    ),
)


@pytest.fixture(scope="session")
def migrated_database() -> str:
    """Apply migrations once per session, from a clean schema."""
    if not _database_available():
        pytest.skip("no PostgreSQL test database")
    environment = {
        **os.environ,
        "LLMFIT_MIGRATION_DATABASE_URL": TEST_MIGRATION_URL,
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"], check=False, env=environment, capture_output=True
    )
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], env=environment, capture_output=True, text=True
    )
    if completed.returncode != 0:
        pytest.fail(f"migrations failed:\n{completed.stdout}\n{completed.stderr}")
    return TEST_DB_URL


@pytest.fixture(scope="session")
def runtime_engine(migrated_database: str):
    """Engine using the non-owner runtime role, so RLS policies actually apply."""
    engine = create_engine(migrated_database, future=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def owner_engine(migrated_database: str):
    """Engine using the migration role, for setup that predates any tenant."""
    engine = create_engine(TEST_MIGRATION_URL, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def owner_session(owner_engine):
    factory = sessionmaker(bind=owner_engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


@pytest.fixture
def runtime_session(runtime_engine):
    factory = sessionmaker(bind=runtime_engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_tables(owner_engine, migrated_database):
    """Empty every table between tests so each one starts from a known state.

    One CASCADE truncate avoids depending on foreign-key ordering.
    """
    tables = ", ".join(
        [
            "audit_events", "benchmark_observations", "catalog_items",
            "catalog_revisions", "crawl_jobs", "evidence_claims", "idempotency_keys",
            "inventory_items", "memberships", "organizations", "plan_model_access",
            "price_observations", "recommendation_evidence", "recommendation_runs",
            "reviews", "scenario_revisions", "sessions", "source_snapshots",
            "sources", "users",
        ]
    )
    with owner_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} CASCADE"))
    yield


def as_tenant(session, organization_id: uuid.UUID | None) -> None:
    """Set the transaction-local workspace context that RLS policies read."""
    session.execute(
        text("SELECT set_config('app.organization_id', :value, true)"),
        {"value": str(organization_id) if organization_id else ""},
    )
