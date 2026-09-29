import pytest
from fastapi.testclient import TestClient
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.db.session import SessionLocal
from app.models.entities import User
from app.core.config import settings
from app.services.tender_service import extract_requirements_from_text
from app.adapters.documents.realistic_generator import generate_realistic_document
from scripts.seed import seed_database
import pymupdf
from io import BytesIO
from uuid import uuid4
from reportlab.pdfgen import canvas

client = TestClient(app)
_read_token = client.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"}).json()["access_token"]
client.headers.update({"Authorization": f"Bearer {_read_token}"})

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["demo_mode"] == True

def test_auth_flow():
    # Invalid password
    bad_res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "WrongPassword"})
    assert bad_res.status_code == 401

    # Valid login
    res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"})
    assert res.status_code == 200
    token_data = res.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # Test me endpoint
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "officer"


def test_documented_demo_accounts_can_sign_in_after_sync(monkeypatch):
    # This mirrors a Render startup against the already-seeded database.
    monkeypatch.setattr(settings, "reset_demo_passwords", True)
    seed_database()
    for username in ("officer", "verifier", "auditor", "admin"):
        res = client.post("/api/v1/auth/login", json={"username": username, "password": "BidShield@123"})
        assert res.status_code == 200
        assert res.json()["user"]["username"] == username

def test_tenders_and_requirements():
    res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # List tenders
    t_res = client.get("/api/v1/tenders")
    assert t_res.status_code == 200
    tenders = t_res.json()
    assert len(tenders) >= 5

    # Get tender 1
    t1_res = client.get(f"/api/v1/tenders/{tenders[0]['id']}")
    assert t1_res.status_code == 200
    t1 = t1_res.json()
    assert len(t1["requirements"]) >= 4
    assert len(t1["bidders"]) == 10

    # Add custom requirement
    add_req_res = client.post(
        f"/api/v1/tenders/{t1['id']}/requirements",
        json={
            "code": "CYBER-001",
            "name": "ISO 27001 Information Security Certification",
            "requirement_type": "TECHNICAL",
            "description": "Bidder must possess valid ISO 27001 certificate."
        },
        headers=headers
    )
    assert add_req_res.status_code == 200
    new_req_id = add_req_res.json()["id"]

    # Approve requirement
    appr_res = client.post(f"/api/v1/tenders/{t1['id']}/requirements/{new_req_id}/approve", headers=headers)
    assert appr_res.status_code == 200
    assert appr_res.json()["approval_status"] == "APPROVED"

def test_bidders_360_and_documents():
    b_res = client.get("/api/v1/bidders")
    assert b_res.status_code == 200
    bidders = b_res.json()
    assert len(bidders) == 10

    # Bidder 360
    b1_res = client.get(f"/api/v1/bidders/{bidders[0]['id']}")
    assert b1_res.status_code == 200
    b1 = b1_res.json()
    assert len(b1["documents"]) >= 6
    assert len(b1["contracts"]) >= 2
    assert b1["compliance_summary"] is not None

    # Stream document file
    doc_id = b1["documents"][0]["id"]
    file_res = client.get(f"/api/v1/documents/{doc_id}/file")
    assert file_res.status_code == 200
    assert file_res.headers["content-type"] == "application/pdf"
    assert file_res.content.startswith(b"%PDF")

def test_ocr_and_verification():
    res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    docs_res = client.get("/api/v1/documents")
    docs = docs_res.json()
    assert len(docs) >= 60

    doc_id = docs[0]["id"]
    ocr_res = client.post(f"/api/v1/documents/{doc_id}/ocr", headers=headers)
    assert ocr_res.status_code == 200
    assert "confidence" in ocr_res.json()

    verif_res = client.post(f"/api/v1/documents/{doc_id}/verify", headers=headers)
    assert verif_res.status_code == 200
    assert "status" in verif_res.json()

