'use client';
import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import StatusBadge from '../../../components/StatusBadge';
import OCRInspectorModal from '../../../components/OCRInspectorModal';
import EvidenceModal from '../../../components/EvidenceModal';
import PermissionGate from '../../../components/PermissionGate';
import MultiDocUpload from '../../../components/MultiDocUpload';
import { api, downloadFile, API_BASE } from '../../../lib/api';
import { useCurrentUser } from '../../../lib/userContext';
import { can } from '../../../lib/permissions';

type BidderTabKey =
  | 'IDENTITY'
  | 'REGISTRATIONS'
  | 'DOCUMENTS'
  | 'OCR'
  | 'VERIFICATION'
  | 'COMPLIANCE'
  | 'CONTRACTS'
  | 'DELIVERY'
  | 'QUALITY'
  | 'RISK'
  | 'EVIDENCE'
  | 'AUDIT';

export default function Bidder360Page() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const tenderId = searchParams.get('tender') || '1';

  const [bidder, setBidder] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [activeTab, setActiveTab] = useState<BidderTabKey>('IDENTITY');

  // Modals
  const [inspectDocId, setInspectDocId] = useState<number | null>(null);
  const [showEvidenceModal, setShowEvidenceModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadDocType, setUploadDocType] = useState('UDYAM');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  // Report generation state
  const [generatingReport, setGeneratingReport] = useState(false);

  // Performance Data
  const [performance, setPerformance] = useState<any>(null);
  const [riskData, setRiskData] = useState<any>(null);
  const [evidenceList, setEvidenceList] = useState<any[]>([]);
  const [auditList, setAuditList] = useState<any[]>([]);

  async function loadBidder() {
    try {
      setLoading(true);
      setLoadError('');
      const b = await api(`/bidders/${id}?tender=${tenderId}`);
      setBidder(b);

      const [perf, risk, evs, audits] = await Promise.all([
        api(`/bidders/${id}/performance?tender=${tenderId}`).catch(() => null),
        api(`/bidders/${id}/risk?tender=${tenderId}`).catch(() => null),
        api(`/bidders/${id}/evidence`).catch(() => []),
        api(`/bidders/${id}/audit`).catch(() => []),
      ]);

      setPerformance(perf);
      setRiskData(risk);
      setEvidenceList(evs);
      setAuditList(audits);
    } catch (err: any) {
      setLoadError(err.message || 'Unable to load this bidder record.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBidder();
  }, [id, tenderId]);

  // Handle Upload Corrected Document Version
  const handleUploadVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      alert('Please select a PDF file to upload.');
      return;
    }

    try {
      setUploading(true);
      const formData = new FormData();
      formData.append('bidder_id', id as string);
      formData.append('tender_id', tenderId);
      formData.append('document_type', uploadDocType);
      formData.append('file', uploadFile);

      await api('/documents/upload', {
        method: 'POST',
        body: formData,
      });

      setShowUploadModal(false);
      setUploadFile(null);
      await loadBidder();
      alert(`Corrected version of ${uploadDocType} uploaded successfully. Version history preserved.`);
    } catch (err: any) {
      alert(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  // Generate Report 2 (Detailed Bidder Assessment)
  const handleGenerateDossier = async () => {
    try {
      setGeneratingReport(true);
      const res = await api('/reports/detailed-assessment', {
        method: 'POST',
        body: JSON.stringify({
          tender_id: parseInt(tenderId),
          bidder_id: parseInt(id as string),
        }),
      });
      await downloadFile(`/reports/${res.report_uid}/download`, res.filename);
    } catch (err: any) {
      alert(err.message || 'Failed to generate dossier PDF');
    } finally {
      setGeneratingReport(false);
    }
  };

  if (loading || !bidder) {
    return (
      <div className="main-wrapper" style={{ textAlign: 'center', padding: '40px' }}>
        {loadError
          ? <div className="alert alert-danger" role="alert">
              {loadError}
              <button className="btn btn-sm btn-outline" onClick={loadBidder} style={{ marginLeft: '10px' }}>Retry</button>
            </div>
          : <><div className="spinner" aria-label="Loading bidder dossier"></div><p style={{ marginTop: '12px', color: 'var(--text-muted)' }}>Loading bidder dossier…</p></>}
      </div>
    );
  }

  const tabs: Array<{ key: BidderTabKey; label: string }> = [
    { key: 'IDENTITY', label: 'Identity' },
    { key: 'REGISTRATIONS', label: 'Registrations' },
    { key: 'DOCUMENTS', label: 'Documents' },
    { key: 'OCR', label: 'OCR & AI Fields' },
    { key: 'VERIFICATION', label: 'Verification' },
    { key: 'COMPLIANCE', label: 'Compliance' },
    { key: 'CONTRACTS', label: 'Contracts' },
    { key: 'DELIVERY', label: 'Delivery & Delays' },
    { key: 'QUALITY', label: 'Quality & Defects' },
    { key: 'RISK', label: 'Risk (8-Dim)' },
    { key: 'EVIDENCE', label: 'Evidence' },
    { key: 'AUDIT', label: 'Audit Trail' },
  ];

  return (
    <main className="main-wrapper">
        {/* Dossier header — identity record, not a banner */}
        <div className="page-header">
          <div className="page-header-text">
            <div className="page-eyebrow">Bidder Dossier</div>
            <h1 className="page-title">{bidder.legal_name}</h1>
            <p className="page-desc">
              {bidder.trade_name ? `Trading as ${bidder.trade_name} · ` : ''}
              {bidder.enterprise_type} Enterprise · {bidder.district}, {bidder.state}
            </p>
          </div>
          <div className="page-actions">
            <PermissionGate permission="document.upload">
              <button
                className="btn btn-outline"
                onClick={() => setShowUploadModal(true)}
              >
                Upload Documents
              </button>
            </PermissionGate>
            <button
              className="btn btn-outline"
              onClick={() => setShowEvidenceModal(true)}
            >
              View Evidence Graph
            </button>
            <PermissionGate permission="report.generate">
              <button
                className="btn btn-primary"
                onClick={handleGenerateDossier}
                disabled={generatingReport}
              >
                {generatingReport ? 'Compiling…' : 'Generate Detailed Dossier PDF'}
              </button>
            </PermissionGate>
          </div>
        </div>

        {/* Reference strip — statutory identifiers in monospace */}
        <div
          className="mono"
          style={{
            display: 'flex', gap: '22px', flexWrap: 'wrap', alignItems: 'baseline',
            borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)',
            padding: '9px 0', fontSize: '12px', color: 'var(--text-muted)',
          }}
          aria-label="Bidder reference details"
        >
          <span>Bidder&nbsp;<b style={{ color: 'var(--text-primary)', fontWeight: 500 }}>#{bidder.id}</b></span>
          <span>PAN&nbsp;<b style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{bidder.pan}</b></span>
          <span>GSTIN&nbsp;<b style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{bidder.gstin}</b></span>
          <span>Review State&nbsp;<StatusBadge status={bidder.compliance_summary?.status || bidder.risk_summary?.overall_category || 'PENDING'} size="sm" /></span>
        </div>

        {/* Dossier sections */}
        <nav className="workspace-tabs" aria-label="Bidder dossier sections">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              className={`workspace-tab ${activeTab === tab.key ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Section 1: IDENTITY — ruled definition lists, no boxes */}
        {activeTab === 'IDENTITY' && (
          <div className="tab-pane">
            <div className="grid-2">
              <div>
                <div className="section-header section-header-soft">
                  <span className="section-title">Corporate Entity Particulars</span>
                </div>
                <table className="data-table" style={{ border: 'none' }}>
                  <tbody>
                    <tr><td className="profile-field-label" style={{ width: '190px' }}>Legal Enterprise Name</td><td>{bidder.legal_name}</td></tr>
                    <tr><td className="profile-field-label" style={{ width: '190px' }}>Trade Name</td><td>{bidder.trade_name || 'N/A'}</td></tr>
                    <tr><td className="profile-field-label" style={{ width: '190px' }}>Corporate Identity (CIN)</td><td className="font-mono">{bidder.cin || 'N/A'}</td></tr>
                    <tr><td className="profile-field-label" style={{ width: '190px' }}>Date of Incorporation</td><td>{bidder.incorporation_date || '2016-04-12'}</td></tr>
                    <tr><td className="profile-field-label" style={{ width: '190px' }}>Enterprise Category</td><td>{bidder.enterprise_type}</td></tr>
                    <tr>
                      <td className="profile-field-label" style={{ width: '190px' }}>DPIIT Startup Status</td>
                      <td>
                        {bidder.is_startup ? (
                          <span className="status-badge badge-success size-sm">Recognized DPIIT Startup</span>
                        ) : 'Not Registered as Startup'}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div>
                <div className="section-header section-header-soft">
                  <span className="section-title">Registered Office &amp; Authorized Contacts</span>
                </div>
                <table className="data-table" style={{ border: 'none' }}>
                  <tbody>
                    <tr><td className="profile-field-label" style={{ width: '190px' }}>Registered Address</td><td>{bidder.address}</td></tr>
                    <tr><td className="profile-field-label" style={{ width: '190px' }}>District</td><td>{bidder.district}</td></tr>
                    <tr><td className="profile-field-label" style={{ width: '190px' }}>State</td><td>{bidder.state}</td></tr>
                    <tr><td className="profile-field-label" style={{ width: '190px' }}>Authorized Representative</td><td><b>{bidder.contact_person}</b></td></tr>
                    <tr><td className="profile-field-label" style={{ width: '190px' }}>Official Contact Email</td><td>{bidder.contact_email}</td></tr>
                    <tr><td className="profile-field-label" style={{ width: '190px' }}>Official Phone Number</td><td>{bidder.contact_phone}</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Section 2: REGISTRATIONS */}
        {activeTab === 'REGISTRATIONS' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Statutory Government Registrations</span>
              </div>
            </div>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Registration Authority</th>
                    <th>Identifier / Reg Number</th>
                    <th>Registered Status</th>
                    <th>Seeding / Validity</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><b>Goods and Services Tax (GSTN)</b></td>
                    <td className="font-mono font-bold">{bidder.gstin}</td>
                    <td><StatusBadge status="VERIFIED" size="sm" /></td>
                    <td>Regular Taxpayer • Active</td>
                    <td><span className="text-xs text-muted">Verified via Demo GSTN API</span></td>
                  </tr>
                  <tr>
                    <td><b>Income Tax Department (PAN)</b></td>
                    <td className="font-mono font-bold">{bidder.pan}</td>
                    <td><StatusBadge status="VERIFIED" size="sm" /></td>
                    <td>Operative • Aadhaar Seeded</td>
                    <td><span className="text-xs text-muted">Verified via Demo NSDL API</span></td>
                  </tr>
                  <tr>
                    <td><b>Ministry of MSME (Udyam)</b></td>
                    <td className="font-mono font-bold">{bidder.udyam_number || 'N/A'}</td>
                    <td><StatusBadge status={bidder.udyam_number ? 'VERIFIED' : 'PENDING'} size="sm" /></td>
                    <td>{bidder.enterprise_type} • Valid</td>
                    <td><span className="text-xs text-muted">Verified via Demo MSME Adapter</span></td>
                  </tr>
                  <tr>
                    <td><b>Ministry of Corporate Affairs (MCA)</b></td>
                    <td className="font-mono font-bold">{bidder.cin || 'N/A'}</td>
                    <td><StatusBadge status="VERIFIED" size="sm" /></td>
                    <td>Active RoC Registration</td>
                    <td><span className="text-xs text-muted">Verified via Demo MCA Adapter</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Section 3: DOCUMENTS */}
        {activeTab === 'DOCUMENTS' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Document Version Repository</span>
                <div className="section-sub">
                  Full version history. Corrected versions (v2) supersede earlier versions without deleting previous records.
                </div>
              </div>
              <div className="section-actions">
                <button
                  className="btn btn-sm btn-primary"
                  onClick={() => setShowUploadModal(true)}
                >
                  Upload New Version
                </button>
              </div>
            </div>

            <div className="table-wrapper">
              <table className="data-table">
                  <thead>
                    <tr>
                      <th>Doc ID</th>
                      <th>Type</th>
                      <th>Filename</th>
                      <th>Version</th>
                      <th>Status Flag</th>
                      <th>SHA-256 Hash</th>
                      <th>OCR Confidence</th>
                      <th>Verification Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bidder.documents?.map((d: any) => (
                      <tr key={d.id} style={{ opacity: d.is_active ? 1 : 0.65 }}>
                        <td className="font-mono">#{d.id}</td>
                        <td><span className="font-bold">{d.document_type}</span></td>
                        <td>{d.filename}</td>
                        <td>
                          v{d.version} {d.is_active ? (
                            <span className="badge-success text-xs" style={{ padding: '1px 5px', borderRadius: '3px' }}>Active</span>
                          ) : (
                            <span className="badge-neutral text-xs" style={{ padding: '1px 5px', borderRadius: '3px' }}>Superseded</span>
                          )}
                        </td>
                        <td><span className="badge-demo text-xs">SYNTHETIC</span></td>
                        <td className="font-mono text-xs">{d.file_hash?.substring(0, 16)}...</td>
                        <td>
                          {d.ocr_confidence !== null ? (
                            <span className="font-bold text-xs" style={{ color: d.ocr_confidence >= 0.8 ? 'var(--success)' : 'var(--warning)' }}>
                              {(d.ocr_confidence * 100).toFixed(0)}%
                            </span>
                          ) : 'Pending'}
                        </td>
                        <td><StatusBadge status={d.verification_status || 'PENDING'} size="sm" /></td>
                        <td>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button
                              className="btn btn-sm btn-outline"
                              onClick={() => setInspectDocId(d.id)}
                            >
                              Inspect OCR
                            </button>
                            <a
                              href={`${API_BASE}/documents/${d.id}/file`}
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

        {/* Section 4: OCR */}
        {activeTab === 'OCR' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">OCR &amp; Document AI Field Extractions</span>
                <div className="section-sub">
                  Inspect structured text and key-value fields extracted from submitted PDF documents.
                </div>
              </div>
            </div>
            <div className="table-wrapper">
              <table className="data-table">
                  <thead>
                    <tr>
                      <th>Document</th>
                      <th>Type</th>
                      <th>Version</th>
                      <th>Extraction Confidence</th>
                      <th>OCR Engine</th>
                      <th>Inspect Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bidder.documents?.map((d: any) => (
                      <tr key={d.id}>
                        <td className="font-mono">Doc #{d.id}</td>
                        <td className="font-bold">{d.document_type}</td>
                        <td>v{d.version}</td>
                        <td>
                          <span className="font-bold" style={{ color: (d.ocr_confidence || 0) >= 0.8 ? 'var(--success)' : 'var(--warning)' }}>
                            {d.ocr_confidence ? `${(d.ocr_confidence * 100).toFixed(1)}%` : 'Pending'}
                          </span>
                        </td>
                        <td>TesseractOCR / PyMuPDF</td>
                        <td>
                          <button
                            className="btn btn-sm btn-primary"
                            onClick={() => setInspectDocId(d.id)}
                          >
                            Open Side-by-Side OCR Inspector
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            </div>
          </div>
        )}

        {/* Section 5: VERIFICATION */}
        {activeTab === 'VERIFICATION' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Registry Verification Status</span>
                <div className="section-sub">
                  Automated verification checks executed against simulated government and OEM authorities.
                </div>
              </div>
            </div>
            <div className="table-wrapper">
              <table className="data-table">
                  <thead>
                    <tr>
                      <th>Document Type</th>
                      <th>Version</th>
                      <th>Status Outcome</th>
                      <th>Discrepancy / Officer Note</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bidder.documents?.map((d: any) => (
                      <tr key={d.id}>
                        <td className="font-bold">{d.document_type}</td>
                        <td>v{d.version}</td>
                        <td><StatusBadge status={d.verification_status || 'PENDING'} size="sm" /></td>
                        <td className="text-sm">{d.verification_notes || 'Authenticity verified with zero discrepancies.'}</td>
                        <td>
                          <button
                            className="btn btn-sm btn-outline"
                            onClick={async () => {
                              await api(`/documents/${d.id}/verify`, { method: 'POST' });
                              await loadBidder();
                            }}
                          >
                            Re-verify
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            </div>
          </div>
        )}

        {/* Section 6: COMPLIANCE */}
        {activeTab === 'COMPLIANCE' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Deterministic Rule Compliance Evaluation</span>
                <div className="section-sub">Evaluated against active rules for Tender #{tenderId}</div>
              </div>
              <div className="section-actions">
                <span className="mono" style={{ fontSize: '22px', fontWeight: 500, color: 'var(--text-primary)' }}>
                  {bidder.compliance_summary?.score !== undefined ? `${bidder.compliance_summary.score.toFixed(1)}%` : 'N/A'}
                </span>
                <StatusBadge status={bidder.compliance_summary?.status || 'PENDING'} />
              </div>
            </div>

            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Rule Code</th>
                    <th>Requirement Name</th>
                    <th>Evaluation Status</th>
                    <th>Deterministic Explanation</th>
                  </tr>
                </thead>
                <tbody>
                  {bidder.compliance_summary?.results?.map((cr: any) => (
                    <tr key={cr.code}>
                      <td className="font-mono font-bold">{cr.code}</td>
                      <td className="font-semibold">{cr.name}</td>
                      <td><StatusBadge status={cr.status} size="sm" /></td>
                      <td className="text-sm">{cr.explanation}</td>
                    </tr>
                  )) || (
                    <tr>
                      <td colSpan={4} className="text-muted p-4 text-center">
                        Compliance evaluation pending. Run AI Analysis from Tender Workspace.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Section 7: CONTRACTS */}
        {activeTab === 'CONTRACTS' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Historical Public Procurement Contracts</span>
                <div className="section-sub">
                  Verified historical contracts executed by this bidder across central and state procuring authorities.
                </div>
              </div>
            </div>
            <div className="table-wrapper">
              <table className="data-table">
                  <thead>
                    <tr>
                      <th>Contract Ref</th>
                      <th>Procuring Entity</th>
                      <th>Project Title</th>
                      <th>Category</th>
                      <th>Value</th>
                      <th>Scheduled Date</th>
                      <th>Actual Completion</th>
                      <th>Delays</th>
                      <th>Performance Rating</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bidder.contracts?.map((c: any) => (
                      <tr key={c.id}>
                        <td className="font-mono font-semibold">{c.contract_ref}</td>
                        <td>{c.procuring_entity}</td>
                        <td className="font-semibold">{c.title}</td>
                        <td>{c.category}</td>
                        <td>₹{c.contract_value_lakhs} Lakhs</td>
                        <td>{c.scheduled_completion}</td>
                        <td>{c.actual_completion || 'In Progress'}</td>
                        <td>
                          {c.delay_days > 0 ? (
                            <span className="text-danger font-bold">{c.delay_days} days</span>
                          ) : (
                            <span className="text-success font-semibold">On-Time</span>
                          )}
                        </td>
                        <td><b>{c.performance_rating} / 5.0</b></td>
                      </tr>
                    ))}
                    {(!bidder.contracts || bidder.contracts.length === 0) && (
                      <tr>
                        <td colSpan={9} className="text-muted p-4 text-center">
                          Zero historical contracts recorded. (Evaluated under Insufficient Evidence rule).
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
            </div>
          </div>
        )}

        {/* Section 8: DELIVERY — figure index + cause analysis */}
        {activeTab === 'DELIVERY' && (
          <div className="tab-pane">
            <div className="metric-strip mb-4" aria-label="Delivery performance figures">
              <div className="metric-cell ok">
                <div className="metric-value">
                  {performance?.on_time_rate !== undefined ? `${performance.on_time_rate}%` : 'N/A'}
                </div>
                <div className="metric-label">On-Time Delivery Rate</div>
                <div className="metric-change">Completed without delay</div>
              </div>
              <div className="metric-cell">
                <div className="metric-value">{performance?.avg_delay_days ?? 'N/A'}</div>
                <div className="metric-label">Average Delay (Days)</div>
                <div className="metric-change">Across all past orders</div>
              </div>
              <div className="metric-cell">
                <div className="metric-value">
                  {performance?.liquidated_damages_inr != null ? `₹${performance.liquidated_damages_inr.toLocaleString()}` : 'N/A'}
                </div>
                <div className="metric-label">Liquidated Damages</div>
                <div className="metric-change">Statutory penalty deductions</div>
              </div>
            </div>

            <div className="section-header">
              <div>
                <span className="section-title">Documented Delay Cause Analysis</span>
                <div className="section-sub">
                  BidShield isolates contractor execution issues from client delays, force majeure, or statutory extensions.
                </div>
              </div>
            </div>
            <div className="metric-strip" aria-label="Delay causes" style={{ borderTopWidth: '1px', borderColor: 'var(--border)' }}>
              {Object.entries(performance?.delay_causes || {}).map(([cause, count]: any) => (
                <div key={cause} className="metric-cell">
                  <div className="metric-value" style={{ fontSize: '20px' }}>{count}</div>
                  <div className="metric-label">{cause}</div>
                </div>
              ))}
              {Object.keys(performance?.delay_causes || {}).length === 0 && (
                <div className="metric-cell"><div className="metric-change">No delay cause data recorded.</div></div>
              )}
            </div>
          </div>
        )}

        {/* Section 9: QUALITY */}
        {activeTab === 'QUALITY' && (
          <div className="tab-pane">
            <div className="metric-strip" aria-label="Quality metrics">
              <div className="metric-cell ok">
                <div className="metric-value">
                  {performance?.quality_metrics?.pass_rate !== undefined ? `${performance.quality_metrics.pass_rate}%` : 'N/A'}
                </div>
                <div className="metric-label">Third-Party Inspection Pass Rate</div>
                <div className="metric-change">DGQA / TPIA certified inspections</div>
              </div>
              <div className="metric-cell">
                <div className="metric-value">{performance?.quality_metrics?.total_defects ?? 'N/A'}</div>
                <div className="metric-label">Reported Defect Count</div>
                <div className="metric-change">Components flagged during QA</div>
              </div>
              <div className="metric-cell">
                <div className="metric-value">{performance?.quality_metrics?.warranty_claims ?? 'N/A'}</div>
                <div className="metric-label">Warranty Complaints</div>
                <div className="metric-change">Post-commissioning issues</div>
              </div>
            </div>
          </div>
        )}

        {/* Section 10: RISK — score strip + dimension rows, no gauge */}
        {activeTab === 'RISK' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">8-Dimensional Explainable Risk Benchmark</span>
                <div className="section-sub">
                  Explainable analysis distinguishing low risk from insufficient evidence. An anomaly is not a fraud finding.
                </div>
              </div>
              <div className="section-actions">
                <StatusBadge status={riskData?.overall_category || bidder.risk_summary?.overall_category || 'PENDING'} size="lg" />
                <span className="mono" style={{ fontSize: '22px', fontWeight: 500 }}>
                  {riskData?.overall_score != null ? Number(riskData.overall_score).toFixed(1) : bidder.risk_summary?.overall_score != null ? Number(bidder.risk_summary.overall_score).toFixed(1) : '—'}
                  <span style={{ fontSize: '12px', color: 'var(--text-faint)' }}> / 100</span>
                </span>
                <span className="status-badge badge-insufficient size-sm">
                  Evidence: {riskData?.data_sufficiency || bidder.risk_summary?.data_sufficiency || 'Not assessed'}
                </span>
              </div>
            </div>

              <div className="alert alert-warning mb-4" role="note">Risk assessment is decision support only, not a final procurement decision. INSUFFICIENT EVIDENCE is distinct from LOW RISK. An anomaly is not a fraud finding.</div>
              {(riskData?.explanation || bidder.risk_summary?.explanation) && <p className="text-sm mb-4">{riskData?.explanation || bidder.risk_summary?.explanation}</p>}
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Risk Dimension</th>
                      <th style={{ width: '160px' }}>Score (0-100)</th>
                      <th>Contributing Factor / Rational Explanation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries((riskData?.dimensions || bidder.risk_summary?.dimensions || {})).map(([dim, data]: any) => (
                      <tr key={dim}>
                        <td className="font-semibold">{dim.replace(/_/g, ' ')}</td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <div className="risk-bar-track" style={{ flex: 1 }}>
                              <div
                                className={`risk-bar-fill ${data.score >= 60 ? 'risk-bar-high' : data.score >= 35 ? 'risk-bar-medium' : 'risk-bar-low'}`}
                                style={{ width: `${Math.min(100, data.score)}%` }}
                              />
                            </div>
                            <span className={`mono font-semibold ${data.score >= 60 ? 'text-danger' : data.score >= 35 ? 'text-warning' : 'text-success'}`} style={{ width: '42px', textAlign: 'right' }}>
                              {data.score?.toFixed(1)}
                            </span>
                          </div>
                        </td>
                        <td className="text-sm">{data.reason}</td>
                      </tr>
                    ))}
                    {Object.keys(riskData?.dimensions || bidder.risk_summary?.dimensions || {}).length === 0 && <tr><td colSpan={3} className="text-muted p-4 text-center">No risk assessment is available for this bidder and tender yet.</td></tr>}
                  </tbody>
                </table>
              </div>
          </div>
        )}

        {/* Section 11: EVIDENCE — chain, not boxes */}
        {activeTab === 'EVIDENCE' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Traceable Cryptographic Evidence Trail</span>
                <div className="section-sub">Every verification conclusion is linked directly to source document bytes and hashes</div>
              </div>
            </div>

            {evidenceList.length > 0 ? (
              <div className="evidence-timeline">
                {evidenceList.map((ev: any) => (
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
                <p className="state-desc">No evidence records are linked to this bidder yet.</p>
              </div>
            )}
          </div>
        )}

        {/* Section 12: AUDIT */}
        {activeTab === 'AUDIT' && (
          <div className="tab-pane">
            <div className="section-header">
              <div>
                <span className="section-title">Immutable Audit Trail · {bidder.legal_name}</span>
              </div>
            </div>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Officer</th>
                    <th>Action</th>
                    <th>Entity</th>
                    <th>Metadata Details</th>
                  </tr>
                </thead>
                <tbody>
                  {auditList.map((log: any) => (
                    <tr key={log.id}>
                      <td className="font-mono text-xs text-muted">{new Date(log.created_at).toLocaleString()}</td>
                      <td className="font-semibold">{log.username}</td>
                      <td>
                        <span className="mono text-xs" style={{ background: 'var(--paper-200)', border: '1px solid var(--border-faint)', padding: '2px 6px', borderRadius: '3px' }}>
                          {log.action}
                        </span>
                      </td>
                      <td>{log.entity_type} #{log.entity_id}</td>
                      <td className="font-mono text-xs text-muted">{JSON.stringify(log.details)}</td>
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

        {showEvidenceModal && (
          <EvidenceModal
            bidderId={bidder.id}
            bidderName={bidder.legal_name}
            onClose={() => setShowEvidenceModal(false)}
          />
        )}

        {/* Upload Documents Modal — uses MultiDocUpload */}
        {showUploadModal && (
          <div className="modal-overlay" onClick={() => setShowUploadModal(false)}>
            <div
              className="modal-container modal-md"
              role="dialog"
              aria-modal="true"
              aria-label="Upload bidder documents"
              onClick={e => e.stopPropagation()}
              style={{ maxWidth: '600px' }}
            >
              <div className="modal-header">
                <div>
                  <div className="modal-pretitle">Document Version Control</div>
                  <h2 className="modal-title">Upload Documents for {bidder.legal_name}</h2>
                </div>
                <button
                  className="btn-close"
                  onClick={() => setShowUploadModal(false)}
                  aria-label="Close document upload dialog"
                >
                  ✕
                </button>
              </div>

              <div className="modal-body">
                <div className="alert" style={{ background: 'var(--blue-50)', borderColor: 'var(--blue-200)', color: 'var(--blue-700)', marginBottom: '16px', fontSize: '12.5px', gap: '8px' }} role="note">
                  <span style={{ fontWeight: 600 }}>ⓘ Version History:</span> Uploading a new version of an existing document type supersedes the previous version without deleting it. All historical OCR and verification results are permanently preserved.
                </div>
                <MultiDocUpload
                  bidderId={Number(id)}
                  tenderId={tenderId ? Number(tenderId) : undefined}
                  onComplete={() => {
                    setShowUploadModal(false);
                    loadBidder();
                  }}
                />
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setShowUploadModal(false)}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
  );
}
