from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import (
    Bidder, BidderDocument, HistoricalContract, QualityInspectionRecord,
    OCRResult, VerificationResult, ComplianceResult, RiskAssessment,
    EvidenceRecord, AuditLog, TenderBidder
)
from app.schemas.schemas import BidderOut, BidderDetailOut, BidderCreate
from app.services.performance_service import get_bidder_performance_analysis
from app.services.risk_service import calculate_bidder_risk
from app.core.security import get_current_user, require_roles, AuthenticatedUser
from app.services.tenant_service import get_tenant_bidder, get_tenant_tender
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/bidders", tags=["Bidders"])

@router.post("", response_model=BidderDetailOut, status_code=201)
def create_bidder_with_submission(
    payload: BidderCreate,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER")),
):
    """Register a bidder and attach it to a tender as a pending submission.

    This is the Procurement Officer's bid-intake entry point: it creates the
    bidder shell (identifiers filled from documents later during OCR review)
    and enrolls it against the tender so documents can be uploaded in bulk.
    """
    get_tenant_tender(db, payload.tender_id, user.tenant_id)

    existing = db.query(Bidder).filter(
        Bidder.tenant_id == user.tenant_id,
        Bidder.legal_name == payload.legal_name.strip(),
    ).first()
    if existing:
        tb = db.query(TenderBidder).filter(
            TenderBidder.tender_id == payload.tender_id,
            TenderBidder.bidder_id == existing.id,
        ).first()
        if tb:
            raise HTTPException(status_code=409, detail="Bidder is already enrolled against this tender")
        tb = TenderBidder(tender_id=payload.tender_id, bidder_id=existing.id, final_decision="PENDING")
        db.add(tb)
        db.commit()
        log_audit_event(db, action="BIDDER_ENROLLED", entity_type="TENDER_BIDDER",
                        entity_id=f"{payload.tender_id}:{existing.id}", user_id=user.id,
                        username=user.username, details={"bidder_id": existing.id, "existing": True})
        return _bidder_detail(db, existing.id, payload.tender_id)

    bidder = Bidder(
        tenant_id=user.tenant_id,
        legal_name=payload.legal_name.strip(),
        trade_name=(payload.trade_name or payload.legal_name).strip(),
        pan=payload.pan or "PENDING",
        gstin=payload.gstin or "PENDING",
        cin=payload.cin,
        udyam_number=payload.udyam_number,
        enterprise_type=payload.enterprise_type or "Unknown",
        is_startup=payload.is_startup or False,
        address=payload.address or "To be captured from submitted documents",
        state=payload.state or "Unknown",
        district=payload.district or "Unknown",
        contact_email=payload.contact_email or "pending@bidshield.local",
        contact_phone=payload.contact_phone or "Pending",
        contact_person=payload.contact_person or "Pending",
    )
    db.add(bidder)
    db.flush()

    tb = TenderBidder(
        tender_id=payload.tender_id,
        bidder_id=bidder.id,
        submission_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        final_decision="PENDING",
    )
    db.add(tb)
    db.commit()

    log_audit_event(db, action="BIDDER_CREATED", entity_type="BIDDER", entity_id=str(bidder.id),
                    user_id=user.id, username=user.username,
                    details={"legal_name": bidder.legal_name, "tender_id": payload.tender_id})

    return _bidder_detail(db, bidder.id, payload.tender_id)


