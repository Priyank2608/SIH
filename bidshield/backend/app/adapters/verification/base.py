from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.models.entities import Bidder, BidderDocument, OCRResult

class VerificationAdapter:
    provider_name: str = "BaseVerificationProvider"
    
    def verify(self, doc: BidderDocument, ocr: Optional[OCRResult], bidder: Bidder) -> Dict[str, Any]:
        raise NotImplementedError

class DemoGSTVerificationAdapter(VerificationAdapter):
    provider_name: str = "DemoGSTNVerificationProvider"

    def verify(self, doc: BidderDocument, ocr: Optional[OCRResult], bidder: Bidder) -> Dict[str, Any]:
        if not ocr or not ocr.fields:
            return {
                "status": "MANUAL_REVIEW",
                "discrepancy_notes": "Unable to extract GSTIN from document via OCR.",
                "raw_response": {"provider": self.provider_name, "error": "No OCR data"}
            }

        extracted_gstin = ocr.fields.get("identifier")
        # Check if document was marked as degraded scan
        if ocr.confidence < 0.60:
            return {
                "status": "MANUAL_REVIEW",
                "discrepancy_notes": f"OCR confidence is low ({ocr.confidence:.2f}). Document clarity requires manual officer verification.",
                "raw_response": {"provider": self.provider_name, "confidence": ocr.confidence}
            }

        if not extracted_gstin:
            return {
                "status": "MANUAL_REVIEW",
                "discrepancy_notes": "GSTIN field absent in extracted text. Officer inspection needed.",
                "raw_response": {"provider": self.provider_name, "found_fields": ocr.fields}
            }

        # Check for simulated provider timeout scenario (e.g. Epsilon Engineering)
        if "RETRY" in doc.filename.upper() or "EPSILON" in bidder.legal_name.upper():
            return {
                "status": "RETRY_REQUIRED",
                "discrepancy_notes": "Upstream verification gateway timed out after 10000ms. Provider unavailable. Retry required.",
                "raw_response": {"provider": self.provider_name, "code": "GATEWAY_TIMEOUT", "http_status": 504}
            }

        # Check mismatch scenario (e.g. Bharat Systems)
        if extracted_gstin != bidder.gstin:
            return {
                "status": "MISMATCH",
                "discrepancy_notes": f"Document GSTIN ({extracted_gstin}) does not match Bidder Profile GSTIN ({bidder.gstin}). Discrepancy detected.",
                "raw_response": {
                    "provider": self.provider_name,
                    "extracted_gstin": extracted_gstin,
                    "expected_gstin": bidder.gstin,
                    "gstin_status": "ACTIVE",
                    "taxpayer_name": ocr.fields.get("legal_name", bidder.legal_name)
                }
            }

        return {
            "status": "VERIFIED",
            "discrepancy_notes": None,
            "raw_response": {
                "provider": self.provider_name,
                "gstin": extracted_gstin,
                "status": "ACTIVE",
                "taxpayer_type": "Regular",
                "legal_name": bidder.legal_name,
                "verified_source": "Local synthetic demo comparison"
            }
        }

class DemoPANVerificationAdapter(VerificationAdapter):
    provider_name: str = "DemoNSDLVerificationProvider"

    def verify(self, doc: BidderDocument, ocr: Optional[OCRResult], bidder: Bidder) -> Dict[str, Any]:
        if not ocr or not ocr.fields:
            return {
                "status": "MANUAL_REVIEW",
                "discrepancy_notes": "No PAN fields identified.",
                "raw_response": {"provider": self.provider_name}
            }

        extracted_pan = ocr.fields.get("identifier")
        if ocr.confidence < 0.60:
            return {
                "status": "MANUAL_REVIEW",
                "discrepancy_notes": f"Low OCR confidence ({ocr.confidence:.2f}). Manual visual inspection required.",
                "raw_response": {"provider": self.provider_name, "confidence": ocr.confidence}
            }

        if not extracted_pan or extracted_pan != bidder.pan:
            return {
                "status": "MISMATCH",
                "discrepancy_notes": f"Document PAN ({extracted_pan}) does not match registered PAN ({bidder.pan}).",
                "raw_response": {"provider": self.provider_name, "extracted": extracted_pan, "registered": bidder.pan}
            }

        return {
            "status": "VERIFIED",
            "discrepancy_notes": None,
            "raw_response": {
                "provider": self.provider_name,
                "pan": extracted_pan,
                "pan_status": "VALID_AND_OPERATIVE",
                "name_on_card": bidder.legal_name,
                "seeding_status": "AADHAAR_SEEDED"
            }
        }

