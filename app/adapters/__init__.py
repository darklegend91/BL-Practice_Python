"""Readers that turn a crawled page into catalog rows.

One reader per kind of page. A source says which one to use and gives it
whatever settings it needs, so adding a new site means writing one small module
here rather than touching the crawler.

| adapter            | what it reads                                    |
| ------------------ | ------------------------------------------------ |
| ``factblock``      | pages that publish a plain ``## kind: slug`` block |
| ``wikipedia_gpu``  | a Wikipedia graphics-card specification table      |
| ``ollama_models``  | an Ollama library tags page                        |

Every reader follows the same rule: if the page does not look the way it
expects, it returns nothing. None of them guess. Zero rows is a visible result
you can see in ``GET /pages``; a wrong number silently entering the catalog
would not be.
"""

from __future__ import annotations

from app.schemas import Hardware, Model, Plan


class Found:
    """What one page yielded."""

    def __init__(self) -> None:
        self.hardware: list[Hardware] = []
        self.models: list[Model] = []
        self.plans: list[Plan] = []
        self.notes: list[str] = []
        """Anything the reader wants you to know, such as rows it left alone."""

    @property
    def count(self) -> int:
        return len(self.hardware) + len(self.models) + len(self.plans)


class UnknownAdapter(ValueError):
    """A source names a reader that does not exist."""


def names() -> list[str]:
    return ["factblock", "wikipedia_gpu", "ollama_models"]


def read(adapter: str, markdown: str, source_url: str, config: dict | None = None) -> Found:
    """Run the named reader over a page."""
    settings = config or {}

    if adapter == "factblock":
        from app.adapters import factblock

        return factblock.read(markdown, source_url, settings)

    if adapter == "wikipedia_gpu":
        from app.adapters import wikipedia_gpu

        found = Found()
        found.hardware, found.notes = wikipedia_gpu.read(markdown, source_url, settings)
        return found

    if adapter == "ollama_models":
        from app.adapters import ollama_models

        found = Found()
        found.models = ollama_models.read(markdown, source_url, settings)
        return found

    raise UnknownAdapter(f"no reader called {adapter!r}; known: {', '.join(names())}")
