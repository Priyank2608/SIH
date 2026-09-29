"""Compare OCR-supported bidder claims without making fraud conclusions."""
from difflib import SequenceMatcher
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.entities import Bidder, BidderDocument, OCRResult, EvidenceRecord


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _compare(field: str, source: str, observed: Any, expected: Any) -> Dict[str, Any]:
    left, right = _normalize(observed), _normalize(expected)
    if not left:
        status = "MISSING_EVIDENCE"
    elif not right:
        status = "MANUAL_REVIEW"
    elif left == right:
        status = "MATCH"
    elif field in {"legal_name", "trade_name", "address"} and SequenceMatcher(None, left, right).ratio() >= 0.82:
        status = "PARTIAL_MATCH"
    else:
        status = "MISMATCH"
    return {"field": field, "source": source, "observed": observed, "bidder_profile": expected, "status": status}


def check_bidder_consistency(db: Session, bidder_id: int, tender_id: int | None = None) -> Dict[str, Any]:
    bidder = db.query(Bidder).filter(Bidder.id == bidder_id).first()
    if bidder is None:
        raise ValueError("Bidder not found")
    docs = db.query(BidderDocument).filter(
        BidderDocument.bidder_id == bidder_id,
        BidderDocument.is_active.is_(True),
        (BidderDocument.tender_id == tender_id) | (BidderDocument.tender_id.is_(None)) if tender_id else True,
    ).order_by(BidderDocument.id.asc()).all()

    findings: List[Dict[str, Any]] = []
    name_claims: List[tuple[str, Any]] = []
    profile_identifiers = {"PAN": bidder.pan, "GST": bidder.gstin, "UDYAM": bidder.udyam_number}
    for document in docs:
        result = db.query(OCRResult).filter(OCRResult.document_id == document.id).order_by(OCRResult.id.desc()).first()
        if result is None or result.confidence < 0.60:
            findings.append({
                "field": "document_fields", "source": f"{document.document_type} document {document.id}",
                "observed": None, "bidder_profile": None, "status": "MANUAL_REVIEW",
                "explanation": "OCR is missing or below the confidence threshold; values were not inferred.",
            })
            continue
        fields = result.fields or {}
        doc_type = document.document_type.upper()
        if doc_type in profile_identifiers:
            value = fields.get("identifier")
            if value:
                findings.append(_compare(doc_type, f"{doc_type} document {document.id}", value, profile_identifiers[doc_type]))
        name = fields.get("legal_name") or fields.get("company_name") or fields.get("trade_name")
        if name:
            name_claims.append((f"{document.document_type} document {document.id}", name))
            findings.append(_compare("legal_name", f"{document.document_type} document {document.id}", name, bidder.legal_name))

    for index, (left_source, left_name) in enumerate(name_claims):
        for right_source, right_name in name_claims[index + 1:]:
            findings.append(_compare("legal_name", f"{left_source} vs {right_source}", left_name, right_name))

    for finding in findings:
        if finding["status"] in {"MISMATCH", "PARTIAL_MATCH", "MANUAL_REVIEW", "MISSING_EVIDENCE"}:
            db.add(EvidenceRecord(
                tender_id=tender_id,
                bidder_id=bidder_id,
                claim_type="CROSS_DOCUMENT_CONSISTENCY",
                evidence_text=(f"{finding['field']} consistency finding: {finding['status']}. "
                               "This finding indicates a discrepancy or evidence gap and is not a fraud determination."),
                source_reference=finding["source"],
                confidence=0.65 if finding["status"] in {"MISMATCH", "PARTIAL_MATCH"} else 0.0,
            ))
    if findings:
        db.commit()
    return {"bidder_id": bidder_id, "tender_id": tender_id, "findings": findings,
            "status": "REVIEW_REQUIRED" if any(f["status"] in {"MISMATCH", "MANUAL_REVIEW", "MISSING_EVIDENCE"} for f in findings) else "CONSISTENT"}
