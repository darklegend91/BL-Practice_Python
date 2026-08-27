import json

import pytest

from processing import normalizer, parser


PAGE = """# This is the crawled extracted data
 ## Source :
https://example.com/rtx-5090

GeForce RTX 5090
NVIDIA Blackwell architecture
21,760 CUDA Cores
32 GB GDDR7
3,352 AI TOPS
Base Clock: 2.01 GHz
Boost Clock: 2.41 GHz
Total Graphics Power: 575 W
"""


def test_split_gpu_pages_supports_crawler_heading_format():
    pages = parser.split_gpu_pages(PAGE)

    assert pages == [
        {
            "url": "https://example.com/rtx-5090",
            "content": (
                "\nGeForce RTX 5090\n"
                "NVIDIA Blackwell architecture\n"
                "21,760 CUDA Cores\n"
                "32 GB GDDR7\n"
                "3,352 AI TOPS\n"
                "Base Clock: 2.01 GHz\n"
                "Boost Clock: 2.41 GHz\n"
                "Total Graphics Power: 575 W"
            ),
        }
    ]


def test_split_gpu_pages_handles_multiple_pages_and_empty_input():
    content = "## Source\nfirst\nOne\n## Source:\nsecond\nTwo"

    assert parser.split_gpu_pages(content) == [
        {"url": "first", "content": "One"},
        {"url": "second", "content": "Two"},
    ]
    assert parser.split_gpu_pages("no source headings") == []


def test_search_pattern_returns_first_capture_or_none():
    assert parser.search_pattern(r"model:\s*(\w+)", "MODEL: RTX") == "RTX"
    assert parser.search_pattern(r"missing: (\w+)", "MODEL: RTX") is None


def test_parse_gpu_page_extracts_gpu_fields():
    page = parser.split_gpu_pages(PAGE)[0]

    parsed = parser.parse_gpu_page(page)

    assert parsed == {
        "source_url": "https://example.com/rtx-5090",
        "model": "GeForce RTX 5090",
        "architecture": "Blackwell",
        "cuda_cores": "21,760",
        "vram": "32",
        "memory_type": "GDDR7",
        "ai_tops": "3,352",
        "base_clock": "2.01 GHz",
        "boost_clock": "2.41 GHz",
        "graphics_power": "575 W",
    }


def test_parse_gpu_page_returns_none_for_missing_optional_fields():
    parsed = parser.parse_gpu_page(
        {"url": "https://example.com", "content": "unrelated content"}
    )

    assert parsed["source_url"] == "https://example.com"
    assert all(value is None for key, value in parsed.items() if key != "source_url")


def test_parse_all_pages_preserves_order(monkeypatch):
    monkeypatch.setattr(
        parser,
        "parse_gpu_page",
        lambda page: {"source_url": page["url"]},
    )

    assert parser.parse_all_pages(
        [{"url": "one", "content": ""}, {"url": "two", "content": ""}]
    ) == [{"source_url": "one"}, {"source_url": "two"}]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("21,760", 21760),
        ("575 W", 575),
        (32, 32),
        (None, None),
        ("unknown", None),
    ],
)
def test_normalize_integer(value, expected):
    assert normalizer.normalize_integer(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2.41 GHz", 2.41),
        ("3,352 AI TOPS", 3352.0),
        (17, 17.0),
        (None, None),
        ("unknown", None),
    ],
)
def test_normalize_float(value, expected):
    assert normalizer.normalize_float(value) == expected


def test_normalize_gpu_builds_normalized_record():
    parsed = parser.parse_gpu_page(parser.split_gpu_pages(PAGE)[0])

    result = normalizer.normalize_gpu(parsed)

    assert result == {
        "type": "hardware",
        "category": "GPU",
        "manufacturer": "NVIDIA",
        "model": "GeForce RTX 5090",
        "generation": "RTX 50 Series",
        "architecture": "Blackwell",
        "cuda_cores": 21760,
        "ai_tops": 3352.0,
        "vram_gb": 32,
        "memory_type": "GDDR7",
        "base_clock_ghz": 2.01,
        "boost_clock_ghz": 2.41,
        "graphics_power_w": 575,
        "source_url": "https://example.com/rtx-5090",
    }


def test_parser_and_normalizer_file_helpers(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    markdown = tmp_path / "input.md"
    parsed_file = tmp_path / "parsed.json"
    normalized_file = tmp_path / "normalized.json"
    markdown.write_text(PAGE, encoding="utf-8")

    content = parser.read_markdown(str(markdown))
    parsed = parser.parse_all_pages(parser.split_gpu_pages(content))
    parser.save_results(parsed, str(parsed_file))
    loaded = normalizer.load_data(str(parsed_file))
    normalized = normalizer.normalize_all(loaded)
    normalizer.save_results(normalized, str(normalized_file))

    assert json.loads(parsed_file.read_text(encoding="utf-8")) == parsed
    assert json.loads(normalized_file.read_text(encoding="utf-8")) == normalized
    assert normalized[0]["model"] == "GeForce RTX 5090"