def test_reports_generation_and_download(signature_png_data):
    res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    db = SessionLocal()
    officer = db.query(User).filter(User.username == "officer").first()
    officer.signature_data = None
    db.commit()
    db.close()

    # Signed report generation is blocked until this account has a saved signature.
    assert client.get("/api/v1/auth/signature", headers=headers).status_code == 200

    tenders = client.get("/api/v1/tenders").json()
    tender_id = tenders[0]["id"]
    bidders = client.get("/api/v1/bidders").json()
    bidder_id = bidders[0]["id"]

    no_signature = client.post("/api/v1/reports/quick-list", json={"tender_id": tender_id}, headers=headers)
    assert no_signature.status_code == 409
    signature_res = client.put("/api/v1/auth/signature", json={"signature_data": signature_png_data}, headers=headers)
    assert signature_res.status_code == 200
    assert client.get("/api/v1/auth/signature", headers=headers).json()["signature_data"] == signature_png_data

    # Report 1: Consolidated Tender Evaluation
    r1_res = client.post("/api/v1/reports/quick-list", json={"tender_id": tender_id}, headers=headers)
    assert r1_res.status_code == 200
    r1 = r1_res.json()
    assert r1["report_type"] == "QUICK_LIST"
    summary_pdf = client.get(f"/api/v1/reports/{r1['report_uid']}/download", headers=headers)
    assert summary_pdf.status_code == 200 and summary_pdf.content.startswith(b"%PDF")
    with pymupdf.open(stream=summary_pdf.content, filetype="pdf") as consolidated_pdf:
        consolidated_text = " ".join(" ".join(page.get_text().split()) for page in consolidated_pdf)
    assert "CONSOLIDATED TENDER EVALUATION REPORT" in consolidated_text
    assert "Verified Docs" in consolidated_text

    # Report 2: Detailed Assessment
    r2_res = client.post("/api/v1/reports/detailed-assessment", json={"tender_id": tender_id, "bidder_id": bidder_id}, headers=headers)
    assert r2_res.status_code == 200
    r2 = r2_res.json()
    assert r2["report_type"] == "DETAILED_ASSESSMENT"

    # Download Report 2
    dl_res = client.get(f"/api/v1/reports/{r2['report_uid']}/download")
    assert dl_res.status_code == 200
    assert dl_res.content.startswith(b"%PDF")
    assert "X-Report-SHA256" in dl_res.headers
    view_res = client.get(f"/api/v1/reports/{r2['report_uid']}/view", headers=headers)
    assert view_res.status_code == 200
    assert view_res.headers["content-disposition"].startswith("inline;")
    assert view_res.content.startswith(b"%PDF")
    with pymupdf.open(stream=dl_res.content, filetype="pdf") as signed_pdf:
        report_text = "\n".join(page.get_text() for page in signed_pdf)
        has_signature_image = any(page.get_images(full=True) for page in signed_pdf)
    assert "Officer Information and Determination" in report_text
    assert "Report ID: BS-RPT-" in report_text
    assert "Evidence Summary" in report_text
    assert has_signature_image

