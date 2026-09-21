"""Reads graphics cards out of a Wikipedia specification table.

Wikipedia's GPU tables have two-level headers and a link in nearly every cell,
so column positions cannot be guessed. Each source therefore carries a small
configuration saying which column is which, and how many cells a data row has.

That cell count is the safety catch. If the table is edited and the shape
changes, rows stop matching and the adapter returns nothing, rather than
reading the wrong column and writing a confident, wrong number into the
catalog.

What it takes from the page:

* the card's name,
* memory size in GB,
* board power in watts,
* the launch price in US dollars, where one is listed.

Board power is **not** whole-system power. It is stored separately and the app
turns it into a clearly-flagged assumption rather than pretending it is a
measurement.
"""

from __future__ import annotations

from decimal import Decimal

from app.adapters.text import cells, first_number, logical_rows, slugify
from app.schemas import Hardware

# Graphics memory is not sold in arbitrary amounts. Checking against the sizes
# that actually exist is a far better guard than a range: if a table's columns
# shift and we read a die size or a bandwidth figure by mistake, the number
# almost never lands on one of these, so the row is dropped instead of being
# written into the catalog as fact.
REAL_VRAM_SIZES = frozenset(Decimal(size) for size in (
    1, 2, 3, 4, 5, 6, 8, 10, 11, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128, 141, 192,
))
PLAUSIBLE_WATTS = (Decimal("15"), Decimal("1200"))
PLAUSIBLE_PRICE = (Decimal("50"), Decimal("50000"))


def _within(value: Decimal | None, bounds: tuple[Decimal, Decimal]) -> Decimal | None:
    """Keep a number only if it is believable. Nonsense becomes unknown."""
    if value is None:
        return None
    low, high = bounds
    return value if low <= value <= high else None


def _bare_number(cell: str) -> Decimal | None:
    """A number only when the cell is just a number.

    ``GDDR6X`` contains a 6 but is not a memory size, and reading it as one is
    how a wrong figure gets into the catalog looking perfectly reasonable.
    """
    text = cell.strip().replace(",", "")
    if not text or not text.replace(".", "", 1).isdigit():
        return None
    return first_number(text)


def _real_memory_size(cell: str) -> Decimal | None:
    """Keep a memory size only if the cell is a number cards actually come in."""
    value = _bare_number(cell)
    if value is None:
        return None
    return value if value in REAL_VRAM_SIZES else None


def _price_in_dollars(cell: str) -> Decimal | None:
    """Read a launch price, which Wikipedia writes in one of two ways.

    Either a bare US figure such as ``299``, or two currencies together such as
    ``¥12,999 ($1,835)``. Anything else - a code name like ``AD104-350``, say -
    is not a price, and reading a number out of it would be worse than reading
    nothing, so only these two shapes are accepted.
    """
    text = cell.strip()
    if not text:
        return None
    if "$" in text:
        return first_number(text, after="$")
    bare = text.replace(",", "").replace(" ", "")
    if bare.replace(".", "", 1).isdigit():
        return first_number(bare)
    return None


def _spaced(name: str) -> str:
    """``GeForceRTX 4090D`` reads better as ``GeForce RTX 4090D``.

    The converter drops the space between two spans. Put one back only where a
    lowercase letter runs into the start of an all-caps word, which is the case
    that actually happens here. Splitting on every capital would turn
    ``GeForce`` into ``Ge Force``.
    """
    out: list[str] = []
    for index, character in enumerate(name):
        starts_caps_word = (
            index > 0
            and character.isupper()
            and name[index - 1].islower()
            and index + 1 < len(name)
            and name[index + 1].isupper()
        )
        if starts_caps_word:
            out.append(" ")
        out.append(character)
    return "".join(out)


def read(markdown: str, source_url: str, config: dict) -> tuple[list[Hardware], list[str]]:
    """Read the cards, and say what was skipped.

    Config carries a list of ``layouts``. Each one says how many cells a row of
    that shape has and which column holds what::

        {"name_contains": "GeForce",
         "layouts": [{"cells": 20, "columns": {"name": 0, "price": 2,
                                               "vram_gb": 13, "board_watts": 19}}]}

    Wikipedia merges cells, so rows of the same table genuinely differ in width
    and some of them do not carry a memory size at all. Only rows matching a
    configured layout are read. Everything else is counted and reported, so the
    gap is visible instead of silent.
    """
    layouts = {
        int(layout["cells"]): layout.get("columns", {})
        for layout in config.get("layouts", [])
        if "cells" in layout
    }
    name_contains = config.get("name_contains", "")

    if not layouts:
        return [], ["no layouts configured for this source, so nothing was read"]

    found: list[Hardware] = []
    seen: set[str] = set()
    skipped_shape = 0
    skipped_no_vram = 0

    for row in logical_rows(markdown):
        values = cells(row)
        columns = layouts.get(len(values))
        if columns is None:
            if len(values) > 8 and name_contains and name_contains in values[0]:
                skipped_shape += 1
            continue

        name_at = columns.get("name")
        if name_at is None or name_at >= len(values):
            continue
        vram_at = columns.get("vram_gb")
        watts_at = columns.get("board_watts")
        price_at = columns.get("price")

        name = values[name_at]
        if name_contains and name_contains not in name:
            continue

        # A footnote marker can trail the name; keep only the readable part.
        name = name.split("[")[0].strip()
        if not name:
            continue

        vram = _real_memory_size(values[vram_at]) if vram_at is not None else None
        if vram is None:
            skipped_no_vram += 1
            continue  # a card we cannot size is no use to the engine

        slug = slugify(name)
        if slug in seen:
            continue
        seen.add(slug)

        board_watts = _within(
            first_number(values[watts_at]) if watts_at is not None else None,
            PLAUSIBLE_WATTS,
        )
        price = _within(
            _price_in_dollars(values[price_at]) if price_at is not None else None,
            PLAUSIBLE_PRICE,
        )

        found.append(Hardware(
            slug=slug,
            name=_spaced(name),
            role="gpu",
            vram_gb=vram,
            gpu_board_watts=board_watts,
            price=price,
            currency="USD" if price is not None else None,
            region="US" if price is not None else None,
            price_note=(
                "Launch price from Wikipedia, in US dollars. This is the price at "
                "release, not what a shop charges today."
                if price is not None else None
            ),
            setup_hours=Decimal("1.5"),
            source_url=source_url,
        ))

    notes: list[str] = []
    if skipped_shape:
        notes.append(
            f"{skipped_shape} row(s) looked like cards but had a cell count with no "
            "configured layout, so they were left out rather than guessed at"
        )
    if skipped_no_vram:
        notes.append(f"{skipped_no_vram} row(s) carried no memory size and were left out")
    return found, notes
