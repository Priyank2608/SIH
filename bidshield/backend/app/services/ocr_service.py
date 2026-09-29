from sqlalchemy.orm import Session
from app.models.entities import BidderDocument, OCRResult
from app.adapters.documents.base import DocumentSourceAdapter
from app.adapters.ocr.base import TesseractOCRAdapter
from app.services.audit_service import log_audit_event

def run_ocr_for_document(db: Session, document_id: int, user_id: int = 1, username: str = "officer") -> OCRResult:
    doc_adapter = DocumentSourceAdapter()
    doc = doc_adapter.fetch_document(db, document_id)
    if not doc:
        raise ValueError(f"Document with ID {document_id} not found")

    content_bytes, mime_type = doc_adapter.get_document_bytes(db, document_id)
    ocr_adapter = TesseractOCRAdapter()
    result = ocr_adapter.extract(content_bytes, doc.document_type, mime_type)

    # Check if existing OCR result exists
    existing = db.query(OCRResult).filter(OCRResult.document_id == doc.id).first()
    if existing:
        existing.extracted_text = result["text"]
        existing.fields = result["fields"]
        existing.bounding_boxes = result["bounding_boxes"]
        existing.confidence = result["confidence"]
        existing.engine = result["engine"]
        existing.model_version = result["model_version"]
        existing.page_count = result["page_count"]
        ocr_obj = existing
    else:
        ocr_obj = OCRResult(
            document_id=doc.id,
            extracted_text=result["text"],
            fields=result["fields"],
            bounding_boxes=result["bounding_boxes"],
            confidence=result["confidence"],
            engine=result["engine"],
            model_version=result["model_version"],
            page_count=result["page_count"]
        )
        db.add(ocr_obj)

    db.commit()
    db.refresh(ocr_obj)

    log_audit_event(
        db,
        action="OCR_COMPLETED",
        entity_type="DOCUMENT",
        entity_id=str(doc.id),
        user_id=user_id,
        username=username,
        details={
            "document_type": doc.document_type,
            "confidence": result["confidence"],
            "engine": result["engine"],
            "fields_found": list(result["fields"].keys())
        }
    )

    return ocr_obj
