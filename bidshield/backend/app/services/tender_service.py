from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import re
from sqlalchemy.orm import Session
from app.models.entities import Tender, TenderRequirement, TenderBidder, Bidder
from app.services.audit_service import log_audit_event

def extract_requirements_from_text(text: str) -> List[Dict[str, Any]]:
    """Extract reviewable keyword candidates from the tender metadata text provided."""
    reqs = []
    source = text.upper()

    def certainty(description: str, structured_rule: dict, code: str, name: str, req_type: str = "CONDITIONAL"):
        return {"code": code, "name": name, "requirement_type": req_type,
                "description": description, "structured_rule": structured_rule,
                "source_page": 0, "confidence": 0.60}

    default_type = "MANDATORY" if re.search(r"\b(mandatory|required|must|required to|requires)\b", source) else "CONDITIONAL"
    
    # GST requirement
    if "GST" in text.upper():
        reqs.append({
            "code": "GST-001",
            "name": "Goods and Services Tax (GST) Registration",
            **certainty("GST registration is referenced in the tender text; confirm the exact condition and evidence with an officer.", {"doc_type": "GST"}, "GST-001", "Goods and Services Tax (GST) Registration", default_type)
        })

    # PAN requirement
    if "PAN" in text.upper():
        reqs.append({
            "code": "PAN-001",
            "name": "Permanent Account Number (PAN)",
            **certainty("PAN is referenced in the tender text; confirm the exact condition and evidence with an officer.", {"doc_type": "PAN", "check_format": True}, "PAN-001", "Permanent Account Number (PAN)", default_type)
        })

    # Udyam / MSME requirement
    if any(k in text.upper() for k in ["UDYAM", "MSME"]):
        reqs.append({
            "code": "UDYAM-001",
            "name": "MSME / Udyam Registration Certificate",
            **certainty("Udyam or MSME registration is referenced; confirm whether it is mandatory, conditional, and which validity condition applies.", {"doc_type": "UDYAM"}, "UDYAM-001", "MSME / Udyam Registration Certificate", "CONDITIONAL")
        })

    # OEM Authorization
    if "OEM" in text.upper() or "MANUFACTURER" in text.upper():
        reqs.append({
            "code": "OEM-001",
            "name": "Original Equipment Manufacturer (OEM) Authorization",
            **certainty("OEM or manufacturer authorization is referenced; confirm the required issuer, evidence, and conditions with an officer.", {"doc_type": "OEM"}, "OEM-001", "Original Equipment Manufacturer (OEM) Authorization", default_type)
        })

    # Past Experience
    if any(k in text.upper() for k in ["EXPERIENCE", "CONTRACT VALUE", "PAST PERFORMANCE"]):
        experience_rule = {"doc_type": "EXPERIENCE"}
        year_match = re.search(r"EXPERIENCE.{0,40}?(\d+)\s*YEAR|(\d+)\s*YEAR.{0,40}?EXPERIENCE", source)
        if year_match:
            experience_rule["min_years"] = int(year_match.group(1) or year_match.group(2))
        experience_desc = "Experience is referenced; the officer must confirm scope and conditions."
        if "min_years" in experience_rule:
            experience_desc = f"The text references at least {experience_rule['min_years']} years of experience; the officer must confirm scope and evidence."
        reqs.append(certainty(experience_desc, experience_rule, "EXP-001", "Past Experience Criteria", "TECHNICAL"))

    # Financial Turnover
    if any(k in text.upper() for k in ["TURNOVER", "ANNUAL TURNOVER", "CA CERTIFICATE"]):
        turnover_rule = {"doc_type": "TURNOVER"}
        amount_match = re.search(r"TURNOVER.{0,60}?(?:INR|RS\.?|₹)?\s*(\d+(?:\.\d+)?)\s*(CR|CRORE|LAKH|LAKHS)?", source)
        if amount_match:
            amount = float(amount_match.group(1))
            unit = (amount_match.group(2) or "CR").upper()
            turnover_rule["min_turnover_cr"] = amount / 100 if unit.startswith("LAKH") else amount
        turnover_desc = "Turnover is referenced; no threshold was extracted. Officer review of the source wording is required."
        if "min_turnover_cr" in turnover_rule:
            turnover_desc = f"The text references a turnover threshold of INR {turnover_rule['min_turnover_cr']:g} crore; confirm its period and calculation with an officer."
        reqs.append(certainty(turnover_desc, turnover_rule, "TURNOVER-001", "Annual Financial Turnover (Audited)", "FINANCIAL"))

    # Local Content / Make in India
    if any(k in text.upper() for k in ["LOCAL CONTENT", "MAKE IN INDIA", "MII"]):
        local_rule = {"doc_type": "LOCAL_CONTENT"}
        local_match = re.search(r"LOCAL CONTENT.{0,60}?(\d+)\s*%|(\d+)\s*%.{0,60}?LOCAL CONTENT", source)
        if local_match:
            local_rule["min_pct"] = int(local_match.group(1) or local_match.group(2))
        local_desc = "Local content is referenced; confirm the applicable threshold and evidence with an officer."
        if "min_pct" in local_rule:
            local_desc = f"The text references a local content threshold of {local_rule['min_pct']}%; confirm its application with an officer."
        reqs.append(certainty(local_desc, local_rule, "LOCAL-001", "Make in India Local Content", default_type))

    return reqs

def process_tender_requirements(
    db: Session,
    tender_id: int,
    user_id: int = 1,
    username: str = "officer",
    source_text: Optional[str] = None,
) -> List[TenderRequirement]:
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise ValueError(f"Tender {tender_id} not found")

    text_corpus = source_text if source_text is not None else f"{tender.title} {tender.department} {tender.category} {tender.description or ''}"
    extracted = extract_requirements_from_text(text_corpus)

    created = []
    for item in extracted:
        # Check if already exists
        exists = db.query(TenderRequirement).filter(
            TenderRequirement.tender_id == tender_id,
            TenderRequirement.code == item["code"]
        ).first()
        if not exists:
            req = TenderRequirement(
                tender_id=tender_id,
                code=item["code"],
                name=item["name"],
                requirement_type=item["requirement_type"],
                description=item["description"],
                structured_rule=item["structured_rule"],
                source_page=item["source_page"],
                confidence=item["confidence"],
                approval_status="PENDING",
                officer_notes="AI extracted. Awaiting procurement officer review and formal approval."
            )
            db.add(req)
            created.append(req)

    db.commit()

    log_audit_event(
        db,
        action="REQUIREMENTS_EXTRACTED",
        entity_type="TENDER",
        entity_id=str(tender.id),
        user_id=user_id,
        username=username,
        details={"extracted_count": len(created)}
    )

    return db.query(TenderRequirement).filter(TenderRequirement.tender_id == tender_id).all()
