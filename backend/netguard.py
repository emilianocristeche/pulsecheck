"""Outbound HTTP for health checks, hardened against SSRF.

PulseCheck fetches URLs that users type in, from inside your network. Without
care, "monitor http://169.254.169.254/latest/meta-data/" (cloud credentials) or
"http://localhost:5432" turns the monitor into a proxy for internal services.

Defenses, applied to every request *and to every redirect hop*:
  1. Only http/https URLs.
  2. The hostname is resolved ONCE; every returned address must be public
     (ipaddress.is_global). If any is private/loopback/link-local, the request
     is refused.
  3. The connection goes to that already-validated IP. The URL is rewritten to
     the IP, the original Host header is kept, and for HTTPS the TLS SNI and
     certificate check still use the hostname. requests never does its own DNS
     lookup, so a second lookup cannot return a different (internal) address.
  4. Redirects are followed manually (max MAX_REDIRECTS); each Location goes
     through steps 1-3 before being requested.
  5. Proxy env vars are ignored (trust_env=False), so the pinned IP is really
     the one we connect to.

Set PULSECHECK_ALLOW_PRIVATE_TARGETS=true to monitor internal hosts on purpose
(e.g. a self-hosted deployment watching services on the same LAN).
"""

from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter

MAX_REDIRECTS = 5
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_DEFAULT_PORTS = {"http": 80, "https": 443}


class BlockedURL(ValueError):
    """The URL is not allowed as a monitoring target."""


@dataclass
class FetchResult:
    status_code: int
    elapsed_ms: float   # summed over all hops
    final_url: str
    redirects: int


def allow_private_targets() -> bool:
    return os.getenv("PULSECHECK_ALLOW_PRIVATE_TARGETS", "false").strip().lower() in (
        "1", "true", "yes")


def ip_is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # ::ffff:127.0.0.1 must be judged as the IPv4 address it wraps.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global


def check_url_syntax(url: str):
    """Scheme/host/port sanity. Returns the SplitResult; raises BlockedURL."""
    parts = urlsplit(url)
    if parts.scheme not in _DEFAULT_PORTS:
        raise BlockedURL(f"only http/https URLs are allowed, got {parts.scheme!r}")
    if not parts.hostname:
        raise BlockedURL("URL has no hostname")
    try:
        parts.port
    except ValueError as e:
        raise BlockedURL(f"invalid port: {e}") from None
    return parts


def resolve_and_validate(url: str):
    """Resolve the URL's host once and validate every address.

    Returns (SplitResult, ip_to_connect). Raises BlockedURL if the target is not
    allowed, or requests.ConnectionError if the name does not resolve (a down
    target, not a policy violation).
    """
    parts = check_url_syntax(url)
    port = parts.port or _DEFAULT_PORTS[parts.scheme]
    try:
        infos = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise requests.ConnectionError(f"DNS resolution failed for {parts.hostname}: {e}") from None

    # Strip IPv6 zone ids ("fe80::1%eth0") before parsing.
    addrs = [ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos]
    if not allow_private_targets():
        for ip in addrs:
            if not ip_is_public(ip):
                raise BlockedURL(f"{parts.hostname} resolves to non-public address {ip}")
    return parts, str(addrs[0])


class _PinnedHTTPSAdapter(HTTPAdapter):
    """Connect to an IP but do SNI + certificate verification for `hostname`."""

    def __init__(self, hostname: str):
        self._hostname = hostname
        super().__init__(max_retries=0)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["server_hostname"] = self._hostname
        kwargs["assert_hostname"] = self._hostname
        super().init_poolmanager(*args, **kwargs)


def _request_pinned(parts, ip: str, timeout: float) -> requests.Response:
    """One GET to `ip`, presenting the original host. No redirects, no body read."""
    ip_host = f"[{ip}]" if ":" in ip else ip
    netloc = f"{ip_host}:{parts.port}" if parts.port else ip_host
    pinned_url = urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))
    host_header = parts.netloc.rsplit("@", 1)[-1]   # drop user:pass@
    auth = None
    if parts.username is not None:
        auth = (unquote(parts.username), unquote(parts.password or ""))

    with requests.Session() as s:
        s.trust_env = False
        if parts.scheme == "https":
            s.mount("https://", _PinnedHTTPSAdapter(parts.hostname))
        resp = s.get(pinned_url, headers={"Host": host_header}, auth=auth,
                     timeout=timeout, allow_redirects=False, stream=True)
        resp.close()    # status + headers are all we need; skip the body
        return resp


def fetch(url: str, timeout: float = 10, max_redirects: int = MAX_REDIRECTS) -> FetchResult:
    """GET `url` with SSRF protections, validating every redirect hop."""
    elapsed_ms = 0.0
    for hop in range(max_redirects + 1):
        parts, ip = resolve_and_validate(url)
        resp = _request_pinned(parts, ip, timeout)
        elapsed_ms += resp.elapsed.total_seconds() * 1000
        location = resp.headers.get("Location")
        if resp.status_code in _REDIRECT_CODES and location:
            url = urljoin(url, location)
            continue
        return FetchResult(resp.status_code, elapsed_ms, url, hop)
    raise requests.TooManyRedirects(f"more than {max_redirects} redirects")
