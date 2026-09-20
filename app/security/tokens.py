"""Opaque session tokens (guide section 11).

A high-entropy random token is returned to the caller exactly once. Only its
SHA-256 digest is stored, so a database disclosure does not yield usable
sessions. Comparison is constant-time.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from app.config import get_settings


def issue_token() -> tuple[str, str]:
    """Return ``(token, digest)``. Only the digest may be persisted."""
    token = secrets.token_urlsafe(get_settings().session_token_bytes)
    return token, digest_token(token)


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(token: str, stored_digest: str) -> bool:
    return hmac.compare_digest(digest_token(token), stored_digest)


def digest_idempotency_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def hash_request_body(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()
