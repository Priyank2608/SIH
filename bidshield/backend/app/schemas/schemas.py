from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

# ── Layer 7 — strict request schemas ────────────────────────────────────────
# extra="forbid" rejects unknown fields outright: an unexpected field is often
# a bug or a probe, so it is never silently dropped.

# Auth
class LoginRequest(BaseModel):
    model_config = {"extra": "forbid"}
    username: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._@-]+$")
    password: str = Field(min_length=1, max_length=256)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool

# Requirements
class TenderRequirementOut(BaseModel):
    id: int
    tender_id: int
    code: str
    name: str
    requirement_type: str
    description: str
    structured_rule: Dict[str, Any]
    source_page: int
    confidence: float
    approval_status: str
    approving_officer_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    officer_notes: Optional[str] = None
    created_at: Optional[datetime] = None

class RequirementUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    code: Optional[str] = Field(default=None, min_length=1, max_length=50, pattern=r"^[A-Z0-9][A-Z0-9-]*$")
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    requirement_type: Optional[Literal["MANDATORY", "OPTIONAL", "TECHNICAL", "FINANCIAL"]] = None
    description: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    structured_rule: Optional[Dict[str, Any]] = None
    approval_status: Optional[Literal["APPROVED", "PENDING", "REJECTED", "MODIFIED", "DISABLED"]] = None
    officer_notes: Optional[str] = Field(default=None, max_length=4000)

class RequirementCreate(BaseModel):
    model_config = {"extra": "forbid"}
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Z0-9][A-Z0-9-]*$")
    name: str = Field(min_length=1, max_length=200)
    requirement_type: Literal["MANDATORY", "OPTIONAL", "TECHNICAL", "FINANCIAL"] = "MANDATORY"
    description: str = Field(min_length=1, max_length=4000)
    structured_rule: Dict[str, Any] = {}

# Tenders
class TenderOut(BaseModel):
    id: int
    tender_ref: str
    gem_ref: Optional[str] = None
    title: str
    department: str
    category: str
    description: Optional[str] = None
    estimated_value_cr: float
    issue_date: str
    closing_date: str
    status: str
    pdf_filename: Optional[str] = None
    created_at: Optional[datetime] = None
    requirements: List[TenderRequirementOut] = []
    bidders_count: int = 0

class TenderDetailOut(TenderOut):
    bidders: List[Dict[str, Any]] = []

