"""Memory estimation for a local model configuration.

Parameter count alone does not establish required memory, and GPU VRAM is not
interchangeable with system RAM (guide section 6).
"""

from __future__ import annotations

from decimal import Decimal

from app.engine.policy import Policy
from app.schemas.catalog import ModelRevision
from app.schemas.result import MemoryEstimate

_GB = Decimal(1024) ** 3


def _kv_cache_gb_exact(
    model: ModelRevision, context_tokens: int, concurrency: int
) -> Decimal | None:
    """Key/value cache size from published architecture details, if complete."""
    arch = model.architecture
    if not (arch.layers and arch.kv_heads and arch.head_dim):
        return None
    bytes_total = (
        Decimal(2)  # one key and one value tensor
        * Decimal(arch.layers)
        * Decimal(arch.kv_heads)
        * Decimal(arch.head_dim)
        * Decimal(context_tokens)
        * Decimal(arch.kv_bytes_per_element)
        * Decimal(concurrency)
    )
    return bytes_total / _GB


def _kv_cache_gb_fallback(
    model: ModelRevision, context_tokens: int, concurrency: int, policy: Policy
) -> Decimal | None:
    params = model.parameters_billion.value
    if params is None:
        return None
    return (
        policy.kv_cache_fallback_gb_per_1k_tokens_per_b_params
        * (Decimal(context_tokens) / Decimal(1000))
        * params
        * Decimal(concurrency)
    )


def estimate(
    model: ModelRevision,
    context_tokens: int,
    concurrency: int,
    policy: Policy,
    *,
    cpu_only: bool = False,
) -> MemoryEstimate | None:
    """Return the estimate, or ``None`` when weights are unknown.

    Unknown weights produce no estimate at all rather than an invented number.
    """
    weights = model.weights_gb.value
    if weights is None:
        return None

    exact = _kv_cache_gb_exact(model, context_tokens, concurrency)
    if exact is not None:
        kv_cache, approximate, method = exact, False, "published architecture"
    else:
        fallback = _kv_cache_gb_fallback(model, context_tokens, concurrency, policy)
        if fallback is None:
            return None
        kv_cache, approximate, method = (
            fallback,
            True,
            "parameter-count fallback (architecture details incomplete)",
        )

    overhead = model.runtime_overhead_gb
    working_set = weights + kv_cache + overhead
    headroom = Decimal(1) + policy.gpu_memory_headroom_fraction

    if cpu_only:
        gpu_gb = Decimal(0)
        system_gb = working_set * policy.system_ram_multiplier_for_cpu_inference
        method += "; CPU-only execution"
    else:
        gpu_gb = working_set * headroom
        system_gb = policy.system_ram_for_gpu_inference_gb

    quantize = lambda value: value.quantize(Decimal("0.001"))  # noqa: E731
    return MemoryEstimate(
        weights_gb=quantize(weights),
        kv_cache_gb=quantize(kv_cache),
        runtime_overhead_gb=quantize(overhead),
        total_gpu_gb=quantize(gpu_gb),
        total_system_ram_gb=quantize(system_gb),
        approximate=approximate,
        method=method,
    )
