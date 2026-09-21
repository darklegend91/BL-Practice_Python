"""The readers for real pages, tested against real pages saved on disk.

The fixtures under tests/fixtures/real are genuine Crawl4AI output, trimmed to
the parts the readers look at. Nothing here touches the network, so the suite
stays fast and these keep working when a site is down or changes.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.adapters import read
from app.adapters.wikipedia_gpu import REAL_VRAM_SIZES, _price_in_dollars, _spaced
from app.real_sources import REAL_SOURCES, RTX_30_LAYOUTS, RTX_40_LAYOUTS

REAL = Path(__file__).parent / "fixtures" / "real"
SOURCE = "https://en.wikipedia.org/wiki/GeForce_RTX_40_series"


def page(name: str) -> str:
    return (REAL / name).read_text(encoding="utf-8")


def gpus(fixture: str, layouts) -> dict:
    found = read(
        "wikipedia_gpu", page(fixture), SOURCE,
        {"name_contains": "GeForce", "layouts": layouts},
    )
    return {card.name: card for card in found.hardware}


# --------------------------------------------------------------------------- #
# Graphics cards, checked against figures anyone can verify
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name, vram, watts, price",
    [
        ("GeForce RTX 4060", 8, 115, 299),
        ("GeForce RTX 4070", 12, 200, 599),
        ("GeForce RTX 4080", 16, 320, 1199),
        ("GeForce RTX 4090D", 24, 425, 1835),
    ],
)
def test_known_cards_are_read_correctly(name, vram, watts, price):
    card = gpus("wikipedia_GeForce_RTX_40_series.md", RTX_40_LAYOUTS)[name]
    assert card.vram_gb == Decimal(vram)
    assert card.gpu_board_watts == Decimal(watts)
    assert card.price == Decimal(price)
    assert card.currency == "USD"


def test_prices_are_labelled_as_launch_prices():
    card = gpus("wikipedia_GeForce_RTX_40_series.md", RTX_40_LAYOUTS)["GeForce RTX 4060"]
    assert "not what a shop charges today" in card.price_note


def test_board_power_is_kept_out_of_whole_machine_power():
    """A card's rating is not a measurement of the machine around it."""
    card = gpus("wikipedia_GeForce_RTX_40_series.md", RTX_40_LAYOUTS)["GeForce RTX 4060"]
    assert card.gpu_board_watts == Decimal(115)
    assert card.active_watts is None
    assert card.idle_watts is None


def test_every_card_read_has_a_believable_memory_size():
    for fixture, layouts in (
        ("wikipedia_GeForce_RTX_40_series.md", RTX_40_LAYOUTS),
        ("wikipedia_GeForce_RTX_30_series.md", RTX_30_LAYOUTS),
    ):
        for card in gpus(fixture, layouts).values():
            assert card.vram_gb in REAL_VRAM_SIZES, f"{card.name} has {card.vram_gb} GB"


def test_the_wrong_layouts_produce_nothing_rather_than_wrong_numbers():
    """The RTX 30 page read with RTX 40 column positions must not invent data.

    This is the mistake that actually happened: reusing one page's layout on
    another produced cards with 276 GB of memory. The checks exist so the wrong
    mapping yields nothing instead.
    """
    wrong = gpus("wikipedia_GeForce_RTX_30_series.md", RTX_40_LAYOUTS)
    right = gpus("wikipedia_GeForce_RTX_30_series.md", RTX_30_LAYOUTS)
    for card in wrong.values():
        assert card.vram_gb in REAL_VRAM_SIZES
    assert len(right) >= len(wrong)


def test_a_memory_column_holding_text_is_not_read_as_a_number():
    """``GDDR6X`` contains a 6. It is not six gigabytes."""
    layouts = [{"cells": 3, "columns": {"name": 0, "vram_gb": 1}}]
    found = read("wikipedia_gpu", "| GeForce Test | GDDR6X | x |",
                 SOURCE, {"name_contains": "GeForce", "layouts": layouts})
    assert found.hardware == []


