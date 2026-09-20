"""Memory estimation rules from guide section 6."""

from __future__ import annotations

from decimal import Decimal

from app.engine.memory import estimate
from app.engine.policy import Policy
from app.schemas.catalog import ModelArchitecture
from app.schemas.common import Evidenced


def _model(snapshot, name: str):
    return next(m for m in snapshot.models if m.variant_name == name)


def test_estimate_uses_published_architecture_when_complete(snapshot, policy):
    model = _model(snapshot, "8B Q4_K_M")
    result = estimate(model, 8192, 1, policy)
    assert result is not None
    assert result.approximate is False
    assert result.weights_gb == Decimal("4.900")
    # 2 * 32 layers * 8 kv heads * 128 dim * 8192 tokens * 2 bytes = 1 GiB exactly.
    assert result.kv_cache_gb == Decimal("1.000")


def test_cache_grows_with_context_and_concurrency(snapshot, policy):
    model = _model(snapshot, "8B Q4_K_M")
    one = estimate(model, 8192, 1, policy)
    four = estimate(model, 8192, 4, policy)
    longer = estimate(model, 32768, 1, policy)
    assert four.kv_cache_gb == one.kv_cache_gb * 4
    assert longer.kv_cache_gb == one.kv_cache_gb * 4


def test_incomplete_architecture_is_marked_approximate(snapshot, policy):
    model = _model(snapshot, "8B Q4_K_M").model_copy(
        update={"architecture": ModelArchitecture(layers=None, kv_heads=None, head_dim=None)}
    )
    result = estimate(model, 8192, 1, policy)
    assert result is not None and result.approximate is True
    assert "fallback" in result.method


def test_unknown_weights_produce_no_estimate(snapshot, policy):
    model = _model(snapshot, "8B Q4_K_M").model_copy(update={"weights_gb": Evidenced()})
    assert estimate(model, 8192, 1, policy) is None


def test_parameter_count_alone_is_not_the_requirement(snapshot, policy):
    """The 8B model needs more than 8 GB once cache and overhead are counted."""
    model = _model(snapshot, "8B Q4_K_M")
    result = estimate(model, 32768, 2, policy)
    assert result.total_gpu_gb > result.weights_gb


def test_gpu_and_system_memory_are_reported_separately(snapshot, policy):
    model = _model(snapshot, "8B Q4_K_M")
    gpu = estimate(model, 8192, 1, policy)
    cpu = estimate(model, 8192, 1, policy, cpu_only=True)
    assert gpu.total_gpu_gb > 0 and gpu.total_system_ram_gb > 0
    assert cpu.total_gpu_gb == 0
    assert cpu.total_system_ram_gb > gpu.weights_gb
    # The two figures are never summed into one pooled number.
    assert gpu.total_gpu_gb != gpu.total_gpu_gb + gpu.total_system_ram_gb


def test_headroom_is_applied_to_gpu_memory():
    from app.seed.dataset import build_models, SEED_EPOCH

    model = build_models(SEED_EPOCH)[0]
    tight = estimate(model, 8192, 1, Policy(gpu_memory_headroom_fraction=Decimal("0")))
    padded = estimate(model, 8192, 1, Policy(gpu_memory_headroom_fraction=Decimal("0.25")))
    assert padded.total_gpu_gb > tight.total_gpu_gb
