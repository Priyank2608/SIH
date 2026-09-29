from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.entities import (
    Tender, Bidder, TenderBidder, TenderRequirement,
    BidderDocument, VerificationResult, ComplianceResult, EvidenceRecord
)
from app.core.config import settings

def evaluate_compliance(db: Session, tender_id: int, bidder_id: int) -> Dict[str, Any]:
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    bidder = db.query(Bidder).filter(Bidder.id == bidder_id).first()
    tb = db.query(TenderBidder).filter(
        TenderBidder.tender_id == tender_id,
        TenderBidder.bidder_id == bidder_id
    ).first()

    if not tender or not bidder or not tb:
        raise ValueError("Tender, bidder, or tender-bidder association not found")

    # Clear previous compliance results
    db.query(ComplianceResult).filter(ComplianceResult.tender_bidder_id == tb.id).delete()

    requirements = db.query(TenderRequirement).filter(
        TenderRequirement.tender_id == tender_id,
        TenderRequirement.approval_status.in_(["APPROVED", "MODIFIED"])
    ).all()

    # Fetch active bidder documents
    active_docs = db.query(BidderDocument).filter(
        BidderDocument.bidder_id == bidder_id,
        BidderDocument.is_active.is_(True),
        or_(BidderDocument.tender_id == tender_id, BidderDocument.tender_id.is_(None)),
    ).all()
    doc_map = {d.document_type.upper(): d for d in active_docs}

    passed_count = 0
    failed_count = 0
    review_count = 0
    missing_count = 0
    expired_count = 0

    results = []

    for req in requirements:
        rule_code = req.code
        rule_name = req.name
        doc_type = req.structured_rule.get("doc_type", rule_code.split("-")[0]).upper()
        doc = doc_map.get(doc_type)

        ev_record = db.query(EvidenceRecord).filter(
            EvidenceRecord.bidder_id == bidder_id,
            EvidenceRecord.claim_type == f"{doc_type}_VERIFICATION"
        ).order_by(EvidenceRecord.id.desc()).first()

        status = "PASS"
        score = 1.0
        explanation = f"Requirement '{req.name}' satisfied."

        if not doc:
            status = "MISSING"
            score = 0.0
            explanation = f"Mandatory document for '{req.name}' ({doc_type}) was not submitted."
            missing_count += 1
        else:
            verif = db.query(VerificationResult).filter(
                VerificationResult.document_id == doc.id
            ).order_by(VerificationResult.id.desc()).first()

            if not verif or verif.status == "PENDING":
                status = "REVIEW"
                score = 0.5
                explanation = f"Document submitted, verification currently pending."
                review_count += 1
            elif verif.status == "VERIFIED":
                status = "PASS"
                score = 1.0
                explanation = f"Document verified active and authentic by {verif.provider_name}."
                passed_count += 1
            elif verif.status == "EXPIRED":
                status = "EXPIRED"
                score = 0.0
                explanation = f"Document expired: {verif.discrepancy_notes or 'Expired certificate.'}"
                expired_count += 1
            elif verif.status == "MISMATCH":
                status = "FAIL"
                score = 0.0
                explanation = f"Data mismatch detected: {verif.discrepancy_notes}"
                failed_count += 1
            elif verif.status in ["MANUAL_REVIEW", "RETRY_REQUIRED", "NOT_AVAILABLE", "PENDING", "ERROR"]:
                status = "REVIEW"
                score = 0.5
                explanation = f"Manual officer review indicated: {verif.discrepancy_notes}"
                review_count += 1
            else:
                status = "FAIL"
                score = 0.0
                explanation = f"Verification failed with status {verif.status}."
                failed_count += 1

        cr = ComplianceResult(
            tender_bidder_id=tb.id,
            requirement_id=req.id,
            rule_code=rule_code,
            rule_name=rule_name,
            status=status,
            score=score,
            explanation=explanation,
            evidence_ids=[ev_record.id] if ev_record else []
        )
        db.add(cr)
        results.append(cr)

    total_reqs = len(requirements) or 1
    total_score = (passed_count * 1.0 + review_count * 0.5) / total_reqs * 100.0
    overall_percentage = round(total_score, 1)

    if failed_count > 0 or missing_count > 0 or expired_count > 0:
        tb.compliance_status = "NON_COMPLIANT"
    elif review_count > 0:
        tb.compliance_status = "REVIEW_REQUIRED"
    else:
        tb.compliance_status = "VERIFIED"

    tb.compliance_score = overall_percentage
    db.commit()

    return {
        "tender_id": tender_id,
        "bidder_id": bidder_id,
        "compliance_score": overall_percentage,
        "compliance_status": tb.compliance_status,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "review_count": review_count,
        "missing_count": missing_count,
        "expired_count": expired_count,
        "total_requirements": len(requirements),
        "results": [
            {
                "rule_code": r.rule_code,
                "rule_name": r.rule_name,
                "status": r.status,
                "score": r.score,
                "explanation": r.explanation
            }
            for r in results
        ]
    }
