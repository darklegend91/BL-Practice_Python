"""Loads the catalog out of the database and into the shapes the engine reads.

The engine never touches the database itself. This is the only place that
turns rows into Pydantic objects, which is why the engine is easy to test.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Hardware as HardwareRow, Model as ModelRow, Plan as PlanRow
from app.schemas import BillingInterval, Catalog, Hardware, Model, Plan, Workload


def _workloads(values) -> list[Workload]:
    known = {member.value for member in Workload}
    return [Workload(name) for name in (values or []) if name in known]


def _decimal(value) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _priced(row, convert_to, rates, converted, *, with_region: bool = True) -> dict:
    """The price fields for one row, in the currency being asked about."""
    price, currency, note = _to_currency(
        _decimal(row.price), row.currency, convert_to, rates, converted,
        getattr(row, "name", row.slug), getattr(row, "price_note", None),
    )
    fields = {"price": price, "currency": currency, "price_note": note}
    if with_region:
        fields["region"] = row.region
    return fields


class Converted:
    """What a load had to convert, so the answer can say so."""

    def __init__(self) -> None:
        self.rates_used: list[str] = []
        self.left_out: list[str] = []

    def note(self, rate) -> None:
        line = rate.describe()
        if line not in self.rates_used:
            self.rates_used.append(line)

    def skipped(self, name: str, currency: str, wanted: str) -> None:
        line = f"{name} is priced in {currency} and there is no reviewed {currency}/{wanted} rate"
        if line not in self.left_out:
            self.left_out.append(line)


def _to_currency(price, currency, wanted, rates, converted, name, note):
    """Return (price, currency, note) in the currency being asked about.

    A price already in that currency passes through. One that is not is
    converted if there is a reviewed rate, and the note says which rate. With
    no rate the price is dropped, because a number in the wrong currency is
    worse than no number.
    """
    if price is None or wanted is None or currency is None or currency == wanted:
        return price, currency, note

    rate = rates.find(currency, wanted)
    if rate is None:
        converted.skipped(name, currency, wanted)
        return None, None, note

    converted.note(rate)
    was = f"{price} {currency}"
    carried = f"{note} " if note else ""
    return (
        rate.convert(price),
        wanted,
        f"{carried}Converted from {was} at {rate.describe()}. "
        f"Any import duty or local tax is not included.",
    )


def load(
    session: Session,
    *,
    region: str | None = None,
    convert_to: str | None = None,
    rates=None,
    converted: "Converted | None" = None,
) -> Catalog:
    """Everything published, optionally narrowed to one region.

    ``convert_to`` puts every price into that currency using the reviewed rates,
    and records what it did in ``converted`` so the answer can show it.
    """
    from app.rates import Rates

    rates = rates if rates is not None else Rates()
    converted = converted if converted is not None else Converted()
    hardware_query = select(HardwareRow).order_by(HardwareRow.slug)
    # When converting, a price quoted elsewhere is still usable once it is in
    # your currency, so the country it came from stops being a filter and
    # becomes something the note tells you about.
    if region is not None and convert_to is None:
        # A card priced only for another country is not an option here.
        hardware_query = hardware_query.where(
            (HardwareRow.region == region) | (HardwareRow.region.is_(None))
        )

    hardware = [
        Hardware(
            slug=row.slug, name=row.name, role=row.role,
            vram_gb=_decimal(row.vram_gb), ram_gb=_decimal(row.ram_gb),
            active_watts=_decimal(row.active_watts), idle_watts=_decimal(row.idle_watts),
            gpu_board_watts=_decimal(row.gpu_board_watts),
            **_priced(row, convert_to, rates, converted),
            setup_hours=_decimal(row.setup_hours) or Decimal("2"),
            source_url=row.source_url, updated_at=row.updated_at,
        )
        for row in session.scalars(hardware_query).all()
    ]

    models = [
        Model(
            slug=row.slug, name=row.name, params_b=_decimal(row.params_b),
            quantization=row.quantization, weights_gb=_decimal(row.weights_gb),
            max_context=row.max_context, layers=row.layers, kv_heads=row.kv_heads,
            head_dim=row.head_dim, commercial_use=row.commercial_use,
            suitable_for=_workloads(row.suitable_for),
            setup_hours=_decimal(row.setup_hours) or Decimal("3"),
            source_url=row.source_url, updated_at=row.updated_at,
        )
        for row in session.scalars(select(ModelRow).order_by(ModelRow.slug)).all()
    ]

    plans = [
        Plan(
            slug=row.slug, provider=row.provider, name=row.name,
            **_priced(row, convert_to, rates, converted, with_region=False),
            billing_interval=BillingInterval(row.billing_interval),
            min_seats=row.min_seats, regions=list(row.regions or []),
            max_context=row.max_context, messages_per_day=row.messages_per_day,
            supports_api=row.supports_api, commercial_use=row.commercial_use,
            suitable_for=_workloads(row.suitable_for),
            setup_hours=_decimal(row.setup_hours) or Decimal("1"),
            source_url=row.source_url, updated_at=row.updated_at,
        )
        for row in session.scalars(select(PlanRow).order_by(PlanRow.slug)).all()
    ]

    return Catalog(hardware=hardware, models=models, plans=plans)


def answer_for(session: Session, request, *, rates=None):
    """Load the catalog in the asked-for currency and run the engine over it.

    Both the command line and the web API go through here, so neither can end
    up converting differently from the other.
    """
    from app.engine.recommend import recommend

    converted = Converted()
    available = load(
        session, region=request.region, convert_to=request.currency,
        rates=rates, converted=converted,
    )

    assumptions: list[str] = []
    for line in converted.rates_used:
        assumptions.append(f"Prices converted at {line}.")
    if converted.rates_used:
        assumptions.append(
            "A converted price is only as good as that rate, and does not "
            "include import duty or local tax."
        )
    for line in converted.left_out:
        assumptions.append(f"Left out: {line}.")

    return recommend(request, available, extra_assumptions=assumptions)
