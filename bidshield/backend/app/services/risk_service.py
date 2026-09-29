from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.entities import (
    Bidder, Tender, TenderBidder, BidderDocument, OCRResult,
    VerificationResult, HistoricalContract, RiskAssessment, EvidenceRecord
)
from app.services.performance_service import get_bidder_performance_analysis
from app.core.config import settings

def calculate_bidder_risk(db: Session, tender_id: int, bidder_id: int) -> Dict[str, Any]:
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    bidder = db.query(Bidder).filter(Bidder.id == bidder_id).first()
    tb = db.query(TenderBidder).filter(
        TenderBidder.tender_id == tender_id,
        TenderBidder.bidder_id == bidder_id
    ).first()

    if not tb or not bidder or not tender:
        raise ValueError("Tender or Bidder record not found")

    perf = get_bidder_performance_analysis(db, bidder_id, tender_id)
    docs = db.query(BidderDocument).filter(
        BidderDocument.bidder_id == bidder_id,
        BidderDocument.is_active.is_(True),
        or_(BidderDocument.tender_id == tender_id, BidderDocument.tender_id.is_(None)),
    ).all()

    ocr_results = [db.query(OCRResult).filter(OCRResult.document_id == d.id).first() for d in docs]
    ocr_results = [o for o in ocr_results if o]
    verif_results = [db.query(VerificationResult).filter(VerificationResult.document_id == d.id).first() for d in docs]
    verif_results = [v for v in verif_results if v]

    contributing_factors = []

    # 1. Document Integrity Risk (0-100)
    avg_conf = (sum(o.confidence for o in ocr_results) / len(ocr_results)) if ocr_results else 0.5
    doc_integrity_score = round(max(0.0, (1.0 - avg_conf) * 100), 1)
    doc_integrity_reason = f"Average OCR confidence across {len(ocr_results)} documents is {avg_conf:.2f}."
    if any(o.confidence < 0.60 for o in ocr_results):
        doc_integrity_score = max(doc_integrity_score, 65.0)
        contributing_factors.append({
            "dimension": "DOCUMENT_INTEGRITY",
            "factor": "Degraded scan or low OCR confidence detected in submitted certificates.",
            "impact": "HIGH"
        })

    # 2. Compliance Risk (0-100)
    failed_verif = [v for v in verif_results if v.status in ["FAILED", "MISMATCH", "EXPIRED"]]
    review_verif = [v for v in verif_results if v.status in ["MANUAL_REVIEW", "RETRY_REQUIRED", "NOT_AVAILABLE", "PENDING", "ERROR"]]
    compliance_score = round(len(failed_verif) * 35.0 + len(review_verif) * 15.0, 1)
    compliance_score = min(100.0, compliance_score)
    compliance_reason = f"{len(failed_verif)} failed/mismatched verification(s), {len(review_verif)} under manual review."
    if failed_verif:
        contributing_factors.append({
            "dimension": "COMPLIANCE",
            "factor": f"Document verification flags identified: {failed_verif[0].status} on {failed_verif[0].provider_name}.",
            "impact": "CRITICAL"
        })

    # 3. Delivery Risk (0-100)
    on_time = perf["on_time_rate"]
    contractor_delays = perf["delay_causes"].get("CONTRACTOR", 0)
    delivery_score = round((100.0 - on_time) * 0.7 + (contractor_delays * 15.0), 1)
    delivery_score = min(100.0, max(0.0, delivery_score))
    delivery_reason = f"Historical on-time delivery rate is {on_time}% with {perf['avg_delay_days']} avg delay days."
    if contractor_delays > 0:
        contributing_factors.append({
            "dimension": "DELIVERY",
            "factor": f"{contractor_delays} past delay(s) attributed specifically to contractor execution.",
            "impact": "MEDIUM"
        })

    # 4. Quality Risk (0-100)
    q_pass_rate = perf["quality_metrics"]["pass_rate"]
    defects = perf["quality_metrics"]["total_defects"]
    warranty_issues = perf["quality_metrics"]["warranty_claims"]
    quality_score = round((100.0 - q_pass_rate) * 0.6 + defects * 4.0 + warranty_issues * 8.0, 1)
    quality_score = min(100.0, max(0.0, quality_score))
    quality_reason = f"Inspection pass rate {q_pass_rate}%, {defects} defects, {warranty_issues} warranty claims."

    # 5. Contract Performance Risk (0-100)
    ld_inr = perf["liquidated_damages_inr"]
    terminated = perf["terminated_count"]
    contract_perf_score = min(100.0, (ld_inr / 100000.0 * 5.0) + (terminated * 50.0))
    contract_perf_reason = f"Liquidated damages of INR {ld_inr:,.0f} recorded; {terminated} terminations."

    # 6. Experience / Capacity Risk (0-100)
    total_val_cr = perf["total_value_lakhs"] / 100.0
    est_cr = tender.estimated_value_cr or 1.0
    val_ratio = total_val_cr / est_cr
    if val_ratio >= 1.5:
        exp_score = 15.0
        exp_reason = f"Extensive capacity: past executed volume (INR {total_val_cr:.1f} Cr) exceeds tender estimate (INR {est_cr:.1f} Cr)."
    elif val_ratio >= 0.5:
        exp_score = 35.0
        exp_reason = f"Moderate capacity: past volume is {val_ratio*100:.0f}% of tender estimated value."
    else:
        exp_score = 65.0
        exp_reason = f"Limited historical execution scale relative to tender size ({val_ratio*100:.0f}%)."

    # 7. Anomaly Risk (0-100)
    # Check for unusual patterns (e.g. multiple versions uploaded rapidly, mismatch with external registry)
    anomaly_score = 10.0
    anomaly_reason = "Standard consistent pattern across documents."
    if len(docs) > 1 and any(d.version > 1 for d in docs):
        anomaly_score = 45.0
        anomaly_reason = "Unusual pattern detected: multiple document versions submitted to supersede initial rejections."
        contributing_factors.append({
            "dimension": "ANOMALY",
            "factor": "Superseded document versions on record. Officer verification of version delta recommended.",
            "impact": "MEDIUM"
        })
    if any(v.status == "MISMATCH" for v in verif_results):
        anomaly_score = max(anomaly_score, 75.0)
        anomaly_reason = "Unusual pattern detected: field values in document differ from registered portal profile."

    # 8. Data Confidence & Sufficiency
    live_source_missing = not settings.demo_mode and any(v.status in {"NOT_AVAILABLE", "PENDING", "ERROR"} for v in verif_results)
    if perf["total_contracts"] == 0 or live_source_missing:
        data_sufficiency = "INSUFFICIENT"
        data_conf_score = 90.0
        data_conf_reason = (
            "Live registry verification is unavailable. Evidence is insufficient for a reliable low-risk assessment."
            if live_source_missing else
            "Zero historical public procurement contracts on file. Low data sufficiency prevents reliable predictive scoring."
        )
        overall_category = "INSUFFICIENT_EVIDENCE"
        overall_score = 50.0
        explanation = (
            "Live registry verification is unavailable. Assessment is marked insufficient evidence rather than low risk."
            if live_source_missing else
            "Insufficient historical procurement data available. Assessment is withheld from assigning low risk to avoid false confidence."
        )
    else:
        data_sufficiency = "HIGH" if perf["total_contracts"] >= 3 else "MODERATE"
        data_conf_score = 20.0 if data_sufficiency == "HIGH" else 40.0
        data_conf_reason = f"High confidence based on {perf['total_contracts']} verified historical procurement contracts."

        weighted_sum = (
            doc_integrity_score * 0.15 +
            compliance_score * 0.30 +
            delivery_score * 0.15 +
            quality_score * 0.10 +
            contract_perf_score * 0.10 +
            exp_score * 0.10 +
            anomaly_score * 0.10
        )
        overall_score = round(weighted_sum, 1)

        if overall_score >= 60.0 or compliance_score >= 70.0:
            overall_category = "HIGH"
            explanation = "Elevated risk profile detected due to compliance discrepancy or historical delivery challenges."
        elif overall_score >= 35.0 or compliance_score >= 35.0:
            overall_category = "MEDIUM"
            explanation = "Moderate operational risk profile. Manual review of contributing factors recommended."
        else:
            overall_category = "LOW"
            explanation = "Demonstrated high compliance, prompt delivery execution, and verified documentation."

    dimensions = {
        "DOCUMENT_INTEGRITY": {"score": doc_integrity_score, "reason": doc_integrity_reason},
        "COMPLIANCE": {"score": compliance_score, "reason": compliance_reason},
        "DELIVERY": {"score": delivery_score, "reason": delivery_reason},
        "QUALITY": {"score": quality_score, "reason": quality_reason},
        "CONTRACT_PERFORMANCE": {"score": contract_perf_score, "reason": contract_perf_reason},
        "EXPERIENCE_CAPACITY": {"score": exp_score, "reason": exp_reason},
        "ANOMALY": {"score": anomaly_score, "reason": anomaly_reason},
        "DATA_CONFIDENCE": {"score": data_conf_score, "reason": data_conf_reason}
    }

    # Store or update RiskAssessment
    existing_ra = db.query(RiskAssessment).filter(RiskAssessment.tender_bidder_id == tb.id).first()
    if existing_ra:
        existing_ra.overall_score = overall_score
        existing_ra.overall_category = overall_category
        existing_ra.dimensions = dimensions
        existing_ra.explanation = explanation
        existing_ra.contributing_factors = contributing_factors
        existing_ra.data_sufficiency = data_sufficiency
        ra_obj = existing_ra
    else:
        ra_obj = RiskAssessment(
            tender_bidder_id=tb.id,
            overall_score=overall_score,
            overall_category=overall_category,
            dimensions=dimensions,
            explanation=explanation,
            contributing_factors=contributing_factors,
            data_sufficiency=data_sufficiency,
            model_version=settings.risk_engine_version
        )
        db.add(ra_obj)

    tb.risk_level = overall_category
    db.commit()

    # Create Evidence Record
    ev = EvidenceRecord(
        tender_id=tender_id,
        bidder_id=bidder_id,
        claim_type="RISK_ASSESSMENT",
        evidence_text=f"Calculated {overall_category} risk ({overall_score}/100). {explanation}",
        source_reference=f"RiskEngine v{settings.risk_engine_version} (8-Dimensions)",
        confidence=0.92
    )
    db.add(ev)
    db.commit()

    return {
        "tender_id": tender_id,
        "bidder_id": bidder_id,
        "overall_score": overall_score,
        "overall_category": overall_category,
        "explanation": explanation,
        "data_sufficiency": data_sufficiency,
        "dimensions": dimensions,
        "contributing_factors": contributing_factors
    }
