"""The numbers the engine uses that are not yours to choose.

They live here rather than being scattered through the code, so you can see and
change them in one place.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class Policy(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Memory
    cache_gb_per_1k_tokens_per_billion_params: Decimal = Decimal("0.0020")
    """Only used when a model does not publish its layer counts. The estimate is
    then marked approximate."""
    gpu_headroom: Decimal = Decimal("0.10")
    system_ram_for_gpu_use_gb: Decimal = Decimal("8")

    # Power, when the hardware does not state a measured figure
    assumed_active_watts: Decimal = Decimal("450")
    assumed_idle_watts: Decimal = Decimal("80")

    # The low / base / high runs
    low_power: Decimal = Decimal("0.75")
    high_power: Decimal = Decimal("1.30")
    low_usage: Decimal = Decimal("0.60")
    high_usage: Decimal = Decimal("1.50")

    days_per_month: Decimal = Decimal("30.4375")  # 365.25 / 12
    max_options: int = 200


DEFAULT_POLICY = Policy()
