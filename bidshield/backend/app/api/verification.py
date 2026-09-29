from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import Bidder, BidderDocument, OCRResult, VerificationResult, ProviderConfig
from app.schemas.schemas import ProviderConfigOut
from app.core.security import get_current_user, AuthenticatedUser
from app.services.verification_service import run_verification_for_document
from app.services.audit_service import log_audit_event
from app.services.tenant_service import get_tenant_document

router = APIRouter(prefix="/verification", tags=["Verification Control Center"])

@router.get("")
def list_verification_records(
    status: Optional[str] = None,
    document_type: Optional[str] = None,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    query = (db.query(BidderDocument).join(Bidder, Bidder.id == BidderDocument.bidder_id)
             .filter(Bidder.tenant_id == user.tenant_id, BidderDocument.is_active.is_(True)))
    if document_type:
        query = query.filter(BidderDocument.document_type == document_type.upper())

    docs = query.order_by(BidderDocument.id.desc()).all()
    results = []

    for d in docs:
        ocr = db.query(OCRResult).filter(OCRResult.document_id == d.id).first()
        verif = db.query(VerificationResult).filter(VerificationResult.document_id == d.id).first()

        v_status = verif.status if verif else "PENDING"
        if status and status.upper() != "ALL" and v_status != status.upper():
            continue

        results.append({
            "document_id": d.id,
            "bidder_id": d.bidder_id,
            "bidder_name": d.bidder.legal_name if d.bidder else "Unknown",
            "document_type": d.document_type,
            "filename": d.filename,
            "version": d.version,
            "file_hash": d.file_hash,
            "ocr_status": "COMPLETED" if ocr else "PENDING",
            "ocr_confidence": ocr.confidence if ocr else 0.0,
            "ocr_engine": ocr.engine if ocr else "N/A",
            "verification_provider": verif.provider_name if verif else "DemoProvider",
            "verification_status": v_status,
            "discrepancy_notes": verif.discrepancy_notes if verif else None,
            "retry_count": verif.retry_count if verif else 0,
            "last_verified_at": verif.verified_at if verif else None
        })

    return results

@router.post("/{document_id}/retry")
def retry_verification(
    document_id: int,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user)
):
    get_tenant_document(db, document_id, user.tenant_id)
    res = run_verification_for_document(db, document_id, user.id, user.username)
    log_audit_event(
        db,
        action="VERIFICATION_RETRIED",
        entity_type="DOCUMENT",
        entity_id=str(document_id),
        user_id=user.id,
        username=user.username,
        details={"status": res.status, "provider": res.provider_name}
    )
    return {
        "message": f"Verification re-evaluated: {res.status}",
        "status": res.status,
        "discrepancy_notes": res.discrepancy_notes,
        "provider": res.provider_name
    }

@router.get("/providers", response_model=List[ProviderConfigOut])
def list_providers(db: Session = Depends(get_db)):
    providers = db.query(ProviderConfig).all()
    if not providers:
        # Seed default demo provider configs
        default_providers = [
            ("DEMO_GSTN", "Synthetic local GST comparison (no live API)", "GST", "NONE", "https://not-configured.invalid/gst"),
            ("DEMO_NSDL", "Synthetic local PAN comparison (no live API)", "PAN", "NONE", "https://not-configured.invalid/pan"),
            ("DEMO_MSME", "Synthetic local Udyam comparison (no live API)", "UDYAM", "NONE", "https://not-configured.invalid/udyam"),
            ("DEMO_OEM", "Synthetic local OEM comparison (no live API)", "OEM", "NONE", "https://not-configured.invalid/oem"),
            ("DEMO_ICAI", "Synthetic local turnover comparison (no live API)", "TURNOVER", "NONE", "https://not-configured.invalid/turnover"),
            ("DEMO_PROC", "Synthetic local experience comparison (no live API)", "EXPERIENCE", "NONE", "https://not-configured.invalid/experience"),
        ]
        for code, name, doc_type, auth_type, ep in default_providers:
            p = ProviderConfig(
                provider_code=code,
                provider_name=name,
                document_type=doc_type,
                auth_type=auth_type,
                api_endpoint=ep,
                is_active=True,
                timeout_seconds=10
            )
            db.add(p)
        db.commit()
        providers = db.query(ProviderConfig).all()
    return providers
