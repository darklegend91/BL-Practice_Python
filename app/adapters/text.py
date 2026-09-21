"""Plain-string helpers for reading Markdown.

No regular expressions, no CSS selectors, no XPath. Real pages are messy, but
they are still just text, and the messiness here is handled by looking at the
characters rather than by pattern matching.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

DIGITS = "0123456789"


def strip_links(text: str) -> str:
    """``[label](url "title")`` becomes ``label``.

    Wikipedia puts a link in almost every cell, which is what makes its tables
    look unreadable in Markdown. Removing them first makes everything else easy.
    """
    out: list[str] = []
    index = 0
    while index < len(text):
        if text[index] == "[":
            close = text.find("]", index)
            if close != -1 and close + 1 < len(text) and text[close + 1] == "(":
                end = text.find(")", close)
                if end != -1:
                    out.append(text[index + 1:close])
                    index = end + 1
                    continue
        out.append(text[index])
        index += 1
    return "".join(out)


def logical_rows(markdown: str) -> list[str]:
    """Rejoin table rows that a link has split across several lines.

    A row starts with ``|``. Any following line that does not start with ``|``
    is a continuation of it, because the converter wrapped a long link. A blank
    line ends the row.
    """
    rows: list[str] = []
    current: str | None = None

    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("|"):
            if current is not None:
                rows.append(current)
            current = line
        elif current is not None:
            if line == "":
                rows.append(current)
                current = None
            else:
                current += " " + line

    if current is not None:
        rows.append(current)
    return rows


def cells(row: str) -> list[str]:
    """Split one table row into its cells, with links and footnotes removed."""
    return [strip_links(cell).strip() for cell in row.strip().strip("|").split("|")]


def first_number(text: str, *, after: str | None = None) -> Decimal | None:
    """The first number in the text, optionally the first one after a marker.

    ``first_number("¥12,999 ($1,835)", after="$")`` gives ``1835``, which is how
    a launch price written in two currencies is read.
    """
    if after is not None:
        position = text.find(after)
        if position < 0:
            return None
        text = text[position + len(after):]

    start = None
    for index, character in enumerate(text):
        if character in DIGITS:
            start = index
            break
    if start is None:
        return None

    collected: list[str] = []
    seen_dot = False
    for character in text[start:]:
        if character in DIGITS:
            collected.append(character)
        elif character == "," :
            continue  # thousands separator
        elif character == "." and not seen_dot:
            seen_dot = True
            collected.append(character)
        else:
            break

    try:
        number = Decimal("".join(collected).rstrip("."))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def size_in_gb(text: str) -> Decimal | None:
    """Read ``4.7GB``, ``243 GB``, ``512MB`` or ``1.2TB`` as a number of GB."""
    upper = text.upper()
    for unit, factor in (("TB", Decimal(1024)), ("GB", Decimal(1)), ("MB", Decimal(1) / Decimal(1024))):
        position = upper.find(unit)
        if position < 0:
            continue
        amount = first_number(upper[:position])
        if amount is None:
            continue
        return (amount * factor).quantize(Decimal("0.001"))
    return None


def tokens_from_context(text: str) -> int | None:
    """Read ``128K context window`` or ``32k`` as a token count."""
    upper = text.upper()
    position = upper.find("K")
    if position < 0:
        amount = first_number(upper)
        return int(amount) if amount is not None else None
    amount = first_number(upper[:position])
    if amount is None:
        return None
    return int(amount * 1024)


def slugify(text: str) -> str:
    """A stable identifier made only of lowercase letters, digits and dashes."""
    kept: list[str] = []
    for character in text.lower():
        if character.isalnum():
            kept.append(character)
        elif kept and kept[-1] != "-":
            kept.append("-")
    return "".join(kept).strip("-")[:120]
