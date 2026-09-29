export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: string;
  tenant_id: number;
}

export interface TenderRequirement {
  id: number;
  tender_id: number;
  code: string;
  name: string;
  requirement_type: string;
  description: string;
  structured_rule: Record<string, any>;
  source_page: number;
  confidence: number;
  approval_status: 'APPROVED' | 'PENDING' | 'REJECTED' | 'MODIFIED' | 'DISABLED';
  approving_officer_id?: number;
  approved_at?: string;
  officer_notes?: string;
}

export interface TenderBidderSummary {
  id: number;
  legal_name: string;
  trade_name?: string;
  pan: string;
  gstin: string;
  enterprise_type: string;
  is_startup: boolean;
  state: string;
  compliance_status: string;
  compliance_score: number;
  risk_level: string;
  final_decision: string;
  decision_notes?: string;
}

export interface Tender {
  id: number;
  tender_ref: string;
  gem_ref?: string;
  title: string;
  department: string;
  category: string;
  description?: string;
  estimated_value_cr: number;
  issue_date: string;
  closing_date: string;
  status: string;
  pdf_filename?: string;
  created_at?: string;
  requirements: TenderRequirement[];
  bidders_count: number;
  bidders?: TenderBidderSummary[];
}

export interface BidderDocument {
  id: number;
  bidder_id: number;
  tender_id?: number;
  document_type: string;
  filename: string;
  mime_type: string;
  file_hash: string;
  file_size_bytes: number;
  version: number;
  is_active: boolean;
  previous_version_id?: number;
  is_synthetic: boolean;
  created_at?: string;
  ocr_confidence?: number;
  verification_status?: string;
  verification_notes?: string;
}

export interface OCRResult {
  id: number;
  document_id: number;
  extracted_text: string;
  fields: Record<string, any>;
  bounding_boxes: Array<{ page: number; box: number[]; text: string }>;
  confidence: number;
  engine: string;
  model_version: string;
  page_count: number;
  created_at?: string;
}

export interface VerificationResult {
  id: number;
  document_id: number;
  provider_name: string;
  status: 'VERIFIED' | 'FAILED' | 'MISMATCH' | 'MANUAL_REVIEW' | 'PENDING' | 'MISSING' | 'NOT_APPLICABLE' | 'EXPIRED' | 'ERROR' | 'RETRY_REQUIRED';
  raw_response: Record<string, any>;
  discrepancy_notes?: string;
  retry_count: number;
  verified_at?: string;
}

export interface QualityRecord {
  id: number;
  contract_id: number;
  inspection_date: string;
  inspection_agency: string;
  result: string;
  defect_count: number;
  rework_required: boolean;
  warranty_claims: number;
  remarks?: string;
}

export interface HistoricalContract {
  id: number;
  bidder_id: number;
  contract_ref: string;
  procuring_entity: string;
  title: string;
  category: string;
  contract_value_lakhs: number;
  issue_date: string;
  scheduled_completion: string;
  actual_completion?: string;
  status: string;
  delay_days: number;
  documented_delay_cause: string;
  liquidated_damages_inr: number;
  performance_rating: number;
  similarity_score: number;
  quality_records: QualityRecord[];
}

export interface ComplianceResult {
  id: number;
  tender_bidder_id: number;
  requirement_id?: number;
  rule_code: string;
  rule_name: string;
  status: string;
  score: number;
  explanation: string;
  evidence_ids: number[];
  evaluated_at?: string;
}

export interface RiskAssessment {
  id: number;
  tender_bidder_id: number;
  overall_score: number;
  overall_category: 'LOW' | 'MEDIUM' | 'HIGH' | 'INSUFFICIENT_EVIDENCE';
  dimensions: Record<string, { score: number; reason: string }>;
  explanation: string;
  contributing_factors: Array<{ dimension: string; factor: string; impact: string }>;
  data_sufficiency: string;
  model_version: string;
  assessed_at?: string;
}

export interface EvidenceRecord {
  id: number;
  tender_id?: number;
  bidder_id: number;
  document_id?: number;
  ocr_result_id?: number;
  verification_result_id?: number;
  contract_id?: number;
  claim_type: string;
  evidence_text: string;
  source_reference: string;
  confidence: number;
  created_at?: string;
}

export interface AuditLog {
  id: number;
  username: string;
  action: string;
  entity_type: string;
  entity_id?: string;
  ip_address: string;
  details: Record<string, any>;
  created_at: string;
}

export interface GeneratedReport {
  id: number;
  report_uid: string;
  tender_id: number;
  bidder_id?: number;
  report_type: 'QUICK_LIST' | 'DETAILED_ASSESSMENT';
  filename: string;
  file_hash: string;
  download_count: number;
  created_at: string;
}

export interface DashboardMetrics {
  active_tenders: number;
  total_bidders: number;
  pending_verifications: number;
  completed_verifications: number;
  manual_reviews_required: number;
  overall_compliance_rate: number;
  risk_distribution: Record<string, number>;
  attention_documents: Array<{
    document_id: number;
    bidder_id: number;
    bidder_name: string;
    document_type: string;
    status: string;
    notes: string;
    version: number;
  }>;
  recent_activity: AuditLog[];
}
