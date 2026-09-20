"""How much memory a model actually needs to run.

Three parts: the weights on disk, the cache that grows with how much text is in
play, and a fixed allowance for the runtime. The parameter count on its own
does not tell you this, and graphics memory is never interchangeable with
system memory.
"""

from __future__ import annotations

from decimal import Decimal

from app.engine.policy import Policy
from app.schemas import MemoryNeeded, Model

GB = Decimal(1024) ** 3


def _cache_gb(model: Model, tokens: int, sessions: int, policy: Policy) -> tuple[Decimal, bool] | None:
    """Cache size, and whether it had to be estimated rather than calculated."""
    if model.layers and model.kv_heads and model.head_dim:
        exact = (
            Decimal(2)                    # one key tensor and one value tensor
            * Decimal(model.layers)
            * Decimal(model.kv_heads)
            * Decimal(model.head_dim)
            * Decimal(tokens)
            * Decimal(2)                  # two bytes per number
            * Decimal(sessions)
        ) / GB
        return exact, False

    if model.params_b is None:
        return None

    rough = (
        policy.cache_gb_per_1k_tokens_per_billion_params
        * (Decimal(tokens) / Decimal(1000))
        * model.params_b
        * Decimal(sessions)
    )
    return rough, True


def needed(
    model: Model, tokens: int, sessions: int, policy: Policy
) -> MemoryNeeded | None:
    """Return the estimate, or ``None`` when the model's size is unknown.

    Unknown size gives no estimate at all, rather than a made-up number.
    """
    if model.weights_gb is None:
        return None

    cache = _cache_gb(model, tokens, sessions, policy)
    if cache is None:
        return None
    cache_gb, approximate = cache

    overhead = Decimal("1.0")
    working = model.weights_gb + cache_gb + overhead

    def round3(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.001"))

    return MemoryNeeded(
        weights_gb=round3(model.weights_gb),
        context_cache_gb=round3(cache_gb),
        overhead_gb=round3(overhead),
        gpu_total_gb=round3(working * (Decimal(1) + policy.gpu_headroom)),
        system_ram_total_gb=round3(policy.system_ram_for_gpu_use_gb),
        approximate=approximate,
    )
