"""A small in-process rate limit for login, writes and exports.

This bounds a single process only. A multi-process deployment enforces limits at
the ingress as well; the guide keeps additional infrastructure out of the first
release until measurements justify it (guide sections 9 and 7).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request, status

from app.errors import error_response
from fastapi.responses import JSONResponse

_WINDOW_SECONDS = 60.0
_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


class RateLimited(Exception):
    def __init__(self, bucket: str, limit: int) -> None:
        super().__init__(f"rate limit of {limit} per minute exceeded for {bucket}")
        self.bucket = bucket
        self.limit = limit


def _client_key(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


def enforce_rate_limit(request: Request, bucket: str, limit: int) -> None:
    key = (bucket, _client_key(request))
    now = time.monotonic()
    recent = _hits[key]
    while recent and now - recent[0] > _WINDOW_SECONDS:
        recent.popleft()
    if len(recent) >= limit:
        raise RateLimited(bucket, limit)
    recent.append(now)


def reset() -> None:
    """Used by tests to keep one test's traffic out of another's budget."""
    _hits.clear()


def handler(request: Request, exception: RateLimited) -> JSONResponse:
    return error_response(
        request,
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        code="rate_limited",
        message=str(exception),
    )
