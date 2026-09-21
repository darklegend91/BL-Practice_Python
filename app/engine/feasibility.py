"""Decides whether each option is possible, impossible, or not yet knowable.

Three outcomes, and the third one matters: if a fact is missing, the option is
*uncertain*. It is not quietly assumed to be fine, and it does not compete with
options that are actually confirmed.
"""

from __future__ import annotations

from decimal import Decimal

from app.engine import reasons
from app.engine.candidates import Candidate
from app.engine.memory import needed as memory_needed
from app.engine.policy import Policy
from app.schemas import (
    AccessRequirement, Deployment, Finding, MemoryNeeded, RecommendInput, Workload,
)


class Check:
    """Collects what was found while looking at one option."""

    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.memory: MemoryNeeded | None = None

    def note(self, code: str, *, blocking: bool = False, **values: object) -> None:
        self.findings.append(
            Finding(code=code, message=reasons.say(code, **values), blocking=blocking)
        )

    @property
    def blocked(self) -> bool:
        return any(finding.blocking for finding in self.findings)

    @property
    def uncertain(self) -> bool:
        return any(finding.code in reasons.UNCERTAIN_CODES for finding in self.findings)


def check(
    candidate: Candidate, request: RecommendInput, used, policy: Policy
) -> Check:
    result = Check()
    if candidate.deployment is Deployment.SUBSCRIPTION:
        _check_subscription(candidate, request, used, result)
    else:
        _check_local(candidate, request, used, policy, result)
    return result


def _suitability(suitable_for, label: str, request: RecommendInput, result: Check) -> None:
    for workload in request.workloads:
        if not suitable_for:
            result.note(reasons.SUITABILITY_UNKNOWN, option=label, workload=workload.value)
        elif workload not in suitable_for:
            result.note(
                reasons.NOT_SUITABLE_FOR_WORKLOAD,
                blocking=True, option=label, workload=workload.value,
            )


def _check_subscription(
    candidate: Candidate, request: RecommendInput, used, result: Check
) -> None:
    plan = candidate.plan
    label = candidate.label

    if request.offline_only:
        result.note(reasons.OFFLINE_ONLY, blocking=True, option=label)

    if plan.regions and request.region not in plan.regions:
        result.note(
            reasons.NOT_IN_YOUR_REGION, blocking=True, option=label, region=request.region
        )

    if request.access is AccessRequirement.APPLICATION_INTEGRATION and not plan.supports_api:
        result.note(reasons.NO_API_ACCESS, blocking=True, option=label)

    if request.commercial_use:
        if plan.commercial_use is False:
            result.note(reasons.COMMERCIAL_USE_NOT_ALLOWED, blocking=True, option=label)
        elif plan.commercial_use is None:
            result.note(reasons.COMMERCIAL_USE_UNKNOWN, option=label)

    if plan.max_context is None:
        result.note(reasons.CONTEXT_LIMIT_UNKNOWN, option=label)
    elif plan.max_context < used.context_tokens:
        result.note(
            reasons.CONTEXT_TOO_SHORT, blocking=True, option=label,
            supported=plan.max_context, wanted=used.context_tokens,
        )

    if plan.messages_per_day is None:
        # A plan with no published limit cannot be compared with your workload.
        result.note(reasons.DAILY_LIMIT_UNKNOWN, option=label)
    elif plan.messages_per_day < used.requests_per_day:
        result.note(
            reasons.DAILY_LIMIT_TOO_LOW, blocking=True, option=label,
            limit=plan.messages_per_day, wanted=used.requests_per_day,
        )

    if plan.price is None:
        result.note(reasons.NO_PRICE, blocking=True, option=label, region=request.region)

    _suitability(plan.suitable_for, label, request, result)


def _check_local(
    candidate: Candidate, request: RecommendInput, used, policy: Policy, result: Check
) -> None:
    model = candidate.model
    machine = candidate.machine
    label = candidate.label
    # The context limit and the licence belong to the model, not to the pairing
    # of model and machine, so findings about them say the model's name.
    model_name = model.name

    # A model on your own machine is reachable by your own programs, so both
    # interactive use and application integration are fine.

    if request.commercial_use:
        if model.commercial_use is False:
            result.note(reasons.COMMERCIAL_USE_NOT_ALLOWED, blocking=True, option=model_name)
        elif model.commercial_use is None:
            result.note(reasons.COMMERCIAL_USE_UNKNOWN, option=model_name)

    if model.max_context is None:
        result.note(reasons.CONTEXT_LIMIT_UNKNOWN, option=model_name)
    elif model.max_context < used.context_tokens:
        result.note(
            reasons.CONTEXT_TOO_SHORT, blocking=True, option=model_name,
            supported=model.max_context, wanted=used.context_tokens,
        )

    memory = memory_needed(model, used.context_tokens, request.people_at_once, policy)
    result.memory = memory
    if memory is None:
        result.note(reasons.SUITABILITY_UNKNOWN, option=label, workload="memory sizing")
    else:
        if memory.approximate:
            result.note(reasons.MEMORY_ESTIMATE_APPROXIMATE, model=model.name)
        _check_memory(memory, machine, model, request, used, result)

    _suitability(model.suitable_for, model_name, request, result)

    if not machine.power_measured:
        result.note(reasons.POWER_IS_ASSUMED, machine=machine.label)

    if request.electricity_per_kwh is None:
        result.note(reasons.NO_ELECTRICITY_PRICE)

    for part in candidate.buys:
        if part.price is None or part.currency != request.currency:
            result.note(
                reasons.NO_PRICE, blocking=True, option=part.name, region=request.region
            )


def _check_memory(
    memory: MemoryNeeded, machine, model, request: RecommendInput, used, result: Check
) -> None:
    available_vram = machine.vram_gb
    if available_vram is None or available_vram < memory.gpu_total_gb:
        result.note(
            reasons.NOT_ENOUGH_VRAM, blocking=True,
            model=model.name, needed=memory.gpu_total_gb, tokens=used.context_tokens,
            sessions=request.people_at_once, machine=machine.label,
            available=available_vram if available_vram is not None else "an unknown amount of",
        )

    available_ram = machine.ram_gb
    if available_ram is None or available_ram < memory.system_ram_total_gb:
        result.note(
            reasons.NOT_ENOUGH_SYSTEM_RAM, blocking=True,
            model=model.name, needed=memory.system_ram_total_gb, machine=machine.label,
            available=available_ram if available_ram is not None else "an unknown amount of",
        )
