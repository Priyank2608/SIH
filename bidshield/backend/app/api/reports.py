from typing import List
import logging
from fastapi import APIRouter, Depends, HTTPException, Response, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import GeneratedReport, Tender, Bidder, TenderBidder, User
from app.schemas.schemas import GeneratedReportOut
from app.core.security import get_current_user, require_roles, AuthenticatedUser
from app.services.report_service import generate_quick_bidder_list_pdf, generate_detailed_bidder_assessment_pdf
from app.services.audit_service import log_audit_event
from app.services.tenant_service import get_tenant_tender, get_tenant_bidder

router = APIRouter(prefix="/reports", tags=["Reports"])
logger = logging.getLogger(__name__)

class QuickListRequest(BaseModel):
    tender_id: int

class DetailedAssessmentRequest(BaseModel):
    tender_id: int
    bidder_id: int

@router.get("", response_model=List[GeneratedReportOut])
def list_reports(db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    return (db.query(GeneratedReport).join(Tender, Tender.id == GeneratedReport.tender_id)
            .filter(Tender.tenant_id == user.tenant_id).order_by(GeneratedReport.id.desc()).all())

@router.post("/quick-list", response_model=GeneratedReportOut)
def create_quick_list_report(
    payload: QuickListRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER"))
):
    get_tenant_tender(db, payload.tender_id, user.tenant_id)
    officer = db.query(User).filter(User.id == user.id, User.tenant_id == user.tenant_id).first()
    if not officer or not officer.signature_data:
        raise HTTPException(status_code=409, detail="Officer signature is not configured")
    try:
        rep = generate_quick_bidder_list_pdf(db, payload.tender_id, user.id, user.username, officer.signature_data)
        return rep
    except Exception:
        logger.exception("Quick list report generation failed")
        raise HTTPException(status_code=500, detail="Failed to generate quick summary report")

@router.post("/detailed-assessment", response_model=GeneratedReportOut)
def create_detailed_assessment_report(
    payload: DetailedAssessmentRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER"))
):
    get_tenant_tender(db, payload.tender_id, user.tenant_id)
    get_tenant_bidder(db, payload.bidder_id, user.tenant_id)
    if not db.query(TenderBidder).filter(TenderBidder.tender_id == payload.tender_id, TenderBidder.bidder_id == payload.bidder_id).first():
        raise HTTPException(status_code=404, detail="Tender-bidder record not found")
    officer = db.query(User).filter(User.id == user.id, User.tenant_id == user.tenant_id).first()
    if not officer or not officer.signature_data:
        raise HTTPException(status_code=409, detail="Officer signature is not configured")
    try:
        rep = generate_detailed_bidder_assessment_pdf(db, payload.tender_id, payload.bidder_id, user.id, user.username, officer.signature_data)
        return rep
    except Exception:
        logger.exception("Detailed assessment report generation failed")
        raise HTTPException(status_code=500, detail="Failed to generate detailed assessment report")

@router.get("/{report_uid}/download")
def download_report(
    report_uid: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    rep = (db.query(GeneratedReport).join(Tender, Tender.id == GeneratedReport.tender_id)
           .filter(GeneratedReport.report_uid == report_uid, Tender.tenant_id == user.tenant_id).first())
    if not rep or not rep.file_bytes:
        raise HTTPException(status_code=404, detail="Report not found")

    rep.download_count += 1
    db.commit()

    log_audit_event(
        db,
        action="REPORT_DOWNLOADED",
        entity_type="REPORT",
        entity_id=rep.report_uid,
        user_id=user.id,
        username=user.username,
        tenant_id=user.tenant_id,
        details={"filename": rep.filename, "download_count": rep.download_count}
    )

    return Response(
        content=rep.file_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={rep.filename}",
            "X-Report-SHA256": rep.file_hash
        }
    )

@router.get("/{report_uid}/view")
def view_report(
    report_uid: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    rep = (db.query(GeneratedReport).join(Tender, Tender.id == GeneratedReport.tender_id)
           .filter(GeneratedReport.report_uid == report_uid, Tender.tenant_id == user.tenant_id).first())
    if not rep or not rep.file_bytes:
        raise HTTPException(status_code=404, detail="Report not found")
    log_audit_event(db, action="REPORT_VIEWED", entity_type="REPORT", entity_id=rep.report_uid,
                    user_id=user.id, username=user.username, tenant_id=user.tenant_id,
                    details={"filename": rep.filename})
    return Response(content=rep.file_bytes, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{rep.filename}"',
        "X-Report-SHA256": rep.file_hash,
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })
