"""The versioned decision policy.

Policy lives in reviewed Python and versioned configuration. The application
never accepts executable rules from administrators (guide section 6).
"""

from __future__ import annotations

from decimal import Decimal

from app.schemas.common import StrictModel

POLICY_VERSION = "policy-2026-09-19"


class Policy(StrictModel):
    version: str = POLICY_VERSION

    # --- freshness ----------------------------------------------------------
    price_freshness_days: int = 7
    spec_freshness_days: int = 30
    allow_stale_evidence: bool = False
    """When a user explicitly asks for an estimate on stale data, the warning is
    still retained in the saved result."""

    # --- memory estimation --------------------------------------------------
    kv_cache_fallback_gb_per_1k_tokens_per_b_params: Decimal = Decimal("0.0020")
    """Used only when published architecture details are incomplete; the estimate
    is then labelled approximate."""
    gpu_memory_headroom_fraction: Decimal = Decimal("0.10")
    system_ram_for_gpu_inference_gb: Decimal = Decimal("8")
    system_ram_multiplier_for_cpu_inference: Decimal = Decimal("1.25")

    # --- power assumptions (labelled, user-changeable) ----------------------
    assumed_active_watts: Decimal = Decimal("450")
    assumed_idle_watts: Decimal = Decimal("80")
    low_case_power_factor: Decimal = Decimal("0.75")
    high_case_power_factor: Decimal = Decimal("1.30")
    low_case_usage_factor: Decimal = Decimal("0.60")
    high_case_usage_factor: Decimal = Decimal("1.50")

    days_per_month: Decimal = Decimal("30.4375")  # 365.25 / 12

    # --- bounds -------------------------------------------------------------
    max_candidates: int = 200

    # --- capability ---------------------------------------------------------
    require_capability_evidence: bool = False
    """False keeps an unknown-capability candidate as *uncertain* rather than
    ruled out; True rules it out. Unknown never counts as supported either way."""


DEFAULT_POLICY = Policy()
