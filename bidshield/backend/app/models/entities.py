from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float,
    ForeignKey, LargeBinary, JSON, Enum, Index
)
from sqlalchemy.orm import relationship
from app.db.session import Base

def utcnow():
    return datetime.now(timezone.utc)

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    users = relationship("User", back_populates="tenant")
    tenders = relationship("Tender", back_populates="tenant")
    bidders = relationship("Bidder", back_populates="tenant")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default=1)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=False)
    role = Column(String(50), nullable=False, default="PROCUREMENT_OFFICER")
    is_active = Column(Boolean, default=True)
    signature_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    tenant = relationship("Tenant", back_populates="users")

class Tender(Base):
    __tablename__ = "tenders"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default=1)
    tender_ref = Column(String(100), unique=True, index=True, nullable=False)
    gem_ref = Column(String(100), index=True, nullable=True)
    title = Column(String(300), nullable=False)
    department = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    estimated_value_cr = Column(Float, default=1.0)
    issue_date = Column(String(50), nullable=False)
    closing_date = Column(String(50), nullable=False)
    status = Column(String(50), default="ACTIVE") # ACTIVE, EVALUATION, CLOSED, CANCELLED
    pdf_filename = Column(String(200), nullable=True)
    pdf_bytes = Column(LargeBinary, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    tenant = relationship("Tenant", back_populates="tenders")
    requirements = relationship("TenderRequirement", back_populates="tender", cascade="all, delete-orphan")
    tender_bidders = relationship("TenderBidder", back_populates="tender", cascade="all, delete-orphan")

class TenderRequirement(Base):
    __tablename__ = "tender_requirements"
    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, ForeignKey("tenders.id"), nullable=False, index=True)
    code = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    requirement_type = Column(String(50), default="MANDATORY") # MANDATORY, OPTIONAL, TECHNICAL, FINANCIAL
    description = Column(Text, nullable=False)
    structured_rule = Column(JSON, default=dict) # e.g. {"doc_type": "GST", "min_turnover_cr": 5.0}
    source_page = Column(Integer, default=1)
    confidence = Column(Float, default=0.95)
    approval_status = Column(String(50), default="APPROVED") # APPROVED, PENDING, REJECTED, MODIFIED, DISABLED
    approving_officer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    officer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    tender = relationship("Tender", back_populates="requirements")

class Bidder(Base):
    __tablename__ = "bidders"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default=1)
    legal_name = Column(String(250), nullable=False, index=True)
    trade_name = Column(String(250), nullable=True)
    pan = Column(String(20), nullable=False, index=True)
    gstin = Column(String(20), nullable=False, index=True)
    cin = Column(String(30), nullable=True)
    udyam_number = Column(String(50), nullable=True)
    enterprise_type = Column(String(50), default="Medium") # Micro, Small, Medium, Large
    is_startup = Column(Boolean, default=False)
    address = Column(Text, nullable=False)
    state = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    contact_email = Column(String(150), nullable=False)
    contact_phone = Column(String(50), nullable=False)
    contact_person = Column(String(150), nullable=False)
    incorporation_date = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    tenant = relationship("Tenant", back_populates="bidders")
    tender_bidders = relationship("TenderBidder", back_populates="bidder")
    documents = relationship("BidderDocument", back_populates="bidder", cascade="all, delete-orphan")
    contracts = relationship("HistoricalContract", back_populates="bidder", cascade="all, delete-orphan")

class TenderBidder(Base):
    __tablename__ = "tender_bidders"
    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, ForeignKey("tenders.id"), nullable=False, index=True)
    bidder_id = Column(Integer, ForeignKey("bidders.id"), nullable=False, index=True)
    submission_date = Column(String(50), default="2026-09-20")
    compliance_status = Column(String(50), default="PENDING") # VERIFIED, REVIEW_REQUIRED, NON_COMPLIANT, PENDING
    compliance_score = Column(Float, default=0.0) # Percentage 0-100
    risk_level = Column(String(50), default="LOW") # LOW, MEDIUM, HIGH, INSUFFICIENT_EVIDENCE
    final_decision = Column(String(50), default="PENDING") # PENDING, ACCEPTED, REJECTED, MANUAL_REVIEW_REQUESTED
    decision_notes = Column(Text, nullable=True)
    decided_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    tender = relationship("Tender", back_populates="tender_bidders")
    bidder = relationship("Bidder", back_populates="tender_bidders")
    compliance_results = relationship("ComplianceResult", back_populates="tender_bidder", cascade="all, delete-orphan")
    risk_assessments = relationship("RiskAssessment", back_populates="tender_bidder", cascade="all, delete-orphan")

