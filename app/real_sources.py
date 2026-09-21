"""The real pages this app knows how to read, and how to read them.

Each entry names the reader and gives it whatever it needs. Registering these
replaces the invented example data with figures from pages anyone can open and
check for themselves.

Both sites were checked against their robots.txt before being listed here, and
the crawler checks again on every run.

Honesty about what these give you:

* **Graphics cards** come from Wikipedia, so the price is the *launch* price in
  US dollars, not what a shop charges today. Ask for ``region=US`` and
  ``currency=USD`` or they will be excluded, which is the correct behaviour
  rather than a bug.
* Wikipedia merges cells in these tables, so rows genuinely differ in shape and
  some carry no memory size at all. Only rows matching a layout below are read;
  the rest are counted and reported by ``POST /crawl``.
* **Models** come from Ollama, which publishes the download size and context
  length for every variant. It does not publish layer counts, so the memory
  estimate is marked approximate, or licences, so commercial use stays unknown.
* **Subscription plans have no real source here.** Provider pricing pages are
  behind bot protection and do not publish machine-readable terms, so plans
  still come from the example page. See docs/guide.md.
"""

from __future__ import annotations

# Wikipedia's GPU tables merge cells, so a row's width tells you which layout
# it is. Each layout below was read off the live page and verified by hand.
RTX_40_LAYOUTS = [
    {"cells": 20, "columns": {"name": 0, "price": 2, "vram_gb": 13, "board_watts": 19}},
    {"cells": 18, "columns": {"name": 0, "price": 2, "board_watts": 17}},
    {"cells": 17, "columns": {"name": 0, "price": 2, "vram_gb": 11}},
    {"cells": 16, "columns": {"name": 0, "vram_gb": 10}},
]

# A different page means a different table and different columns. These were
# read off the RTX 30 page itself. Reusing the list above appeared to work and
# quietly produced wrong memory sizes, so every page gets its own mapping that
# somebody has actually checked.
RTX_30_LAYOUTS = [
    {"cells": 19, "columns": {"name": 0, "price": 2, "vram_gb": 11, "board_watts": 18}},
    {"cells": 22, "columns": {"name": 0, "price": 2, "vram_gb": 13, "board_watts": 21}},
    {"cells": 18, "columns": {"name": 0, "price": 2, "vram_gb": 10, "board_watts": 17}},
    {"cells": 17, "columns": {"name": 0, "price": 2, "board_watts": 16}},
    {"cells": 16, "columns": {"name": 0, "price": 2, "board_watts": 15}},
]

REAL_SOURCES: list[dict] = [
    {
        "url": "https://en.wikipedia.org/wiki/GeForce_RTX_40_series",
        "label": "Nvidia RTX 40 series (Wikipedia)",
        "adapter": "wikipedia_gpu",
        "config": {"name_contains": "GeForce", "layouts": RTX_40_LAYOUTS},
    },
    {
        "url": "https://en.wikipedia.org/wiki/GeForce_RTX_30_series",
        "label": "Nvidia RTX 30 series (Wikipedia)",
        "adapter": "wikipedia_gpu",
        "config": {"name_contains": "GeForce", "layouts": RTX_30_LAYOUTS},
    },
    {
        "url": "https://ollama.com/library/llama3.1/tags",
        "label": "Llama 3.1 variants (Ollama)",
        "adapter": "ollama_models",
        "config": {"max_models": 12, "only_quantizations": ["q4_K_M", "q5_K_M", "q8_0"]},
    },
    {
        "url": "https://ollama.com/library/qwen2.5/tags",
        "label": "Qwen 2.5 variants (Ollama)",
        "adapter": "ollama_models",
        "config": {"max_models": 12, "only_quantizations": ["q4_K_M", "q5_K_M", "q8_0"]},
    },
    {
        "url": "https://ollama.com/library/gemma2/tags",
        "label": "Gemma 2 variants (Ollama)",
        "adapter": "ollama_models",
        "config": {"max_models": 8, "only_quantizations": ["q4_K_M", "q8_0"]},
    },
]
