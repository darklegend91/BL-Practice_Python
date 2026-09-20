"""Release identity recorded on every saved recommendation (guide section 6)."""

APP_VERSION = "0.1.0"
"""Application release. Stored with results so past decisions stay reproducible."""

SCENARIO_SCHEMA_VERSION = "scenario-2026-09-19"
"""Version of the structured input contract in ``app.schemas.scenario``."""

CATALOG_SCHEMA_VERSION = "catalog-2026-09-19"
"""Version of the typed catalog attribute contracts."""

PRESET_VERSION = "presets-2026-09-19"
"""Version of the questionnaire presets that expand into explicit values."""

RESULT_SCHEMA_VERSION = "result-2026-09-19"
"""Version of the persisted result contract."""
