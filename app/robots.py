"""Respects each site's robots.txt before fetching anything from it.

Now that the crawler visits real sites this is not politeness, it is the rule
those sites publish for automated visitors. The file is fetched once per host
and remembered for the run.

One trap worth knowing about: the standard library's ``RobotFileParser`` fetches
robots.txt with urllib's own user agent, and some large sites answer that with
403. The parser then follows the standard and reads 403 as "disallow
everything", so a site that plainly allows crawling looks forbidden. This module
fetches the file itself under an honest, descriptive user agent and hands the
text to the parser, which avoids that.

Status codes follow RFC 9309: 2xx uses the rules, 4xx means there are none and
everything is allowed, and 5xx or an unreachable host means hold off.
"""

from __future__ import annotations

import urllib.error
import urllib.request
import urllib.robotparser
from urllib.parse import urlsplit

USER_AGENT = "llmfit-advisor/0.2 (local catalog builder; respects robots.txt)"
TIMEOUT_SECONDS = 15


class Disallowed(PermissionError):
    """This site asks automated visitors not to fetch this path."""


class _Rules:
    def __init__(self, parser: urllib.robotparser.RobotFileParser | None, allow_all: bool,
                 reason: str) -> None:
        self.parser = parser
        self.allow_all = allow_all
        self.reason = reason

    def can_fetch(self, url: str, user_agent: str) -> bool:
        if self.parser is None:
            return self.allow_all
        return self.parser.can_fetch(user_agent, url)


_cache: dict[str, _Rules] = {}


def _fetch_rules(origin: str) -> _Rules:
    request = urllib.request.Request(
        f"{origin}/robots.txt", headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        if 400 <= error.code < 500:
            # No rules published for us. The standard says that means allowed.
            return _Rules(None, True, f"robots.txt returned {error.code}, so nothing is barred")
        return _Rules(None, False, f"robots.txt returned {error.code}, so hold off for now")
    except (urllib.error.URLError, OSError, ValueError) as error:
        return _Rules(None, False, f"could not read robots.txt ({error})")

    parser = urllib.robotparser.RobotFileParser()
    parser.parse(body.splitlines())
    return _Rules(parser, True, "robots.txt read")


def rules_for(url: str) -> _Rules:
    parts = urlsplit(url)
    origin = f"{parts.scheme or 'https'}://{parts.netloc}"
    if origin not in _cache:
        _cache[origin] = _fetch_rules(origin)
    return _cache[origin]


def allowed(url: str, user_agent: str = USER_AGENT) -> bool:
    if not urlsplit(url).hostname:
        return False
    return rules_for(url).can_fetch(url, user_agent)


def check(url: str, user_agent: str = USER_AGENT) -> str:
    """Return the URL, or raise ``Disallowed`` explaining which rule applied."""
    rules = rules_for(url)
    if not rules.can_fetch(url, user_agent):
        raise Disallowed(f"{url} is not allowed for crawlers: {rules.reason}")
    return url


def forget() -> None:
    """Drop the cache, so one test cannot affect another."""
    _cache.clear()
