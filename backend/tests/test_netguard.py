"""SSRF protections in netguard, against a real local HTTP server."""

import ipaddress
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import netguard
from netguard import BlockedURL, fetch, resolve_and_validate

LOOPBACK = ipaddress.ip_address("127.0.0.1")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        routes = {
            "/redirect": (302, "/ok"),
            "/redirect-internal": (302, "http://10.0.0.1/latest/meta-data/"),
            "/redirect-ftp": (302, "ftp://example.com/"),
            "/loop": (302, "/loop"),
        }
        if self.path in routes:
            code, location = routes[self.path]
            self.send_response(code)
            self.send_header("Location", location)
            self.end_headers()
            return
        self.send_response(200 if self.path in ("/ok", "/echo-host") else 404)
        self.send_header("X-Seen-Host", self.headers.get("Host", ""))
        self.end_headers()


@pytest.fixture(scope="module")
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


@pytest.fixture
def loopback_is_public(monkeypatch):
    """Treat 127.0.0.1 as public (so the test server is reachable) and every
    other address as private. Lets us test redirects/pinning without internet."""
    monkeypatch.delenv("PULSECHECK_ALLOW_PRIVATE_TARGETS", raising=False)
    monkeypatch.setattr(netguard, "ip_is_public", lambda ip: ip == LOOPBACK)


# --- validation (no network) ---------------------------------------------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/",
    "http://localhost/",
    "http://169.254.169.254/latest/meta-data/",   # cloud metadata
    "http://10.0.0.5:8080/",
    "http://192.168.1.1/",
    "http://[::1]/",
    "http://[::ffff:127.0.0.1]/",                  # IPv4-mapped IPv6
    "http://0.0.0.0/",
])
def test_private_targets_blocked(monkeypatch, url):
    monkeypatch.delenv("PULSECHECK_ALLOW_PRIVATE_TARGETS", raising=False)
    with pytest.raises(BlockedURL):
        resolve_and_validate(url)


@pytest.mark.parametrize("url", ["ftp://example.com/", "file:///etc/passwd",
                                 "http:///nohost", "http://example.com:99999/"])
def test_bad_scheme_or_syntax_blocked(url):
    with pytest.raises(BlockedURL):
        resolve_and_validate(url)


def test_public_ip_literal_allowed(monkeypatch):
    monkeypatch.delenv("PULSECHECK_ALLOW_PRIVATE_TARGETS", raising=False)
    _, ip = resolve_and_validate("https://8.8.8.8/")
    assert ip == "8.8.8.8"


def test_any_private_address_in_dns_answer_blocks(monkeypatch):
    # A name returning one public and one private address must be refused,
    # otherwise the connection could land on the private one.
    monkeypatch.delenv("PULSECHECK_ALLOW_PRIVATE_TARGETS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 80)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", 80)),
    ])
    with pytest.raises(BlockedURL):
        resolve_and_validate("http://mixed.test/")


def test_allow_private_flag(monkeypatch):
    monkeypatch.setenv("PULSECHECK_ALLOW_PRIVATE_TARGETS", "true")
    _, ip = resolve_and_validate("http://127.0.0.1/")
    assert ip == "127.0.0.1"


# --- fetching ---------------------------------------------------------------

def test_follows_safe_redirect(server, loopback_is_public):
    r = fetch(f"http://127.0.0.1:{server}/redirect")
    assert r.status_code == 200
    assert r.redirects == 1
    assert r.final_url.endswith("/ok")


def test_redirect_to_internal_address_is_blocked(server, loopback_is_public):
    with pytest.raises(BlockedURL, match="10.0.0.1"):
        fetch(f"http://127.0.0.1:{server}/redirect-internal")


def test_redirect_to_other_scheme_is_blocked(server, loopback_is_public):
    with pytest.raises(BlockedURL):
        fetch(f"http://127.0.0.1:{server}/redirect-ftp")


def test_redirect_loop_is_capped(server, loopback_is_public):
    with pytest.raises(requests.TooManyRedirects):
        fetch(f"http://127.0.0.1:{server}/loop", max_redirects=3)


def test_dns_resolved_once_and_connection_pinned(server, loopback_is_public, monkeypatch):
    """The 1st DNS answer is validated; a 2nd lookup would return an internal
    IP (rebinding). The request must connect to the 1st answer and never look
    the name up again, while still sending the original Host header."""
    real_getaddrinfo = socket.getaddrinfo
    lookups = []

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host == "rebind.test":
            lookups.append(host)
            ip = "127.0.0.1" if len(lookups) == 1 else "10.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
        return real_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    seen = {}
    orig = netguard._request_pinned

    def spy(parts, ip, timeout):
        resp = orig(parts, ip, timeout)
        seen["host"] = resp.headers.get("X-Seen-Host")
        seen["ip"] = ip
        return resp

    monkeypatch.setattr(netguard, "_request_pinned", spy)
    r = fetch(f"http://rebind.test:{server}/echo-host")
    assert r.status_code == 200
    assert lookups == ["rebind.test"]          # resolved exactly once
    assert seen["ip"] == "127.0.0.1"
    assert seen["host"] == f"rebind.test:{server}"


def test_proxy_env_vars_are_ignored(server, loopback_is_public, monkeypatch):
    # A proxy would make the pinned IP meaningless; requests must not use it.
    monkeypatch.setenv("HTTP_PROXY", "http://10.9.9.9:3128")
    assert fetch(f"http://127.0.0.1:{server}/ok").status_code == 200


# --- integration -------------------------------------------------------------

def test_scheduler_records_blocked_check(monkeypatch):
    import database
    import scheduler
    from models import CheckResult, Endpoint

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    database.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(scheduler, "SessionLocal", Session)
    monkeypatch.delenv("PULSECHECK_ALLOW_PRIVATE_TARGETS", raising=False)

    with Session() as s:
        ep = Endpoint(name="metadata", url="http://169.254.169.254/latest/meta-data/")
        s.add(ep)
        s.commit()
        eid = ep.id

    scheduler.check_endpoint(eid)

    with Session() as s:
        result = s.query(CheckResult).filter_by(endpoint_id=eid).one()
        assert result.is_up is False
        assert result.status_code is None
        assert result.error_msg.startswith("blocked:")


def test_create_endpoint_rejects_private_url(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app

    monkeypatch.delenv("PULSECHECK_ALLOW_PRIVATE_TARGETS", raising=False)
    client = TestClient(app)   # no context manager: lifespan/scheduler not started
    r = client.post("/api/endpoints/", json={"name": "x", "url": "http://127.0.0.1:5432/"})
    assert r.status_code == 422
    assert "not allowed" in r.json()["detail"]
