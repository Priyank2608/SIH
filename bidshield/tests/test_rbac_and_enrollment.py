"""Regression tests: bidder bid-intake enrollment API + strict RBAC 403 responses.

These tests lock in two behaviors:
  1. POST /api/v1/bidders (officer-only bid intake): creates a bidder shell,
     enrolls it against a tender, re-enrolls an existing tenant bidder, and
     rejects duplicate enrollments with 409.
  2. require_roles() is strict: any role NOT explicitly listed by an endpoint
     gets 403 (deliberately including SUPER_ADMIN -- administration authority
     does not confer procurement authority).

Ordering note: test_backend.py (asserts exactly 10 total bidders) and
test_e2e_flow.py (asserts exactly 10 bidders on tenders[0]) both run before
this file alphabetically, and test_tenant_isolation.py runs after and relies
on tender id 1 existing. The enrollment tests therefore clean up every row
they create so the suite stays re-runnable against the persistent demo DB.
Audit rows are append-only (hash-chained) and are intentionally NOT deleted.
"""
import os
import sys
from uuid import uuid4

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import or_

from app.main import app
from app.db.session import SessionLocal
from app.models.entities import Bidder, TenderBidder

client = TestClient(app)
_read_token = client.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"}).json()["access_token"]
client.headers.update({"Authorization": f"Bearer {_read_token}"})


