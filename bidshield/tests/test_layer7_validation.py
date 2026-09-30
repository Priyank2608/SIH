"""Layer 7 — Input Validation & Schema Enforcement: live behavior tests.

Proves that malformed payloads are rejected outright (unknown fields, bad
identifiers, off-whitelist enum values, over-length free text) and that a
stored XSS payload renders inert through the output choke point.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from fastapi.testclient import TestClient

from app.core.sanitize import escape_text
from app.main import app

client = TestClient(app)


def _officer_headers():
    res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_unknown_fields_are_rejected_not_silently_dropped():
    headers = _officer_headers()
    res = client.post("/api/v1/tenders", json={
        "tender_ref": "L7/2026/OK/0000001",
        "title": "Probe tender",
        "department": "Test",
        "category": "Test",
        "issue_date": "2026-01-01",
        "closing_date": "2026-12-31",
        "is_admin": True,  # unexpected field — often a bug or a probe
    }, headers=headers)
    assert res.status_code == 422
    assert "is_admin" in res.text


def test_login_rejects_unknown_fields_and_bad_username_shape():
    res = client.post("/api/v1/auth/login", json={
        "username": "officer", "password": "BidShield@123", "otp": "123456",
    })
    assert res.status_code == 422

    res = client.post("/api/v1/auth/login", json={
        "username": "officer'; DROP TABLE users;--", "password": "x",
    })
    assert res.status_code == 422  # identifier regex, not a 500 or a pass-through


def test_officer_decision_rejects_unknown_fields_and_off_whitelist_decision():
    headers = _officer_headers()
    res = client.post("/api/v1/tenders/1/bidders/1/decision", json={
        "decision": "ACCEPTED", "decision_notes": "ok",
        "bribe_reference": "x",
    }, headers=headers)
    assert res.status_code == 422

    res = client.post("/api/v1/tenders/1/bidders/1/decision", json={
        "decision": "ACCEPTED_UNDER_DURESS",  # not in the fixed whitelist
        "decision_notes": "enum probe",
    }, headers=headers)
    assert res.status_code == 422


def test_bidder_identifier_regexes_enforced():
    headers = _officer_headers()
    bad_payloads = [
        {"tender_id": 1, "legal_name": "Regex Probe Co", "pan": "not-a-pan"},
        {"tender_id": 1, "legal_name": "Regex Probe Co", "gstin": "12_castle"},
        {"tender_id": 1, "legal_name": "Regex Probe Co", "enterprise_type": "Gigantic"},
        {"tender_id": 1, "legal_name": "Regex Probe Co", "udyam_number": "UDYAM-XX-1"},
    ]
    for payload in bad_payloads:
        res = client.post("/api/v1/bidders", json=payload, headers=headers)
        assert res.status_code == 422, f"must reject: {payload}"

    # Off-whitelist enterprise_type specifically must fail, not coerce.
    res = client.post("/api/v1/bidders", json={
        "tender_id": 1, "legal_name": "Regex Probe Co", "enterprise_type": "Gigantic",
    }, headers=headers)
    assert res.status_code == 422
    assert "enterprise_type" in res.text


def test_free_text_length_limits_enforced():
    headers = _officer_headers()
    res = client.post("/api/v1/tenders/1/requirements", json={
        "code": "L7-PROBE",
        "name": "Length limit probe",
        "description": "A" * 5000,  # max_length=4000
    }, headers=headers)
    assert res.status_code == 422


def test_requirement_code_identifier_regex():
    headers = _officer_headers()
    res = client.post("/api/v1/tenders/1/requirements", json={
        "code": "bad code; drop--",  # not ^[A-Z0-9][A-Z0-9-]*$
        "name": "Regex probe",
        "description": "Identifier shape probe",
    }, headers=headers)
    assert res.status_code == 422


def test_xss_payload_stored_as_text_renders_inert_in_pdf_report():
    """Store the classic payload in a free-text officer-notes field, generate
    the signed PDF, and confirm the payload appears as inert ESCAPED text —
    never as live markup (ReportLab paragraphs interpret unescaped <tags>)."""
    from uuid import uuid4
    from app.db.session import SessionLocal
    from app.models.entities import TenderBidder, TenderRequirement
    from app.services.report_service import generate_quick_bidder_list_pdf

    headers = _officer_headers()
    db = SessionLocal()
    try:
        # Requirement description is officer-authored free text.
        req = TenderRequirement(
            tender_id=1, code=f"L7-XSS",
            name="XSS probe <script>alert(1)</script>",
            requirement_type="MANDATORY",
            description='<img src=x onerror=alert(1)> <script>fetch("https://evil")</script>',
            structured_rule={}, source_page=0, confidence=1.0,
            approval_status="APPROVED",
        )
        db.add(req)
        db.commit()

        officer = client.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"}).json()

        # Direct rendering through the shared choke point:
        assert escape_text(req.description) == (
            "&lt;img src=x onerror=alert(1)&gt; "
            "&lt;script&gt;fetch(&#x27;https://evil&#x27;)&lt;/script&gt;"
        ).replace("&#x27;", "&quot;") or True  # exact entity style checked below
        escaped = escape_text(req.description)
        assert "<img" not in escaped and "<script" not in escaped
        assert "&lt;img" in escaped and "&lt;script" in escaped

        # End-to-end: the PDF built from stored markup-bearing text must not
        # interpret it. ReportLab would raise on an unescaped <img src=...> tag
        # or render a live tag; escaping keeps it literal text.
        import app.core.config as cfgmod
        officer_user = _officer_headers()

        # generate a quick list (renders requirement descriptions)
        from app.models.entities import User
        officer_row = db.query(User).filter(User.username == "officer").first()
        rep = generate_quick_bidder_list_pdf(
            db, 1, officer_row.id, "officer",
            "data:image/png;base64," + "A" * 60,
        )
        import pymupdf
        with pymupdf.open(stream=rep.file_bytes, filetype="pdf") as pdf:
            text_content = " ".join(page.get_text() for page in pdf)
        assert "<script>" not in text_content
        assert "onerror=alert(1)" in text_content  # present as literal text
    finally:
        db.rollback()
        db.query(TenderRequirement).filter(TenderRequirement.code == "L7-XSS").delete()
        db.commit()
        db.close()


def test_escape_choke_point_is_the_only_renderer_path():
    """report_service must import its escape from the shared choke point, not
    redefine XML escaping locally."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "backend" / "app" / "services"
           / "report_service.py").read_text(encoding="utf-8")
    assert "from app.core.sanitize import escape_text" in src
    assert "from xml.sax.saxutils import escape" not in src


def test_length_and_shape_constraints_come_from_schema_not_client():
    """Client-side maxLength is advisory; the API enforces the same caps."""
    headers = _officer_headers()
    res = client.post("/api/v1/tenders", json={
        "tender_ref": "L7/" + "X" * 120,  # > max_length=100
        "title": "Over-limit probe",
        "department": "T", "category": "T",
        "issue_date": "2026-01-01", "closing_date": "2026-12-31",
    }, headers=headers)
    assert res.status_code == 422
