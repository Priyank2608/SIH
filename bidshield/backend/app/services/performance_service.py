from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.entities import Bidder, HistoricalContract, QualityInspectionRecord, Tender

def get_bidder_performance_analysis(db: Session, bidder_id: int, tender_id: int = None) -> Dict[str, Any]:
    bidder = db.query(Bidder).filter(Bidder.id == bidder_id).first()
    if not bidder:
        raise ValueError(f"Bidder {bidder_id} not found")

    contracts = db.query(HistoricalContract).filter(HistoricalContract.bidder_id == bidder_id).all()
    
    total_contracts = len(contracts)
    completed_contracts = [c for c in contracts if c.status == "COMPLETED"]
    terminated_contracts = [c for c in contracts if c.status == "TERMINATED"]
    ongoing_contracts = [c for c in contracts if c.status == "ONGOING"]

    total_value_lakhs = sum(c.contract_value_lakhs for c in contracts)
    
    delays = [c.delay_days for c in completed_contracts if c.delay_days > 0]
    on_time_contracts = [c for c in completed_contracts if c.delay_days <= 0]
    on_time_rate = round((len(on_time_contracts) / len(completed_contracts) * 100), 1) if completed_contracts else 0.0
    avg_delay_days = round(sum(delays) / len(delays), 1) if delays else 0.0

    total_ld = sum(c.liquidated_damages_inr for c in contracts)

    # Documented delay cause breakdown
    delay_causes = {"NONE": 0, "CONTRACTOR": 0, "PROCURING_ENTITY": 0, "FORCE_MAJEURE": 0, "APPROVED_EXTENSION": 0}
    for c in completed_contracts:
        cause = c.documented_delay_cause or "NONE"
        delay_causes[cause] = delay_causes.get(cause, 0) + 1

    # Quality inspection aggregation
    all_quality_records = []
    for c in contracts:
        all_quality_records.extend(c.quality_records)

    total_inspections = len(all_quality_records)
    passed_inspections = sum(1 for q in all_quality_records if q.result == "PASS")
    total_defects = sum(q.defect_count for q in all_quality_records)
    rework_count = sum(1 for q in all_quality_records if q.rework_required)
    warranty_claims = sum(q.warranty_claims for q in all_quality_records)

    inspection_pass_rate = round((passed_inspections / total_inspections * 100), 1) if total_inspections else 100.0

    # Comparable contract intelligence
    comparable_contracts = []
    tender = db.query(Tender).filter(Tender.id == tender_id).first() if tender_id else None
    
    for c in contracts:
        similarity = c.similarity_score
        if tender:
            # Dynamically compute similarity if category matches
            cat_match = 1.0 if c.category.lower() in tender.category.lower() or tender.category.lower() in c.category.lower() else 0.4
            similarity = round(cat_match * 0.7 + (min(c.contract_value_lakhs, tender.estimated_value_cr * 100) / max(c.contract_value_lakhs, tender.estimated_value_cr * 100)) * 0.3, 2)
        comparable_contracts.append({
            "contract_ref": c.contract_ref,
            "title": c.title,
            "procuring_entity": c.procuring_entity,
            "category": c.category,
            "contract_value_lakhs": c.contract_value_lakhs,
            "actual_completion": c.actual_completion,
            "delay_days": c.delay_days,
            "documented_delay_cause": c.documented_delay_cause,
            "performance_rating": c.performance_rating,
            "similarity_score": similarity
        })

    return {
        "bidder_id": bidder_id,
        "total_contracts": total_contracts,
        "completed_count": len(completed_contracts),
        "ongoing_count": len(ongoing_contracts),
        "terminated_count": len(terminated_contracts),
        "total_value_lakhs": round(total_value_lakhs, 2),
        "on_time_rate": on_time_rate,
        "avg_delay_days": avg_delay_days,
        "liquidated_damages_inr": round(total_ld, 2),
        "delay_causes": delay_causes,
        "quality_metrics": {
            "total_inspections": total_inspections,
            "pass_rate": inspection_pass_rate,
            "total_defects": total_defects,
            "rework_required_count": rework_count,
            "warranty_claims": warranty_claims
        },
        "comparable_contracts": comparable_contracts
    }