def _login(username: str) -> dict:
    """Fresh login for a demo account -> Authorization headers."""
    res = client.post("/api/v1/auth/login", json={"username": username, "password": "BidShield@123"})
    assert res.status_code == 200, f"login as {username} failed: {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def enrolled_bidder():
    """Create bidder rows via the enrollment API, then remove them again.

    The fixture receives a dict; tests store the created bidder id under
    "bidder_id". Teardown re-queries tender_bidders links at teardown time
    (tests may enroll the same bidder into more tenders afterwards), deletes
    the links and the bidder, and verifies the demo tenant's data is back to
    the seeded 10 bidders. Audit events (BIDDER_CREATED / BIDDER_ENROLLED)
    are hash-chained and stay in place -- they are append-only by design.
    """
    created = {"bidder_id": None}

    yield created

    db = SessionLocal()
    try:
        # Self-heal: also sweep probe bidders left behind by a previously
        # crashed run of this file (the demo DB persists between runs).
        leftovers = db.query(Bidder.id).filter(
            Bidder.tenant_id == 1,
            or_(Bidder.legal_name.like("Regression Bidder %"),
                Bidder.legal_name.like("Chain Probe %")),
        ).all()
        ids = {row.id for row in leftovers}
        if created["bidder_id"]:
            ids.add(created["bidder_id"])
        if ids:
            db.query(TenderBidder).filter(TenderBidder.bidder_id.in_(ids)).delete(synchronize_session=False)
            db.query(Bidder).filter(Bidder.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
        assert db.query(Bidder).filter(Bidder.tenant_id == 1).count() == 10, \
            "cleanup failed: demo tenant must be back to its 10 seeded bidders"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Bidder enrollment API (POST /api/v1/bidders)
# ---------------------------------------------------------------------------

def test_officer_can_enroll_new_bidder_with_minimal_payload(enrolled_bidder):
    tenders = client.get("/api/v1/tenders").json()
    tender_id = tenders[0]["id"]
    legal_name = f"Regression Bidder {uuid4().hex[:10]}"

    res = client.post("/api/v1/bidders", json={
        "tender_id": tender_id,
        "legal_name": legal_name,
    })
    assert res.status_code == 201, res.text
    detail = res.json()
    enrolled_bidder["bidder_id"] = detail["id"]

    # Required fields echoed; optional identifiers defaulted for later OCR capture.
    assert detail["legal_name"] == legal_name
    assert detail["pan"] == "PENDING"
    assert detail["gstin"] == "PENDING"
    assert detail["contact_email"] == "pending@bidshield.local"

    # Bidder is enrolled against the tender and visible in the tender workspace.
    tender_detail = client.get(f"/api/v1/tenders/{tender_id}").json()
    tb = next(b for b in tender_detail["bidders"] if b["id"] == detail["id"])
    assert tb["legal_name"] == legal_name
    assert tb["final_decision"] == "PENDING"

    # The intake action is audit-logged.
    audit = client.get("/api/v1/audit?limit=50").json()
    actions = [e["action"] for e in audit if e["entity_id"] == str(detail["id"])]
    assert "BIDDER_CREATED" in actions


def test_officer_can_reenroll_existing_bidder_into_another_tender(enrolled_bidder):
    tenders = client.get("/api/v1/tenders").json()
    first_tender, second_tender = tenders[0]["id"], tenders[1]["id"]
    legal_name = f"Regression Bidder {uuid4().hex[:10]}"

    first = client.post("/api/v1/bidders", json={"tender_id": first_tender, "legal_name": legal_name})
    assert first.status_code == 201, first.text
    detail = first.json()
    enrolled_bidder["bidder_id"] = detail["id"]

    # Same legal_name against a different tender: enroll the existing bidder, not a new row.
    second = client.post("/api/v1/bidders", json={"tender_id": second_tender, "legal_name": legal_name})
    assert second.status_code == 201, second.text
    assert second.json()["id"] == detail["id"], "existing bidder must be reused, not duplicated"

    db = SessionLocal()
    try:
        assert db.query(Bidder).filter(Bidder.legal_name == legal_name).count() == 1
        links = db.query(TenderBidder).filter(TenderBidder.bidder_id == detail["id"]).count()
        assert links == 2, "bidder must be enrolled against both tenders"
    finally:
        db.close()

    # Enrolling the same bidder into the same tender again is a conflict.
    duplicate = client.post("/api/v1/bidders", json={"tender_id": first_tender, "legal_name": legal_name})
    assert duplicate.status_code == 409
    assert "already enrolled" in duplicate.json()["detail"]


def test_enrollment_validation_rejects_bad_payloads():
    tenders = client.get("/api/v1/tenders").json()
    tender_id = tenders[0]["id"]

    # legal_name shorter than the 2-char minimum.
    short = client.post("/api/v1/bidders", json={"tender_id": tender_id, "legal_name": "A"})
    assert short.status_code == 422

    # legal_name missing entirely.
    missing = client.post("/api/v1/bidders", json={"tender_id": tender_id})
    assert missing.status_code == 422

    # tender_id missing entirely.
    no_tender = client.post("/api/v1/bidders", json={"legal_name": "Some Valid Name"})
    assert no_tender.status_code == 422

    # Unknown tender: authenticated + authorized, but the tender is not in this tenant.
    foreign = client.post("/api/v1/bidders", json={"tender_id": 999999, "legal_name": "Some Valid Name"})
    assert foreign.status_code == 404


def test_enrollment_requires_authentication():
    res = client.post("/api/v1/bidders", json={"tender_id": 1, "legal_name": "Anon Bidder"},
                      headers={"Authorization": ""})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Strict RBAC 403s (require_roles has NO SUPER_ADMIN bypass)
# ---------------------------------------------------------------------------

# (name, method, url, request kwargs builder, roles that must be blocked)
RBAC_MATRIX = [
    ("create tender", "POST", "/api/v1/tenders", lambda: {
        "json": {
            "tender_ref": f"RBAC-{uuid4().hex[:8]}", "title": "RBAC probe", "department": "Test",
            "category": "Test", "issue_date": "2026-01-01", "closing_date": "2026-12-31",
        }}, ("verifier", "auditor", "admin")),
    ("enroll bidder", "POST", "/api/v1/bidders", lambda: {
        "json": {"tender_id": 1, "legal_name": "RBAC Probe Bidder"}}, ("verifier", "auditor", "admin")),
    ("upload document", "POST", "/api/v1/documents/upload", lambda: {
        "data": {"bidder_id": "1", "document_type": "GST"},
        "files": {"file": ("rbac-probe.pdf", b"%PDF-1.4 rbac probe", "application/pdf")},
    }, ("verifier", "auditor", "admin")),
    ("quick-list report", "POST", "/api/v1/reports/quick-list", lambda: {
        "json": {"tender_id": 1}}, ("verifier", "auditor", "admin")),
    ("officer decision", "POST", "/api/v1/tenders/1/bidders/1/decision", lambda: {
        "json": {"decision": "REJECTED", "decision_notes": "RBAC regression probe"}},
     ("verifier", "auditor", "admin")),
]

BLOCKED_CASES = [(name, method, url, body, role)
                 for name, method, url, body, roles in RBAC_MATRIX
                 for role in roles]


@pytest.mark.parametrize("name,method,url,body,role", BLOCKED_CASES,
                         ids=[f"{c[0]}:{c[4]}" for c in BLOCKED_CASES])
def test_non_officer_roles_get_403_on_procurement_writes(name, method, url, body, role):
    res = client.request(method, url, **body(), headers=_login(role))
    assert res.status_code == 403, f"{role} must be blocked from {name}: got {res.status_code}"
    assert res.json()["detail"] == "Insufficient operational permissions"


def test_officer_still_allowed_on_procurement_writes():
    """Sanity: the strict gates did not lock the officer out. Where the full
    happy path would create data, assert the gate outcome by the *next*
    status the app returns after authorization (never 401/403)."""
    headers = _login("officer")

    # Decision: officer passes the gate and the decision is recorded.
    dec = client.post("/api/v1/tenders/1/bidders/1/decision",
                      json={"decision": "REJECTED", "decision_notes": "officer role sanity probe"},
                      headers=headers)
    assert dec.status_code == 200, dec.text
    assert dec.json()["decision"] == "REJECTED"

    # Report: gate passes; without a signature the app answers 409 (not 403).
    rep = client.post("/api/v1/reports/quick-list", json={"tender_id": 1}, headers=headers)
    assert rep.status_code in (200, 409), rep.text

    # Upload: gate passes; a structurally invalid file answers 415 (not 403).
    up = client.post("/api/v1/documents/upload",
                     data={"bidder_id": "1", "document_type": "GST"},
                     files={"file": ("probe.txt", b"not a pdf", "text/plain")},
                     headers=headers)
    assert up.status_code == 415, up.text

    # Enrollment: gate passes; an invalid payload answers 422 (not 403).
    enroll = client.post("/api/v1/bidders", json={"tender_id": 1, "legal_name": "X"}, headers=headers)
    assert enroll.status_code == 422, enroll.text


def test_verification_endpoints_allow_officer_and_verifier_but_block_auditor_and_admin():
    docs = client.get("/api/v1/documents").json()
    doc_id = docs[0]["id"]

    for role, expected in (("officer", 200), ("verifier", 200), ("auditor", 403), ("admin", 403)):
        headers = _login(role)
        ocr = client.post(f"/api/v1/documents/{doc_id}/ocr", headers=headers)
        assert ocr.status_code == expected, f"{role} on OCR: got {ocr.status_code}, wanted {expected}"

        retry = client.post(f"/api/v1/verification/{doc_id}/retry", headers=headers)
        assert retry.status_code == expected, f"{role} on retry: got {retry.status_code}, wanted {expected}"


def test_audit_integrity_is_auditor_only_and_chain_stays_valid(enrolled_bidder):
    # The integrity report itself is auditor-gated.
    assert client.get("/api/v1/audit/integrity", headers=_login("auditor")).status_code == 200
    assert client.get("/api/v1/audit/integrity", headers=_login("officer")).status_code == 403
    assert client.get("/api/v1/audit/integrity", headers=_login("verifier")).status_code == 403
    assert client.get("/api/v1/audit/integrity", headers=_login("admin")).status_code == 403

    # Enrollment writes audit events; the tenant chain must still verify cleanly.
    tenders = client.get("/api/v1/tenders").json()
    res = client.post("/api/v1/bidders", json={
        "tender_id": tenders[0]["id"], "legal_name": f"Chain Probe {uuid4().hex[:8]}",
    })
    assert res.status_code == 201
    enrolled_bidder["bidder_id"] = res.json()["id"]

    integrity = client.get("/api/v1/audit/integrity", headers=_login("auditor")).json()
    assert integrity["valid"] is True, "append-only audit writes must keep the tenant chain valid"
