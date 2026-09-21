"""Fixtures for the app's own tests.

The engine tests need no database at all. The database and API tests use a real
PostgreSQL test database and skip cleanly if there is not one.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.schemas import Catalog, Hardware, Model, Plan, RecommendInput, Workload

TEST_DATABASE_URL = os.environ.get(
    "LLMFIT_TEST_DATABASE_URL",
    "postgresql+psycopg://llmfit:llmfit@localhost:5432/llmfit_test",
)

FIXTURE_PAGES = Path(__file__).parent / "fixtures" / "pages"


def _database_reachable() -> bool:
    try:
        engine = create_engine(TEST_DATABASE_URL)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


needs_database = pytest.mark.skipif(
    not _database_reachable(),
    reason="no PostgreSQL test database; set LLMFIT_TEST_DATABASE_URL",
)


@pytest.fixture(scope="session")
def migrated() -> str:
    if not _database_reachable():
        pytest.skip("no PostgreSQL test database")
    environment = {**os.environ, "LLMFIT_DATABASE_URL": TEST_DATABASE_URL}
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        check=False, env=environment, capture_output=True,
    )
    done = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=environment, capture_output=True, text=True,
    )
    if done.returncode != 0:
        pytest.fail(f"migrations failed:\n{done.stdout}\n{done.stderr}")
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def engine(migrated: str):
    made = create_engine(migrated, future=True)
    yield made
    made.dispose()


@pytest.fixture(autouse=True)
def empty_tables(request):
    """Every database test starts from empty tables."""
    if "engine" not in request.fixturenames:
        return
    made = request.getfixturevalue("engine")
    with made.begin() as connection:
        connection.execute(text("TRUNCATE sources, pages, hardware, models, plans"))


@pytest.fixture
def session(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    made = factory()
    try:
        yield made
        made.commit()
    finally:
        made.close()


@pytest.fixture
def client(engine, monkeypatch):
    """A TestClient wired to the test database, with the fixture crawler."""
    from fastapi.testclient import TestClient

    from app import db as db_module
    from app.config import Settings, get_settings

    settings = Settings(
        database_url=TEST_DATABASE_URL,
        crawler="fixture",
        fixture_dir=str(FIXTURE_PAGES),
    )
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.crawler.get_settings", lambda: settings)
    monkeypatch.setattr("app.netguard.get_settings", lambda: settings)

    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    monkeypatch.setattr(db_module, "get_sessionmaker", lambda: factory)

    from app.main import app as application

    with TestClient(application, raise_server_exceptions=False) as made:
        yield made


# --------------------------------------------------------------------------- #
# Catalog builders for the engine tests
# --------------------------------------------------------------------------- #


def a_gpu(slug="gpu-16g", vram="16", price="430.00", **kwargs) -> Hardware:
    defaults = dict(
        slug=slug, name=f"Card {slug}", role="gpu",
        vram_gb=Decimal(vram), active_watts=Decimal("420"), idle_watts=Decimal("75"),
        price=Decimal(price), currency="EUR", region="DE", setup_hours=Decimal("1.5"),
    )
    defaults.update(kwargs)
    return Hardware(**defaults)


def a_system(slug="workstation", vram="24", ram="64", price="2150.00", **kwargs) -> Hardware:
    defaults = dict(
        slug=slug, name=f"Machine {slug}", role="system",
        vram_gb=Decimal(vram), ram_gb=Decimal(ram),
        active_watts=Decimal("560"), idle_watts=Decimal("95"),
        price=Decimal(price), currency="EUR", region="DE", setup_hours=Decimal("3"),
    )
    defaults.update(kwargs)
    return Hardware(**defaults)


def a_model(slug="small", weights="4.9", context=131072, params="8", **kwargs) -> Model:
    defaults = dict(
        slug=slug, name=f"Model {slug}", params_b=Decimal(params), quantization="Q4_K_M",
        weights_gb=Decimal(weights), max_context=context,
        layers=32, kv_heads=8, head_dim=128, commercial_use=True,
        suitable_for=[Workload.CODING, Workload.WRITING], setup_hours=Decimal("2"),
    )
    defaults.update(kwargs)
    return Model(**defaults)


def a_plan(slug="chat", price="20.00", interval="monthly", **kwargs) -> Plan:
    defaults = dict(
        slug=slug, provider="SampleHost", name=f"Plan {slug}",
        price=Decimal(price), currency="EUR", billing_interval=interval,
        min_seats=1, regions=["DE", "FR"], max_context=32768, messages_per_day=200,
        supports_api=False, commercial_use=True,
        suitable_for=[Workload.CODING, Workload.WRITING], setup_hours=Decimal("0.5"),
    )
    defaults.update(kwargs)
    return Plan(**defaults)


def a_catalog(hardware=None, models=None, plans=None) -> Catalog:
    return Catalog(
        hardware=hardware if hardware is not None else [a_gpu(), a_system()],
        models=models if models is not None else [a_model()],
        plans=plans if plans is not None else [a_plan()],
    )


def ask(**overrides) -> RecommendInput:
    """A working request; keyword arguments replace individual fields."""
    base = dict(
        workloads=["coding"], usage="medium", months=24,
        region="DE", currency="EUR",
        electricity_per_kwh=Decimal("0.32"), hours_for_setup=Decimal("40"),
        existing_computer={
            "label": "my computer", "gpu_vram_gb": "16", "system_ram_gb": "32",
            "active_watts": "410", "idle_watts": "70",
        },
    )
    base.update(overrides)
    return RecommendInput(**base)


@pytest.fixture
def catalog() -> Catalog:
    return a_catalog()


@pytest.fixture
def cli_database(engine, monkeypatch):
    """Point the CLI's own session maker at the test database."""
    from app import db as db_module
    from app.config import Settings

    settings = Settings(
        database_url=TEST_DATABASE_URL, crawler="fixture",
        fixture_dir=str(FIXTURE_PAGES),
    )
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.crawler.get_settings", lambda: settings)
    monkeypatch.setattr("app.netguard.get_settings", lambda: settings)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    monkeypatch.setattr(db_module, "get_sessionmaker", lambda: factory)
    return engine
