"""Egress control for crawler destinations (guide section 11).

Browser requests originate from company infrastructure, so every destination is
checked before it is fetched and again after each redirect. Loopback, private,
link-local, unique-local and cloud-metadata addresses are refused, and the check
is applied to the resolved addresses rather than only to the hostname.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from app.config import get_settings

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_PORTS = frozenset({80, 443})

CLOUD_METADATA_ADDRESSES = frozenset(
    {
        ipaddress.ip_address("169.254.169.254"),  # AWS, Azure, GCP, OpenStack
        ipaddress.ip_address("100.100.100.200"),  # Alibaba Cloud
        ipaddress.ip_address("fd00:ec2::254"),  # AWS IMDS over IPv6
    }
)


class DestinationRefused(ValueError):
    """Raised for a destination the crawler is not permitted to reach."""


def _refuse(reason: str) -> None:
    raise DestinationRefused(reason)


def address_is_permitted(address: ipaddress._BaseAddress) -> bool:
    if address in CLOUD_METADATA_ADDRESSES:
        return False
    return not (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def resolve(host: str) -> list[ipaddress._BaseAddress]:
    """Resolve every address the host maps to, so DNS cannot hide one."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as error:
        raise DestinationRefused(f"cannot resolve host {host!r}: {error}") from error
    return [ipaddress.ip_address(info[4][0]) for info in infos]


def check_url_shape(url: str, allowed_hosts: list[str] | None = None) -> str:
    """Static checks only: scheme, port, credentials, literal address, allow-list.

    Used when a source is registered. Name resolution is deliberately not done
    here: a host that is briefly unresolvable should not block registration, and
    a resolution check at registration time would be worthless anyway because
    DNS can change before the page is ever fetched.
    """
    parts = urlsplit(url)

    if parts.scheme not in ALLOWED_SCHEMES:
        _refuse(f"scheme {parts.scheme!r} is not permitted")
    if not parts.hostname:
        _refuse("destination has no host")
    if parts.port is not None and parts.port not in ALLOWED_PORTS:
        _refuse(f"port {parts.port} is not permitted")
    if parts.username or parts.password:
        _refuse("credentials in a URL are not permitted")

    host = parts.hostname
    if allowed_hosts:
        permitted = any(
            host == entry or host.endswith(f".{entry}") for entry in allowed_hosts
        )
        if not permitted:
            _refuse(f"host {host!r} is outside the approved domains for this source")

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not address_is_permitted(literal):
        _refuse(f"address {host} is not a permitted destination")

    return url


def check_url(url: str, allowed_hosts: list[str] | None = None) -> str:
    """Full check, applied immediately before a page is fetched.

    Runs the static checks and then resolves the host, refusing every address it
    maps to that is loopback, private, link-local or cloud metadata. This is the
    check that matters, because it happens at the moment of the request.
    """
    check_url_shape(url, allowed_hosts)

    if get_settings().crawl_allow_private_destinations:
        # Only ever enabled against a local fixture server in development.
        return url

    host = urlsplit(url).hostname
    assert host is not None  # guaranteed by check_url_shape
    for address in resolve(host):
        if not address_is_permitted(address):
            _refuse(f"host {host!r} resolves to non-public address {address}")

    return url


def check_redirect(original_url: str, target_url: str, allowed_hosts: list[str] | None) -> str:
    """Re-run the full check on a redirect target; a redirect is a new request."""
    return check_url(target_url, allowed_hosts)
