"""Argon2id password hashing (guide section 11).

Plaintext passwords are never stored, logged, or returned. Verification also
reports when a stored hash should be upgraded to the current parameters.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError, VerificationError
from argon2.low_level import Type

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,  # Argon2id
)

MIN_PASSWORD_LENGTH = 12


class WeakPassword(ValueError):
    pass


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPassword(
            f"password must be at least {MIN_PASSWORD_LENGTH} characters"
        )
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return True
