"""Builds the list of things worth comparing.

Four kinds, from the guide's original four questions:

1. the computer you already have,
2. that computer plus one new graphics card,
3. a whole new machine,
4. a subscription.

Local options are paired with each model in the catalog, because "will it run"
depends on both.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.engine.policy import Policy
from app.schemas import Catalog, Deployment, Hardware, Model, Plan, RecommendInput


@dataclass(frozen=True)
class Machine:
    """The computer an option would actually run on."""

    label: str
    vram_gb: Decimal | None
    ram_gb: Decimal | None
    active_watts: Decimal | None
    idle_watts: Decimal | None
    power_measured: bool
    setup_hours: Decimal


@dataclass(frozen=True)
class Candidate:
    id: str
    label: str
    deployment: Deployment
    machine: Machine | None = None
    model: Model | None = None
    plan: Plan | None = None
    buys: list[Hardware] = field(default_factory=list)
    """Hardware that has to be purchased. What you already own is not listed."""

    @property
    def sources(self) -> list[str]:
        urls = [part.source_url for part in self.buys]
        if self.model:
            urls.append(self.model.source_url)
        if self.plan:
            urls.append(self.plan.source_url)
        return [url for url in dict.fromkeys(urls) if url]


def _yours(request: RecommendInput, policy: Policy) -> Machine | None:
    owned = request.existing_computer
    if owned is None:
        return None
    measured = owned.active_watts is not None and owned.idle_watts is not None
    return Machine(
        label=owned.label,
        vram_gb=owned.gpu_vram_gb,
        ram_gb=owned.system_ram_gb,
        active_watts=owned.active_watts or policy.assumed_active_watts,
        idle_watts=owned.idle_watts or policy.assumed_idle_watts,
        power_measured=measured,
        setup_hours=Decimal(0),
    )


def build(request: RecommendInput, catalog: Catalog, policy: Policy) -> list[Candidate]:
    candidates: list[Candidate] = []
    machines: list[tuple[Deployment, Machine, list[Hardware]]] = []

    yours = _yours(request, policy)
    if yours is not None:
        machines.append((Deployment.EXISTING_COMPUTER, yours, []))

        # Your computer plus one new card. Only the card is bought.
        for card in catalog.hardware:
            if card.role != "gpu" or card.vram_gb is None:
                continue
            machines.append((
                Deployment.UPGRADE,
                Machine(
                    label=f"{yours.label} plus {card.name}",
                    vram_gb=card.vram_gb,
                    ram_gb=yours.ram_gb,
                    active_watts=card.active_watts or policy.assumed_active_watts,
                    idle_watts=card.idle_watts or policy.assumed_idle_watts,
                    power_measured=card.active_watts is not None,
                    setup_hours=card.setup_hours,
                ),
                [card],
            ))

    # A complete machine. A bare graphics card is never priced as a whole computer.
    for system in catalog.hardware:
        if system.role != "system":
            continue
        machines.append((
            Deployment.NEW_MACHINE,
            Machine(
                label=system.name,
                vram_gb=system.vram_gb,
                ram_gb=system.ram_gb,
                active_watts=system.active_watts or policy.assumed_active_watts,
                idle_watts=system.idle_watts or policy.assumed_idle_watts,
                power_measured=system.active_watts is not None,
                setup_hours=system.setup_hours,
            ),
            [system],
        ))

    for deployment, machine, buys in machines:
        for model in catalog.models:
            candidates.append(Candidate(
                id=f"{deployment.value}:{machine.label}:{model.slug}",
                label=f"{model.name} on {machine.label}",
                deployment=deployment,
                machine=machine,
                model=model,
                buys=list(buys),
            ))

    for plan in catalog.plans:
        candidates.append(Candidate(
            id=f"{Deployment.SUBSCRIPTION.value}:{plan.slug}",
            label=f"{plan.provider} {plan.name}",
            deployment=Deployment.SUBSCRIPTION,
            plan=plan,
        ))

    candidates.sort(key=lambda candidate: candidate.id)
    return candidates[: policy.max_options]