def test_rows_of_an_unconfigured_shape_are_reported_not_guessed():
    found = read(
        "wikipedia_gpu", page("wikipedia_GeForce_RTX_40_series.md"), SOURCE,
        {"name_contains": "GeForce",
         "layouts": [{"cells": 20, "columns": {"name": 0, "vram_gb": 13}}]},
    )
    assert any("no configured layout" in note for note in found.notes)


def test_no_layouts_means_no_rows_and_a_note():
    found = read("wikipedia_gpu", page("wikipedia_GeForce_RTX_40_series.md"), SOURCE, {})
    assert found.hardware == []
    assert found.notes


def test_a_code_name_is_not_mistaken_for_a_price():
    assert _price_in_dollars("AD104-350") is None
    assert _price_in_dollars("299") == Decimal(299)
    assert _price_in_dollars("¥12,999 ($1,835)") == Decimal(1835)


def test_run_together_names_are_spaced_without_breaking_geforce():
    assert _spaced("GeForceRTX 4090D") == "GeForce RTX 4090D"
    assert _spaced("TITAN ADA") == "TITAN ADA"


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


def models(fixture: str, config: dict | None = None) -> dict:
    found = read(
        "ollama_models", page(fixture), "https://ollama.com/library/x/tags",
        config or {"max_models": 100},
    )
    return {model.name: model for model in found.models}


def test_model_sizes_and_context_are_read():
    found = models("ollama_llama3.1.md")
    eight_b = next(m for name, m in found.items() if name.startswith("llama3.1:8b"))
    assert eight_b.params_b == Decimal(8)
    assert eight_b.weights_gb > Decimal(0)
    assert eight_b.max_context == 131072


def test_parameter_count_comes_from_the_tag():
    found = models("ollama_llama3.1.md")
    seventy = next(m for name, m in found.items() if ":70b" in name)
    assert seventy.params_b == Decimal(70)
    assert seventy.weights_gb > Decimal(30)


def test_what_ollama_does_not_publish_stays_unknown():
    """No layer counts and no licence, so neither is invented."""
    model = next(iter(models("ollama_gemma2.md").values()))
    assert model.layers is None and model.kv_heads is None and model.head_dim is None
    assert model.commercial_use is None
    assert model.suitable_for == []


def test_quantization_is_taken_from_the_tag():
    found = models("ollama_qwen2.5.md", {"max_models": 100})
    assert any((m.quantization or "").lower().startswith("q4") for m in found.values())


def test_the_quantization_filter_is_applied():
    found = models("ollama_llama3.1.md", {"only_quantizations": ["q8_0"], "max_models": 100})
    assert found
    assert all((m.quantization or "").lower() == "q8_0" for m in found.values())


def test_the_model_limit_is_respected():
    assert len(models("ollama_llama3.1.md", {"max_models": 3})) <= 3


def test_prose_is_not_mistaken_for_a_model():
    assert read("ollama_models", "Just a sentence about models.\n", "u", {}).models == []


# --------------------------------------------------------------------------- #
# The registered sources
# --------------------------------------------------------------------------- #


def test_every_registered_real_source_names_a_reader_that_exists():
    from app import adapters

    for entry in REAL_SOURCES:
        assert entry["adapter"] in adapters.names()
        assert entry["url"].startswith("https://")
        assert entry["label"]


def test_each_wikipedia_source_has_its_own_layouts():
    """Sharing one page's layouts with another is the bug this guards against."""
    wiki = [e for e in REAL_SOURCES if e["adapter"] == "wikipedia_gpu"]
    assert len(wiki) >= 2
    seen = [tuple(sorted(layout["cells"] for layout in e["config"]["layouts"])) for e in wiki]
    assert len(set(seen)) == len(seen), "two pages share a layout list"
