"""Bounded candidate generation (guide section 6, step 3).

A candidate pairs a deployment with everything needed to evaluate it. Local
candidates pair a hardware profile with one model revision; hosted candidates
are a single plan revision. The set is capped by policy so the engine's work
stays predictable.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.engine.policy import Policy
from app.schemas.catalog import (
    CatalogSnapshot,
    HardwareRevision,
    ModelRevision,
    PlanRevision,
)
from app.schemas.common import DeploymentKind, StrictModel
from app.schemas.scenario import ExpandedScenario


class HardwareProfile(StrictModel):
    """The machine a local candidate would actually run on."""

    label: str
    gpu_vram_gb: Decimal | None
    system_ram_gb: Decimal | None
    active_watts: Decimal | None
    idle_watts: Decimal | None
    power_is_measured: bool
    purchased_revisions: list[UUID] = Field(default_factory=list)
    """Revisions that must be bought. Existing equipment is not listed here."""
    setup_hours: Decimal = Decimal("0")


class Candidate(StrictModel):
    candidate_id: str
    label: str
    deployment: DeploymentKind
    hardware: HardwareProfile | None = None
    model: ModelRevision | None = None
    plan: PlanRevision | None = None
    cpu_only: bool = False

    @property
    def revision_ids(self) -> list[UUID]:
        ids: list[UUID] = []
        if self.hardware:
            ids.extend(self.hardware.purchased_revisions)
        if self.model:
            ids.append(self.model.header.revision_id)
        if self.plan:
            ids.append(self.plan.header.revision_id)
        return ids


def _existing_profile(scenario: ExpandedScenario, policy: Policy) -> HardwareProfile | None:
    inventory = scenario.source.inventory
    if inventory is None:
        return None
    measured = (
        inventory.measured_active_watts is not None
        and inventory.measured_idle_watts is not None
    )
    return HardwareProfile(
        label=inventory.label,
        gpu_vram_gb=(
            inventory.gpu_vram_gb * inventory.gpu_count
            if inventory.gpu_vram_gb is not None
            else None
        ),
        system_ram_gb=inventory.system_ram_gb,
        active_watts=inventory.measured_active_watts or policy.assumed_active_watts,
        idle_watts=inventory.measured_idle_watts or policy.assumed_idle_watts,
        power_is_measured=measured,
        purchased_revisions=[],
        setup_hours=Decimal("0"),
    )


def _upgrade_profiles(
    scenario: ExpandedScenario, snapshot: CatalogSnapshot, policy: Policy
) -> list[HardwareProfile]:
    """Existing machine plus one catalog GPU. Only the GPU is a new purchase."""
    base = _existing_profile(scenario, policy)
    if base is None:
        return []
    profiles: list[HardwareProfile] = []
    for gpu in snapshot.hardware:
        if gpu.component_role != "gpu" or gpu.vram_gb.value is None:
            continue
        profiles.append(
            HardwareProfile(
                label=f"{base.label} + {gpu.vendor} {gpu.model_name}",
                gpu_vram_gb=gpu.vram_gb.value,
                system_ram_gb=base.system_ram_gb,
                active_watts=(
                    gpu.whole_system_active_watts.value or policy.assumed_active_watts
                ),
                idle_watts=gpu.whole_system_idle_watts.value or policy.assumed_idle_watts,
                power_is_measured=gpu.whole_system_active_watts.value is not None,
                purchased_revisions=[gpu.header.revision_id],
                setup_hours=gpu.baseline_setup_hours,
            )
        )
    return profiles


def _new_machine_profiles(
    snapshot: CatalogSnapshot, policy: Policy
) -> list[HardwareProfile]:
    """Complete systems only. A bare GPU is never priced as a whole machine."""
    profiles: list[HardwareProfile] = []
    for system in snapshot.hardware:
        if system.component_role != "complete_system":
            continue
        profiles.append(
            HardwareProfile(
                label=f"{system.vendor} {system.model_name}",
                gpu_vram_gb=system.vram_gb.value,
                system_ram_gb=system.system_ram_gb.value,
                active_watts=(
                    system.whole_system_active_watts.value or policy.assumed_active_watts
                ),
                idle_watts=(
                    system.whole_system_idle_watts.value or policy.assumed_idle_watts
                ),
                power_is_measured=system.whole_system_active_watts.value is not None,
                purchased_revisions=[system.header.revision_id],
                setup_hours=system.baseline_setup_hours,
            )
        )
    return profiles


def generate(
    scenario: ExpandedScenario, snapshot: CatalogSnapshot, policy: Policy
) -> list[Candidate]:
    """Produce the bounded candidate set for one scenario."""
    candidates: list[Candidate] = []

    local_sets: list[tuple[DeploymentKind, HardwareProfile]] = []
    existing = _existing_profile(scenario, policy)
    if existing is not None:
        local_sets.append((DeploymentKind.EXISTING_LOCAL, existing))
    local_sets += [
        (DeploymentKind.LOCAL_UPGRADE, profile)
        for profile in _upgrade_profiles(scenario, snapshot, policy)
    ]
    local_sets += [
        (DeploymentKind.NEW_LOCAL_MACHINE, profile)
        for profile in _new_machine_profiles(snapshot, policy)
    ]

    for deployment, profile in local_sets:
        for model in snapshot.models:
            candidate_id = f"{deployment.value}:{profile.label}:{model.variant_name}"
            candidates.append(
                Candidate(
                    candidate_id=candidate_id,
                    label=f"{model.family} {model.variant_name} on {profile.label}",
                    deployment=deployment,
                    hardware=profile,
                    model=model,
                )
            )

    for plan in snapshot.plans:
        candidates.append(
            Candidate(
                candidate_id=(
                    f"{DeploymentKind.HOSTED_SUBSCRIPTION.value}:"
                    f"{plan.provider}:{plan.plan_name}"
                ),
                label=f"{plan.provider} {plan.plan_name}",
                deployment=DeploymentKind.HOSTED_SUBSCRIPTION,
                plan=plan,
            )
        )

    # Stable ordering keeps the bound deterministic when it bites.
    candidates.sort(key=lambda candidate: candidate.candidate_id)
    return candidates[: policy.max_candidates]
