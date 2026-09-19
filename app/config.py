"""Runtime configuration.

Secrets stay outside source control (guide section 11); every value here is read
from the environment with a development-safe default that is obviously local.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LLMFIT_", env_file=".env", extra="ignore", frozen=True
    )

    environment: str = "development"

    # --- database -----------------------------------------------------------
    # Runtime role: never the table owner, never superuser, never BYPASSRLS.
    database_url: str = "postgresql+psycopg://llmfit_app:llmfit_app@localhost:5432/llmfit"
    # Migrations run under a separate credential (guide section 11).
    migration_database_url: str = (
        "postgresql+psycopg://llmfit_migrate:llmfit_migrate@localhost:5432/llmfit"
    )
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_statement_timeout_ms: int = 10_000

    # --- sessions -----------------------------------------------------------
    session_ttl_seconds: int = 12 * 60 * 60
    session_token_bytes: int = 32

    # --- HTTP limits --------------------------------------------------------
    max_page_size: int = 100
    default_page_size: int = 25
    max_request_bytes: int = 1 * 1024 * 1024
    idempotency_retention_seconds: int = 24 * 60 * 60
    login_rate_limit_per_minute: int = 10
    write_rate_limit_per_minute: int = 60

    # --- collection ---------------------------------------------------------
    crawl_backend: str = "fixture"  # "fixture" | "crawl4ai"
    crawl_fixture_dir: str = "tests/fixtures/pages"
    crawl_max_page_bytes: int = 512 * 1024
    crawl_timeout_seconds: int = 30
    crawl_browser_concurrency: int = 2
    crawl_per_domain_min_interval_seconds: float = 2.0
    crawl_lease_seconds: int = 300
    crawl_max_attempts: int = 5
    crawl_allow_private_destinations: bool = False

    # --- catalog freshness (guide section 5) --------------------------------
    price_freshness_days: int = 7
    spec_freshness_days: int = 30

    # --- engine defaults ----------------------------------------------------
    max_candidate_configurations: int = 200
    default_currency: str = "EUR"
    default_hourly_value: Decimal = Field(default=Decimal("0"))

    @field_validator("crawl_backend")
    @classmethod
    def _known_backend(cls, value: str) -> str:
        if value not in {"fixture", "crawl4ai"}:
            raise ValueError("crawl_backend must be 'fixture' or 'crawl4ai'")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
