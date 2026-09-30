import hashlib
import logging
import os
import re
import pymupdf as fitz
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.session import get_db
from app.models.entities import BidderDocument, OCRResult, VerificationResult, Bidder, Tender
from app.schemas.schemas import BidderDocumentOut, OCRResultOut, VerificationResultOut
from app.core.security import get_current_user, require_roles, AuthenticatedUser
from app.services.ocr_service import run_ocr_for_document
from app.services.verification_service import run_verification_for_document
from app.services.audit_service import log_audit_event
from app.core.config import settings
from app.services.tenant_service import get_tenant_bidder, get_tenant_tender, get_tenant_document

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger(__name__)

@router.get("", response_model=List[BidderDocumentOut])
def list_documents(
    tender_id: Optional[int] = None,
    bidder_id: Optional[int] = None,
    document_type: Optional[str] = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    query = (db.query(BidderDocument).join(Bidder, Bidder.id == BidderDocument.bidder_id)
             .outerjoin(Tender, Tender.id == BidderDocument.tender_id)
             .filter(Bidder.tenant_id == user.tenant_id,
                     or_(BidderDocument.tender_id.is_(None), Tender.tenant_id == user.tenant_id)))
    if tender_id is not None:
        get_tenant_tender(db, tender_id, user.tenant_id)
    if tender_id: query = query.filter(BidderDocument.tender_id == tender_id)
    if bidder_id: query = query.filter(BidderDocument.bidder_id == bidder_id)
    if document_type: query = query.filter(BidderDocument.document_type == document_type.upper())
    if active_only: query = query.filter(BidderDocument.is_active == True)

    docs = query.order_by(BidderDocument.id.desc()).all()
    out = []
    for d in docs:
        ocr = db.query(OCRResult).filter(OCRResult.document_id == d.id).first()
        verif = db.query(VerificationResult).filter(VerificationResult.document_id == d.id).first()
        out.append({
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
    return out

@router.get("/{id}")
def get_document_details(id: int, db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    doc = get_tenant_document(db, id, user.tenant_id)

    ocr = db.query(OCRResult).filter(OCRResult.document_id == doc.id).first()
    verif = db.query(VerificationResult).filter(VerificationResult.document_id == doc.id).first()

    # Get version history
    versions = db.query(BidderDocument).filter(
        BidderDocument.bidder_id == doc.bidder_id,
        BidderDocument.document_type == doc.document_type
    ).order_by(BidderDocument.version.asc()).all()

    return {
        "document": {
            "id": doc.id,
            "bidder_id": doc.bidder_id,
            "bidder_name": doc.bidder.legal_name if doc.bidder else "Unknown",
            "tender_id": doc.tender_id,
            "document_type": doc.document_type,
            "filename": doc.filename,
            "mime_type": doc.mime_type,
            "file_hash": doc.file_hash,
            "file_size_bytes": doc.file_size_bytes,
            "version": doc.version,
            "is_active": doc.is_active,
            "previous_version_id": doc.previous_version_id,
            "is_synthetic": doc.is_synthetic,
            "created_at": doc.created_at
        },
        "ocr": ocr,
        "verification": verif,
        "versions": [
            {
                "id": v.id,
                "version": v.version,
                "is_active": v.is_active,
                "filename": v.filename,
                "created_at": v.created_at
            }
            for v in versions
        ]
    }

@router.get("/{id}/file")
def stream_document_file(id: int, db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    doc = get_tenant_document(db, id, user.tenant_id)
    if not doc.content_bytes:
        raise HTTPException(status_code=404, detail="Document binary not found")

    return Response(
        content=doc.content_bytes,
        media_type=doc.mime_type or "application/pdf",
        headers={"Content-Disposition": f"inline; filename={doc.filename}"}
    )

@router.post("/{id}/ocr", response_model=OCRResultOut)
def trigger_ocr(
    id: int,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER", "VERIFICATION_OFFICER"))
):
    get_tenant_document(db, id, user.tenant_id)
    try:
        return run_ocr_for_document(db, id, user.id, user.username)
    except Exception:
        logger.exception("OCR processing failed for document %s", id)
        raise HTTPException(status_code=500, detail="OCR processing failed; review the document and retry")

@router.post("/{id}/verify", response_model=VerificationResultOut)
def trigger_verify(
    id: int,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER", "VERIFICATION_OFFICER"))
):
    get_tenant_document(db, id, user.tenant_id)
    try:
        return run_verification_for_document(db, id, user.id, user.username)
    except Exception:
        logger.exception("Verification processing failed for document %s", id)
        raise HTTPException(status_code=500, detail="Verification processing failed; review provider availability and retry")

@router.post("/upload")
async def upload_document(
    bidder_id: int = Form(...),
    document_type: str = Form(...),
    tender_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("PROCUREMENT_OFFICER"))
):
    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds the {settings.max_upload_mb} MB upload limit")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if file.content_type != "application/pdf" or not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="Only structurally valid PDF documents are accepted")
    try:
        with fitz.open(stream=content, filetype="pdf") as pdf:
            if pdf.page_count < 1:
                raise HTTPException(status_code=400, detail="PDF must contain at least one page")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Uploaded file is not a readable PDF")

    bidder = get_tenant_bidder(db, bidder_id, user.tenant_id)
    if tender_id is not None:
        get_tenant_tender(db, tender_id, user.tenant_id)

    file_hash = hashlib.sha256(content).hexdigest()
    doc_type_clean = document_type.strip().upper()

    # Check for existing document of this type for bidder
    existing_docs = db.query(BidderDocument).filter(
        BidderDocument.bidder_id == bidder_id,
        BidderDocument.document_type == doc_type_clean
    ).order_by(BidderDocument.version.desc()).all()

    version = 1
    prev_id = None
    if existing_docs:
        # Mark all previous versions as inactive but preserve them completely
        for ed in existing_docs:
            ed.is_active = False
        version = existing_docs[0].version + 1
        prev_id = existing_docs[0].id

    new_doc = BidderDocument(
        bidder_id=bidder_id,
        tender_id=tender_id,
        document_type=doc_type_clean,
        filename=re.sub(r"[^A-Za-z0-9._ -]", "_", os.path.basename(file.filename or f"{doc_type_clean}_doc.pdf"))[:250],
        mime_type=file.content_type or "application/pdf",
        file_hash=file_hash,
        file_size_bytes=len(content),
        version=version,
        is_active=True,
        previous_version_id=prev_id,
        is_synthetic=False,
        content_bytes=content
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    # Immediately run OCR & verification on the newly uploaded document
    run_ocr_for_document(db, new_doc.id, user.id, user.username)
    run_verification_for_document(db, new_doc.id, user.id, user.username)

    log_audit_event(
        db,
        action="DOCUMENT_UPLOADED",
        entity_type="DOCUMENT",
        entity_id=str(new_doc.id),
        user_id=user.id,
        username=user.username,
        details={
            "document_type": doc_type_clean,
            "version": version,
            "superseded_previous": bool(prev_id)
        }
    )

    return {
        "message": f"Document uploaded successfully as version {version}",
        "document_id": new_doc.id,
        "version": version,
        "file_hash": file_hash
    }