def _bidder_detail(db: Session, bidder_id: int, tender_id: Optional[int]) -> Dict[str, Any]:
    """Shared 360° payload builder for create + read paths."""
    b = db.query(Bidder).filter(Bidder.id == bidder_id).first()
    docs = db.query(BidderDocument).filter(BidderDocument.bidder_id == bidder_id).order_by(BidderDocument.id.desc()).all()
    contracts = db.query(HistoricalContract).filter(HistoricalContract.bidder_id == bidder_id).all()

    doc_out = []
    for d in docs:
        ocr = db.query(OCRResult).filter(OCRResult.document_id == d.id).first()
        verif = db.query(VerificationResult).filter(VerificationResult.document_id == d.id).first()
        doc_out.append({
            "id": d.id, "bidder_id": d.bidder_id, "tender_id": d.tender_id,
            "document_type": d.document_type, "filename": d.filename, "mime_type": d.mime_type,
            "file_hash": d.file_hash, "file_size_bytes": d.file_size_bytes, "version": d.version,
            "is_active": d.is_active, "previous_version_id": d.previous_version_id,
            "is_synthetic": d.is_synthetic, "created_at": d.created_at,
            "ocr_confidence": ocr.confidence if ocr else None,
            "verification_status": verif.status if verif else "PENDING",
            "verification_notes": verif.discrepancy_notes if verif else None,
        })

    tb = None
    if tender_id:
        tb = db.query(TenderBidder).filter(TenderBidder.tender_id == tender_id, TenderBidder.bidder_id == bidder_id).first()
    else:
        tb = db.query(TenderBidder).filter(TenderBidder.bidder_id == bidder_id).first()

    comp_summary = None
    risk_summary = None
    if tb:
        comp_results = db.query(ComplianceResult).filter(ComplianceResult.tender_bidder_id == tb.id).all()
        comp_summary = {
            "status": tb.compliance_status, "score": tb.compliance_score,
            "results": [
                {"code": c.rule_code, "name": c.rule_name, "status": c.status, "explanation": c.explanation}
                for c in comp_results
            ],
        }
        ra = db.query(RiskAssessment).filter(RiskAssessment.tender_bidder_id == tb.id).first()
        if ra:
            risk_summary = {
                "overall_category": ra.overall_category, "overall_score": ra.overall_score,
                "data_sufficiency": ra.data_sufficiency, "explanation": ra.explanation,
                "dimensions": ra.dimensions, "contributing_factors": ra.contributing_factors,
            }

    ev_count = db.query(EvidenceRecord).filter(EvidenceRecord.bidder_id == bidder_id).count()

    return {
        "id": b.id, "legal_name": b.legal_name, "trade_name": b.trade_name,
        "pan": b.pan, "gstin": b.gstin, "cin": b.cin, "udyam_number": b.udyam_number,
        "enterprise_type": b.enterprise_type, "is_startup": b.is_startup,
        "address": b.address, "state": b.state, "district": b.district,
        "contact_email": b.contact_email, "contact_phone": b.contact_phone,
        "contact_person": b.contact_person, "incorporation_date": b.incorporation_date,
        "created_at": b.created_at, "documents": doc_out, "contracts": contracts,
        "compliance_summary": comp_summary, "risk_summary": risk_summary,
        "evidence_count": ev_count,
    }


