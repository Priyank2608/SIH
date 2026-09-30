'use client';
import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import StatusBadge from '../../../components/StatusBadge';
import BulkBidderUpload from '../../../components/BulkBidderUpload';
import OCRInspectorModal from '../../../components/OCRInspectorModal';
import DecisionModal from '../../../components/DecisionModal';
import EvidenceModal from '../../../components/EvidenceModal';
import PermissionGate from '../../../components/PermissionGate';
import { api, downloadFile, API_BASE } from '../../../lib/api';
import { useCurrentUser } from '../../../lib/userContext';
import { can } from '../../../lib/permissions';
import { Users, Upload as UploadIcon } from 'lucide-react';

type TabKey =
  | 'OVERVIEW'
  | 'REQUIREMENTS'
  | 'BIDDERS'
  | 'DOCUMENTS'
  | 'VERIFICATION'
  | 'COMPLIANCE'
  | 'PERFORMANCE'
  | 'RISK'
  | 'EVIDENCE'
  | 'REPORTS'
  | 'AUDIT';

export default function TenderWorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const [tender, setTender] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const currentUser = useCurrentUser();
  const userRole = currentUser?.role || '';
  const [activeTab, setActiveTab] = useState<TabKey>('OVERVIEW');

  // Interactive States
  const [busyBidderId, setBusyBidderId] = useState<number | null>(null);
  const [extractingReqs, setExtractingReqs] = useState(false);
  const [inspectDocId, setInspectDocId] = useState<number | null>(null);
  const [decisionModal, setDecisionModal] = useState<{ open: boolean; bidderId: number; bidderName: string; currentDecision?: string } | null>(null);
  const [evidenceModal, setEvidenceModal] = useState<{ open: boolean; bidderId: number; bidderName: string } | null>(null);

  // Tab Data States
  const [complianceMatrix, setComplianceMatrix] = useState<any>(null);
  const [tenderDocs, setTenderDocs] = useState<any[]>([]);
  const [tenderAudit, setTenderAudit] = useState<any[]>([]);
  const [evidenceItems, setEvidenceItems] = useState<any[]>([]);
  const [performanceByBidder, setPerformanceByBidder] = useState<Record<number, any>>({});
  const [performanceLoading, setPerformanceLoading] = useState(false);
  const [performanceError, setPerformanceError] = useState('');
  const [performanceLoaded, setPerformanceLoaded] = useState(false);
  const [generatingReport, setGeneratingReport] = useState<string | null>(null);

  // Add Requirement Modal State
  const [showAddReq, setShowAddReq] = useState(false);
  const [newReq, setNewReq] = useState({
    code: '',
    name: '',
    requirement_type: 'MANDATORY',
    description: '',
  });

  // Tender document upload (officer action)
  const tenderPdfInputRef = useRef<HTMLInputElement>(null);
  const [uploadingPdf, setUploadingPdf] = useState(false);

  // Bidder enrollment (bid intake entry point)
  const [showEnroll, setShowEnroll] = useState(false);
  const [enrollForm, setEnrollForm] = useState({ legal_name: '', pan: '', gstin: '' });
  const [enrolling, setEnrolling] = useState(false);

  // Bulk bid-document intake (Documents tab) — reset selection when switching away
  const [bulkUploadOpen, setBulkUploadOpen] = useState(false);

  async function loadTender() {
    try {
      setLoading(true);
      setLoadError('');
      setPerformanceLoaded(false);
      const t = await api(`/tenders/${id}`);
      setTender(t);

      // Preload ancillary tab data
      const [matrix, docs, auditLogs, evs] = await Promise.all([
        api(`/tenders/${id}/compliance-matrix`).catch(() => null),
        api(`/documents?tender_id=${id}`).catch(() => []),
        api(`/audit?limit=25`).catch(() => []),
        api(`/tenders/${id}/evidence`).catch(() => []),
      ]);

      setComplianceMatrix(matrix);
      setTenderDocs(docs);
      setTenderAudit(auditLogs);
      setEvidenceItems(evs);
    } catch (err: any) {
      setLoadError(err.message || 'Unable to load this tender workspace.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTender();
  }, [id]);

  useEffect(() => {
    if (activeTab !== 'PERFORMANCE' || !tender || performanceLoaded) return;
    let cancelled = false;
    setPerformanceLoading(true);
    setPerformanceError('');
    Promise.all(tender.bidders.map(async (bidder: any) => {
      try { return [bidder.id, await api(`/bidders/${bidder.id}/performance?tender=${tender.id}`)] as const; }
      catch { return [bidder.id, null] as const; }
    })).then((rows) => {
      if (cancelled) return;
      setPerformanceByBidder(Object.fromEntries(rows));
      if (rows.some(([, value]) => value === null)) setPerformanceError('Some bidder performance records could not be loaded.');
      setPerformanceLoaded(true);
    }).finally(() => { if (!cancelled) setPerformanceLoading(false); });
    return () => { cancelled = true; };
  }, [activeTab, tender, performanceLoaded]);

  // AI Extract Requirements
  const handleExtractReqs = async () => {
    try {
      setExtractingReqs(true);
      await api(`/tenders/${id}/extract-requirements`, { method: 'POST' });
      await loadTender();
    } catch (err: any) {
      alert(err.message || 'Failed to extract requirements');
    } finally {
      setExtractingReqs(false);
    }
  };

  // Requirement Actions
  const handleApproveReq = async (reqId: number) => {
    try {
      await api(`/tenders/${id}/requirements/${reqId}/approve`, { method: 'POST' });
      await loadTender();
    } catch (err: any) {
      alert(err.message || 'Failed to approve requirement');
    }
  };

  const handleRejectReq = async (reqId: number) => {
    try {
      await api(`/tenders/${id}/requirements/${reqId}/reject`, { method: 'POST' });
      await loadTender();
    } catch (err: any) {
      alert(err.message || 'Failed to reject requirement');
    }
  };

  const handleAddRequirement = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api(`/tenders/${id}/requirements`, {
        method: 'POST',
        body: JSON.stringify(newReq),
      });
      setShowAddReq(false);
      setNewReq({ code: '', name: '', requirement_type: 'MANDATORY', description: '' });
      await loadTender();
    } catch (err: any) {
      alert(err.message || 'Failed to add requirement');
    }
  };

  // Run AI Analysis for a Bidder
  const handleAnalyzeBidder = async (bidderId: number) => {
    try {
      setBusyBidderId(bidderId);
      await api(`/tenders/${id}/bidders/${bidderId}/analyze`, { method: 'POST' });
      await loadTender();
    } catch (err: any) {
      alert(err.message || 'Analysis failed');
    } finally {
      setBusyBidderId(null);
    }
  };

  // Tender document upload — validates and stores the official tender PDF.
  const handleTenderPdfUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.type !== 'application/pdf') {
      alert('Only PDF tender documents are accepted.');
      e.target.value = '';
      return;
    }
    try {
      setUploadingPdf(true);
      const formData = new FormData();
      formData.append('file', file);
      await api(`/tenders/${id}/pdf`, { method: 'POST', body: formData });
      // Offer requirement extraction from the freshly stored document.
      try { await api(`/tenders/${id}/extract-requirements`, { method: 'POST' }); } catch { /* officer can re-run manually */ }
      await loadTender();
    } catch (err: any) {
      alert(err.message || 'Tender document upload failed');
    } finally {
      setUploadingPdf(false);
      if (tenderPdfInputRef.current) tenderPdfInputRef.current.value = '';
    }
  };

  // Bidder enrollment — creates the bidder shell and attaches it to this tender.
  const handleEnrollBidder = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setEnrolling(true);
      await api('/bidders', {
        method: 'POST',
        body: JSON.stringify({
          tender_id: parseInt(id as string),
          legal_name: enrollForm.legal_name.trim(),
          pan: enrollForm.pan.trim() || undefined,
          gstin: enrollForm.gstin.trim() || undefined,
        }),
      });
      setShowEnroll(false);
      setEnrollForm({ legal_name: '', pan: '', gstin: '' });
      await loadTender();
    } catch (err: any) {
      alert(err.message || 'Failed to enroll bidder');
    } finally {
      setEnrolling(false);
    }
  };

  // Generate Reports
  const handleGenerateQuickReport = async () => {
    try {
      setGeneratingReport('QUICK');
      const res = await api('/reports/quick-list', {
        method: 'POST',
        body: JSON.stringify({ tender_id: parseInt(id as string) }),
      });
      await downloadFile(`/reports/${res.report_uid}/download`, res.filename);
    } catch (err: any) {
      alert(err.message || 'Failed to generate report');
    } finally {
      setGeneratingReport(null);
    }
  };

  const handleGenerateDetailedReport = async (bidderId: number) => {
    try {
      setGeneratingReport(`DETAILED_${bidderId}`);
      const res = await api('/reports/detailed-assessment', {
        method: 'POST',
        body: JSON.stringify({ tender_id: parseInt(id as string), bidder_id: bidderId }),
      });
      await downloadFile(`/reports/${res.report_uid}/download`, res.filename);
    } catch (err: any) {
      alert(err.message || 'Failed to generate report');
    } finally {
      setGeneratingReport(null);
    }
  };

  if (loading || !tender) {
    return (
      <div className="main-wrapper" style={{ textAlign: 'center', padding: '40px' }}>
        {loadError
          ? <div className="alert alert-danger" role="alert">
              {loadError}
              <button className="btn btn-sm btn-outline" onClick={loadTender} style={{ marginLeft: '10px' }}>Retry</button>
            </div>
          : <><div className="spinner" aria-label="Loading tender workspace"></div><p style={{ marginTop: '12px', color: 'var(--text-muted)' }}>Loading tender workspace…</p></>}
      </div>
    );
  }

  const tabs: Array<{ key: TabKey; label: string; count?: number }> = [
    { key: 'OVERVIEW', label: 'Overview' },
    { key: 'REQUIREMENTS', label: 'Requirements', count: tender.requirements?.length },
    { key: 'BIDDERS', label: 'Bidders', count: tender.bidders?.length },
    { key: 'DOCUMENTS', label: 'Documents', count: tenderDocs.length },
    { key: 'VERIFICATION', label: 'Verification' },
    { key: 'COMPLIANCE', label: 'Compliance Matrix' },
    { key: 'PERFORMANCE', label: 'Past Performance' },
    { key: 'RISK', label: 'Risk Intelligence' },
    { key: 'EVIDENCE', label: 'Evidence Graph', count: evidenceItems.length },
    { key: 'REPORTS', label: 'Secure Reports' },
    { key: 'AUDIT', label: 'Audit Trail' },
  ];

  return (
    <main className="main-wrapper">
        {/* Structured tender header — reference block, not a banner card */}
        <div className="page-header">
          <div className="page-header-text">
            <div className="page-eyebrow">Tender Workspace</div>
            <h1 className="page-title">{tender.title}</h1>
            <p className="page-desc">
              {tender.department} · {tender.category}
            </p>
          </div>
          <div className="page-actions">
            {can(userRole, 'tender.edit') && (
              <>
                <input
                  ref={tenderPdfInputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  style={{ display: 'none' }}
                  onChange={handleTenderPdfUpload}
                  aria-hidden="true"
                />
                <button
                  className="btn btn-outline"
                  onClick={() => tenderPdfInputRef.current?.click()}
                  disabled={uploadingPdf}
                  title={tender.pdf_filename ? `Replace tender document (current: ${tender.pdf_filename})` : 'Upload the complete tender document (PDF)'}
                >
                  {uploadingPdf ? 'Uploading…' : tender.pdf_filename ? 'Replace Tender Document' : 'Upload Tender Document'}
                </button>
                <button
                  className="btn btn-outline"
                  onClick={handleExtractReqs}
                  disabled={extractingReqs}
                >
                  {extractingReqs ? 'Extracting…' : 'Re-extract Requirements'}
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => setShowEnroll(true)}
                >
                  + Enroll Bidder
                </button>
              </>
            )}
            <button
              className="btn btn-primary"
              onClick={handleGenerateQuickReport}
              disabled={generatingReport === 'QUICK'}
            >
              {generatingReport === 'QUICK' ? 'Compiling PDF…' : 'Generate Quick Summary PDF'}
            </button>
          </div>
        </div>

        {/* Reference strip — monospace identifiers, ledger style */}
        <div
          className="mono"
          style={{
            display: 'flex', gap: '22px', flexWrap: 'wrap', alignItems: 'baseline',
            borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)',
            padding: '9px 0', fontSize: '12px', color: 'var(--text-muted)',
            marginBottom: '0',
          }}
          aria-label="Tender reference details"
        >
          <span>Tender&nbsp;<b style={{ color: 'var(--text-primary)' }}>{tender.tender_ref}</b></span>
          <span>Status&nbsp;<StatusBadge status={tender.status} size="sm" /></span>
          <span>Value&nbsp;<b style={{ color: 'var(--text-primary)', fontWeight: 500 }}>₹{tender.estimated_value_cr} Cr</b></span>
          <span>Closing&nbsp;<b style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{tender.closing_date}</b></span>
          <span>
            Tender Document&nbsp;<b style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
              {tender.pdf_filename || 'Not uploaded yet'}
            </b>
          </span>
        </div>

        {/* Working tabs */}
        <nav className="workspace-tabs" aria-label="Tender Workspace Tabs">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              className={`workspace-tab ${activeTab === tab.key ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
              {tab.count !== undefined && <span className="mono text-muted ml-1" style={{ fontSize: '10.5px' }}>({tab.count})</span>}
            </button>
          ))}
        </nav>

        {/* Tab 1: OVERVIEW */}
        {activeTab === 'OVERVIEW' && (
          <div className="tab-pane">
            {/* Figure index — ledger style, not stat cards */}
            <div className="metric-strip mb-4" aria-label="Tender figures">
              <div className="metric-cell">
                <div className="metric-value">{tender.bidders?.length || 0}</div>
                <div className="metric-label">Participating Bidders</div>
                <div className="metric-change">Screened across criteria</div>
              </div>
              <div className="metric-cell ok">
                <div className="metric-value">
                  {tender.requirements?.filter((r: any) => r.approval_status === 'APPROVED').length || 0}
                </div>
                <div className="metric-label">Approved Requirements</div>
                <div className="metric-change">Out of {tender.requirements?.length || 0} extracted</div>
              </div>
              <div className="metric-cell">
                <div className="metric-value">{tenderDocs.length}</div>
                <div className="metric-label">Submitted Documents</div>
                <div className="metric-change">Versioned submissions</div>
              </div>
            </div>

            <div className="section-header">
              <div>
                <span className="section-title">Procurement Scope &amp; Objective</span>
              </div>
            </div>
            <p className="text-sm" style={{ maxWidth: '860px', lineHeight: 1.65, marginBottom: '26px' }}>
              {tender.description || 'Enterprise procurement for government department specifications.'}
            </p>

            <div className="section-header">
              <div>
                <span className="section-title">Executive Bidder Roster</span>
                <div className="section-sub">Use Bidders tab for full actions &amp; decisions</div>
              </div>
            </div>
            <div className="table-wrapper" style={{ marginBottom: '10px' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Bidder Legal Name</th>
                    <th>PAN / GSTIN</th>
                    <th>Compliance Status</th>
                    <th>Score</th>
                    <th>Risk Category</th>
                    <th>Officer Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {tender.bidders?.length === 0 && (
                    <tr>
                      <td colSpan={6}>
                        <div className="state-wrapper" style={{ padding: '26px 24px' }}>
                          <Users size={26} className="state-icon" aria-hidden="true" />
                          <div className="state-title">No bidder submissions uploaded yet</div>
                          <div className="state-desc">Enroll bidders and upload their documents to begin scrutiny.</div>
                          {can(userRole, 'tender.edit') && (
                            <button className="btn btn-primary btn-sm" style={{ marginTop: '12px' }} onClick={() => setShowEnroll(true)}>
                              + Enroll First Bidder
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                  {tender.bidders?.map((b: any) => (
                    <tr key={b.id}>
                      <td>
                        <Link href={`/bidders/${b.id}?tender=${tender.id}`} className="font-semibold">
                          {b.legal_name}
                        </Link>
                        <div className="text-xs text-muted">{b.state} • {b.enterprise_type}</div>
                      </td>
                      <td className="font-mono text-xs">{b.pan}<br/>{b.gstin}</td>
                      <td><StatusBadge status={b.compliance_status} size="sm" /></td>
                      <td className="font-bold">{b.compliance_score?.toFixed(1)}%</td>
                      <td><StatusBadge status={b.risk_level} size="sm" /></td>
                      <td><StatusBadge status={b.final_decision} size="sm" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 2: REQUIREMENTS */}
        {activeTab === 'REQUIREMENTS' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Tender Compliance Requirements &amp; Rules</span>
                <div className="section-sub">
                  AI extracts criteria from tender PDFs. Authorized Procurement Officers must review, approve, modify, or reject each condition.
                </div>
              </div>
              <div className="section-actions">
                <button
                  className="btn btn-sm btn-outline"
                  onClick={() => {
                    setNewReq({
                      code: `REQ-00${(tender.requirements?.length || 0) + 1}`,
                      name: '',
                      requirement_type: 'MANDATORY',
                      description: '',
                    });
                    setShowAddReq(true);
                  }}
                >
                  + Add Custom Requirement
                </button>
                <button
                  className="btn btn-sm btn-primary"
                  onClick={handleExtractReqs}
                  disabled={extractingReqs}
                >
                  {extractingReqs ? 'Extracting…' : 'Re-extract via AI'}
                </button>
              </div>
            </div>
            <div className="table-wrapper">
              <table className="data-table">
                  <thead>
                    <tr>
                      <th>Rule Code</th>
                      <th>Requirement Title</th>
                      <th>Type</th>
                      <th>Description / Structured Mandate</th>
                      <th>AI Confidence</th>
                      <th>Approval Status</th>
                      <th>Officer Notes</th>
                      <th>Officer Authority Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tender.requirements?.map((r: any) => (
                      <tr key={r.id}>
                        <td className="font-mono font-bold">{r.code}</td>
                        <td className="font-semibold">{r.name}</td>
                        <td>
                          <span className="badge-neutral" style={{ padding: '2px 6px', fontSize: '11px', borderRadius: '4px' }}>
                            {r.requirement_type}
                          </span>
                        </td>
                        <td className="text-sm" style={{ maxWidth: '300px' }}>
                          {r.description}
                          {r.structured_rule && Object.keys(r.structured_rule).length > 0 && (
                            <div className="text-xs text-muted font-mono mt-1">
                              Rule: {JSON.stringify(r.structured_rule)}
                            </div>
                          )}
                        </td>
                        <td>
                          <span className="font-bold text-xs" style={{ color: r.confidence >= 0.9 ? 'var(--success)' : 'var(--warning)' }}>
                            {(r.confidence * 100).toFixed(0)}% (p.{r.source_page})
                          </span>
                        </td>
                        <td><StatusBadge status={r.approval_status} size="sm" /></td>
                        <td className="text-xs text-muted" style={{ maxWidth: '180px' }}>
                          {r.officer_notes || '—'}
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            {r.approval_status !== 'APPROVED' && (
                              <button
                                className="btn btn-sm btn-primary"
                                onClick={() => handleApproveReq(r.id)}
                                title="Approve Requirement"
                              >
                                Approve
                              </button>
                            )}
                            {r.approval_status !== 'REJECTED' && (
                              <button
                                className="btn btn-sm btn-outline"
                                onClick={() => handleRejectReq(r.id)}
                                title="Reject Requirement"
                              >
                                Reject
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            </div>


            {/* Add Requirement Modal */}
            {showAddReq && (
              <div className="modal-overlay" onClick={() => setShowAddReq(false)}>
                <div className="modal-container modal-md" role="dialog" aria-modal="true" aria-label="Add tender requirement" onClick={(e) => e.stopPropagation()}>
                  <div className="modal-header">
                    <h2 className="modal-title">Add Official Tender Requirement</h2>
                    <button className="btn-close" onClick={() => setShowAddReq(false)} aria-label="Close requirement dialog">✕</button>
                  </div>
                  <form onSubmit={handleAddRequirement}>
                    <div className="modal-body">
                      <div className="grid-2">
                        <div className="form-group">
                          <label className="form-label">Rule Code *</label>
                          <input
                            type="text"
                            className="form-input"
                            value={newReq.code}
                            onChange={(e) => setNewReq({ ...newReq, code: e.target.value })}
                            required
                          />
                        </div>
                        <div className="form-group">
                          <label className="form-label">Requirement Type</label>
                          <select
                            className="form-select"
                            value={newReq.requirement_type}
                            onChange={(e) => setNewReq({ ...newReq, requirement_type: e.target.value })}
                          >
                            <option value="MANDATORY">MANDATORY</option>
                            <option value="OPTIONAL">OPTIONAL</option>
                            <option value="TECHNICAL">TECHNICAL</option>
                            <option value="FINANCIAL">FINANCIAL</option>
                          </select>
                        </div>
                      </div>
                      <div className="form-group">
                        <label className="form-label">Requirement Title *</label>
                        <input
                          type="text"
                          className="form-input"
                          value={newReq.name}
                          onChange={(e) => setNewReq({ ...newReq, name: e.target.value })}
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Description & Validation Mandate *</label>
                        <textarea
                          className="form-textarea"
                          rows={3}
                          value={newReq.description}
                          onChange={(e) => setNewReq({ ...newReq, description: e.target.value })}
                          required
                        />
                      </div>
                    </div>
                    <div className="modal-footer">
                      <button type="button" className="btn btn-outline" onClick={() => setShowAddReq(false)}>Cancel</button>
                      <button type="submit" className="btn btn-primary">Save & Approve Requirement</button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: BIDDERS */}
        {activeTab === 'BIDDERS' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Participating Bidder Evaluations</span>
                <div className="section-sub">
                  Run automated pipeline (OCR + Verification + Deterministic Compliance + Risk) and commit final officer determinations.
                </div>
              </div>
            </div>

            <div className="table-wrapper">
              <table className="data-table">
                  <thead>
                    <tr>
                      <th>Bidder Legal Entity</th>
                      <th>Tax Identifiers</th>
                      <th>Compliance State</th>
                      <th>Score</th>
                      <th>Risk Dimension</th>
                      <th>Officer Decision</th>
                      <th>Actions</th>
                    </tr>
                  </thead>                <tbody>
                  {tender.bidders?.length === 0 && (
                    <tr>
                      <td colSpan={7}>
                        <div className="state-wrapper" style={{ padding: '26px 24px' }}>
                          <Users size={26} className="state-icon" aria-hidden="true" />
                          <div className="state-title">No bidder submissions uploaded yet</div>
                          <div className="state-desc">Enroll a bidder, then upload their bid documents from the bidder dossier.</div>
                          {can(userRole, 'tender.edit') && (
                            <button className="btn btn-primary btn-sm" style={{ marginTop: '12px' }} onClick={() => setShowEnroll(true)}>
                              + Enroll First Bidder
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                  {tender.bidders?.map((b: any) => (
                  <tr key={b.id}>
                        <td>
                          <Link href={`/bidders/${b.id}?tender=${tender.id}`} className="font-semibold text-main">
                            {b.legal_name}
                          </Link>
                          <div className="text-xs text-muted">{b.state} • {b.enterprise_type} {b.is_startup ? '• Startup' : ''}</div>
                        </td>
                        <td className="font-mono text-xs">
                          PAN: {b.pan}<br/>GSTIN: {b.gstin}
                        </td>
                        <td><StatusBadge status={b.compliance_status} size="sm" /></td>
                        <td className="font-bold">{b.compliance_score?.toFixed(1)}%</td>
                        <td><StatusBadge status={b.risk_level} size="sm" /></td>
                        <td><StatusBadge status={b.final_decision} size="sm" /></td>
                        <td>
                          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                            <button
                              className="btn btn-sm btn-primary"
                              onClick={() => handleAnalyzeBidder(b.id)}
                              disabled={busyBidderId === b.id}
                            >
                              {busyBidderId === b.id ? 'Analyzing…' : 'Run AI Analysis'}
                            </button>
                            <button
                              className="btn btn-sm btn-outline"
                              onClick={() => setDecisionModal({ open: true, bidderId: b.id, bidderName: b.legal_name, currentDecision: b.final_decision })}
                              disabled={!can(userRole, 'decision.create')}
                            >
                              Record Decision
                            </button>
                            <Link
                              href={`/bidders/${b.id}?tender=${tender.id}`}
                              className="btn btn-sm btn-outline"
                            >
                              Bidder 360 →
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            </div>

          </div>
        )}

        {/* Tab 4: DOCUMENTS */}
        {activeTab === 'DOCUMENTS' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Tender Document Repository</span>
                <div className="section-sub">Versioned bidder submissions with SHA-256 content hashes</div>
              </div>
              <div className="section-actions">
                {can(userRole, 'document.upload') && (tender.bidders?.length ?? 0) > 0 && (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => setBulkUploadOpen(v => !v)}
                    aria-expanded={bulkUploadOpen}
                    aria-controls="bulk-upload-workspace"
                  >
                    {bulkUploadOpen ? 'Close Bulk Upload' : 'Bulk Upload Documents'}
                  </button>
                )}
              </div>
            </div>

            {/* Bulk bid-document intake — group files by bidder with live per-bidder status */}
            {bulkUploadOpen && can(userRole, 'document.upload') && (
              <div id="bulk-upload-workspace" className="card" style={{ padding: '16px', marginBottom: '18px' }}>
                <div className="section-header section-header-soft" style={{ marginBottom: '10px' }}>
                  <div>
                    <span className="section-title">Bulk Bid Intake</span>
                    <div className="section-sub">Drop PDFs for multiple bidders at once — files are grouped per bidder with live upload status</div>
                  </div>
                </div>
                <BulkBidderUpload
                  bidders={(tender.bidders || []).map((b: any) => ({ id: b.id, legal_name: b.legal_name }))}
                  tenderId={tender.id}
                  onComplete={loadTender}
                />
              </div>
            )}

            <div className="table-wrapper">
              <table className="data-table">
                  <thead>
                    <tr>
                      <th>Doc ID</th>
                      <th>Bidder</th>
                      <th>Document Type</th>
                      <th>Version</th>
                      <th>SHA-256 Hash</th>
                      <th>OCR Confidence</th>
                      <th>Verification Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tenderDocs.length === 0 && (
                      <tr>
                        <td colSpan={8}>
                          <div className="state-wrapper" style={{ padding: '24px' }}>
                            <UploadIcon size={24} className="state-icon" aria-hidden="true" />
                            <div className="state-title">No bidder documents have been uploaded</div>
                            <div className="state-desc">Upload bid documents from each bidder&apos;s dossier after enrollment.</div>
                            {can(userRole, 'document.upload') && (tender.bidders?.length ?? 0) > 0 && (
                              <button className="btn btn-primary btn-sm" style={{ marginTop: '12px' }} onClick={() => setBulkUploadOpen(true)}>
                                Bulk Upload Bid Documents
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                    {tenderDocs.map((doc: any) => (
                      <tr key={doc.id}>
                        <td className="font-mono">#{doc.id}</td>
                        <td>
                          <Link href={`/bidders/${doc.bidder_id}?tender=${tender.id}`}>
                            <b>{doc.bidder_name || `Bidder #${doc.bidder_id}`}</b>
                          </Link>
                        </td>
                        <td><span className="font-semibold">{doc.document_type}</span></td>
                        <td>v{doc.version} {doc.is_active ? '(Active)' : '(Superseded)'}</td>
                        <td className="font-mono text-xs">{doc.file_hash?.substring(0, 16)}...</td>
                        <td>
                          {doc.ocr_confidence !== null && doc.ocr_confidence !== undefined ? (
                            <span className="font-bold text-xs" style={{ color: doc.ocr_confidence >= 0.8 ? 'var(--success)' : 'var(--warning)' }}>
                              {(doc.ocr_confidence * 100).toFixed(0)}%
                            </span>
                          ) : 'Pending'}
                        </td>
                        <td><StatusBadge status={doc.verification_status || 'PENDING'} size="sm" /></td>
                        <td>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button
                              className="btn btn-sm btn-outline"
                              onClick={() => setInspectDocId(doc.id)}
                            >
                              Inspect OCR
                            </button>
                            <a
                              href={`${API_BASE}/documents/${doc.id}/file`}
                              target="_blank"
                              rel="noreferrer"
                              className="btn btn-sm btn-outline"
                            >
                              View PDF ↗
                            </a>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            </div>
          </div>
        )}

        {/* Tab 5: VERIFICATION */}
        {activeTab === 'VERIFICATION' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Tender Document Verification Operations</span>
                <div className="section-sub">Adapter registry dispatching to GSTN, NSDL PAN, Udyam, and OEM portals</div>
              </div>
              <div className="section-actions">
                <Link href="/verification" className="btn btn-sm btn-outline">
                  Global Verification Center →
                </Link>
              </div>
            </div>

            <div className="table-wrapper">
              <table className="data-table">
                  <thead>
                    <tr>
                      <th>Document</th>
                      <th>Bidder</th>
                      <th>Type</th>
                      <th>Provider Engine</th>
                      <th>Verification Status</th>
                      <th>Discrepancy / Outcome Notes</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tenderDocs.map((doc: any) => (
                      <tr key={doc.id}>
                        <td className="font-mono">Doc #{doc.id}</td>
                        <td><b>{doc.bidder_name || `Bidder #${doc.bidder_id}`}</b></td>
                        <td>{doc.document_type} v{doc.version}</td>
                        <td className="text-xs font-mono">DemoRegistryProvider</td>
                        <td><StatusBadge status={doc.verification_status || 'PENDING'} size="sm" /></td>
                        <td className="text-sm">{doc.verification_notes || 'Confirmed authentic against synthetic registry.'}</td>
                        <td>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button
                              className="btn btn-sm btn-primary"
                              onClick={async () => {
                                await api(`/documents/${doc.id}/verify`, { method: 'POST' });
                                await loadTender();
                              }}
                            >
                              Re-Verify
                            </button>
                            <button
                              className="btn btn-sm btn-outline"
                              onClick={() => setInspectDocId(doc.id)}
                            >
                              OCR Data
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            </div>
          </div>
        )}

        {/* Tab 6: COMPLIANCE MATRIX */}
        {activeTab === 'COMPLIANCE' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Deterministic Rule Compliance Matrix</span>
                <div className="section-sub">
                  Requirement-by-requirement evaluation for all participating bidders. The rule engine never determines qualification.
                </div>
              </div>
            </div>

            {complianceMatrix ? (
              <div className="table-wrapper">
                <table className="data-table">
                    <thead>
                      <tr>
                        <th>Bidder Legal Name</th>
                        <th>Overall Score</th>
                        <th>Status</th>
                        {complianceMatrix.requirements?.map((req: any) => (
                          <th key={req.code} title={req.name}>
                            {req.code}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {complianceMatrix.matrix?.map((row: any) => (
                        <tr key={row.bidder_id}>
                          <td>
                            <Link href={`/bidders/${row.bidder_id}?tender=${tender.id}`} className="font-semibold">
                              {row.legal_name}
                            </Link>
                          </td>
                          <td className="td-num font-mono">{row.compliance_score?.toFixed(1)}%</td>
                          <td><StatusBadge status={row.compliance_status} size="sm" /></td>
                          {complianceMatrix.requirements?.map((req: any) => {
                            const evalItem = row.evaluations?.[req.code];
                            return (
                              <td key={req.code} title={evalItem?.explanation || ''}>
                                <StatusBadge status={evalItem?.status || 'MISSING'} size="sm" />
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
              </div>
              ) : (
                <div className="state-wrapper"><div className="spinner" aria-hidden="true" /><p className="state-desc">Loading compliance matrix…</p></div>
              )}
          </div>
        )}

        {/* Tab 7: PERFORMANCE */}
        {activeTab === 'PERFORMANCE' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Historical Contract Performance &amp; Delivery Tracking</span>
                <div className="section-sub">
                  Tracks documented delay causes (Contractor vs Procuring Entity vs Force Majeure) without presuming delay is contractor fault.
                </div>
              </div>
            </div>

            {performanceLoading && <p role="status" className="text-sm text-muted" style={{ marginBottom: '10px' }}>Loading backend performance records…</p>}
            {performanceError && <div role="alert" className="alert alert-danger mb-4">{performanceError}</div>}

            <div className="table-wrapper">
              <table className="data-table">
                  <thead>
                    <tr>
                      <th>Bidder</th>
                      <th>Past Contracts</th>
                      <th>On-Time Rate</th>
                      <th>Liquidated Damages</th>
                      <th>Inspection Pass Rate</th>
                      <th>Key Delivery Insight</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tender.bidders?.map((b: any) => (
                      <tr key={b.id}>
                        <td>
                          <Link href={`/bidders/${b.id}?tender=${tender.id}`} className="font-semibold">
                            {b.legal_name}
                          </Link>
                        </td>
                        <td>{performanceByBidder[b.id]?.total_contracts ?? 'N/A'}</td>
                        <td className="font-bold text-success">{performanceByBidder[b.id]?.completed_count ? `${performanceByBidder[b.id].on_time_rate}%` : 'N/A'}</td>
                        <td>{performanceByBidder[b.id]?.total_contracts ? `INR ${performanceByBidder[b.id].liquidated_damages_inr.toLocaleString()}` : 'N/A'}</td>
                        <td>{performanceByBidder[b.id]?.quality_metrics?.total_inspections ? `${performanceByBidder[b.id].quality_metrics.pass_rate}%` : 'N/A'}</td>
                        <td className="text-xs text-muted">{performanceByBidder[b.id]?.total_contracts ? `${performanceByBidder[b.id].completed_count} completed; ${performanceByBidder[b.id].avg_delay_days} average delay days` : 'No historical contract records are available.'}</td>
                        <td>
                          <Link href={`/bidders/${b.id}?tender=${tender.id}`} className="btn btn-sm btn-outline">
                            View 360 →
                          </Link>
                        </td>
                      </tr>
                    ))}
                    {tender.bidders?.length === 0 && <tr><td colSpan={7} className="text-muted p-4 text-center">No bidders are associated with this tender.</td></tr>}
                  </tbody>
                </table>
            </div>
          </div>
        )}

        {/* Tab 8: RISK INTELLIGENCE */}
        {activeTab === 'RISK' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">8-Dimensional Explainable Risk Benchmark</span>
                <div className="section-sub">
                  Dimensions: Document Integrity, Compliance, Delivery, Quality, Contract Performance, Capacity, Anomaly ("Unusual pattern detected"), and Data Sufficiency.
                </div>
              </div>
            </div>
            <div className="alert alert-warning mb-4" role="note">Risk assessment is decision support only, not a final procurement decision. INSUFFICIENT EVIDENCE is not LOW RISK.</div>

            <div className="table-wrapper">
              <table className="data-table">
                  <thead>
                    <tr>
                      <th>Bidder</th>
                      <th>Overall Category</th>
                      <th>Score and dimensions</th>
                      <th>Officer decision</th>
                      <th>Assessment detail</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tender.bidders?.map((b: any) => (
                      <tr key={b.id}>
                        <td>
                          <Link href={`/bidders/${b.id}?tender=${tender.id}`} className="font-semibold">
                            {b.legal_name}
                          </Link>
                        </td>
                        <td><StatusBadge status={b.risk_level || 'PENDING'} size="sm" /></td>
                        <td className="text-sm">{b.risk_level ? 'Open bidder breakdown for backend score and dimensions' : 'Assessment not yet available'}</td>
                        <td><StatusBadge status={b.final_decision || 'PENDING'} size="sm" /></td>
                        <td>
                          <Link href={`/bidders/${b.id}?tender=${tender.id}`} className="btn btn-sm btn-outline">
                            Explainable Breakdown →
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            </div>
          </div>
        )}

        {/* Tab 9: EVIDENCE */}
        {activeTab === 'EVIDENCE' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Tender Evidence Lineage Graph</span>
                <div className="section-sub">Traceable cryptographic chain connecting claims directly to document hashes and verification logs</div>
              </div>
            </div>

            {evidenceItems.length > 0 ? (
              <div className="evidence-timeline">
                {evidenceItems.map((ev: any) => (
                  <div key={ev.id} className="evidence-card">
                    <div className="evidence-header">
                      <span className="evidence-tag">{ev.claim_type}</span>
                      <span className="evidence-conf">Confidence: {(ev.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <p className="evidence-text">{ev.evidence_text}</p>
                    <div className="evidence-footer">
                      <span className="evidence-source">Source Reference: <b>{ev.source_reference}</b></span>
                      <span className="evidence-date">{new Date(ev.created_at).toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="state-wrapper">
                <p className="state-desc">No evidence nodes recorded yet. Run analysis on bidders to build the evidence graph.</p>
              </div>
            )}
          </div>
        )}

        {/* Tab 10: REPORTS */}
        {activeTab === 'REPORTS' && (
          <div className="tab-pane">
            <div className="grid-2 mb-4">
              <div className="panel">
                <h2 className="card-title">REPORT 1 · Executive Bidder Summary (Quick List)</h2>
                <p className="text-sm text-muted mb-4" style={{ lineHeight: 1.55 }}>
                  Consolidated PDF summary for the procurement committee showing all participating bidders, compliance rates, verification flags, and officer decisions.
                </p>
                <button
                  className="btn btn-primary"
                  onClick={handleGenerateQuickReport}
                  disabled={generatingReport === 'QUICK'}
                >
                  {generatingReport === 'QUICK' ? 'Generating Report…' : 'Generate & Download Report 1 (PDF)'}
                </button>
              </div>

              <div className="panel">
                <h2 className="card-title">REPORT 2 · Detailed Bidder Dossier Generator</h2>
                <p className="text-sm text-muted mb-4" style={{ lineHeight: 1.55 }}>
                  Full multi-page dossier for an individual bidder with submitted document hashes, OCR bounding boxes, 8-dimensional risk breakdown, and audit seals.
                </p>
                <p className="text-xs text-muted mb-2">Select a bidder to generate a detailed assessment dossier:</p>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {tender.bidders?.slice(0, 5).map((b: any) => (
                    <button
                      key={b.id}
                      className="btn btn-sm btn-outline"
                      onClick={() => handleGenerateDetailedReport(b.id)}
                      disabled={generatingReport === `DETAILED_${b.id}`}
                    >
                      {generatingReport === `DETAILED_${b.id}` ? 'Building…' : `Dossier: ${b.legal_name.split(' ')[0]}`}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 11: AUDIT */}
        {activeTab === 'AUDIT' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Immutable Audit Log · {tender.tender_ref}</span>
              </div>
            </div>
            <div className="table-wrapper">
              <table className="data-table">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Actor</th>
                      <th>Action</th>
                      <th>Entity</th>
                      <th>Audit Context</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tenderAudit.map((log: any) => (
                      <tr key={log.id}>
                        <td className="text-xs font-mono text-muted">{new Date(log.created_at).toLocaleString()}</td>
                        <td className="font-semibold">{log.username}</td>
                        <td>
                          <span className="mono text-xs" style={{ background: 'var(--paper-200)', border: '1px solid var(--border-faint)', padding: '2px 6px', borderRadius: '3px' }}>
                            {log.action}
                          </span>
                        </td>
                        <td>{log.entity_type} #{log.entity_id}</td>
                        <td className="text-xs font-mono text-muted">{JSON.stringify(log.details)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            </div>
          </div>
        )}

        {/* Modals */}
        {inspectDocId && (
          <OCRInspectorModal
            documentId={inspectDocId}
            onClose={() => setInspectDocId(null)}
          />
        )}

        {decisionModal?.open && (
          <DecisionModal
            tenderId={tender.id}
            bidderId={decisionModal.bidderId}
            bidderName={decisionModal.bidderName}
            currentDecision={decisionModal.currentDecision}
            onClose={() => setDecisionModal(null)}
            onSuccess={loadTender}
          />
        )}

        {evidenceModal?.open && (
          <EvidenceModal
            bidderId={evidenceModal.bidderId}
            bidderName={evidenceModal.bidderName}
            onClose={() => setEvidenceModal(null)}
          />
        )}

        {/* Bidder enrollment modal — bid intake entry point */}
        {showEnroll && (
          <div className="modal-overlay" onClick={() => setShowEnroll(false)}>
            <div className="modal-container modal-md" role="dialog" aria-modal="true" aria-label="Enroll bidder" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <div>
                  <div className="modal-pretitle">Bid Intake</div>
                  <h2 className="modal-title">Enroll Bidder</h2>
                </div>
                <button className="btn-close" onClick={() => setShowEnroll(false)} aria-label="Close dialog">×</button>
              </div>
              <form onSubmit={handleEnrollBidder}>
                <div className="modal-body">
                  <div className="form-group">
                    <label className="form-label" htmlFor="en-name">
                      Bidder / Company Legal Name <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    <input
                      id="en-name" type="text" className="form-input"
                      value={enrollForm.legal_name}
                      onChange={(e) => setEnrollForm({ ...enrollForm, legal_name: e.target.value })}
                      placeholder="e.g. Company A Private Limited"
                      required aria-required="true" maxLength={250}
                    />
                    <span className="form-hint">
                      Statutory identifiers can be captured later from OCR&apos;d documents during officer review.
                    </span>
                  </div>
                  <div className="grid-2">
                    <div className="form-group">
                      <label className="form-label" htmlFor="en-pan">PAN (if known)</label>
                      <input
                        id="en-pan" type="text" className="form-input"
                        value={enrollForm.pan}
                        onChange={(e) => setEnrollForm({ ...enrollForm, pan: e.target.value })}
                        maxLength={20}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label" htmlFor="en-gstin">GSTIN (if known)</label>
                      <input
                        id="en-gstin" type="text" className="form-input"
                        value={enrollForm.gstin}
                        onChange={(e) => setEnrollForm({ ...enrollForm, gstin: e.target.value })}
                        maxLength={20}
                      />
                    </div>
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-outline" onClick={() => setShowEnroll(false)}>Cancel</button>
                  <button type="submit" className="btn btn-primary" disabled={enrolling} aria-busy={enrolling}>
                    {enrolling ? 'Enrolling…' : 'Enroll Bidder'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
  );
}
