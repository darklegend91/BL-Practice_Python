"""A small, clearly labelled sample catalog (guide section 14, stage 1).

Every record here is illustrative sample data with a placeholder source URL. It
is *not* verified vendor evidence and must never be presented as such; the
``SAMPLE_DATA_NOTICE`` is carried into anything built from it.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from uuid import UUID, uuid5, NAMESPACE_URL

from app.schemas.catalog import (
    BenchmarkObservation,
    CatalogSnapshot,
    HardwareRevision,
    LicenseTerms,
    ModelArchitecture,
    ModelRevision,
    PlanLimits,
    PlanRevision,
    PriceObservation,
    RevisionHeader,
)
from app.schemas.common import (
    AccessRequirement,
    BillingInterval,
    Claimed,
    EvidenceRef,
    Evidenced,
    Money,
    ReviewStatus,
    Workload,
)

SAMPLE_DATA_NOTICE = (
    "Sample catalog for development and tests. Values are illustrative, not "
    "reviewed vendor evidence, and must not be used for a real purchase decision."
)

SEED_EPOCH = dt.datetime(2026, 9, 15, 12, 0, tzinfo=dt.timezone.utc)


def _id(name: str) -> UUID:
    """Deterministic identifiers keep seeded data stable across reloads."""
    return uuid5(NAMESPACE_URL, f"https://example.invalid/llmfit/seed/{name}")


def _evidence(field_name: str, excerpt: str, reviewed_at: dt.datetime) -> EvidenceRef:
    return EvidenceRef(
        claim_id=_id(f"claim/{field_name}/{excerpt[:24]}"),
        field_name=field_name,
        source_url="https://example.invalid/sample-source",
        excerpt=excerpt,
        review_status=ReviewStatus.PUBLISHED,
        reviewed_at=reviewed_at,
        observed_at=reviewed_at,
    )


def _known(field_name: str, value, excerpt: str, reviewed_at: dt.datetime) -> Evidenced:
    return Evidenced(value=value, evidence=_evidence(field_name, excerpt, reviewed_at))


def _header(name: str, reviewed_at: dt.datetime) -> RevisionHeader:
    return RevisionHeader(
        item_id=_id(f"item/{name}"),
        revision_id=_id(f"revision/{name}"),
        review_status=ReviewStatus.PUBLISHED,
        published_at=reviewed_at,
        specs_reviewed_at=reviewed_at,
    )


def build_hardware(as_of: dt.datetime) -> list[HardwareRevision]:
    return [
        HardwareRevision(
            header=_header("gpu-16gb", as_of),
            component_role="gpu",
            vendor="SampleVendor",
            model_name="Accelerator 16G",
            vram_gb=_known("vram_gb", Decimal("16"), "16 GB GDDR6", as_of),
            whole_system_active_watts=_known(
                "whole_system_active_watts",
                Decimal("420"),
                "measured 420 W at the wall under load",
                as_of,
            ),
            whole_system_idle_watts=_known(
                "whole_system_idle_watts", Decimal("75"), "measured 75 W idle", as_of
            ),
            gpu_board_power_watts=_known(
                "gpu_board_power_watts", Decimal("220"), "220 W board power limit", as_of
            ),
            baseline_setup_hours=Decimal("1.5"),
        ),
        HardwareRevision(
            header=_header("gpu-24gb", as_of),
            component_role="gpu",
            vendor="SampleVendor",
            model_name="Accelerator 24G",
            vram_gb=_known("vram_gb", Decimal("24"), "24 GB GDDR6X", as_of),
            whole_system_active_watts=_known(
                "whole_system_active_watts", Decimal("520"), "measured 520 W at the wall", as_of
            ),
            whole_system_idle_watts=_known(
                "whole_system_idle_watts", Decimal("85"), "measured 85 W idle", as_of
            ),
            baseline_setup_hours=Decimal("1.5"),
        ),
        HardwareRevision(
            header=_header("workstation-24gb", as_of),
            component_role="complete_system",
            vendor="SampleVendor",
            model_name="Workstation 24G",
            vram_gb=_known("vram_gb", Decimal("24"), "24 GB GDDR6X", as_of),
            system_ram_gb=_known("system_ram_gb", Decimal("64"), "64 GB DDR5", as_of),
            storage_gb=_known("storage_gb", Decimal("2000"), "2 TB NVMe", as_of),
            whole_system_active_watts=_known(
                "whole_system_active_watts", Decimal("560"), "measured 560 W at the wall", as_of
            ),
            whole_system_idle_watts=_known(
                "whole_system_idle_watts", Decimal("95"), "measured 95 W idle", as_of
            ),
            requires_components=[],
            baseline_setup_hours=Decimal("3"),
        ),
    ]


def build_models(as_of: dt.datetime) -> list[ModelRevision]:
    return [
        ModelRevision(
            header=_header("model-8b-q4", as_of),
            family="SampleOpen",
            variant_name="8B Q4_K_M",
            parameters_billion=_known("parameters_billion", Decimal("8"), "8B parameters", as_of),
            quantization="Q4_K_M",
            weights_gb=_known("weights_gb", Decimal("4.9"), "4.9 GB GGUF file", as_of),
            max_context_tokens=_known(
                "max_context_tokens", 131_072, "128k token context window", as_of
            ),
            architecture=ModelArchitecture(layers=32, kv_heads=8, head_dim=128),
            supported_runtimes=["llama.cpp", "vllm"],
            license=LicenseTerms(
                open_weights=Claimed.SUPPORTED,
                osi_approved_license=Claimed.UNSUPPORTED,
                commercial_use_permitted=Claimed.SUPPORTED,
                license_name="SampleOpen Community License",
            ),
            capability_claims={
                Workload.CODING: Claimed.SUPPORTED,
                Workload.WRITING: Claimed.SUPPORTED,
                Workload.STUDYING: Claimed.SUPPORTED,
                Workload.DOCUMENT_ANALYSIS: Claimed.UNKNOWN,
            },
            runtime_overhead_gb=Decimal("1.0"),
            baseline_setup_hours=Decimal("2"),
        ),
        ModelRevision(
            header=_header("model-70b-q4", as_of),
            family="SampleOpen",
            variant_name="70B Q4_K_M",
            parameters_billion=_known("parameters_billion", Decimal("70"), "70B parameters", as_of),
            quantization="Q4_K_M",
            weights_gb=_known("weights_gb", Decimal("40"), "40 GB GGUF file", as_of),
            max_context_tokens=_known(
                "max_context_tokens", 32_768, "32k token context window", as_of
            ),
            architecture=ModelArchitecture(layers=80, kv_heads=8, head_dim=128),
            supported_runtimes=["llama.cpp"],
            license=LicenseTerms(
                open_weights=Claimed.SUPPORTED,
                osi_approved_license=Claimed.UNSUPPORTED,
                commercial_use_permitted=Claimed.UNKNOWN,
                license_name=None,
            ),
            capability_claims={
                Workload.CODING: Claimed.SUPPORTED,
                Workload.DOCUMENT_ANALYSIS: Claimed.SUPPORTED,
            },
            runtime_overhead_gb=Decimal("1.5"),
            baseline_setup_hours=Decimal("3"),
        ),
    ]


def build_plans(as_of: dt.datetime) -> list[PlanRevision]:
    return [
        PlanRevision(
            header=_header("plan-chat-monthly", as_of),
            provider="SampleHost",
            plan_name="Assistant Monthly",
            price=Money(amount=Decimal("20.00"), currency="EUR"),
            billing_interval=BillingInterval.MONTHLY,
            minimum_seats=1,
            commitment_months=1,
            available_regions=["DE", "FR", "NL"],
            supported_access=[AccessRequirement.INTERACTIVE_USE],
            limits=PlanLimits(
                messages_per_day=_known(
                    "messages_per_day", 200, "up to 200 messages per day", as_of
                ),
                max_context_tokens=_known(
                    "max_context_tokens", 32_768, "32k context per conversation", as_of
                ),
            ),
            capability_claims={
                Workload.CODING: Claimed.SUPPORTED,
                Workload.WRITING: Claimed.SUPPORTED,
                Workload.STUDYING: Claimed.SUPPORTED,
                Workload.DOCUMENT_ANALYSIS: Claimed.SUPPORTED,
            },
            commercial_use_permitted=Claimed.SUPPORTED,
            price_reviewed_at=as_of,
            baseline_setup_hours=Decimal("0.5"),
        ),
        PlanRevision(
            header=_header("plan-team-annual", as_of),
            provider="SampleHost",
            plan_name="Team Annual",
            price=Money(amount=Decimal("180.00"), currency="EUR"),
            billing_interval=BillingInterval.ANNUAL,
            minimum_seats=3,
            commitment_months=12,
            available_regions=["DE", "FR"],
            supported_access=[
                AccessRequirement.INTERACTIVE_USE,
                AccessRequirement.APPLICATION_INTEGRATION,
            ],
            limits=PlanLimits(
                messages_per_day=Evidenced(),  # deliberately undocumented
                max_context_tokens=_known(
                    "max_context_tokens", 65_536, "64k context per conversation", as_of
                ),
                fair_use_note="Documented as fair use without a numeric daily limit.",
            ),
            capability_claims={
                Workload.CODING: Claimed.SUPPORTED,
                Workload.DOCUMENT_ANALYSIS: Claimed.SUPPORTED,
            },
            commercial_use_permitted=Claimed.SUPPORTED,
            price_reviewed_at=as_of,
            baseline_setup_hours=Decimal("1"),
        ),
    ]


def build_prices(
    hardware: list[HardwareRevision], as_of: dt.datetime
) -> list[PriceObservation]:
    amounts = {
        "Accelerator 16G": Decimal("430.00"),
        "Accelerator 24G": Decimal("780.00"),
        "Workstation 24G": Decimal("2150.00"),
    }
    observations: list[PriceObservation] = []
    for item in hardware:
        for seller in ("SampleRetailerA", "SampleRetailerB"):
            markup = Decimal("1.00") if seller == "SampleRetailerA" else Decimal("1.04")
            observations.append(
                PriceObservation(
                    observation_id=_id(f"price/{item.model_name}/{seller}"),
                    revision_id=item.header.revision_id,
                    seller=seller,
                    region="DE",
                    price=Money(
                        amount=(amounts[item.model_name] * markup).quantize(Decimal("0.01")),
                        currency="EUR",
                    ),
                    tax_included=True,
                    in_stock=Claimed.SUPPORTED,
                    observed_at=as_of,
                    reviewed_at=as_of,
                    source_url="https://example.invalid/sample-offer",
                )
            )
    return observations


def build_benchmarks(models: list[ModelRevision], as_of: dt.datetime) -> list[BenchmarkObservation]:
    small = models[0]
    return [
        BenchmarkObservation(
            observation_id=_id("benchmark/8b-q4"),
            model_revision_id=small.header.revision_id,
            quantization="Q4_K_M",
            gpu_model="Accelerator 16G",
            runtime="llama.cpp",
            context_tokens=131_072,
            concurrency=4,
            tokens_per_second=Decimal("48.5"),
            measured_at=as_of,
            source_url="https://example.invalid/sample-benchmark",
        )
    ]


def build_snapshot(as_of: dt.datetime = SEED_EPOCH) -> CatalogSnapshot:
    """Assemble the sample data into one immutable snapshot."""
    hardware = build_hardware(as_of)
    models = build_models(as_of)
    return CatalogSnapshot(
        snapshot_id=_id("snapshot/sample"),
        taken_at=as_of,
        currency="EUR",
        hardware=hardware,
        models=models,
        plans=build_plans(as_of),
        prices=build_prices(hardware, as_of),
        benchmarks=build_benchmarks(models, as_of),
        plan_model_access=[],
    )
