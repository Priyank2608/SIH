import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.main import app

client = TestClient(app)
_read_token = client.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"}).json()["access_token"]
client.headers.update({"Authorization": f"Bearer {_read_token}"})

def test_complete_19_step_e2e_flow(signature_png_data):
    # 1. Login
    login_res = client.post("/api/v1/auth/login", json={"username": "officer", "password": "BidShield@123"})
    assert login_res.status_code == 200, "Step 1: Login failed"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.put("/api/v1/auth/signature", json={"signature_data": signature_png_data}, headers=headers).status_code == 200

    # 2. Open synthetic GeM tender
    tenders_res = client.get("/api/v1/tenders")
    assert tenders_res.status_code == 200
    tenders = tenders_res.json()
    assert len(tenders) >= 5, "Step 2: Should have at least 5 synthetic tenders"
    tender_id = tenders[0]["id"]

    t_detail = client.get(f"/api/v1/tenders/{tender_id}").json()
    assert t_detail["tender_ref"] == "GEM/2026/B/0012345"

    # 3. View extracted requirements
    reqs = t_detail["requirements"]
    assert len(reqs) >= 4, "Step 3: Requirements must be present"

    # 4. Approve requirements
    unapproved = [r for r in reqs if r["approval_status"] != "APPROVED"]
    for u in unapproved:
        appr_res = client.post(f"/api/v1/tenders/{tender_id}/requirements/{u['id']}/approve", headers=headers)
        assert appr_res.status_code == 200
        assert appr_res.json()["approval_status"] == "APPROVED", "Step 4: Approval failed"

    # 5. Open bidders
    bidders = t_detail["bidders"]
    assert len(bidders) == 10, "Step 5: Must have 10 bidders in tender"

    # 6. Select bidder (Alpha Technologies Pvt Ltd)
    alpha_bidder = next(b for b in bidders if "Alpha" in b["legal_name"])
    bidder_id = alpha_bidder["id"]

    # 7. View bidder documents
    b360 = client.get(f"/api/v1/bidders/{bidder_id}?tender={tender_id}").json()
    docs = b360["documents"]
    assert len(docs) >= 6, "Step 7: Bidder should have multiple documents"

    # 8. Open synthetic GST document
    gst_doc = next(d for d in docs if d["document_type"] == "GST")
    gst_doc_id = gst_doc["id"]

    # 9. Run OCR
    ocr_res = client.post(f"/api/v1/documents/{gst_doc_id}/ocr", headers=headers)
    assert ocr_res.status_code == 200, "Step 9: OCR failed"
    ocr_data = ocr_res.json()

    # 10. View extracted GSTIN
    assert "fields" in ocr_data
    assert "identifier" in ocr_data["fields"], "Step 10: GSTIN must be extracted"
    extracted_gstin = ocr_data["fields"]["identifier"]
    assert extracted_gstin == "27AAACA1234A1Z5"

    # 11. Run verification
    verif_res = client.post(f"/api/v1/documents/{gst_doc_id}/verify", headers=headers)
    assert verif_res.status_code == 200, "Step 11: Verification failed"

    # 12. View verification result
    verif_data = verif_res.json()
    assert verif_data["status"] == "VERIFIED", "Step 12: Status must be VERIFIED for Alpha Tech"

    # 13. Run compliance analysis
    comp_run = client.post(f"/api/v1/tenders/{tender_id}/bidders/{bidder_id}/analyze", headers=headers)
    assert comp_run.status_code == 200, "Step 13: Analysis failed"

    # 14. View compliance result
    comp_data = comp_run.json()["compliance"]
    assert comp_data["compliance_score"] >= 80.0, "Step 14: Compliance score must be high for Alpha Tech"
    assert comp_data["compliance_status"] in ["VERIFIED", "NON_COMPLIANT", "REVIEW_REQUIRED"]

    # 15. View risk
    risk_data = comp_run.json()["risk"]
    assert risk_data["overall_category"] == "LOW", "Step 15: Risk should be LOW"
    assert "DOCUMENT_INTEGRITY" in risk_data["dimensions"]
    assert "findings" in comp_run.json()["consistency"]
    assert all("fraud" not in f.get("explanation", "").casefold() for f in comp_run.json()["consistency"]["findings"])

    # 16. Open evidence
    ev_res = client.get(f"/api/v1/bidders/{bidder_id}/evidence")
    assert ev_res.status_code == 200
    ev_list = ev_res.json()
    assert len(ev_list) >= 1, "Step 16: Evidence records must exist"

    # 17. Review evidence
    first_ev = ev_list[0]
    assert "source_reference" in first_ev, "Step 17: Evidence must have source reference"

    # 18. Generate detailed PDF report
    rep_res = client.post(
        "/api/v1/reports/detailed-assessment",
        json={"tender_id": tender_id, "bidder_id": bidder_id},
        headers=headers
    )
    assert rep_res.status_code == 200, "Step 18: Report generation failed"
    rep_data = rep_res.json()
    assert rep_data["report_type"] == "DETAILED_ASSESSMENT"

    # Verify report download
    pdf_res = client.get(f"/api/v1/reports/{rep_data['report_uid']}/download")
    assert pdf_res.status_code == 200
    assert pdf_res.content.startswith(b"%PDF")

    # 19. View audit event
    audit_res = client.get("/api/v1/audit?limit=10")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert any("REPORT_GENERATED" in l["action"] for l in logs), "Step 19: Audit log must record generation"

