"""Candidate URL discovery (guide section 5).

Discovery inspects links Crawl4AI already returned and parses sitemaps with the
standard-library XML parser. No CSS selectors, XPath or regular expressions are
used. Discovered URLs are reviewable candidates, never automatically approved
sources, and they stay inside the approved domains and budgets.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

from app.schemas.common import StrictModel
from app.security.net_guard import DestinationRefused, check_url_shape

SITEMAP_NAMESPACE = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class DiscoveryBudget(StrictModel):
    max_pages: int = 50
    max_depth: int = 2


class Candidate(StrictModel):
    url: str
    depth: int
    discovered_from: str


def _within_allowed_hosts(url: str, allowed_hosts: list[str]) -> bool:
    host = urlsplit(url).hostname
    if host is None:
        return False
    if not allowed_hosts:
        return False
    return any(host == entry or host.endswith(f".{entry}") for entry in allowed_hosts)


def candidates_from_links(
    links: list[str],
    *,
    base_url: str,
    allowed_hosts: list[str],
    depth: int,
    budget: DiscoveryBudget,
) -> list[Candidate]:
    """Turn returned links into bounded, in-domain review candidates."""
    if depth > budget.max_depth:
        return []

    found: list[Candidate] = []
    seen: set[str] = set()
    for href in links:
        absolute = urljoin(base_url, href)
        normalized = absolute.split("#", 1)[0]
        if normalized in seen or not _within_allowed_hosts(normalized, allowed_hosts):
            continue
        try:
            # Shape only: these are review candidates, not requests. The full
            # check, including name resolution, runs when one is fetched.
            check_url_shape(normalized, allowed_hosts)
        except DestinationRefused:
            continue
        seen.add(normalized)
        found.append(Candidate(url=normalized, depth=depth, discovered_from=base_url))
        if len(found) >= budget.max_pages:
            break
    return found


def candidates_from_sitemap(
    sitemap_xml: str,
    *,
    sitemap_url: str,
    allowed_hosts: list[str],
    budget: DiscoveryBudget,
) -> list[Candidate]:
    """Parse a sitemap with the standard XML parser."""
    try:
        root = ElementTree.fromstring(sitemap_xml)
    except ElementTree.ParseError:
        return []

    locations = [
        element.text.strip()
        for element in root.iter(f"{SITEMAP_NAMESPACE}loc")
        if element.text and element.text.strip()
    ]
    return candidates_from_links(
        locations,
        base_url=sitemap_url,
        allowed_hosts=allowed_hosts,
        depth=1,
        budget=budget,
    )