class BidderDocument(Base):
    __tablename__ = "bidder_documents"
    id = Column(Integer, primary_key=True, index=True)
    bidder_id = Column(Integer, ForeignKey("bidders.id"), nullable=False, index=True)
    tender_id = Column(Integer, ForeignKey("tenders.id"), nullable=True, index=True)
    document_type = Column(String(50), nullable=False, index=True) # PAN, GST, UDYAM, OEM, EXPERIENCE, TURNOVER, EPFO, ESIC, MCA, NSIC, STARTUP, LOCAL_CONTENT
    filename = Column(String(250), nullable=False)
    mime_type = Column(String(100), default="application/pdf")
    file_hash = Column(String(64), nullable=False) # SHA-256
    file_size_bytes = Column(Integer, default=0)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    previous_version_id = Column(Integer, ForeignKey("bidder_documents.id"), nullable=True)
    is_synthetic = Column(Boolean, default=True)
    storage_path = Column(String(255), nullable=True)
    content_bytes = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    bidder = relationship("Bidder", back_populates="documents")
    ocr_results = relationship("OCRResult", back_populates="document", cascade="all, delete-orphan")
    verification_results = relationship("VerificationResult", back_populates="document", cascade="all, delete-orphan")

class OCRResult(Base):
    __tablename__ = "ocr_results"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("bidder_documents.id"), nullable=False, index=True)
    extracted_text = Column(Text, nullable=False)
    fields = Column(JSON, default=dict)
    bounding_boxes = Column(JSON, default=list)
    confidence = Column(Float, default=0.0)
    engine = Column(String(100), default="TesseractOCR")
    model_version = Column(String(100), default="tesseract-local")
    page_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=utcnow)

    document = relationship("BidderDocument", back_populates="ocr_results")

class ProviderConfig(Base):
    __tablename__ = "provider_configs"
    id = Column(Integer, primary_key=True, index=True)
    provider_code = Column(String(100), unique=True, nullable=False)
    provider_name = Column(String(200), nullable=False)
    document_type = Column(String(50), nullable=False)
    auth_type = Column(String(50), default="API_KEY") # API_KEY, BEARER, OAUTH2, BASIC, CLIENT_CREDENTIALS, HMAC
    api_endpoint = Column(String(255), default="https://not-configured.invalid/verify")
    is_active = Column(Boolean, default=True)
    timeout_seconds = Column(Integer, default=10)
    retry_limit = Column(Integer, default=3)
    created_at = Column(DateTime, default=utcnow)

class VerificationResult(Base):
    __tablename__ = "verification_results"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("bidder_documents.id"), nullable=False, index=True)
    provider_name = Column(String(150), default="DemoVerificationProvider")
    status = Column(String(50), default="PENDING") # VERIFIED, FAILED, MISMATCH, MANUAL_REVIEW, PENDING, MISSING, NOT_APPLICABLE, EXPIRED, ERROR, RETRY_REQUIRED
    raw_response = Column(JSON, default=dict)
    discrepancy_notes = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    verified_at = Column(DateTime, default=utcnow)

    document = relationship("BidderDocument", back_populates="verification_results")

class HistoricalContract(Base):
    __tablename__ = "historical_contracts"
    id = Column(Integer, primary_key=True, index=True)
    bidder_id = Column(Integer, ForeignKey("bidders.id"), nullable=False, index=True)
    contract_ref = Column(String(100), nullable=False, index=True)
    procuring_entity = Column(String(250), nullable=False)
    title = Column(String(300), nullable=False)
    category = Column(String(100), nullable=False)
    contract_value_lakhs = Column(Float, nullable=False)
    issue_date = Column(String(50), nullable=False)
    scheduled_completion = Column(String(50), nullable=False)
    actual_completion = Column(String(50), nullable=True)
    status = Column(String(50), default="COMPLETED") # COMPLETED, ONGOING, TERMINATED
    delay_days = Column(Integer, default=0)
    documented_delay_cause = Column(String(100), default="NONE") # NONE, CONTRACTOR, PROCURING_ENTITY, FORCE_MAJEURE, APPROVED_EXTENSION
    liquidated_damages_inr = Column(Float, default=0.0)
    performance_rating = Column(Float, default=4.5) # Out of 5.0
    similarity_score = Column(Float, default=0.85) # Comparable contract intelligence similarity
    created_at = Column(DateTime, default=utcnow)

    bidder = relationship("Bidder", back_populates="contracts")
    quality_records = relationship("QualityInspectionRecord", back_populates="contract", cascade="all, delete-orphan")

