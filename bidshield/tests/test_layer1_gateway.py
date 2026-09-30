"""Layer 1 — Perimeter & API Gateway: live behavior tests.

Each test drives the running ASGI app through the real middleware stack and
asserts the observable failure mode (status code, header, side effect), not
the presence of code. Rate-limit tests give their client a UNIQUE source IP
via ASGITransport so they neither interfere with each other nor with the
business-flow suites (which run with the gateway relaxed by conftest).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import ASGITransport

from app.core.config import settings
from app.core.gateway import SECURITY_HEADERS
from app.db.session import SessionLocal
from app.main import app
from app.models.entities import SecurityEvent

client = TestClient(app)


def _client_from_ip(fake_ip: str) -> TestClient:
    """Build a TestClient whose requests report a unique fake source IP, so
    rate-limit buckets are per-test and cannot leak into other suites."""

    class IPTransport(ASGITransport):
        async def handle_request(self, request):
            original = self.app

            async def app_with_client(scope, receive, send):
                if scope["type"] == "http":
                    scope["client"] = (fake_ip, 12345)
                await original(scope, receive, send)

            self.app = app_with_client
            try:
                return await super().handle_request(request)
            finally:
                self.app = original

    return TestClient(app, transport=IPTransport(app))


def test_every_response_carries_security_headers():
    for path in ("/health", "/api/v1/tenders", "/definitely/not/here"):
        res = client.get(path)
        for name, value in SECURITY_HEADERS.items():
            assert res.headers.get(name) == value, f"{path} missing {name}"
        # CSP must be strict: no unsafe-inline anywhere.
        assert "unsafe-inline" not in res.headers.get("Content-Security-Policy", "")


def test_rate_limit_returns_429_with_retry_after_on_health():
    probes = _client_from_ip("10.77.0.1")
    seen_429 = None
    for _ in range(settings.rate_limit_per_minute + 5):
        res = probes.get("/health")
        if res.status_code == 429:
            seen_429 = res
            break
    assert seen_429 is not None, "gateway never rate-limited a flood of requests"
    assert "Retry-After" in seen_429.headers
    assert int(seen_429.headers["Retry-After"]) >= 1


def test_login_endpoint_has_stricter_limit():
    probes = _client_from_ip("10.77.0.2")
    codes = []
    for _ in range(settings.login_rate_limit_per_minute + 3):
        codes.append(probes.post("/api/v1/auth/login", json={"username": "officer", "password": "nope"}).status_code)
    assert 429 in codes, "login flood was not rate-limited"
    assert codes[-1] == 429


def test_oversized_json_body_rejected_with_413():
    big = b"x" * (settings.max_body_bytes + 1024)
    res = client.post("/api/v1/auth/login", data=big,
                      headers={"Content-Type": "application/json",
                               "Content-Length": str(len(big))})
    assert res.status_code == 413


def test_injection_pattern_in_body_rejected_with_400_and_logged():
    db = SessionLocal()
    before = db.query(SecurityEvent).filter(SecurityEvent.kind == "INJECTION_PATTERN").count()
    db.close()

    res = client.post("/api/v1/auth/login",
                      json={"username": "officer", "password": "' UNION SELECT password FROM users --"})

    assert res.status_code == 400
    db = SessionLocal()
    after = db.query(SecurityEvent).filter(SecurityEvent.kind == "INJECTION_PATTERN").count()
    latest = (db.query(SecurityEvent)
              .filter(SecurityEvent.kind == "INJECTION_PATTERN")
              .order_by(SecurityEvent.id.desc()).first())
    db.close()
    assert after == before + 1, "injection hit was not logged to security_events"
    assert latest.detail["pattern"]


def test_injection_pattern_in_query_string_rejected_with_400():
    res = client.get("/api/v1/documents?document_type=GST%20UNION%20SELECT%20null--")
    assert res.status_code == 400


def test_benign_json_requests_pass_through_intact():
    """A legitimate login body must reach the app after the scan buffers it
    (regression for the body-replay hang)."""
    res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"})
    assert res.status_code == 200
    assert res.json()["access_token"]


def test_interactive_docs_disabled_by_default():
    probes = TestClient(app)
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None
    assert probes.get("/api/v1/docs").status_code in (404, 405)
    assert probes.get("/api/v1/openapi.json").status_code == 404


def test_cors_disallows_unlisted_origin():
    res = client.options("/api/v1/auth/login", headers={
        "Origin": "https://evil.example.com",
        "Access-Control-Request-Method": "POST",
    })
    allow = res.headers.get("access-control-allow-origin", "")
    assert allow != "https://evil.example.com"
    assert allow != "*"


def test_cors_allows_configured_origin():
    origin = settings.cors_origins.split(",")[0].strip()
    res = client.options("/api/v1/auth/login", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
    })
    assert res.headers.get("access-control-allow-origin") == origin
