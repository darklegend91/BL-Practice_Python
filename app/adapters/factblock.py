"""Reads catalog rows out of a crawled Markdown page.

The page has to publish a small fact block. That is the whole trick: we do not
try to understand arbitrary vendor HTML, we read a format that states the
values plainly:

    ## hardware: sample-gpu-16g
    - name: SampleVendor Accelerator 16G
    - role: gpu
    - vram_gb: 16
    - price: 430.00 EUR
    - region: DE

Parsing is ordinary string splitting. There are no CSS selectors, no XPath and
no regular expressions anywhere in this file, which is a constraint from the
original design and also why it stays readable.

A page that does not use this format simply yields nothing. It is not a crash,
and it is not a guess.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.adapters.text import slugify  # noqa: F401  (kept for callers)
from app.schemas import BillingInterval, Hardware, Model, Plan, Workload

BLOCK_MARKER = "## "
FIELD_MARKER = "- "
KINDS = ("hardware", "model", "plan")


class Block:
    """One `## kind: slug` section and the fields under it."""

    def __init__(self, kind: str, slug: str) -> None:
        self.kind = kind
        self.slug = slug
        self.fields: dict[str, str] = {}


def _split_once(line: str, separator: str) -> tuple[str, str] | None:
    if separator not in line:
        return None
    left, right = line.split(separator, 1)
    return left.strip(), right.strip()


def blocks(markdown: str) -> list[Block]:
    """Find every fact block on the page."""
    found: list[Block] = []
    current: Block | None = None

    for raw in markdown.splitlines():
        line = raw.strip()

        if line.startswith(BLOCK_MARKER):
            current = None
            heading = _split_once(line[len(BLOCK_MARKER):], ":")
            if heading is None:
                continue
            kind, slug = heading
            kind = kind.lower()
            if kind in KINDS and slug:
                current = Block(kind, slug)
                found.append(current)
            continue

        if current is not None and line.startswith(FIELD_MARKER):
            field = _split_once(line[len(FIELD_MARKER):], ":")
            if field is None:
                continue
            key, value = field
            if key:
                current.fields[key.lower()] = value

    return found


# --------------------------------------------------------------------------- #
# Turning text into values. Anything unreadable becomes None, which means
# unknown, and the engine treats unknown as unknown.
# --------------------------------------------------------------------------- #


def as_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        number = Decimal(value.replace(",", "").strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def as_int(value: str | None) -> int | None:
    number = as_decimal(value)
    if number is None:
        return None
    try:
        return int(number)
    except (ValueError, OverflowError):
        return None


def as_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in ("yes", "true", "allowed", "permitted"):
        return True
    if lowered in ("no", "false", "not allowed", "forbidden"):
        return False
    return None


def as_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def as_money(value: str | None) -> tuple[Decimal | None, str | None]:
    """Reads `430.00 EUR` into an amount and a currency code."""
    if not value:
        return None, None
    parts = value.split()
    if len(parts) < 2:
        return as_decimal(value), None
    amount = as_decimal(parts[0])
    currency = parts[1].upper()
    if len(currency) != 3 or not currency.isalpha():
        return amount, None
    return amount, currency


def as_workloads(value: str | None) -> list[Workload]:
    known = {member.value for member in Workload}
    return [Workload(name) for name in as_list(value) if name in known]


# --------------------------------------------------------------------------- #
# Blocks to catalog rows
# --------------------------------------------------------------------------- #


def _hardware(block: Block, source_url: str) -> Hardware | None:
    fields = block.fields
    role = (fields.get("role") or "").lower()
    if role not in ("gpu", "system"):
        return None  # without a role we cannot tell a card from a whole machine
    price, currency = as_money(fields.get("price"))
    return Hardware(
        slug=block.slug,
        name=fields.get("name") or block.slug,
        role=role,
        vram_gb=as_decimal(fields.get("vram_gb")),
        ram_gb=as_decimal(fields.get("ram_gb")),
        active_watts=as_decimal(fields.get("active_watts")),
        idle_watts=as_decimal(fields.get("idle_watts")),
        price=price,
        currency=currency,
        region=(fields.get("region") or None),
        setup_hours=as_decimal(fields.get("setup_hours")) or Decimal("2"),
        source_url=source_url,
    )


def _model(block: Block, source_url: str) -> Model:
    fields = block.fields
    return Model(
        slug=block.slug,
        name=fields.get("name") or block.slug,
        params_b=as_decimal(fields.get("params_b")),
        quantization=fields.get("quantization"),
        weights_gb=as_decimal(fields.get("weights_gb")),
        max_context=as_int(fields.get("max_context")),
        layers=as_int(fields.get("layers")),
        kv_heads=as_int(fields.get("kv_heads")),
        head_dim=as_int(fields.get("head_dim")),
        commercial_use=as_bool(fields.get("commercial_use")),
        suitable_for=as_workloads(fields.get("suitable_for")),
        setup_hours=as_decimal(fields.get("setup_hours")) or Decimal("3"),
        source_url=source_url,
    )


def _plan(block: Block, source_url: str) -> Plan:
    fields = block.fields
    price, currency = as_money(fields.get("price"))
    interval = (fields.get("billing_interval") or "monthly").lower()
    return Plan(
        slug=block.slug,
        provider=fields.get("provider") or block.slug,
        name=fields.get("name") or block.slug,
        price=price,
        currency=currency,
        billing_interval=(
            BillingInterval.ANNUAL if interval == "annual" else BillingInterval.MONTHLY
        ),
        min_seats=as_int(fields.get("min_seats")) or 1,
        regions=[code.upper() for code in as_list(fields.get("regions"))],
        max_context=as_int(fields.get("max_context")),
        messages_per_day=as_int(fields.get("messages_per_day")),
        supports_api=as_bool(fields.get("supports_api")),
        commercial_use=as_bool(fields.get("commercial_use")),
        suitable_for=as_workloads(fields.get("suitable_for")),
        setup_hours=as_decimal(fields.get("setup_hours")) or Decimal("1"),
        source_url=source_url,
    )


def read(markdown: str, source_url: str, config: dict | None = None):
    """Everything this page has to say about the catalog."""
    from app.adapters import Found

    found = Found()
    for block in blocks(markdown):
        if block.kind == "hardware":
            row = _hardware(block, source_url)
            if row is not None:
                found.hardware.append(row)
        elif block.kind == "model":
            found.models.append(_model(block, source_url))
        else:
            found.plans.append(_plan(block, source_url))
    return found
