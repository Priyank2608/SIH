import hashlib
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.entities import BidderDocument

class DocumentSourceAdapter:
    """Document Source Abstraction layer to isolate database/storage specifics."""
    
    def fetch_document(self, db: Session, document_id: int) -> Optional[BidderDocument]:
        return db.query(BidderDocument).filter(BidderDocument.id == document_id).first()

    def fetch_metadata(self, db: Session, document_id: int) -> dict:
        doc = self.fetch_document(db, document_id)
        if not doc:
            return {}
        return {
            "id": doc.id,
            "bidder_id": doc.bidder_id,
            "tender_id": doc.tender_id,
            "document_type": doc.document_type,
            "filename": doc.filename,
            "mime_type": doc.mime_type,
            "file_hash": doc.file_hash,
            "version": doc.version,
            "is_active": doc.is_active,
            "is_synthetic": doc.is_synthetic,
            "created_at": doc.created_at.isoformat() if doc.created_at else None
        }

    def get_document_bytes(self, db: Session, document_id: int) -> Tuple[Optional[bytes], str]:
        doc = self.fetch_document(db, document_id)
        if not doc:
            return None, ""
        return doc.content_bytes, doc.mime_type

    def get_document_version(self, db: Session, bidder_id: int, document_type: str, version: int) -> Optional[BidderDocument]:
        return db.query(BidderDocument).filter(
            BidderDocument.bidder_id == bidder_id,
            BidderDocument.document_type == document_type,
            BidderDocument.version == version
        ).first()

class SyntheticDocumentDatabaseAdapter(DocumentSourceAdapter):
    """Concrete demo implementation reading from the internal synthetic database storage."""
    pass
