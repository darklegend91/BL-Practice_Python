"""Cash and optional time cost (guide section 6, "Cost calculation").

All money is ``Decimal``. Existing hardware costs nothing in the incremental
cash view; an annual commitment is never silently prorated; a missing price or
tariff is unknown rather than zero.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from uuid import UUID

from app.engine.candidates import Candidate
from app.engine.policy import Policy
from app.schemas.catalog import CatalogSnapshot
from app.schemas.common import BillingInterval, DeploymentKind, Money, StrictModel
from app.schemas.result import CostBreakdown, MonthlyCost
from app.schemas.scenario import ExpandedScenario

CENTS = Decimal("0.0001")


class Assumptions(StrictModel):
    """One sensitivity case. ``base`` uses the user's own values unchanged."""

    case_id: str = "base"
    description: str = "User-supplied values"
    usage_factor: Decimal = Decimal("1")
    power_factor: Decimal = Decimal("1")


BASE_CASE = Assumptions()


def cases(policy: Policy) -> list[Assumptions]:
    return [
        Assumptions(
            case_id="low",
            description="Lower usage and lower whole-system power",
            usage_factor=policy.low_case_usage_factor,
            power_factor=policy.low_case_power_factor,
        ),
        BASE_CASE,
        Assumptions(
            case_id="high",
            description="Higher usage and higher whole-system power",
            usage_factor=policy.high_case_usage_factor,
            power_factor=policy.high_case_power_factor,
        ),
    ]


class PriceUnavailable(LookupError):
    """Raised when a required price has no reviewed observation."""


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(CENTS, rounding=ROUND_HALF_EVEN)


def _cheapest_offer(
    snapshot: CatalogSnapshot, revision_id: UUID, region: str, currency: str
) -> Money:
    offers = [
        offer
        for offer in snapshot.offers_for(revision_id, region)
        if offer.price.currency == currency
    ]
    if not offers:
        raise PriceUnavailable(f"no reviewed {currency} price for revision {revision_id}")
    return min((offer.price for offer in offers), key=lambda price: price.amount)


# --------------------------------------------------------------------------- #
# Energy
# --------------------------------------------------------------------------- #


def monthly_energy_kwh(
    scenario: ExpandedScenario, candidate: Candidate, policy: Policy, case: Assumptions
) -> Decimal | None:
    hardware = candidate.hardware
    if hardware is None or hardware.active_watts is None or hardware.idle_watts is None:
        return None
    operating = scenario.operating_time
    active_hours = operating.active_hours_per_day * case.usage_factor
    idle_hours = operating.idle_hours_per_day
    total = active_hours + idle_hours
    if total > Decimal(24):
        # Scaled-up usage cannot invent a longer day; idle time gives way first.
        idle_hours = max(Decimal(0), Decimal(24) - active_hours)
        active_hours = min(active_hours, Decimal(24))
    watt_hours_per_day = (
        hardware.active_watts * case.power_factor * active_hours
        + hardware.idle_watts * case.power_factor * idle_hours
    )
    return policy.days_per_month * watt_hours_per_day / Decimal(1000)


# --------------------------------------------------------------------------- #
# Recurring charges
# --------------------------------------------------------------------------- #


def _plan_charge_for_month(
    candidate: Candidate, scenario: ExpandedScenario, month: int
) -> Money:
    """Charge billed in a given 1-based month of the horizon.

    A twelve-month commitment is billed in full at its renewal month; it is not
    spread across a shorter comparison window.
    """
    plan = candidate.plan
    assert plan is not None
    seats = max(scenario.source.seats, plan.minimum_seats)
    per_event = plan.price.scaled(Decimal(seats))
    if plan.billing_interval is BillingInterval.MONTHLY:
        return per_event
    cycle = max(plan.commitment_months, 12)
    return per_event if (month - 1) % cycle == 0 else Money.zero(plan.price.currency)


# --------------------------------------------------------------------------- #
# Whole breakdown
# --------------------------------------------------------------------------- #


def setup_hours(candidate: Candidate, scenario: ExpandedScenario) -> Decimal:
    baseline = Decimal("0")
    if candidate.hardware is not None:
        baseline += candidate.hardware.setup_hours
    if candidate.model is not None:
        baseline += candidate.model.baseline_setup_hours
    if candidate.plan is not None:
        baseline += candidate.plan.baseline_setup_hours
    return _round(baseline * scenario.setup_effort_multiplier)


def build(
    candidate: Candidate,
    scenario: ExpandedScenario,
    snapshot: CatalogSnapshot,
    policy: Policy,
    case: Assumptions = BASE_CASE,
) -> CostBreakdown:
    """Compute the month-by-month cash schedule for one candidate.

    Raises ``PriceUnavailable`` when a required purchase has no reviewed price;
    the caller turns that into a ``PRICE_MISSING`` finding rather than a zero.
    """
    currency = scenario.currency
    months = scenario.months

    upfront = Money.zero(currency)
    if candidate.hardware is not None:
        for revision_id in candidate.hardware.purchased_revisions:
            upfront = upfront + _cheapest_offer(
                snapshot, revision_id, scenario.source.region, currency
            )

    tariff = scenario.source.electricity_tariff_per_kwh
    energy_unknown = candidate.deployment is not DeploymentKind.HOSTED_SUBSCRIPTION and (
        tariff is None
    )

    schedule: list[MonthlyCost] = []
    cumulative = Money(amount=_round(upfront.amount), currency=currency)
    for month in range(1, months + 1):
        if candidate.deployment is DeploymentKind.HOSTED_SUBSCRIPTION:
            recurring = _plan_charge_for_month(candidate, scenario, month)
            energy: Money | None = None
        else:
            recurring = Money.zero(currency)
            kwh = monthly_energy_kwh(scenario, candidate, policy, case)
            if kwh is None or tariff is None:
                energy = None
            else:
                energy = Money(amount=_round(kwh * tariff.amount), currency=currency)

        month_total = recurring + (energy or Money.zero(currency))
        cumulative = cumulative + month_total
        schedule.append(
            MonthlyCost(
                month=month,
                energy=energy,
                recurring=Money(amount=_round(recurring.amount), currency=currency),
                total=Money(amount=_round(month_total.amount), currency=currency),
                cumulative=Money(amount=_round(cumulative.amount), currency=currency),
            )
        )

    time_cost: Money | None = None
    hourly = scenario.source.hourly_value
    if hourly is not None and hourly.amount > 0:
        hours = setup_hours(candidate, scenario) + (
            scenario.source.maintenance_allowance_hours_per_month * Decimal(months)
        )
        time_cost = Money(amount=_round(hours * hourly.amount), currency=hourly.currency)

    return CostBreakdown(
        currency=currency,
        upfront=Money(amount=_round(upfront.amount), currency=currency),
        monthly=schedule,
        horizon_total=Money(amount=_round(cumulative.amount), currency=currency),
        optional_time_cost=time_cost,
        energy_unknown=energy_unknown,
    )