class TenderCreate(BaseModel):
    model_config = {"extra": "forbid"}
    tender_ref: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9/_.:-]*$")
    gem_ref: Optional[str] = Field(default=None, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9/_.:-]*$")
    title: str = Field(min_length=1, max_length=300)
    department: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=4000)
    estimated_value_cr: float = Field(default=1.0, ge=0, le=1_000_000)
    issue_date: str = Field(min_length=8, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")
    closing_date: str = Field(min_length=8, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")

# Documents
class BidderDocumentOut(BaseModel):
    id: int
    bidder_id: int
    tender_id: Optional[int] = None
    document_type: str
    filename: str
    mime_type: str
    file_hash: str
    file_size_bytes: int
    version: int
    is_active: bool
    previous_version_id: Optional[int] = None
    is_synthetic: bool
    created_at: Optional[datetime] = None
    ocr_confidence: Optional[float] = None
    verification_status: Optional[str] = None
    verification_notes: Optional[str] = None

# OCR
class OCRResultOut(BaseModel):
    id: int
    document_id: int
    extracted_text: str
    fields: Dict[str, Any]
    bounding_boxes: List[Dict[str, Any]]
    confidence: float
    engine: str
    model_version: str
    page_count: int
    created_at: Optional[datetime] = None

# Verification
class VerificationResultOut(BaseModel):
    id: int
    document_id: int
    provider_name: str
    status: str
    raw_response: Dict[str, Any]
    discrepancy_notes: Optional[str] = None
    retry_count: int
    verified_at: Optional[datetime] = None

class ProviderConfigOut(BaseModel):
    id: int
    provider_code: str
    provider_name: str
    document_type: str
    auth_type: str
    api_endpoint: str
    is_active: bool
    timeout_seconds: int

# Historical Contracts & Quality
class QualityRecordOut(BaseModel):
    id: int
    contract_id: int
    inspection_date: str
    inspection_agency: str
    result: str
    defect_count: int
    rework_required: bool
    warranty_claims: int
    remarks: Optional[str] = None

class HistoricalContractOut(BaseModel):
    id: int
    bidder_id: int
    contract_ref: str
    procuring_entity: str
    title: str
    category: str
    contract_value_lakhs: float
    issue_date: str
    scheduled_completion: str
    actual_completion: Optional[str] = None
    status: str
    delay_days: int
    documented_delay_cause: str
    liquidated_damages_inr: float
    performance_rating: float
    similarity_score: float
    quality_records: List[QualityRecordOut] = []

class BidderCreate(BaseModel):
    """Officer bid-intake payload: bidder shell + tender enrollment.

    Only legal_name and tender_id are required; statutory identifiers may be
    captured later from OCR'd documents during officer review. Identifiers use
    strict regexes; enterprise_type is a fixed whitelist, not free text.
    """
    model_config = {"extra": "forbid"}
    tender_id: int = Field(gt=0)
    legal_name: str = Field(min_length=2, max_length=250)
    trade_name: Optional[str] = Field(default=None, max_length=250)
    pan: Optional[str] = Field(default=None, max_length=20, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$|^PENDING$")
    gstin: Optional[str] = Field(default=None, max_length=20, pattern=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$|^PENDING$")
    cin: Optional[str] = Field(default=None, max_length=30, pattern=r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
    udyam_number: Optional[str] = Field(default=None, max_length=50, pattern=r"^UDYAM-[A-Z]{2}-\d{2}-\d{7}$")
    enterprise_type: Optional[Literal["Micro", "Small", "Medium", "Large", "Unknown"]] = None
    is_startup: Optional[bool] = False
    address: Optional[str] = Field(default=None, max_length=2000)
    state: Optional[str] = Field(default=None, max_length=100)
    district: Optional[str] = Field(default=None, max_length=100)
    contact_email: Optional[str] = Field(default=None, max_length=150)
    contact_phone: Optional[str] = Field(default=None, max_length=50)
    contact_person: Optional[str] = Field(default=None, max_length=150)

# Compliance
class ComplianceResultOut(BaseModel):
    id: int
    tender_bidder_id: int
    requirement_id: Optional[int] = None
    rule_code: str
    rule_name: str
    status: str
    score: float
    explanation: str
    evidence_ids: List[int] = []
    evaluated_at: Optional[datetime] = None

# Risk
class RiskAssessmentOut(BaseModel):
    id: int
    tender_bidder_id: int
    overall_score: float
    overall_category: str
    dimensions: Dict[str, Any]
    explanation: str
    contributing_factors: List[Dict[str, Any]]
    data_sufficiency: str
    model_version: str
    assessed_at: Optional[datetime] = None

# Evidence
class EvidenceRecordOut(BaseModel):
    id: int
    tender_id: Optional[int] = None
    bidder_id: int
    document_id: Optional[int] = None
    ocr_result_id: Optional[int] = None
    verification_result_id: Optional[int] = None
    contract_id: Optional[int] = None
    claim_type: str
    evidence_text: str
    source_reference: str
    confidence: float
    created_at: Optional[datetime] = None

# Bidder
class BidderOut(BaseModel):
    id: int
    legal_name: str
    trade_name: Optional[str] = None
    pan: str
    gstin: str
    cin: Optional[str] = None
    udyam_number: Optional[str] = None
    enterprise_type: str
    is_startup: bool
    address: str
    state: str
    district: str
    contact_email: str
    contact_phone: str
    contact_person: str
    incorporation_date: Optional[str] = None
    created_at: Optional[datetime] = None

class BidderDetailOut(BidderOut):
    documents: List[BidderDocumentOut] = []
    contracts: List[HistoricalContractOut] = []
    compliance_summary: Optional[Dict[str, Any]] = None
    risk_summary: Optional[Dict[str, Any]] = None
    evidence_count: int = 0

# Officer Decision
class OfficerDecisionRequest(BaseModel):
    model_config = {"extra": "forbid"}
    decision: Literal["ACCEPTED", "REJECTED", "MANUAL_REVIEW_REQUESTED"] = Field(..., description="Formal decision entered by the authorized Procurement Officer")
    decision_notes: str = Field(..., min_length=1, max_length=4000)

# Audit Log
class AuditLogOut(BaseModel):
    id: int
    username: str
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    ip_address: str
    details: Dict[str, Any]
    created_at: datetime
    previous_hash: Optional[str] = None
    current_hash: Optional[str] = None

# Reports
class GeneratedReportOut(BaseModel):
    id: int
    report_uid: str
    tender_id: int
    bidder_id: Optional[int] = None
    report_type: str
    filename: str
    file_hash: str
    download_count: int
    created_at: datetime

# Dashboard
class DashboardMetricsOut(BaseModel):
    active_tenders: int
    total_bidders: int
    pending_verifications: int
    completed_verifications: int
    manual_reviews_required: int
    total_documents: int
    analyzed_bidders: int
    overall_compliance_rate: float
    risk_distribution: Dict[str, int]
    attention_documents: List[Dict[str, Any]]
    recent_activity: List[AuditLogOut]
