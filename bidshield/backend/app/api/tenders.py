from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.session import get_db
from app.models.entities import Tender, TenderRequirement, TenderBidder, Bidder, ComplianceResult, EvidenceRecord
from app.schemas.schemas import (
    TenderOut, TenderDetailOut, TenderCreate, TenderRequirementOut,
    RequirementCreate, RequirementUpdate, OfficerDecisionRequest
)
from app.core.security import get_current_user, require_roles, AuthenticatedUser
from app.services.tender_service import process_tender_requirements
from app.services.ocr_service import run_ocr_for_document
from app.services.verification_service import run_verification_for_document
from app.services.compliance_service import evaluate_compliance
from app.services.risk_service import calculate_bidder_risk
from app.services.audit_service import log_audit_event
from app.services.consistency_service import check_bidder_consistency
from app.services.tenant_service import get_tenant_tender, get_tenant_bidder
from app.adapters.ocr.base import TesseractOCRAdapter
import hashlib
import os
from app.core.config import settings

router = APIRouter(prefix="/tenders", tags=["Tenders"])

@router.get("", response_model=List[TenderOut])
def list_tenders(db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    tenders = db.query(Tender).filter(Tender.tenant_id == user.tenant_id).order_by(Tender.id.asc()).all()
    out = []
    for t in tenders:
        reqs = db.query(TenderRequirement).filter(TenderRequirement.tender_id == t.id).all()
        bidder_count = (db.query(TenderBidder).join(Bidder, Bidder.id == TenderBidder.bidder_id)
                        .filter(TenderBidder.tender_id == t.id, Bidder.tenant_id == user.tenant_id).count())
        out.append({
            "id": t.id,
            "tender_ref": t.tender_ref,
            "gem_ref": t.gem_ref,
            "title": t.title,
            "department": t.department,
            "category": t.category,
            "description": t.description,
            "estimated_value_cr": t.estimated_value_cr,
            "issue_date": t.issue_date,
            "closing_date": t.closing_date,
            "status": t.status,
            "pdf_filename": t.pdf_filename,
            "created_at": t.created_at,
            "requirements": reqs,
            "bidders_count": bidder_count
        })
    return out

@router.post("", response_model=TenderOut)
def create_tender(
    payload: TenderCreate,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER", "SYSTEM_ADMIN"))
):
    existing = db.query(Tender).filter(Tender.tenant_id == user.tenant_id, Tender.tender_ref == payload.tender_ref).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tender reference already exists")

    t = Tender(
        tenant_id=user.tenant_id,
        tender_ref=payload.tender_ref,
        gem_ref=payload.gem_ref,
        title=payload.title,
        department=payload.department,
        category=payload.category,
        description=payload.description,
        estimated_value_cr=payload.estimated_value_cr,
        issue_date=payload.issue_date,
        closing_date=payload.closing_date,
        status="ACTIVE",
        created_by_id=user.id
    )
    db.add(t)
    db.commit()
    db.refresh(t)

    # Automatically extract initial requirements
    process_tender_requirements(db, t.id, user.id, user.username)

    log_audit_event(
        db,
        action="TENDER_CREATED",
        entity_type="TENDER",
        entity_id=str(t.id),
        user_id=user.id,
        username=user.username,
        details={"tender_ref": t.tender_ref, "title": t.title}
    )

    reqs = db.query(TenderRequirement).filter(TenderRequirement.tender_id == t.id).all()
    return {
        "id": t.id,
        "tender_ref": t.tender_ref,
        "gem_ref": t.gem_ref,
        "title": t.title,
        "department": t.department,
        "category": t.category,
        "description": t.description,
        "estimated_value_cr": t.estimated_value_cr,
        "issue_date": t.issue_date,
        "closing_date": t.closing_date,
        "status": t.status,
        "pdf_filename": t.pdf_filename,
        "created_at": t.created_at,
        "requirements": reqs,
        "bidders_count": 0
    }

@router.get("/{id}", response_model=TenderDetailOut)
def get_tender(id: int, db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    t = get_tenant_tender(db, id, user.tenant_id)

    reqs = db.query(TenderRequirement).filter(TenderRequirement.tender_id == t.id).order_by(TenderRequirement.id.asc()).all()
    tbs = (db.query(TenderBidder).join(Bidder, Bidder.id == TenderBidder.bidder_id)
           .filter(TenderBidder.tender_id == t.id, Bidder.tenant_id == user.tenant_id).all())

    bidders_list = []
    for tb in tbs:
        b = tb.bidder
        bidders_list.append({
            "id": b.id,
            "legal_name": b.legal_name,
            "trade_name": b.trade_name,
            "pan": b.pan,
            "gstin": b.gstin,
            "enterprise_type": b.enterprise_type,
            "is_startup": b.is_startup,
            "state": b.state,
            "compliance_status": tb.compliance_status,
            "compliance_score": tb.compliance_score,
            "risk_level": tb.risk_level,
            "final_decision": tb.final_decision,
            "decision_notes": tb.decision_notes
        })

    return {
        "id": t.id,
        "tender_ref": t.tender_ref,
        "gem_ref": t.gem_ref,
        "title": t.title,
        "department": t.department,
        "category": t.category,
        "description": t.description,
        "estimated_value_cr": t.estimated_value_cr,
        "issue_date": t.issue_date,
        "closing_date": t.closing_date,
        "status": t.status,
        "pdf_filename": t.pdf_filename,
        "created_at": t.created_at,
        "requirements": reqs,
        "bidders_count": len(bidders_list),
        "bidders": bidders_list
    }

@router.post("/{id}/extract-requirements")
def trigger_requirement_extraction(
    id: int,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER", "SYSTEM_ADMIN"))
):
    tender = get_tenant_tender(db, id, user.tenant_id)
    if tender.pdf_bytes:
        # Prefer a PDF's embedded text layer; OCR is the fallback for scans.
        # This keeps printed text accurate and avoids turning clear numerals
        # into ambiguous OCR characters before requirement parsing.
        import pymupdf
        with pymupdf.open(stream=tender.pdf_bytes, filetype="pdf") as pdf:
            embedded_text = "\n".join(page.get_text() for page in pdf)
        result = ({"text": embedded_text, "confidence": 1.0}
                  if embedded_text.strip() else
                  TesseractOCRAdapter().extract(tender.pdf_bytes, "TENDER", "application/pdf"))
        if result["confidence"] < 0.60 or not result["text"].strip():
            return {"message": "Tender PDF needs manual review; no requirements were promoted or inferred from unreadable content.",
                    "status": "MANUAL_REVIEW", "ocr_confidence": result["confidence"], "requirements":
                    db.query(TenderRequirement).filter(TenderRequirement.tender_id == id).all()}
        reqs = process_tender_requirements(db, id, user.id, user.username, source_text=result["text"])
    else:
        reqs = process_tender_requirements(db, id, user.id, user.username)
    return {"message": "Requirements extracted successfully", "requirements": reqs}

@router.post("/{id}/pdf")
async def upload_tender_pdf(
    id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER", "SUPER_ADMIN")),
):
    tender = get_tenant_tender(db, id, user.tenant_id)
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds the {settings.max_upload_mb} MB upload limit")
    if file.content_type != "application/pdf" or not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="Only PDF tender documents are accepted")
    try:
        import pymupdf
        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            if not pdf.page_count:
                raise ValueError("empty PDF")
    except Exception:
        raise HTTPException(status_code=400, detail="Tender PDF is unreadable")
    tender.pdf_bytes = content
    tender.pdf_filename = os.path.basename(file.filename or f"tender-{id}.pdf")[:200]
    tender.updated_at = datetime.now(timezone.utc)
    db.commit()
    result = TesseractOCRAdapter().extract(content, "TENDER", "application/pdf")
    log_audit_event(db, action="TENDER_PDF_UPLOADED", entity_type="TENDER", entity_id=str(id),
                    user_id=user.id, username=user.username, details={"sha256": hashlib.sha256(content).hexdigest(),
                    "ocr_confidence": result["confidence"]})
    return {"tender_id": id, "filename": tender.pdf_filename,
            "sha256": hashlib.sha256(content).hexdigest(), "ocr_confidence": result["confidence"],
            "extraction_status": "READY" if result["confidence"] >= 0.60 else "MANUAL_REVIEW"}

@router.post("/{id}/requirements", response_model=TenderRequirementOut)
def add_requirement(
    id: int,
    payload: RequirementCreate,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER", "SYSTEM_ADMIN"))
):
    get_tenant_tender(db, id, user.tenant_id)
    existing = db.query(TenderRequirement).filter(
        TenderRequirement.tender_id == id,
        TenderRequirement.code == payload.code
    ).first()
    if existing:
        return existing

    req = TenderRequirement(
        tender_id=id,
        code=payload.code,
        name=payload.name,
        requirement_type=payload.requirement_type,
        description=payload.description,
        structured_rule=payload.structured_rule,
        approval_status="APPROVED",
        approving_officer_id=user.id,
        approved_at=datetime.now(timezone.utc),
        officer_notes="Manually created and approved by Procurement Officer."
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    log_audit_event(
        db,
        action="REQUIREMENT_CREATED",
        entity_type="TENDER_REQUIREMENT",
        entity_id=str(req.id),
        user_id=user.id,
        username=user.username,
        details={"code": req.code, "name": req.name}
    )
    return req

@router.put("/{id}/requirements/{req_id}", response_model=TenderRequirementOut)
def update_requirement(
    id: int,
    req_id: int,
    payload: RequirementUpdate,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER", "SYSTEM_ADMIN"))
):
    get_tenant_tender(db, id, user.tenant_id)
    req = db.query(TenderRequirement).filter(
        TenderRequirement.id == req_id,
        TenderRequirement.tender_id == id
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")

    if payload.code is not None: req.code = payload.code
    if payload.name is not None: req.name = payload.name
    if payload.requirement_type is not None: req.requirement_type = payload.requirement_type
    if payload.description is not None: req.description = payload.description
    if payload.structured_rule is not None: req.structured_rule = payload.structured_rule
    if payload.approval_status is not None:
        req.approval_status = payload.approval_status
        req.approving_officer_id = user.id
        req.approved_at = datetime.now(timezone.utc)
    if payload.officer_notes is not None: req.officer_notes = payload.officer_notes

    db.commit()
    db.refresh(req)

    log_audit_event(
        db,
        action="REQUIREMENT_MODIFIED",
        entity_type="TENDER_REQUIREMENT",
        entity_id=str(req.id),
        user_id=user.id,
        username=user.username,
        details={"code": req.code, "status": req.approval_status}
    )
    return req

@router.post("/{id}/requirements/{req_id}/approve", response_model=TenderRequirementOut)
def approve_requirement(
    id: int,
    req_id: int,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER", "SYSTEM_ADMIN"))
):
    get_tenant_tender(db, id, user.tenant_id)
    req = db.query(TenderRequirement).filter(
        TenderRequirement.id == req_id,
        TenderRequirement.tender_id == id
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")

    req.approval_status = "APPROVED"
    req.approving_officer_id = user.id
    req.approved_at = datetime.now(timezone.utc)
    req.officer_notes = f"Formally verified and approved by {user.full_name} ({user.role})."
    db.commit()

    log_audit_event(
        db,
        action="REQUIREMENT_APPROVED",
        entity_type="TENDER_REQUIREMENT",
        entity_id=str(req.id),
        user_id=user.id,
        username=user.username,
        details={"code": req.code}
    )
    return req

@router.post("/{id}/requirements/{req_id}/reject", response_model=TenderRequirementOut)
def reject_requirement(
    id: int,
    req_id: int,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER", "SYSTEM_ADMIN"))
):
    get_tenant_tender(db, id, user.tenant_id)
    req = db.query(TenderRequirement).filter(
        TenderRequirement.id == req_id,
        TenderRequirement.tender_id == id
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")

    req.approval_status = "REJECTED"
    req.approving_officer_id = user.id
    req.approved_at = datetime.now(timezone.utc)
    req.officer_notes = f"Rejected / excluded by {user.full_name} ({user.role})."
    db.commit()

    log_audit_event(
        db,
        action="REQUIREMENT_REJECTED",
        entity_type="TENDER_REQUIREMENT",
        entity_id=str(req.id),
        user_id=user.id,
        username=user.username,
        details={"code": req.code}
    )
    return req

@router.post("/{id}/bidders/{bidder_id}/analyze")
def analyze_bidder(
    id: int,
    bidder_id: int,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER", "SYSTEM_ADMIN"))
):
    get_tenant_tender(db, id, user.tenant_id)
    get_tenant_bidder(db, bidder_id, user.tenant_id)
    tb = db.query(TenderBidder).filter(
        TenderBidder.tender_id == id,
        TenderBidder.bidder_id == bidder_id
    ).first()
    if not tb:
        raise HTTPException(status_code=404, detail="Bidder is not associated with this tender")

    # Step 1: Run OCR on all active documents
    from app.models.entities import BidderDocument
    docs = db.query(BidderDocument).filter(
        BidderDocument.bidder_id == bidder_id,
        BidderDocument.is_active.is_(True),
        or_(BidderDocument.tender_id == id, BidderDocument.tender_id.is_(None)),
    ).all()

    for d in docs:
        run_ocr_for_document(db, d.id, user.id, user.username)

    # Step 2: Run Verification for all active documents
    for d in docs:
        run_verification_for_document(db, d.id, user.id, user.username)

    # Step 3: Compare OCR-backed claims across active bidder documents and profile.
    consistency = check_bidder_consistency(db, bidder_id, id)

    # Step 4: Run deterministic tender-specific compliance evaluation.
    comp = evaluate_compliance(db, id, bidder_id)

    # Step 5: Run the explainable risk engine.
    risk = calculate_bidder_risk(db, id, bidder_id)

    log_audit_event(
        db,
        action="ANALYSIS_RUN",
        entity_type="TENDER_BIDDER",
        entity_id=f"{id}:{bidder_id}",
        user_id=user.id,
        username=user.username,
        details={
            "compliance_score": comp["compliance_score"],
            "risk_category": risk["overall_category"],
            "risk_score": risk["overall_score"]
        }
    )

    return {
        "tender_id": id,
        "bidder_id": bidder_id,
        "compliance": comp,
        "risk": risk,
        "consistency": consistency,
    }

@router.post("/{id}/bidders/{bidder_id}/decision")
def record_officer_decision(
    id: int,
    bidder_id: int,
    payload: OfficerDecisionRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER", "SYSTEM_ADMIN"))
):
    get_tenant_tender(db, id, user.tenant_id)
    get_tenant_bidder(db, bidder_id, user.tenant_id)
    tb = db.query(TenderBidder).filter(
        TenderBidder.tender_id == id,
        TenderBidder.bidder_id == bidder_id
    ).first()
    if not tb:
        raise HTTPException(status_code=404, detail="Tender-bidder record not found")

    # Findings inform the authorized officer; they never make or block a procurement decision.
    tb.final_decision = payload.decision
    tb.decision_notes = payload.decision_notes
    tb.decided_by_id = user.id
    tb.decided_at = datetime.now(timezone.utc)
    db.commit()

    # Append an audit record for the formal officer decision.
    log_audit_event(
        db,
        action=f"OFFICER_DECISION_{payload.decision}",
        entity_type="TENDER_BIDDER",
        entity_id=f"{id}:{bidder_id}",
        user_id=user.id,
        username=user.username,
        details={
            "decision": payload.decision,
            "decision_notes": payload.decision_notes,
            "compliance_status": tb.compliance_status,
            "risk_level": tb.risk_level
        }
    )

    return {
        "message": f"Procurement Officer decision recorded: {payload.decision}",
        "decision": tb.final_decision,
        "decision_notes": tb.decision_notes,
        "decided_at": tb.decided_at
    }

@router.get("/{id}/compliance-matrix")
def get_compliance_matrix(id: int, db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    tender = get_tenant_tender(db, id, user.tenant_id)

    reqs = db.query(TenderRequirement).filter(TenderRequirement.tender_id == id).all()
    tbs = (db.query(TenderBidder).join(Bidder, Bidder.id == TenderBidder.bidder_id)
           .filter(TenderBidder.tender_id == id, Bidder.tenant_id == user.tenant_id).all())

    matrix = []
    for tb in tbs:
        b = tb.bidder
        evals = db.query(ComplianceResult).filter(ComplianceResult.tender_bidder_id == tb.id).all()
        eval_map = {e.rule_code: {"status": e.status, "explanation": e.explanation} for e in evals}
        matrix.append({
            "bidder_id": b.id,
            "legal_name": b.legal_name,
            "compliance_score": tb.compliance_score,
            "compliance_status": tb.compliance_status,
            "risk_level": tb.risk_level,
            "final_decision": tb.final_decision,
            "evaluations": eval_map
        })

    return {
        "tender_id": id,
        "requirements": [{"code": r.code, "name": r.name, "type": r.requirement_type} for r in reqs],
        "matrix": matrix
    }

@router.get("/{id}/evidence")
def get_tender_evidence(id: int, db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    get_tenant_tender(db, id, user.tenant_id)
    evs = (db.query(EvidenceRecord).join(Bidder, Bidder.id == EvidenceRecord.bidder_id)
           .filter(EvidenceRecord.tender_id == id, Bidder.tenant_id == user.tenant_id)
           .order_by(EvidenceRecord.id.desc()).all())
    return evs
