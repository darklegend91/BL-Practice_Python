"""Stops the crawler being pointed at things it should not fetch.

Source URLs come out of a database table, so treat them as input. This blocks
anything that is not ordinary public http/https: your own machine, private
networks, and the cloud metadata address that hands out credentials.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from app.config import get_settings

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_PORTS = frozenset({80, 443})

METADATA_ADDRESSES = frozenset({
    ipaddress.ip_address("169.254.169.254"),  # AWS, Azure, GCP, OpenStack
    ipaddress.ip_address("100.100.100.200"),  # Alibaba Cloud
})

# On an IPv6-only network an ordinary public site resolves to something like
# 64:ff9b::2224:850f, which carries the real IPv4 in its last 32 bits. Python
# calls that whole range "reserved", so judging it as-is would refuse every
# site on such a network. Unwrap it and judge where the traffic really goes,
# which also means 64:ff9b::7f00:1 is correctly recognised as 127.0.0.1.
NAT64_PREFIXES = (
    ipaddress.ip_network("64:ff9b::/96"),    # RFC 6052 well-known prefix
    ipaddress.ip_network("64:ff9b:1::/48"),  # RFC 8215 local-use prefix
)


def unwrap(address):
    """Return the IPv4 inside a translated IPv6 address, or the address itself."""
    if not isinstance(address, ipaddress.IPv6Address):
        return address
    if address.ipv4_mapped is not None:
        return address.ipv4_mapped
    for prefix in NAT64_PREFIXES:
        if address in prefix:
            return ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    return address


class Blocked(ValueError):
    """This URL will not be fetched, and here is why."""


def is_public(address) -> bool:
    address = unwrap(address)
    if address in METADATA_ADDRESSES:
        return False
    return not (
        address.is_loopback or address.is_private or address.is_link_local
        or address.is_multicast or address.is_reserved or address.is_unspecified
    )


def check_shape(url: str) -> str:
    """Checks that need no network: scheme, port, credentials, literal address.

    Used when a source is registered and before reading a saved page, because
    neither of those sends a request anywhere.
    """
    parts = urlsplit(url)

    if parts.scheme not in ALLOWED_SCHEMES:
        raise Blocked(f"{parts.scheme or 'that'} links are not fetched, only http and https")
    if not parts.hostname:
        raise Blocked("that URL has no host")
    if parts.port is not None and parts.port not in ALLOWED_PORTS:
        raise Blocked(f"port {parts.port} is not fetched")
    if parts.username or parts.password:
        raise Blocked("URLs with a username or password in them are not fetched")

    host = parts.hostname
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not is_public(literal):
        raise Blocked(f"{host} is not a public address")

    return url


def check(url: str) -> str:
    """Everything above, plus where the name actually points.

    This is the one that runs immediately before a real request, because that
    is the moment the address matters.
    """
    check_shape(url)

    if get_settings().allow_private_addresses:
        return url

    host = urlsplit(url).hostname
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as error:
        raise Blocked(f"cannot look up {host}: {error}") from error

    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not is_public(address):
            raise Blocked(f"{host} points at {address}, which is not public")

    return url
