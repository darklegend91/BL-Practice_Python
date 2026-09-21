"""Reads downloadable model variants from an Ollama library tags page.

Each variant is one line of the form::

    llama3.1:8b-instruct-q4_K_M  abc123  •  4.9GB  •  128K context window  • ...

which is far friendlier than most real pages: the fields are separated by a
bullet, so splitting on it is enough. The download size is the size of the
weights, which is exactly what the memory estimate needs.

Parameter counts come from the tag itself (``8b``, ``70b``, ``405b``). The
model's layer counts are not published here, so they stay unknown and the
memory estimate is reported as approximate, which is true.
"""

from __future__ import annotations

from decimal import Decimal

from app.adapters.text import first_number, size_in_gb, slugify, strip_links, tokens_from_context
from app.schemas import Model

BULLET = "•"
PLAUSIBLE_WEIGHTS_GB = (Decimal("0.05"), Decimal("2000"))


def _params_from_tag(tag: str) -> Decimal | None:
    """``llama3.1:70b-instruct-q4_K_M`` gives 70 billion parameters."""
    after_colon = tag.split(":", 1)[-1]
    for part in after_colon.replace("-", " ").split():
        lowered = part.lower()
        if lowered.endswith("b") and lowered[:-1].replace(".", "", 1).isdigit():
            amount = first_number(lowered)
            if amount is not None and Decimal("0.1") <= amount <= Decimal("5000"):
                return amount
    return None


def _quantization_from_tag(tag: str) -> str | None:
    after_colon = tag.split(":", 1)[-1]
    for part in after_colon.split("-"):
        lowered = part.lower()
        if lowered.startswith("q") and any(ch.isdigit() for ch in lowered):
            return part
        if lowered in ("fp16", "f16", "fp32", "bf16"):
            return part
    return None


def read(markdown: str, source_url: str, config: dict) -> list[Model]:
    """Config: optional ``only_quantizations`` and ``max_models``."""
    wanted = {q.lower() for q in config.get("only_quantizations", [])}
    limit = config.get("max_models", 40)

    found: list[Model] = []
    seen: set[str] = set()

    for raw in markdown.splitlines():
        line = strip_links(raw).strip()
        if BULLET not in line or ":" not in line:
            continue

        parts = [part.strip() for part in line.split(BULLET)]
        head = parts[0]
        tag = head.split()[0] if head.split() else ""
        if ":" not in tag:
            continue

        weights = size_in_gb(" ".join(parts[1:2]))
        if weights is None or not (
            PLAUSIBLE_WEIGHTS_GB[0] <= weights <= PLAUSIBLE_WEIGHTS_GB[1]
        ):
            continue

        quantization = _quantization_from_tag(tag)
        if wanted and (quantization or "").lower() not in wanted:
            continue

        slug = slugify(tag)
        if slug in seen:
            continue
        seen.add(slug)

        context = None
        for part in parts[2:]:
            if "context" in part.lower():
                context = tokens_from_context(part)
                break

        found.append(Model(
            slug=slug,
            name=tag,
            params_b=_params_from_tag(tag),
            quantization=quantization,
            weights_gb=weights,
            max_context=context,
            # Ollama does not publish layer counts, so the cache size has to be
            # estimated and the result is marked approximate.
            layers=None, kv_heads=None, head_dim=None,
            # Licences differ per model and are not stated on this page.
            commercial_use=None,
            suitable_for=[],
            setup_hours=Decimal("1"),
            source_url=source_url,
        ))
        if len(found) >= limit:
            break

    return found