class QualityInspectionRecord(Base):
    __tablename__ = "quality_inspection_records"
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("historical_contracts.id"), nullable=False, index=True)
    inspection_date = Column(String(50), nullable=False)
    inspection_agency = Column(String(200), default="Third-Party Inspection Agency (TPIA)")
    result = Column(String(50), default="PASS") # PASS, FAIL, CONDITIONAL
    defect_count = Column(Integer, default=0)
    rework_required = Column(Boolean, default=False)
    warranty_claims = Column(Integer, default=0)
    remarks = Column(Text, nullable=True)

    contract = relationship("HistoricalContract", back_populates="quality_records")

class ComplianceResult(Base):
    __tablename__ = "compliance_results"
    id = Column(Integer, primary_key=True, index=True)
    tender_bidder_id = Column(Integer, ForeignKey("tender_bidders.id"), nullable=False, index=True)
    requirement_id = Column(Integer, ForeignKey("tender_requirements.id"), nullable=True)
    rule_code = Column(String(50), nullable=False)
    rule_name = Column(String(200), nullable=False)
    status = Column(String(50), default="PASS") # PASS, FAIL, REVIEW, MISSING, EXPIRED
    score = Column(Float, default=1.0)
    explanation = Column(Text, nullable=False)
    evidence_ids = Column(JSON, default=list)
    evaluated_at = Column(DateTime, default=utcnow)

    tender_bidder = relationship("TenderBidder", back_populates="compliance_results")
    requirement = relationship("TenderRequirement")

class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    id = Column(Integer, primary_key=True, index=True)
    tender_bidder_id = Column(Integer, ForeignKey("tender_bidders.id"), nullable=False, index=True)
    overall_score = Column(Float, default=20.0) # 0 to 100
    overall_category = Column(String(50), default="LOW") # LOW, MEDIUM, HIGH, INSUFFICIENT_EVIDENCE
    dimensions = Column(JSON, default=dict) # 8 dimensions
    explanation = Column(Text, nullable=False)
    contributing_factors = Column(JSON, default=list)
    data_sufficiency = Column(String(50), default="HIGH") # HIGH, MODERATE, LOW, INSUFFICIENT
    model_version = Column(String(100), default="bidshield-risk-v1.8")
    assessed_at = Column(DateTime, default=utcnow)

    tender_bidder = relationship("TenderBidder", back_populates="risk_assessments")

class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, nullable=True, index=True)
    bidder_id = Column(Integer, nullable=False, index=True)
    document_id = Column(Integer, nullable=True)
    ocr_result_id = Column(Integer, nullable=True)
    verification_result_id = Column(Integer, nullable=True)
    contract_id = Column(Integer, nullable=True)
    claim_type = Column(String(100), nullable=False) # GST_VERIFICATION, PAN_VERIFICATION, PERFORMANCE, ANOMALY, RISK
    evidence_text = Column(Text, nullable=False)
    source_reference = Column(String(250), nullable=False)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, default=1, index=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(100), default="system")
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(100), nullable=True)
    ip_address = Column(String(50), default="127.0.0.1")
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)
    previous_hash = Column(String(64), nullable=True, index=True)
    current_hash = Column(String(64), nullable=True, unique=True, index=True)

class AuditChainHead(Base):
    __tablename__ = "audit_chain_heads"
    tenant_id = Column(Integer, primary_key=True)
    last_event_id = Column(Integer, nullable=True)
    last_hash = Column(String(64), nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

class GeneratedReport(Base):
    __tablename__ = "generated_reports"
    id = Column(Integer, primary_key=True, index=True)
    report_uid = Column(String(64), unique=True, index=True, nullable=False)
    tender_id = Column(Integer, nullable=False, index=True)
    bidder_id = Column(Integer, nullable=True, index=True)
    report_type = Column(String(50), nullable=False) # QUICK_LIST, DETAILED_ASSESSMENT
    filename = Column(String(250), nullable=False)
    file_hash = Column(String(64), nullable=False)
    file_bytes = Column(LargeBinary, nullable=False)
    generated_by_id = Column(Integer, nullable=True)
    download_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
