"""Settings, all from the environment with working local defaults.

Every name starts with ``LLMFIT_``. Copy ``.env.example`` to ``.env`` to change
them.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LLMFIT_", env_file=".env", extra="ignore", frozen=True
    )

    database_url: str = "postgresql+psycopg://llmfit:llmfit@localhost:5432/llmfit"

    # "fixture" reads saved pages from disk and needs no browser.
    # "crawl4ai" drives a real browser against the registered source URLs.
    crawler: str = "fixture"
    fixture_dir: str = "tests/fixtures/pages"
    crawl_timeout_seconds: int = 30
    max_page_bytes: int = 512 * 1024
    # Leave false unless you are pointing the crawler at a local test server;
    # true switches off the check that blocks internal addresses.
    allow_private_addresses: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
