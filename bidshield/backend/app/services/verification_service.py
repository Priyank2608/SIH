from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.entities import BidderDocument, OCRResult, VerificationResult, EvidenceRecord
from app.adapters.verification.base import provider_registry
from app.services.audit_service import log_audit_event
from app.core.config import settings

def run_verification_for_document(
    db: Session,
    document_id: int,
    user_id: int = 1,
    username: str = "officer"
) -> VerificationResult:
    doc = db.query(BidderDocument).filter(BidderDocument.id == document_id).first()
    if not doc:
        raise ValueError(f"Document with ID {document_id} not found")

    ocr = db.query(OCRResult).filter(OCRResult.document_id == doc.id).first()
    bidder = doc.bidder
    adapter = provider_registry.get_adapter(doc.document_type)

    # No live government registry adapters or credentials are configured in this
    # project. Outside demo mode, report the source as unavailable rather than
    # presenting a local comparison as an external verification.
    if settings.demo_mode:
        verif_data = adapter.verify(doc, ocr, bidder)
    else:
        verif_data = {
            "status": "NOT_AVAILABLE",
            "discrepancy_notes": "No authorized live registry integration is configured. Officer review is required.",
            "raw_response": {"provider": adapter.provider_name, "source_classification": "NOT_AVAILABLE"},
        }

    # Run ML Model for Fake / Dummy / Deformatted Document Evaluation
    from app.services.document_classifier_ml import ml_fraud_classifier
    declared_id = getattr(bidder, doc.document_type.lower(), None) if hasattr(bidder, doc.document_type.lower()) else None
    ml_eval = ml_fraud_classifier.evaluate_document(
        extracted_text=ocr.extracted_text if ocr else "",
        doc_type=doc.document_type,
        ocr_confidence=ocr.confidence if ocr else 0.5,
        declared_identifier=declared_id
    )

    raw_resp = verif_data.get("raw_response", {})
    raw_resp["document_screening"] = ml_eval
    raw_resp["source_classification"] = "SYNTHETIC_DEMO" if settings.demo_mode else "NOT_AVAILABLE"
    raw_resp["live_registry_call"] = False

    status = verif_data["status"]
    notes = verif_data.get("discrepancy_notes")

    # A heuristic screen can add context, but cannot declare fraud or determine
    # document authenticity. Low quality remains a manual review finding.
    if status == "VERIFIED" and ml_eval.get("classification") in {"UNUSUAL_PATTERN", "MANUAL_REVIEW", "MANUAL_SCRUTINY_RECOMMENDED"}:
        status = "MANUAL_REVIEW"
        notes = "Unusual document pattern detected by local screening. This is not a fraud determination; officer review is required."

    # Check for existing result
    existing = db.query(VerificationResult).filter(VerificationResult.document_id == doc.id).first()
    if existing:
        existing.provider_name = adapter.provider_name
        existing.status = status
        existing.raw_response = raw_resp
        existing.discrepancy_notes = notes
        existing.retry_count = existing.retry_count + 1
        res = existing
    else:
        res = VerificationResult(
            document_id=doc.id,
            provider_name=adapter.provider_name,
            status=status,
            raw_response=raw_resp,
            discrepancy_notes=notes,
            retry_count=0
        )
        db.add(res)

    db.commit()
    db.refresh(res)

    # Create / update Evidence Record
    evidence_text = f"Verification outcome: {res.status} via {res.provider_name}."
    if res.discrepancy_notes:
        evidence_text += f" Notes: {res.discrepancy_notes}"
    else:
        evidence_text += " No discrepancy was returned by the configured provider."
    if settings.demo_mode:
        evidence_text += " Result is from a synthetic local demo provider and is not a live government registry verification."

    ev = EvidenceRecord(
        tender_id=doc.tender_id,
        bidder_id=bidder.id,
        document_id=doc.id,
        ocr_result_id=ocr.id if ocr else None,
        verification_result_id=res.id,
        claim_type=f"{doc.document_type}_VERIFICATION",
        evidence_text=evidence_text,
        source_reference=f"Doc#{doc.id} ({doc.document_type} v{doc.version})",
        confidence=0.75 if res.status == "VERIFIED" and settings.demo_mode else (0.0 if res.status == "NOT_AVAILABLE" else 0.55)
    )
    db.add(ev)
    db.commit()

    log_audit_event(
        db,
        action="VERIFICATION_COMPLETED",
        entity_type="DOCUMENT",
        entity_id=str(doc.id),
        user_id=user_id,
        username=username,
        details={
            "document_type": doc.document_type,
            "provider": res.provider_name,
            "status": res.status,
            "has_discrepancy": bool(res.discrepancy_notes)
        }
    )

    return res