@router.get("", response_model=List[BidderOut])
def list_bidders(db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    return db.query(Bidder).filter(Bidder.tenant_id == user.tenant_id).order_by(Bidder.id.asc()).all()

@router.get("/{id}", response_model=BidderDetailOut)
def get_bidder_360(id: int, tender: Optional[int] = None, db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    b = get_tenant_bidder(db, id, user.tenant_id)
    if tender is not None:
        get_tenant_tender(db, tender, user.tenant_id)

    docs = db.query(BidderDocument).filter(BidderDocument.bidder_id == id).order_by(BidderDocument.id.desc()).all()
    contracts = db.query(HistoricalContract).filter(HistoricalContract.bidder_id == id).all()

    doc_out = []
    for d in docs:
        ocr = db.query(OCRResult).filter(OCRResult.document_id == d.id).first()
        verif = db.query(VerificationResult).filter(VerificationResult.document_id == d.id).first()
        doc_out.append({
            "id": d.id,
            "bidder_id": d.bidder_id,
            "tender_id": d.tender_id,
            "document_type": d.document_type,
            "filename": d.filename,
            "mime_type": d.mime_type,
            "file_hash": d.file_hash,
            "file_size_bytes": d.file_size_bytes,
            "version": d.version,
            "is_active": d.is_active,
            "previous_version_id": d.previous_version_id,
            "is_synthetic": d.is_synthetic,
            "created_at": d.created_at,
            "ocr_confidence": ocr.confidence if ocr else None,
            "verification_status": verif.status if verif else "PENDING",
            "verification_notes": verif.discrepancy_notes if verif else None
        })

    tb = None
    if tender:
        tb = db.query(TenderBidder).filter(TenderBidder.tender_id == tender, TenderBidder.bidder_id == id).first()
    else:
        tb = db.query(TenderBidder).filter(TenderBidder.bidder_id == id).first()

    comp_summary = None
    risk_summary = None

    if tb:
        comp_results = db.query(ComplianceResult).filter(ComplianceResult.tender_bidder_id == tb.id).all()
        comp_summary = {
            "status": tb.compliance_status,
            "score": tb.compliance_score,
            "results": [
                {"code": c.rule_code, "name": c.rule_name, "status": c.status, "explanation": c.explanation}
                for c in comp_results
            ]
        }
        ra = db.query(RiskAssessment).filter(RiskAssessment.tender_bidder_id == tb.id).first()
        if ra:
            risk_summary = {
                "overall_category": ra.overall_category,
                "overall_score": ra.overall_score,
                "data_sufficiency": ra.data_sufficiency,
                "explanation": ra.explanation,
                "dimensions": ra.dimensions,
                "contributing_factors": ra.contributing_factors
            }

    ev_count = db.query(EvidenceRecord).filter(EvidenceRecord.bidder_id == id).count()

    return {
        "id": b.id,
        "legal_name": b.legal_name,
        "trade_name": b.trade_name,
        "pan": b.pan,
        "gstin": b.gstin,
        "cin": b.cin,
        "udyam_number": b.udyam_number,
        "enterprise_type": b.enterprise_type,
        "is_startup": b.is_startup,
        "address": b.address,
        "state": b.state,
        "district": b.district,
        "contact_email": b.contact_email,
        "contact_phone": b.contact_phone,
        "contact_person": b.contact_person,
        "incorporation_date": b.incorporation_date,
        "created_at": b.created_at,
        "documents": doc_out,
        "contracts": contracts,
        "compliance_summary": comp_summary,
        "risk_summary": risk_summary,
        "evidence_count": ev_count
    }

@router.get("/{id}/performance")
def get_performance(id: int, tender: Optional[int] = None, db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    get_tenant_bidder(db, id, user.tenant_id)
    if tender is not None:
        get_tenant_tender(db, tender, user.tenant_id)
    return get_bidder_performance_analysis(db, id, tender)

@router.get("/{id}/risk")
def get_risk(id: int, tender: int, db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    get_tenant_bidder(db, id, user.tenant_id)
    get_tenant_tender(db, tender, user.tenant_id)
    return calculate_bidder_risk(db, tender, id)

@router.get("/{id}/evidence")
def get_evidence(id: int, db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    get_tenant_bidder(db, id, user.tenant_id)
    return db.query(EvidenceRecord).filter(EvidenceRecord.bidder_id == id).order_by(EvidenceRecord.id.desc()).all()

@router.get("/{id}/audit")
def get_bidder_audit(id: int, db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    get_tenant_bidder(db, id, user.tenant_id)
    all_logs = db.query(AuditLog).filter(AuditLog.tenant_id == user.tenant_id).order_by(AuditLog.id.desc()).limit(100).all()
    # Filter logs pertaining to this bidder
    matching = [
        l for l in all_logs
        if (l.entity_id == str(id)) or (l.details and (l.details.get("bidder_id") == id or str(id) in str(l.details)))
    ]
    return matching[:50]