def test_demonstration_scenarios():
    # Scenario 2: Bharat Systems GSTIN Mismatch
    b_res = client.get("/api/v1/bidders").json()
    bharat = next(b for b in b_res if "Bharat" in b["legal_name"])
    bharat_docs = client.get(f"/api/v1/documents?bidder_id={bharat['id']}&document_type=GST").json()
    assert len(bharat_docs) >= 1
    bharat_verif = client.get(f"/api/v1/documents/{bharat_docs[0]['id']}").json()["verification"]
    assert bharat_verif["status"] == "MISMATCH", "Scenario 2: Bharat Systems must have MISMATCH status"

    # Scenario 4: Delta Digital Low-Quality Scan (MANUAL_REVIEW)
    delta = next(b for b in b_res if "Delta" in b["legal_name"])
    delta_docs = client.get(f"/api/v1/documents?bidder_id={delta['id']}&document_type=GST").json()
    delta_verif = client.get(f"/api/v1/documents/{delta_docs[0]['id']}").json()["verification"]
    assert delta_verif["status"] == "MANUAL_REVIEW", "Scenario 4: Delta Digital must have MANUAL_REVIEW status"

    # Scenario 5 & 7: Gamma Infotech Expired v1 and Corrected v2
    gamma = next(b for b in b_res if "Gamma" in b["legal_name"])
    gamma_udyam_docs = client.get(f"/api/v1/documents?bidder_id={gamma['id']}&document_type=UDYAM").json()
    assert len(gamma_udyam_docs) >= 2, "Scenario 7: Gamma Infotech must have both v1 and v2"
    v1_doc = next(d for d in gamma_udyam_docs if d["version"] == 1)
    v2_doc = next(d for d in gamma_udyam_docs if d["version"] == 2)
    assert v1_doc["is_active"] == False, "v1 must be superseded"
    assert v2_doc["is_active"] == True, "v2 must be active"

    v1_verif = client.get(f"/api/v1/documents/{v1_doc['id']}").json()["verification"]
    v2_verif = client.get(f"/api/v1/documents/{v2_doc['id']}").json()["verification"]
    assert v1_verif["status"] == "EXPIRED", "v1 must be EXPIRED"
    assert v2_verif["status"] == "VERIFIED", "v2 must be VERIFIED"

    # Scenario 6: Epsilon Engineering Provider Retry Required
    epsilon = next(b for b in b_res if "Epsilon" in b["legal_name"])
    eps_docs = client.get(f"/api/v1/documents?bidder_id={epsilon['id']}&document_type=GST").json()
    eps_verif = client.get(f"/api/v1/documents/{eps_docs[0]['id']}").json()["verification"]
    assert eps_verif["status"] == "RETRY_REQUIRED", "Scenario 6: Epsilon must be RETRY_REQUIRED"

    # Scenario 3: Zeta Innovations Missing Mandatory OEM Document
    zeta = next(b for b in b_res if "Zeta" in b["legal_name"])
    zeta_tb = client.get(f"/api/v1/bidders/{zeta['id']}?tender=1").json()
    oem_eval = next((r for r in zeta_tb["compliance_summary"]["results"] if "OEM" in r["code"]), None)
    assert oem_eval is not None
    assert oem_eval["status"] == "MISSING", "Scenario 3: Zeta must have MISSING OEM condition"

    # Dynamic Heavy Electricals: Insufficient Data != Low Risk
    dynamic = next(b for b in b_res if "Dynamic" in b["legal_name"])
    dyn_risk = client.get("/api/v1/bidders/{}/risk?tender=1".format(dynamic["id"])).json()
    assert dyn_risk["overall_category"] == "INSUFFICIENT_EVIDENCE", "Zero historical contracts must trigger INSUFFICIENT_EVIDENCE"
