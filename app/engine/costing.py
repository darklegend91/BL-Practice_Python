"""What each option costs, month by month.

Every amount is a ``Decimal``. Hardware you already own costs nothing new. An
annual plan is charged in full when it renews, not spread thinly across a
shorter comparison. A missing price is an error the caller handles, never a
zero.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

from app.engine.policy import Policy
from app.schemas import BillingInterval, Cost, Deployment, Month, RecommendInput

PLACES = Decimal("0.0001")


class Assumptions:
    """One of the three runs: low, base or high."""

    def __init__(self, case: str, description: str, usage: Decimal, power: Decimal) -> None:
        self.case = case
        self.description = description
        self.usage = usage
        self.power = power


BASE = Assumptions("base", "The numbers you gave", Decimal(1), Decimal(1))


def three_cases(policy: Policy) -> list[Assumptions]:
    return [
        Assumptions("low", "Less use and lower power draw", policy.low_usage, policy.low_power),
        BASE,
        Assumptions("high", "More use and higher power draw", policy.high_usage, policy.high_power),
    ]


class NoPrice(LookupError):
    """Something that has to be bought has no price in the chosen region."""


def money(value: Decimal) -> Decimal:
    return value.quantize(PLACES, rounding=ROUND_HALF_EVEN)


def electricity_kwh_per_month(
    machine, request: RecommendInput, used, policy: Policy, case: Assumptions
) -> Decimal | None:
    """Whole-machine electricity, not just the graphics card's rating."""
    if machine is None or machine.active_watts is None or machine.idle_watts is None:
        return None

    active = used.active_hours_per_day * case.usage
    idle = used.idle_hours_per_day
    if active + idle > Decimal(24):
        idle = max(Decimal(0), Decimal(24) - active)
        active = min(active, Decimal(24))

    watt_hours = (
        machine.active_watts * case.power * active + machine.idle_watts * case.power * idle
    )
    return policy.days_per_month * watt_hours / Decimal(1000)


def _subscription_charge(plan, request: RecommendInput, month: int) -> Decimal:
    """What the plan bills in this month of the comparison."""
    if plan.price is None:
        raise NoPrice(f"{plan.name} has no price")
    seats = max(request.seats, plan.min_seats)
    per_charge = plan.price * Decimal(seats)
    if plan.billing_interval is BillingInterval.MONTHLY:
        return per_charge
    # Annual: charged in full at renewal, never prorated.
    return per_charge if (month - 1) % 12 == 0 else Decimal(0)


def setup_hours(option_parts, used) -> Decimal:
    total = sum((part.setup_hours for part in option_parts if part is not None), Decimal(0))
    return money(total * used.setup_effort_multiplier)


def build(
    candidate, request: RecommendInput, used, policy: Policy, case: Assumptions = BASE
) -> Cost:
    """The full month-by-month schedule for one candidate."""
    currency = request.currency
    upfront = Decimal(0)

    for part in candidate.buys:
        if part.price is None or part.currency != currency:
            raise NoPrice(f"{part.name} has no {currency} price in {request.region}")
        upfront += part.price

    electricity_unknown = (
        candidate.deployment is not Deployment.SUBSCRIPTION
        and request.electricity_per_kwh is None
    )

    months: list[Month] = []
    running = money(upfront)
    for month in range(1, used.months + 1):
        if candidate.deployment is Deployment.SUBSCRIPTION:
            subscription = _subscription_charge(candidate.plan, request, month)
            electricity = None
        else:
            subscription = Decimal(0)
            kwh = electricity_kwh_per_month(candidate.machine, request, used, policy, case)
            electricity = (
                None
                if kwh is None or request.electricity_per_kwh is None
                else money(kwh * request.electricity_per_kwh)
            )

        this_month = subscription + (electricity or Decimal(0))
        running += this_month
        months.append(
            Month(
                month=month,
                electricity=electricity,
                subscription=money(subscription),
                total=money(this_month),
                running_total=money(running),
            )
        )

    return Cost(
        currency=currency,
        upfront=money(upfront),
        months=months,
        total=money(running),
        electricity_unknown=electricity_unknown,
    )
