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


def load(session: Session, *, region: str | None = None) -> Catalog:
    """Everything published, optionally narrowed to one region."""
    hardware_query = select(HardwareRow).order_by(HardwareRow.slug)
    if region is not None:
        # A card priced only for another country is not an option here.
        hardware_query = hardware_query.where(
            (HardwareRow.region == region) | (HardwareRow.region.is_(None))
        )

    hardware = [
        Hardware(
            slug=row.slug, name=row.name, role=row.role,
            vram_gb=_decimal(row.vram_gb), ram_gb=_decimal(row.ram_gb),
            active_watts=_decimal(row.active_watts), idle_watts=_decimal(row.idle_watts),
            price=_decimal(row.price), currency=row.currency, region=row.region,
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
            price=_decimal(row.price), currency=row.currency,
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
