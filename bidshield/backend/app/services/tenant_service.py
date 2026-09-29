"""Shared tenant-scoped lookup helpers for API resources."""
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.entities import Bidder, BidderDocument, Tender


def get_tenant_tender(db: Session, tender_id: int, tenant_id: int) -> Tender:
    item = db.query(Tender).filter(Tender.id == tender_id, Tender.tenant_id == tenant_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    return item


def get_tenant_bidder(db: Session, bidder_id: int, tenant_id: int) -> Bidder:
    item = db.query(Bidder).filter(Bidder.id == bidder_id, Bidder.tenant_id == tenant_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Bidder not found")
    return item


def get_tenant_document(db: Session, document_id: int, tenant_id: int) -> BidderDocument:
    item = (db.query(BidderDocument)
            .join(Bidder, Bidder.id == BidderDocument.bidder_id)
            .outerjoin(Tender, Tender.id == BidderDocument.tender_id)
            .filter(BidderDocument.id == document_id, Bidder.tenant_id == tenant_id,
                    or_(BidderDocument.tender_id.is_(None), Tender.tenant_id == tenant_id))
            .first())
    if item is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return item
