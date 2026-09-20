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


class Blocked(ValueError):
    """This URL will not be fetched, and here is why."""


def is_public(address) -> bool:
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
