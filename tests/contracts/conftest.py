"""Contract-test fixtures: a real application over a real database."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api import deps, ratelimit
from app.db.session import set_tenant
from app.main import create_app
from app.seed import dataset, load
from tests.integration.conftest import (  # noqa: F401  - fixtures are used by name
    clean_tables,
    migrated_database,
    owner_engine,
    owner_session,
    requires_postgres,
    runtime_engine,
    runtime_session,
)

pytestmark = requires_postgres


@pytest.fixture
def seeded(owner_engine, clean_tables):
    """Publish the sample catalog and return the accounts it created."""
    factory = sessionmaker(bind=owner_engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        result = load.seed(session, as_of=dataset.SEED_EPOCH)
        session.commit()
        return result
    finally:
        session.close()


@pytest.fixture
def client(runtime_engine, seeded):
    """A client whose requests use the non-privileged runtime role."""
    ratelimit.reset()
    application = create_app()
    factory = sessionmaker(bind=runtime_engine, expire_on_commit=False, future=True)

    def override_session():
        session = factory()
        try:
            set_tenant(session, None)  # fail closed until a principal is verified
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    application.dependency_overrides[deps.db_session] = override_session
    with TestClient(application, raise_server_exceptions=False) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def log_in(client: TestClient, email: str) -> str:
    response = client.post(
        "/v1/auth/login",
        json={"email": email, "password": load.DEFAULT_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def headers(token: str, organization_id=None) -> dict:
    result = {"Authorization": f"Bearer {token}"}
    if organization_id is not None:
        result["X-Organization-Id"] = str(organization_id)
    return result


def scenario_body(**overrides) -> dict:
    from tests.conftest import make_scenario

    return make_scenario(**overrides).model_dump(mode="json")
