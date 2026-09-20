"""Puts the options that fit in order, using whichever priority you chose.

The tie-breakers are fixed and written down, so the same question always gets
the same answer in the same order.
"""

from __future__ import annotations

from decimal import Decimal

from app.schemas import Deployment, Option, Priority

TIE_BREAKERS = (
    "lower total cost over the whole period",
    "lower upfront cost",
    "fewer setup hours",
    "identifier, alphabetically",
)

_LOCAL_FIRST = {
    Deployment.EXISTING_COMPUTER: 0,
    Deployment.UPGRADE: 1,
    Deployment.NEW_MACHINE: 2,
    Deployment.SUBSCRIPTION: 3,
}

_LAST = Decimal("1e15")


def _key(option: Option, priority: Priority) -> tuple:
    total = option.cost.total if option.cost else _LAST
    upfront = option.cost.upfront if option.cost else _LAST
    setup = option.setup_hours if option.setup_hours is not None else _LAST
    tail = (total, upfront, setup, option.id)

    if priority is Priority.LOWEST_COST:
        return tail
    if priority is Priority.LEAST_SETUP:
        return (setup, *tail)
    return (_LOCAL_FIRST[option.deployment], *tail)


def rank(options: list[Option], priority: Priority) -> list[Option]:
    return sorted(options, key=lambda option: _key(option, priority))
