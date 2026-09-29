import os
import sys
import hashlib
from app.db.session import SessionLocal
from app.models.entities import BidderDocument, Bidder
from app.services.ocr_service import run_ocr_for_document
from app.services.verification_service import run_verification_for_document

def seed_realistic_pan():
    db = SessionLocal()
    try:
        # Get image bytes
        img_path = r"C:\Users\mrpri\.gemini\antigravity-ide\brain\655865aa-a89b-4f7d-87aa-2ec19bc37efd\dummy_pan_card_1790421989487.jpg"
        if not os.path.exists(img_path):
            print("Image not found at path.")
            return

        with open(img_path, "rb") as f:
            content_bytes = f.read()

        file_hash = hashlib.sha256(content_bytes).hexdigest()

        # Find a bidder or create one
        bidder = db.query(Bidder).filter(Bidder.pan == "ABCDE1234F").first()
        if not bidder:
            bidder = Bidder(
                tenant_id=1,
                legal_name="ROHIT KUMAR",
                pan="ABCDE1234F",
                gstin="22AAAAA0000A1Z5",
                state="Maharashtra"
            )
            db.add(bidder)
            db.commit()
            db.refresh(bidder)

        # Deactivate old PAN docs for this bidder
        old_docs = db.query(BidderDocument).filter(
            BidderDocument.bidder_id == bidder.id,
            BidderDocument.document_type == "PAN"
        ).all()
        version = 1
        for old in old_docs:
            old.is_active = False
            version = max(version, old.version + 1)

        # Create realistic doc
        doc = BidderDocument(
            bidder_id=bidder.id,
            document_type="PAN",
            filename="Rohit_Kumar_Realistic_PAN.jpg",
            mime_type="image/jpeg",
            file_hash=file_hash,
            file_size_bytes=len(content_bytes),
            version=version,
            is_active=True,
            is_synthetic=False,
            content_bytes=content_bytes
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        print(f"Realistic PAN seeded. Doc ID: {doc.id}")

        # Run OCR
        print("Running OCR...")
        run_ocr_for_document(db, doc.id, 1, "system")
        
        # Run verification
        print("Running Verification...")
        run_verification_for_document(db, doc.id, 1, "system")
        
        print("Done!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_realistic_pan()
