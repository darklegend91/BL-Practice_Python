"""CSV export hardening (guide section 11).

A spreadsheet treats a leading ``=``, ``+``, ``-``, ``@``, tab or carriage
return as the start of a formula. User-controlled strings are prefixed so the
cell is read as text.
"""

from __future__ import annotations

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def neutralize(value: object) -> object:
    """Return a value safe to place in a CSV cell."""
    if not isinstance(value, str):
        return value
    if value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value
