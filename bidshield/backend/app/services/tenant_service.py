"""Shared tenant-scoped lookup helpers for API resources (Layer 5).

Every fetch is pre-filtered at the QUERY level by the caller's tenant. A
resource outside the caller's scope answers 404 — never 403 — so the API does
not reveal that the resource exists. Each out-of-scope hit is logged to the
Layer 2 security log, which detects violation bursts.
"""
import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.entities import Bidder, BidderDocument, Tender

logger = logging.getLogger("bidshield.security")


def _log_scope_violation(db: Session, resource: str, resource_id, tenant_id: int,
                         user, path: str = "") -> None:
    """Record the out-of-scope attempt; burst detection runs in Layer 2."""
    try:
        from app.services import anomaly_service
        anomaly_service.log_security_event(
            db, kind="SCOPE_VIOLATION", username=user.username, user_id=user.id,
            tenant_id=tenant_id,
            detail={"resource": resource, "resource_id": str(resource_id), "path": path},
        )
        anomaly_service.check_violation_burst(db, user.id, tenant_id, user.username)
    except Exception:
        # Detection logging must never break the 404 the caller should see.
        logger.exception("Failed to log scope violation")


def get_tenant_tender(db: Session, tender_id: int, tenant_id: int,
                      user=None, path: str = "") -> Tender:
    item = db.query(Tender).filter(Tender.id == tender_id, Tender.tenant_id == tenant_id).first()
    if item is None:
        if user is not None:
            _log_scope_violation(db, "tender", tender_id, tenant_id, user, path)
        raise HTTPException(status_code=404, detail="Tender not found")
    return item


def get_tenant_bidder(db: Session, bidder_id: int, tenant_id: int,
                      user=None, path: str = "") -> Bidder:
    item = db.query(Bidder).filter(Bidder.id == bidder_id, Bidder.tenant_id == tenant_id).first()
    if item is None:
        if user is not None:
            _log_scope_violation(db, "bidder", bidder_id, tenant_id, user, path)
        raise HTTPException(status_code=404, detail="Bidder not found")
    return item


def get_tenant_document(db: Session, document_id: int, tenant_id: int,
                        user=None, path: str = "") -> BidderDocument:
    item = (db.query(BidderDocument)
            .join(Bidder, Bidder.id == BidderDocument.bidder_id)
            .outerjoin(Tender, Tender.id == BidderDocument.tender_id)
            .filter(BidderDocument.id == document_id, Bidder.tenant_id == tenant_id,
                    or_(BidderDocument.tender_id.is_(None), Tender.tenant_id == tenant_id))
            .first())
    if item is None:
        if user is not None:
            _log_scope_violation(db, "document", document_id, tenant_id, user, path)
        raise HTTPException(status_code=404, detail="Document not found")
    return item