class DemoUdyamVerificationAdapter(VerificationAdapter):
    provider_name: str = "DemoMSMEVerificationProvider"

    def verify(self, doc: BidderDocument, ocr: Optional[OCRResult], bidder: Bidder) -> Dict[str, Any]:
        if not ocr:
            return {"status": "MANUAL_REVIEW", "discrepancy_notes": "OCR missing.", "raw_response": {}}

        # Check for expired scenario (e.g. Gamma Infotech v1)
        expiry_date = ocr.fields.get("expiry_date")
        extracted_status = str(ocr.fields.get("status", "")).upper()
        if (expiry_date and expiry_date < "2026-09-01") or "EXPIRED" in extracted_status or "EXPIRED" in doc.filename.upper():
            return {
                "status": "EXPIRED",
                "discrepancy_notes": f"Udyam registration certificate expired on {expiry_date or '2026-05-15'}. Current tender closing requires active registration.",
                "raw_response": {"provider": self.provider_name, "expiry_date": expiry_date or "2026-05-15", "status": "EXPIRED"}
            }

        extracted_udyam = ocr.fields.get("identifier")
        if bidder.udyam_number and extracted_udyam and extracted_udyam != bidder.udyam_number:
            return {
                "status": "MISMATCH",
                "discrepancy_notes": f"Udyam number {extracted_udyam} does not match {bidder.udyam_number}",
                "raw_response": {"provider": self.provider_name}
            }

        return {
            "status": "VERIFIED",
            "discrepancy_notes": None,
            "raw_response": {
                "provider": self.provider_name,
                "udyam_number": extracted_udyam or bidder.udyam_number,
                "enterprise_type": bidder.enterprise_type,
                "status": "ACTIVE"
            }
        }

class DemoOEMVerificationAdapter(VerificationAdapter):
    provider_name: str = "DemoOEMAuthorizationPortalProvider"

    def verify(self, doc: BidderDocument, ocr: Optional[OCRResult], bidder: Bidder) -> Dict[str, Any]:
        if not ocr or not ocr.fields:
            return {"status": "MANUAL_REVIEW", "discrepancy_notes": "OEM details unverified.", "raw_response": {}}
        
        oem_id = ocr.fields.get("identifier")
        if not oem_id:
            return {"status": "MANUAL_REVIEW", "discrepancy_notes": "OEM authorization ID not detected.", "raw_response": {}}

        return {
            "status": "VERIFIED",
            "discrepancy_notes": None,
            "raw_response": {
                "provider": self.provider_name,
                "authorization_id": oem_id,
                "authorized_partner": bidder.legal_name,
                "validity": "2027-12-31",
                "tier": "Tier-1 Certified Enterprise Partner"
            }
        }

class DemoExperienceVerificationAdapter(VerificationAdapter):
    provider_name: str = "DemoPublicProcurementExperienceRegistry"

    def verify(self, doc: BidderDocument, ocr: Optional[OCRResult], bidder: Bidder) -> Dict[str, Any]:
        return {
            "status": "VERIFIED",
            "discrepancy_notes": None,
            "raw_response": {
                "provider": self.provider_name,
                "bidder": bidder.legal_name,
                "verified_contracts_count": len(bidder.contracts),
                "experience_duration": "Verified > 3 Years"
            }
        }

class DemoTurnoverVerificationAdapter(VerificationAdapter):
    provider_name: str = "DemoICAIUDINVerificationProvider"

    def verify(self, doc: BidderDocument, ocr: Optional[OCRResult], bidder: Bidder) -> Dict[str, Any]:
        return {
            "status": "VERIFIED",
            "discrepancy_notes": None,
            "raw_response": {
                "provider": self.provider_name,
                "udin_status": "GENERATED_AND_ACTIVE",
                "auditor": "M/s R.K. Mehta & Associates (Chartered Accountants)",
                "average_turnover_verified": "INR 8.5 Crore"
            }
        }

class DemoGenericVerificationAdapter(VerificationAdapter):
    provider_name: str = "DemoGovernmentRegistryProvider"

    def verify(self, doc: BidderDocument, ocr: Optional[OCRResult], bidder: Bidder) -> Dict[str, Any]:
        if ocr and ocr.confidence < 0.60:
            return {
                "status": "MANUAL_REVIEW",
                "discrepancy_notes": f"Low scan clarity ({ocr.confidence:.2f}). Manual review needed.",
                "raw_response": {"provider": self.provider_name}
            }
        return {
            "status": "VERIFIED",
            "discrepancy_notes": None,
            "raw_response": {
                "provider": self.provider_name,
                "document_type": doc.document_type,
                "status": "CONFIRMED_GENUINE",
                "bidder": bidder.legal_name
            }
        }

class ProviderRegistry:
    """Provider Manager that registers and dispatches verification adapters."""

    def __init__(self):
        self._adapters: Dict[str, VerificationAdapter] = {
            "GST": DemoGSTVerificationAdapter(),
            "PAN": DemoPANVerificationAdapter(),
            "UDYAM": DemoUdyamVerificationAdapter(),
            "OEM": DemoOEMVerificationAdapter(),
            "EXPERIENCE": DemoExperienceVerificationAdapter(),
            "TURNOVER": DemoTurnoverVerificationAdapter(),
            "EPFO": DemoGenericVerificationAdapter(),
            "ESIC": DemoGenericVerificationAdapter(),
            "MCA": DemoGenericVerificationAdapter(),
            "NSIC": DemoGenericVerificationAdapter(),
            "STARTUP": DemoGenericVerificationAdapter(),
            "LOCAL_CONTENT": DemoGenericVerificationAdapter(),
        }

    def get_adapter(self, document_type: str) -> VerificationAdapter:
        return self._adapters.get(document_type.upper(), DemoGenericVerificationAdapter())

provider_registry = ProviderRegistry()
