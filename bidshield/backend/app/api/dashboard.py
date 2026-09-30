from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import (
    Tender, Bidder, TenderBidder, BidderDocument,
    VerificationResult, AuditLog, OCRResult, ComplianceResult
)
from app.schemas.schemas import DashboardMetricsOut
from app.core.security import get_current_user, AuthenticatedUser

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("", response_model=DashboardMetricsOut)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER")),
):
    active_tenders = db.query(Tender).filter(Tender.tenant_id == user.tenant_id, Tender.status == "ACTIVE").count()
    total_bidders = db.query(Bidder).filter(Bidder.tenant_id == user.tenant_id).count()

    verif_results = (db.query(VerificationResult).join(BidderDocument, BidderDocument.id == VerificationResult.document_id)
                     .join(Bidder, Bidder.id == BidderDocument.bidder_id).filter(Bidder.tenant_id == user.tenant_id).all())
    completed_verifs = sum(1 for v in verif_results if v.status == "VERIFIED")
    pending_verifs = sum(1 for v in verif_results if v.status in ["PENDING", "RETRY_REQUIRED"])
    manual_reviews = sum(1 for v in verif_results if v.status in ["MANUAL_REVIEW", "MISMATCH", "EXPIRED"])

    tbs = (db.query(TenderBidder).join(Tender, Tender.id == TenderBidder.tender_id)
           .join(Bidder, Bidder.id == TenderBidder.bidder_id)
           .filter(Tender.tenant_id == user.tenant_id, Bidder.tenant_id == user.tenant_id).all())
    # A score is meaningful only after at least one requirement has actually
    # been evaluated. A newly enrolled bidder must not depress a real rate or
    # be presented as a zero-percent analysis result.
    analyzed_tbs = [
        tb for tb in tbs
        if db.query(ComplianceResult.id).filter(
            ComplianceResult.tender_bidder_id == tb.id
        ).first()
    ]
    total_score = sum(tb.compliance_score for tb in analyzed_tbs)
    overall_compliance = round(total_score / len(analyzed_tbs), 1) if analyzed_tbs else 0.0

    risk_dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "INSUFFICIENT_EVIDENCE": 0, "NOT_ASSESSED": 0}
    for tb in tbs:
        # Missing analysis is not a risk finding. In particular, it must never
        # become LOW risk merely because a bidder has not been processed yet.
        r = tb.risk_level or "NOT_ASSESSED"
        risk_dist[r] = risk_dist.get(r, 0) + 1

    total_documents = (db.query(BidderDocument)
        .join(Bidder, Bidder.id == BidderDocument.bidder_id)
        .filter(Bidder.tenant_id == user.tenant_id)
        .count())

    # Documents requiring attention
    attention_docs = []
    flagged_verifs = (db.query(VerificationResult).join(BidderDocument, BidderDocument.id == VerificationResult.document_id)
        .join(Bidder, Bidder.id == BidderDocument.bidder_id).filter(
        Bidder.tenant_id == user.tenant_id,
        VerificationResult.status.in_(["MISMATCH", "EXPIRED", "MANUAL_REVIEW", "RETRY_REQUIRED"])
    ).limit(8).all())

    for f in flagged_verifs:
        doc = f.document
        if doc and doc.is_active:
            attention_docs.append({
                "document_id": doc.id,
                "bidder_id": doc.bidder_id,
                "bidder_name": doc.bidder.legal_name if doc.bidder else "Unknown",
                "document_type": doc.document_type,
                "status": f.status,
                "notes": f.discrepancy_notes or f"Flagged with status {f.status}",
                "version": doc.version
            })

    recent_logs = db.query(AuditLog).filter(AuditLog.tenant_id == user.tenant_id).order_by(AuditLog.id.desc()).limit(10).all()

    return {
        "active_tenders": active_tenders,
        "total_bidders": total_bidders,
        "pending_verifications": pending_verifs,
        "completed_verifications": completed_verifs,
        "manual_reviews_required": manual_reviews,
        "total_documents": total_documents,
        "analyzed_bidders": len(analyzed_tbs),
        "overall_compliance_rate": overall_compliance,
        "risk_distribution": risk_dist,
        "attention_documents": attention_docs,
        "recent_activity": recent_logs
    }
