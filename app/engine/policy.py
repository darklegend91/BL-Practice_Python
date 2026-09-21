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
    rest_of_machine_active_watts: Decimal = Decimal("120")
    """Added to a card's board rating to guess what the whole machine draws.
    A card's rating is not a measurement of the machine around it, so anything
    built this way is reported as an assumption."""
    rest_of_machine_idle_watts: Decimal = Decimal("60")

    # The low / base / high runs
    low_power: Decimal = Decimal("0.75")
    high_power: Decimal = Decimal("1.30")
    low_usage: Decimal = Decimal("0.60")
    high_usage: Decimal = Decimal("1.50")

    days_per_month: Decimal = Decimal("30.4375")  # 365.25 / 12
    max_options: int = 200


DEFAULT_POLICY = Policy()
