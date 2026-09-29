import os
import sys
from uuid import uuid4
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.core.security import hash_password
from app.models.entities import (Tenant, User, Tender, TenderRequirement, Bidder, TenderBidder,
    BidderDocument, EvidenceRecord, GeneratedReport)
from app.services.audit_service import log_audit_event


@pytest.fixture
def foreign_resources():
    db = SessionLocal()
    suffix = uuid4().hex[:10]
    tenant = Tenant(code=f"TEST-{suffix}", name="Isolation test tenant")
    db.add(tenant)
    db.flush()
    user = User(tenant_id=tenant.id, username=f"tenantb-{suffix}", email=f"{suffix}@test.invalid",
                hashed_password=hash_password("Temporary-Test-Password-1"), full_name="Tenant B Officer",
                role="PROCUREMENT_OFFICER")
    tender = Tender(tenant_id=tenant.id, tender_ref=f"TEST/{suffix}", title="Private tender",
                    department="Test", category="Test", issue_date="2026-01-01", closing_date="2026-12-31")
    bidder = Bidder(tenant_id=tenant.id, legal_name="Private Bidder", pan=f"ABCDE{suffix[:4].upper()}F",
                    gstin=f"27ABCDE{suffix[:4].upper()}F1Z5", address="Private", state="X", district="Y",
                    contact_email=f"b-{suffix}@test.invalid", contact_phone="000", contact_person="B")
    db.add_all([user, tender, bidder])
    db.flush()
    requirement = TenderRequirement(tender_id=tender.id, code="TEST-1", name="Private requirement",
        requirement_type="MANDATORY", description="Private", structured_rule={}, source_page=0,
        confidence=0.6, approval_status="PENDING")
    association = TenderBidder(tender_id=tender.id, bidder_id=bidder.id)
    document = BidderDocument(bidder_id=bidder.id, tender_id=tender.id, document_type="GST",
        filename="private.pdf", mime_type="application/pdf", file_hash="a" * 64,
        file_size_bytes=8, content_bytes=b"private")
    db.add_all([requirement, association, document])
    db.flush()
    evidence = EvidenceRecord(tender_id=tender.id, bidder_id=bidder.id, claim_type="TEST",
        evidence_text="private evidence", source_reference="test")
    report = GeneratedReport(report_uid=suffix * 3, tender_id=tender.id, bidder_id=bidder.id,
        report_type="QUICK_LIST", filename="private.pdf", file_hash="b" * 64, file_bytes=b"%PDF-private")
    db.add_all([evidence, report])
    db.commit()
    log_audit_event(db, action=f"TENANT_B_PRIVATE_{suffix}", entity_type="TEST", tenant_id=tenant.id,
                    user_id=user.id, username=user.username)
    result = {"tender": tender.id, "requirement": requirement.id, "bidder": bidder.id,
              "document": document.id, "report": report.report_uid, "audit_action": f"TENANT_B_PRIVATE_{suffix}",
              "username": user.username, "password": "Temporary-Test-Password-1"}
    db.close()
    return result


@pytest.fixture
def tenant_a_client(signature_png_data):
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"})
    assert login.status_code == 200
    client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
    assert client.put("/api/v1/auth/signature", json={"signature_data": signature_png_data}).status_code == 200
    return client


def test_tenant_cannot_read_or_modify_foreign_resources(tenant_a_client, foreign_resources):
    client, foreign = tenant_a_client, foreign_resources
    own_tenders = client.get("/api/v1/tenders")
    assert own_tenders.status_code == 200
    assert all(item["id"] != foreign["tender"] for item in own_tenders.json())
    assert client.get(f"/api/v1/tenders/{foreign['tender']}").status_code == 404
    assert client.get(f"/api/v1/bidders/{foreign['bidder']}").status_code == 404
    assert client.get(f"/api/v1/documents/{foreign['document']}/file").status_code == 404
    assert client.get(f"/api/v1/reports/{foreign['report']}/download").status_code == 404
    assert client.get(f"/api/v1/reports/{foreign['report']}/view").status_code == 404
    assert client.get(f"/api/v1/bidders/{foreign['bidder']}/evidence").status_code == 404
    audit = client.get("/api/v1/audit?limit=200")
    assert audit.status_code == 200
    assert foreign["audit_action"] not in [event["action"] for event in audit.json()]
    assert client.put(f"/api/v1/tenders/{foreign['tender']}/requirements/{foreign['requirement']}",
                      json={"name": "attempted change"}).status_code == 404
    assert client.post(f"/api/v1/tenders/{foreign['tender']}/bidders/{foreign['bidder']}/decision",
                       json={"decision": "REJECTED", "decision_notes": "unauthorized tenant"}).status_code == 404