def test_officer_decision_and_audit():
    res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    tenders = client.get("/api/v1/tenders").json()
    tender_id = tenders[0]["id"]
    bidders = client.get("/api/v1/bidders").json()
    bidder_id = bidders[0]["id"]

    dec_res = client.post(
        f"/api/v1/tenders/{tender_id}/bidders/{bidder_id}/decision",
        json={"decision": "ACCEPTED", "decision_notes": "All technical and financial criteria verified genuine."},
        headers=headers
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["decision"] == "ACCEPTED"

    # An automated finding cannot make or block the officer's formal procurement decision.
    bad_dec_res = client.post(
        f"/api/v1/tenders/{tender_id}/bidders/{bidders[1]['id']}/decision",
        json={"decision": "ACCEPTED", "decision_notes": "Attempting to pass disqualified bidder"},
        headers=headers
    )
    assert bad_dec_res.status_code == 200
    assert bad_dec_res.json()["decision"] == "ACCEPTED"

    # Rejecting disqualified bidder succeeds
    rej_res = client.post(
        f"/api/v1/tenders/{tender_id}/bidders/{bidders[1]['id']}/decision",
        json={"decision": "REJECTED", "decision_notes": "Disqualified due to GSTIN mismatch"},
        headers=headers
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["decision"] == "REJECTED"

    # Check audit log
    audit_res = client.get("/api/v1/audit?limit=10")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) > 0
    actions = [l["action"] for l in logs]
    assert any("OFFICER_DECISION" in a for a in actions)

    auditor_login = client.post("/api/v1/auth/login", json={"username": "auditor", "password": "BidShield@123"})
    auditor_headers = {"Authorization": f"Bearer {auditor_login.json()['access_token']}"}
    denied = client.post(
        f"/api/v1/tenders/{tender_id}/bidders/{bidder_id}/decision",
        json={"decision": "REJECTED", "decision_notes": "RBAC check"},
        headers=auditor_headers,
    )
    assert denied.status_code == 403

def test_procurement_data_requires_authentication():
    assert client.get("/api/v1/tenders", headers={"Authorization": ""}).status_code == 401

def test_upload_rejects_non_pdf_and_malformed_pdf():
    bidder_id = client.get("/api/v1/bidders").json()[0]["id"]
    form = {"bidder_id": str(bidder_id), "document_type": "GST"}
    plain = client.post("/api/v1/documents/upload", data=form,
                        files={"file": ("proof.txt", b"not a pdf", "text/plain")})
    assert plain.status_code == 415
    malformed = client.post("/api/v1/documents/upload", data=form,
                            files={"file": ("proof.pdf", b"%PDF-1.7 broken", "application/pdf")})
    assert malformed.status_code == 400

def test_requirement_extraction_does_not_invent_thresholds():
    candidates = extract_requirements_from_text("Tender mentions annual turnover, past experience, and local content.")
    by_code = {item["code"]: item for item in candidates}
    assert "min_turnover_cr" not in by_code["TURNOVER-001"]["structured_rule"]
    assert "min_years" not in by_code["EXP-001"]["structured_rule"]
    assert "min_pct" not in by_code["LOCAL-001"]["structured_rule"]
    assert all(item["source_page"] == 0 for item in candidates)

def test_generated_demo_document_has_unofficial_disclaimer():
    data = generate_realistic_document("GST", "Synthetic Bidder", "27AAACA1234A1Z5", {})
    with pymupdf.open(stream=data, filetype="pdf") as document:
        assert "SYNTHETIC DEMO ONLY" in document[0].get_text()
        assert "NOT VALID FOR OFFICIAL USE" in document[0].get_text()

def test_tender_pdf_upload_extracts_reviewable_candidates():
    tender = client.post("/api/v1/tenders", json={
        "tender_ref": f"PDF-TEST-{uuid4().hex[:8]}", "title": "Supply tender",
        "department": "Test", "category": "Test", "issue_date": "2026-01-01", "closing_date": "2026-12-31"
    })
    assert tender.status_code == 200
    pdf = BytesIO()
    writer = canvas.Canvas(pdf)
    writer.drawString(72, 720, "Annual turnover must be at least 10 Cr. Experience of 5 years. Local content threshold 40%.")
    writer.save()
    uploaded = client.post(f"/api/v1/tenders/{tender.json()['id']}/pdf", files={
        "file": ("tender.pdf", pdf.getvalue(), "application/pdf")
    })
    assert uploaded.status_code == 200
    extracted = client.post(f"/api/v1/tenders/{tender.json()['id']}/extract-requirements")
    assert extracted.status_code == 200
    by_code = {item["code"]: item for item in extracted.json()["requirements"]}
    assert by_code["TURNOVER-001"]["structured_rule"]["min_turnover_cr"] == 10
    assert by_code["EXP-001"]["structured_rule"]["min_years"] == 5
    assert by_code["LOCAL-001"]["structured_rule"]["min_pct"] == 40
    assert all(item["approval_status"] == "PENDING" for item in by_code.values())

def test_blank_tender_pdf_requires_manual_review():
    tender = client.post("/api/v1/tenders", json={
        "tender_ref": f"PDF-BLANK-{uuid4().hex[:8]}", "title": "Scanned tender",
        "department": "Test", "category": "Test", "issue_date": "2026-01-01", "closing_date": "2026-12-31"
    })
    assert tender.status_code == 200
    pdf = BytesIO()
    blank = canvas.Canvas(pdf)
    blank.showPage()
    blank.save()
    uploaded = client.post(f"/api/v1/tenders/{tender.json()['id']}/pdf", files={
        "file": ("blank.pdf", pdf.getvalue(), "application/pdf")
    })
    assert uploaded.status_code == 200
    extracted = client.post(f"/api/v1/tenders/{tender.json()['id']}/extract-requirements")
    assert extracted.status_code == 200
    assert extracted.json()["status"] == "MANUAL_REVIEW"

def test_dashboard():
    dash_res = client.get("/api/v1/dashboard")
    assert dash_res.status_code == 200
    dash = dash_res.json()
    assert dash["active_tenders"] >= 5
    assert dash["total_bidders"] == 10
    assert "risk_distribution" in dash
