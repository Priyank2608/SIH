"""Layer 5 — Application Logic Isolation: live behavior tests.

Query-level tenant scoping must answer 404 (not 403) for out-of-scope
resources, log every violation to the Layer 2 security log, and never
string-format user input into SQL.
"""
import os
import sys
from uuid import uuid4

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal
from app.main import app
from app.models.entities import SecurityEvent, Tenant, Tender, User

client = TestClient(app)


@pytest.fixture
def outsider_user():
    db = SessionLocal()
    suffix = uuid4().hex[:8]
    tenant = Tenant(code=f"L5-{suffix}", name="Layer 5 probe tenant")
    db.add(tenant)
    db.flush()
    user = User(tenant_id=tenant.id, username=f"l5-{suffix}", email=f"l5-{suffix}@t.invalid",
                hashed_password=__import__("app.core.security", fromlist=["hash_password"]).hash_password("Scoped-Pass-1"),
                full_name="Outsider", role="PROCUREMENT_OFFICER")
    db.add(user)
    db.commit()
    info = {"username": user.username, "password": "Scoped-Pass-1", "tenant_id": tenant.id}
    db.close()
    yield info
    db = SessionLocal()
    db.query(User).filter(User.username == info["username"]).delete()
    db.query(Tenant).filter(Tenant.code == f"L5-{suffix}").delete()
    db.commit()
    db.close()


def _outsider_headers(outsider_user):
    res = client.post("/api/v1/auth/login",
                      json={"username": outsider_user["username"], "password": outsider_user["password"]})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_out_of_scope_resource_returns_404_not_403(outsider_user):
    headers = _outsider_headers(outsider_user)
    db = SessionLocal()
    demo_tender_id = db.query(Tender).filter(Tender.tenant_id == 1).order_by(Tender.id).first().id
    db.close()

    # Correct role (PROCUREMENT_OFFICER), wrong tenant → 404, never 403.
    for url in (f"/api/v1/tenders/{demo_tender_id}",
                f"/api/v1/tenders/{demo_tender_id}/compliance-matrix",
                "/api/v1/bidders/1",
                "/api/v1/bidders/1/evidence",
                "/api/v1/documents/1",
                "/api/v1/documents/1/file"):
        res = client.get(url, headers=headers)
        assert res.status_code == 404, f"{url} must answer 404 for out-of-scope access"


def test_out_of_scope_access_is_logged_as_scope_violation(outsider_user):
    headers = _outsider_headers(outsider_user)
    db = SessionLocal()
    demo_tender_id = db.query(Tender).filter(Tender.tenant_id == 1).order_by(Tender.id).first().id
    username = outsider_user["username"]
    before = (db.query(SecurityEvent)
              .filter(SecurityEvent.kind == "SCOPE_VIOLATION", SecurityEvent.username == username)
              .count())
    db.close()

    client.get(f"/api/v1/tenders/{demo_tender_id}", headers=headers)

    db = SessionLocal()
    after = (db.query(SecurityEvent)
             .filter(SecurityEvent.kind == "SCOPE_VIOLATION", SecurityEvent.username == username)
             .count())
    latest = (db.query(SecurityEvent)
              .filter(SecurityEvent.kind == "SCOPE_VIOLATION", SecurityEvent.username == username)
              .order_by(SecurityEvent.id.desc()).first())
    db.close()
    assert after == before + 1
    assert latest.detail["resource"] == "tender"


def test_in_scope_access_is_not_logged_as_violation(outsider_user):
    headers = _outsider_headers(outsider_user)
    db = SessionLocal()
    username = outsider_user["username"]
    own_tender = Tender(tenant_id=outsider_user["tenant_id"], tender_ref=f"L5/{uuid4().hex[:8]}",
                        title="Own tender", department="T", category="T",
                        issue_date="2026-01-01", closing_date="2026-12-31")
    db.add(own_tender)
    db.commit()
    tender_id = own_tender.id
    db.close()

    res = client.get(f"/api/v1/tenders/{tender_id}", headers=headers)
    assert res.status_code == 200

    db = SessionLocal()
    hits = (db.query(SecurityEvent)
            .filter(SecurityEvent.kind == "SCOPE_VIOLATION", SecurityEvent.username == username)
            .count())
    db.close()
    assert hits == 0
    # Cleanup
    db = SessionLocal()
    db.query(Tender).filter(Tender.id == tender_id).delete()
    db.commit()
    db.close()


def test_queries_are_parameterized_no_string_formatting_of_user_input():
    """Grep-level guarantee: the data-access layer never builds SQL by f-string
    or %-formatting of request-derived values. All reads go through the ORM."""
    import pathlib
    backend = pathlib.Path(__file__).resolve().parents[1] / "backend" / "app"
    offenders = []
    for path in backend.rglob("*.py"):
        src = path.read_text(encoding="utf-8", errors="ignore")
        for needle in ('execute(f"', "execute(f'", '.format(', '% (', "text(f'"):
            if needle in src and "test" not in path.name:
                offenders.append(f"{path.name}: {needle}")
    assert offenders == [], f"possible SQL string-formatting: {offenders}"


def test_dynamic_identifiers_never_come_from_user_input():
    """The only dynamic table/column construction uses code-controlled values
    (e.g. document type strings validated against a fixed whitelist upstream).
    A probe of an unknown identifier cannot reach SQL text."""
    headers = {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'username': 'officer', 'password': 'BidShield@123'}).json()['access_token']}"}
    res = client.get("/api/v1/documents", params={"document_type": "GST; DROP TABLE users--"},
                     headers=headers)
    # Must be a clean empty list (filter matches nothing), not a 500.
    assert res.status_code == 200
    assert isinstance(res.json(), list)
