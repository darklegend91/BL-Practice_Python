"""Root test configuration for the two code trees that share this repository.

``app/`` is the production application; its tests need only the dependencies in
``requirements-dev.txt``. ``src/`` holds the earlier learning prototypes, whose
tests import optional packages listed in ``requirements-prototype.txt``
(``crawl4ai`` in particular pulls in a browser stack that the production image
deliberately does not carry - see guide section 15).

Without this, a checkout that has installed only the production dependencies
fails collection and runs nothing at all. Prototype tests whose imports are
unavailable are skipped instead, so ``pytest`` works either way and the reason
is visible in the run summary.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# Prototype test module -> the third-party import it needs.
PROTOTYPE_REQUIREMENTS = {
    "test_requests.py": "requests",
    "test_crawler.py": "crawl4ai",
    "test_benchmark.py": "crawl4ai",
}

collect_ignore = []

_tests = Path(__file__).parent / "tests"
for module_name, requirement in PROTOTYPE_REQUIREMENTS.items():
    if importlib.util.find_spec(requirement) is None:
        collect_ignore.append(str(_tests / module_name))