def test_foreign_tenant_cannot_read_or_modify_tenant_a_resources(foreign_resources, signature_png_data):
    db = SessionLocal()
    tenant_a_tender = db.query(Tender).filter(Tender.tenant_id == 1).order_by(Tender.id).first()
    tenant_a_bidder = db.query(Bidder).filter(Bidder.tenant_id == 1).order_by(Bidder.id).first()
    tenant_a_document = db.query(BidderDocument).filter(
        BidderDocument.bidder_id == tenant_a_bidder.id
    ).order_by(BidderDocument.id).first()
    tenant_a_requirement = db.query(TenderRequirement).filter(
        TenderRequirement.tender_id == tenant_a_tender.id
    ).order_by(TenderRequirement.id).first()
    tenant_a_bid = db.query(TenderBidder).filter(
        TenderBidder.tender_id == tenant_a_tender.id,
        TenderBidder.bidder_id == tenant_a_bidder.id,
    ).first()
    db.close()

    client_a = TestClient(app)
    login_a = client_a.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"})
    assert login_a.status_code == 200
    client_a.headers.update({"Authorization": f"Bearer {login_a.json()['access_token']}"})
    assert client_a.put("/api/v1/auth/signature", json={"signature_data": signature_png_data}).status_code == 200
    report = client_a.post("/api/v1/reports/quick-list", json={"tender_id": tenant_a_tender.id})
    assert report.status_code == 200
    tenant_a_audit_action = f"TENANT_A_PRIVATE_{report.json()['report_uid']}"
    db = SessionLocal()
    actor = db.query(User).filter(User.username == "officer").first()
    log_audit_event(db, action=tenant_a_audit_action, entity_type="TEST", tenant_id=1,
                    user_id=actor.id, username=actor.username)
    db.close()

    client_b = TestClient(app)
    login_b = client_b.post("/api/v1/auth/login", json={
        "username": foreign_resources["username"], "password": foreign_resources["password"]
    })
    assert login_b.status_code == 200
    client_b.headers.update({"Authorization": f"Bearer {login_b.json()['access_token']}"})
    assert client_b.get("/api/v1/auth/signature").json() == {"signature_data": None}

    assert client_b.get(f"/api/v1/tenders/{foreign_resources['tender']}").status_code == 200
    assert client_b.get(f"/api/v1/tenders/{tenant_a_tender.id}").status_code == 404
    assert client_b.get(f"/api/v1/bidders/{tenant_a_bidder.id}").status_code == 404
    assert client_b.get(f"/api/v1/documents/{tenant_a_document.id}/file").status_code == 404
    assert client_b.get(f"/api/v1/reports/{report.json()['report_uid']}/download").status_code == 404
    assert client_b.get(f"/api/v1/reports/{report.json()['report_uid']}/view").status_code == 404
    assert client_b.get(f"/api/v1/bidders/{tenant_a_bidder.id}/evidence").status_code == 404
    assert client_b.put(
        f"/api/v1/tenders/{tenant_a_tender.id}/requirements/{tenant_a_requirement.id}",
        json={"name": "cross-tenant edit"},
    ).status_code == 404
    if tenant_a_bid:
        assert client_b.post(
            f"/api/v1/tenders/{tenant_a_tender.id}/bidders/{tenant_a_bidder.id}/decision",
            json={"decision": "REJECTED", "decision_notes": "cross-tenant attempt"},
        ).status_code == 404

    visible_audit_actions = [event["action"] for event in client_b.get("/api/v1/audit?limit=200").json()]
    assert foreign_resources["audit_action"] in visible_audit_actions
    assert tenant_a_audit_action not in visible_audit_actions
