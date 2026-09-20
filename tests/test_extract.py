"""Reading catalog rows out of a page, with plain string handling only."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.extract import as_bool, as_money, as_workloads, blocks, read_page

PAGES = Path(__file__).parent / "fixtures" / "pages"
SOURCE = "https://sample-vendor.example.invalid/gpus"


def test_a_page_with_no_fact_blocks_yields_nothing():
    found = read_page("# Just a normal page\n\nSome prose about graphics cards.", SOURCE)
    assert found.count == 0


def test_blocks_are_found_by_their_heading():
    page = "## hardware: a\n- role: gpu\n\n## model: b\n- name: B\n"
    assert [(block.kind, block.slug) for block in blocks(page)] == [
        ("hardware", "a"), ("model", "b")
    ]


def test_an_unknown_block_kind_is_ignored():
    assert blocks("## recipe: soup\n- name: Soup\n") == []


def test_hardware_is_read_with_its_price_and_currency():
    found = read_page(
        (PAGES / "sample-vendor.example.invalid" / "gpus.md").read_text(), SOURCE
    )
    card = next(row for row in found.hardware if row.slug == "gpu-16g")
    assert card.vram_gb == Decimal("16")
    assert card.price == Decimal("430.00")
    assert card.currency == "EUR"
    assert card.region == "DE"
    assert card.source_url == SOURCE


def test_a_whole_machine_is_distinguished_from_a_card():
    found = read_page(
        (PAGES / "sample-vendor.example.invalid" / "gpus.md").read_text(), SOURCE
    )
    roles = {row.slug: row.role for row in found.hardware}
    assert roles["gpu-16g"] == "gpu"
    assert roles["workstation-24g"] == "system"


def test_hardware_without_a_role_is_skipped():
    """Without a role we cannot tell a spare part from a whole computer."""
    found = read_page("## hardware: mystery\n- name: Something\n- price: 10.00 EUR\n", SOURCE)
    assert found.hardware == []


def test_a_model_keeps_the_details_that_size_its_memory():
    found = read_page(
        (PAGES / "sample-models.example.invalid" / "open-models.md").read_text(), SOURCE
    )
    small = next(row for row in found.models if row.slug == "sampleopen-8b-q4")
    assert small.weights_gb == Decimal("4.9")
    assert small.layers == 32 and small.kv_heads == 8 and small.head_dim == 128
    assert small.max_context == 131072


def test_a_missing_field_becomes_unknown_not_zero():
    found = read_page(
        (PAGES / "sample-models.example.invalid" / "open-models.md").read_text(), SOURCE
    )
    large = next(row for row in found.models if row.slug == "sampleopen-70b-q4")
    assert large.commercial_use is None  # the page does not say


def test_plans_read_their_billing_and_regions():
    found = read_page(
        (PAGES / "sample-host.example.invalid" / "plans.md").read_text(), SOURCE
    )
    annual = next(row for row in found.plans if row.slug == "samplehost-team-annual")
    assert annual.billing_interval.value == "annual"
    assert annual.min_seats == 3
    assert annual.regions == ["DE", "FR"]
    assert annual.supports_api is True
    assert annual.messages_per_day is None  # not published


def test_money_is_split_into_amount_and_currency():
    assert as_money("430.00 EUR") == (Decimal("430.00"), "EUR")
    assert as_money("1,299.99 USD") == (Decimal("1299.99"), "USD")
    assert as_money("") == (None, None)
    assert as_money("not a price")[0] is None


def test_yes_and_no_become_true_and_false():
    assert as_bool("yes") is True
    assert as_bool("No") is False
    assert as_bool("maybe") is None
    assert as_bool(None) is None


def test_unknown_workload_names_are_dropped():
    assert [w.value for w in as_workloads("coding, telepathy, writing")] == [
        "coding", "writing"
    ]


def test_nonsense_numbers_become_unknown():
    found = read_page(
        "## model: odd\n- name: Odd\n- weights_gb: lots\n- max_context: soon\n", SOURCE
    )
    assert found.models[0].weights_gb is None
    assert found.models[0].max_context is None


def test_the_parser_uses_no_regular_expressions_or_selectors():
    """The original design forbids regex and selectors in extraction code."""
    source = Path("app/extract.py").read_text()
    for banned in (
        "import re\n", "from re import", "import regex",
        "re.compile(", "re.match(", "re.search(", "re.findall(", "re.sub(", "re.split(",
        "select_one", "find_all", "xpath", "cssselect", "BeautifulSoup",
    ):
        assert banned not in source, f"{banned!r} should not appear in the extractor"
