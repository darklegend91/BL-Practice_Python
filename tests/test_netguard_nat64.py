"""The guard must judge where traffic really goes, not how an address looks.

On an IPv6-only network every public site resolves to something like
64:ff9b::2224:850f, which carries the real IPv4 in its last 32 bits. Python
calls that whole range "reserved". Taking that at face value refused every
site; taking it apart is what makes both halves of this work.
"""

from __future__ import annotations

import ipaddress

import pytest

from app import netguard


@pytest.mark.parametrize(
    "address, goes_to",
    [
        ("64:ff9b::2224:850f", "34.36.133.15"),
        ("64:ff9b::7f00:1", "127.0.0.1"),
        ("64:ff9b::a00:1", "10.0.0.1"),
        ("::ffff:127.0.0.1", "127.0.0.1"),
    ],
)
def test_translated_addresses_are_unwrapped(address, goes_to):
    assert netguard.unwrap(ipaddress.ip_address(address)) == ipaddress.ip_address(goes_to)


def test_an_ordinary_address_is_left_alone():
    for address in ("2606:4700::1111", "34.36.133.15"):
        parsed = ipaddress.ip_address(address)
        assert netguard.unwrap(parsed) == parsed


@pytest.mark.parametrize(
    "address",
    [
        "64:ff9b::2224:850f",   # public IPv4 behind NAT64
        "::ffff:34.36.133.15",  # public IPv4, mapped
        "2606:4700::1111",      # public IPv6
        "34.36.133.15",         # public IPv4
    ],
)
def test_public_destinations_are_allowed(address):
    assert netguard.is_public(ipaddress.ip_address(address)) is True


@pytest.mark.parametrize(
    "address, why",
    [
        ("64:ff9b::7f00:1", "loopback behind NAT64"),
        ("64:ff9b::a00:1", "private network behind NAT64"),
        ("64:ff9b::a9fe:a9fe", "cloud metadata behind NAT64"),
        ("::ffff:127.0.0.1", "loopback, mapped"),
        ("::ffff:169.254.169.254", "cloud metadata, mapped"),
        ("127.0.0.1", "plain loopback"),
        ("10.0.0.1", "plain private"),
        ("169.254.169.254", "plain cloud metadata"),
    ],
)
def test_internal_destinations_are_refused_however_they_are_written(address, why):
    assert netguard.is_public(ipaddress.ip_address(address)) is False, why
