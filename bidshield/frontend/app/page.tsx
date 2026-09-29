'use client';
import React, { useState } from 'react';
import { useCurrentUser } from '../lib/userContext';
import VerificationDashboard from './dashboard/VerificationDashboard';
import AuditorDashboard from './dashboard/AuditorDashboard';
import AdminDashboard from './dashboard/AdminDashboard';
import Link from 'next/link';
import StatusBadge from '../components/StatusBadge';
import { useApi } from '../lib/useApi';
import { api, downloadFile } from '../lib/api';
import {
  FileText,
  Users,
  AlertTriangle,
  ArrowRight,
  RotateCw,
  PlusCircle,
  Download,
  FileBarChart,
  CheckCircle2,
  History,
  ChevronRight,
  Activity,
  Sparkles,
} from 'lucide-react';

/* ================================================================
   PROCUREMENT OFFICER DASHBOARD — review command center
   Work-first composition: metric index → review queue → signals rail
   ================================================================ */
function ProcurementDashboard() {
  const {
    data: metrics,
    loading: metricsLoading,
    error: metricsError,
    mutate: refreshDashboard,
  } = useApi<any>('/dashboard');
  const { data: tenders = [], error: tendersError, mutate: refreshTenders } = useApi<any[]>('/tenders');
  const { data: bidders = [], error: biddersError, mutate: refreshBidders } = useApi<any[]>('/bidders');

  const [isRefreshing, setIsRefreshing]   = useState(false);
  const [generatingReport, setGeneratingReport] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTender, setNewTender] = useState({
    tender_ref: '',
    gem_ref: '',
    title: '',
    department: 'Ministry of Electronics and Information Technology',
    category: 'IT Equipment & Hardware',
    estimated_value_cr: 5.5,
    issue_date: new Date().toISOString().slice(0, 10),
    closing_date: new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
    description: 'Procurement of enterprise workstations, OEM authorization, Make in India 50% content, GST and PAN compliance.',
  });
  const [creatingTender, setCreatingTender] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await Promise.all([refreshDashboard(true), refreshTenders(true), refreshBidders(true)]);
    setIsRefreshing(false);
  };

  const handleCreateTenderSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setCreatingTender(true);
      await api('/tenders', { method: 'POST', body: JSON.stringify(newTender) });
      setShowCreateModal(false);
      await Promise.all([refreshDashboard(true), refreshTenders(true)]);
    } catch (err: any) {
      alert(err.message || 'Failed to create tender');
    } finally {
      setCreatingTender(false);
    }
  };

  const handleQuickReport = async (tenderId?: number) => {
    const id = tenderId ?? tenders[0]?.id;
    if (!id) { alert('Create a tender first.'); return; }
    try {
      setGeneratingReport('QUICK');
      const res = await api('/reports/quick-list', { method: 'POST', body: JSON.stringify({ tender_id: id }) });
      await downloadFile(`/reports/${res.report_uid}/download`, res.filename);
    } catch (err: any) {
      alert(err.message || 'Failed to generate report');
    } finally {
      setGeneratingReport(null);
    }
  };

  const openCreateModal = () => {
    setNewTender({
      tender_ref: `GEM/2026/B/${Math.floor(10000 + Math.random() * 90000)}`,
      gem_ref: `GEM-REF-${Math.floor(10000 + Math.random() * 90000)}`,
      title: '',
      department: 'Ministry of Electronics and Information Technology',
      category: 'IT Equipment & Hardware',
      estimated_value_cr: 6.2,
      issue_date: new Date().toISOString().slice(0, 10),
      closing_date: new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
      description: 'Tender procurement for IT infrastructure and hardware.',
    });
    setShowCreateModal(true);
  };

  // Derived figures — ledger index row
  const totalValue       = tenders.reduce((a: number, t: any) => a + (t.estimated_value_cr || 0), 0);
  const departmentCount  = new Set(tenders.map((t: any) => t.department).filter(Boolean)).size;
  const priorityBidders  = bidders.filter((b: any) => b.is_startup || String(b.enterprise_type || '').toUpperCase().includes('MSME')).length;
  const verificationTotal =
    metrics
      ? (metrics.completed_verifications ?? 0) + (metrics.pending_verifications ?? 0) + (metrics.manual_reviews_required ?? 0)
      : null;
  const passRate =
    verificationTotal && verificationTotal > 0
      ? `${((metrics.completed_verifications / verificationTotal) * 100).toFixed(0)}%`
      : '—';

  const anyError = metricsError || tendersError || biddersError;

  // Pipeline stage figures
  const pipelineStages = [
    { key: 'submitted', label: 'Submitted',  count: bidders.length,                        status: 'default' },
    { key: 'ocr',       label: 'OCR',        count: verificationTotal ?? 0,                status: 'default' },
    { key: 'verified',  label: 'Verified',   count: metrics?.completed_verifications ?? 0, status: 'done' },
    { key: 'flagged',   label: 'Manual',     count: metrics?.manual_reviews_required ?? 0, status: metrics?.manual_reviews_required > 0 ? 'error' : 'default' },
    { key: 'pending',   label: 'Pending',    count: metrics?.pending_verifications ?? 0,   status: metrics?.pending_verifications > 0 ? 'active' : 'default' },
  ];

  return (
    <div className="main-wrapper">
      {/* ── Page header ───────────────────────────────────────── */}
      <div className="page-header">
        <div className="page-header-text">
          <div className="page-eyebrow">Procurement Operations · Review Command</div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-desc">
            Active GeM bid submissions, verification pipeline status, and the officer review queue.
          </p>
        </div>
        <div className="page-actions">
          <button
            className="btn btn-outline"
            onClick={handleRefresh}
            disabled={isRefreshing}
            aria-label="Refresh dashboard"
          >
            <RotateCw size={13} aria-hidden="true" className={isRefreshing ? 'animate-spin' : ''} />
            {isRefreshing ? 'Refreshing…' : 'Refresh'}
          </button>
          <button
            className="btn btn-primary"
            onClick={openCreateModal}
          >
            <PlusCircle size={13} aria-hidden="true" />
            New Tender
          </button>
        </div>
      </div>
      <hr className="page-rule" />

      {/* Alerts */}
      {anyError && (
        <div className="alert alert-warning mb-4" role="alert">
          <AlertTriangle size={14} aria-hidden="true" style={{ flexShrink: 0 }} />
          <span>Some data could not be loaded. Use Refresh to retry.</span>
        </div>
      )}

      {/* ── Metric index row (figures, not cards) ────────────── */}
      <div className="metric-strip" aria-label="Operational metrics">
        <div className="metric-cell">
          <div className="metric-value">
            {metricsLoading ? '…' : (metrics?.active_tenders ?? tenders.length)}
          </div>
          <div className="metric-label">Active Tenders</div>
          <div className="metric-change">
            ₹{totalValue.toFixed(1)} Cr portfolio · {departmentCount} dept{departmentCount !== 1 ? 's' : ''}
          </div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">
            {metricsLoading ? '…' : (metrics?.total_bidders ?? bidders.length)}
          </div>
          <div className="metric-label">Bidders Enrolled</div>
          <div className="metric-change">{priorityBidders} MSME / startup</div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">
            {metricsLoading ? '…' : (metrics?.completed_verifications ?? '—')}
          </div>
          <div className="metric-label">Verified</div>
          <div className="metric-change">{passRate} pass rate</div>
        </div>
        <div className={`metric-cell${(metrics?.manual_reviews_required ?? 0) > 0 ? ' alert' : ''}`}>
          <div className="metric-value">
            {metricsLoading ? '…' : (metrics?.manual_reviews_required ?? 0)}
          </div>
          <div className="metric-label">Flagged for Review</div>
          <div className="metric-change">Requires officer attention</div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">
            {metricsLoading ? '…' : `${metrics?.overall_compliance_rate ?? 0}%`}
          </div>
          <div className="metric-label">Compliance Rate</div>
          <div className="metric-change">
            {metrics?.risk_distribution?.HIGH ?? 0} high risk
          </div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">
            {metricsLoading ? '…' : (metrics?.pending_verifications ?? 0)}
          </div>
          <div className="metric-label">Pending OCR</div>
          <div className="metric-change">In verification queue</div>
        </div>
      </div>

      {/* ── Main workspace: queue + signals rail ─────────────── */}
      <div className="grid-main-side">

        {/* LEFT: Review queue tables */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '26px', minWidth: 0 }}>

          {/* Active review queue — tenders */}
          <div>
            <div className="section-header">
              <div>
                <span className="section-title">Active Review Queue</span>
                <div className="section-sub">Tenders under evaluation, by closing date</div>
              </div>
              <div className="section-actions">
                <Link href="/tenders" className="btn btn-ghost btn-sm">
                  Open Register <ArrowRight size={12} aria-hidden="true" />
                </Link>
                <button className="btn btn-outline btn-sm" onClick={() => setShowCreateModal(true)}>
                  <PlusCircle size={12} aria-hidden="true" /> New
                </button>
              </div>
            </div>
            <div className="table-wrapper">
              <table className="data-table" aria-label="Active review queue — tenders">
                <thead>
                  <tr>
                    <th>Tender Reference</th>
                    <th>Title</th>
                    <th>Department</th>
                    <th className="td-num">Value</th>
                    <th>Status</th>
                    <th>Closing</th>
                    <th><span className="sr-only">Open</span></th>
                  </tr>
                </thead>
                <tbody>
                  {metricsLoading && !tenders.length && (
                    <>
                      <tr><td colSpan={7}><div className="skeleton-row" /></td></tr>
                      <tr><td colSpan={7}><div className="skeleton-row" /></td></tr>
                    </>
                  )}
                  {!metricsLoading && tenders.length === 0 && (
                    <tr>
                      <td colSpan={7}>
                        <div className="state-wrapper" style={{ padding: '28px 24px' }}>
                          <FileText size={28} className="state-icon" aria-hidden="true" />
                          <div className="state-title">No tenders yet</div>
                          <div className="state-desc">Create the first GeM tender to begin the review workflow.</div>
                          <button className="btn btn-primary btn-sm" style={{ marginTop: '12px' }} onClick={() => setShowCreateModal(true)}>
                            <PlusCircle size={12} aria-hidden="true" /> Create First Tender
                          </button>
                        </div>
                      </td>
                    </tr>
                  )}
                  {tenders.slice(0, 6).map((t: any) => (
                    <tr key={t.id} className="row-link">
                      <td><span className="mono td-mono" style={{ fontWeight: 500 }}>{t.tender_ref}</span></td>
                      <td style={{ maxWidth: '220px' }}>
                        <div className="td-primary" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {t.title}
                        </div>
                      </td>
                      <td className="td-muted" style={{ maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '12px' }}>
                        {t.department}
                      </td>
                      <td className="td-num td-mono" style={{ fontWeight: 500 }}>
                        ₹{t.estimated_value_cr} Cr
                      </td>
                      <td><StatusBadge status={t.status} size="sm" /></td>
                      <td className="td-mono td-muted">
                        {t.closing_date ? new Date(t.closing_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' }) : '—'}
                      </td>
                      <td>
                        <Link href={`/tenders/${t.id}`} className="btn btn-ghost btn-sm btn-icon" aria-label={`Open tender ${t.tender_ref}`}>
                          <ChevronRight size={14} aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {tenders.length > 6 && (
                <div className="table-footer">
                  Showing 6 of {tenders.length} tenders
                  <Link href="/tenders" className="btn btn-ghost btn-sm">View all</Link>
                </div>
              )}
            </div>
          </div>

          {/* Bidder enrollment */}
          <div>
            <div className="section-header">
              <div>
                <span className="section-title">Bidder Enrollment</span>
                <div className="section-sub">Registrations and statutory identifiers under review</div>
              </div>
              <div className="section-actions">
                <Link href="/bidders" className="btn btn-ghost btn-sm">
                  Open Registry <ArrowRight size={12} aria-hidden="true" />
                </Link>
              </div>
            </div>
            <div className="table-wrapper">
              <table className="data-table" aria-label="Bidder enrollment list">
                <thead>
                  <tr>
                    <th>Legal Name</th>
                    <th>PAN</th>
                    <th>GSTIN</th>
                    <th>Type</th>
                    <th>State</th>
                    <th><span className="sr-only">Open</span></th>
                  </tr>
                </thead>
                <tbody>
                  {bidders.length === 0 && (
                    <tr>
                      <td colSpan={6}>
                        <div className="state-wrapper" style={{ padding: '24px' }}>
                          <Users size={24} className="state-icon" aria-hidden="true" />
                          <div className="state-title">No bidders enrolled</div>
                          <div className="state-desc">Bidders will appear here once they are enrolled against a tender.</div>
                        </div>
                      </td>
                    </tr>
                  )}
                  {bidders.slice(0, 8).map((b: any) => (
                    <tr key={b.id} className="row-link">
                      <td><span className="td-primary">{b.legal_name}</span></td>
                      <td className="td-mono td-muted">{b.pan}</td>
                      <td className="td-mono td-muted">{b.gstin}</td>
                      <td>
                        <span className="status-badge badge-neutral size-sm">{b.enterprise_type || '—'}</span>
                        {b.is_startup && <span className="status-badge badge-success size-sm" style={{ marginLeft: '4px' }}>Startup</span>}
                      </td>
                      <td className="td-muted" style={{ fontSize: '12px' }}>{b.state || '—'}</td>
                      <td>
                        <Link href={`/bidders/${b.id}?tender=1`} className="btn btn-ghost btn-sm btn-icon" aria-label={`Open dossier for ${b.legal_name}`}>
                          <ChevronRight size={14} aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {bidders.length > 8 && (
                <div className="table-footer">
                  Showing 8 of {bidders.length} bidders
                  <Link href="/bidders" className="btn btn-ghost btn-sm">View all</Link>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT: Signals rail */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '26px', minWidth: 0 }}>

          {/* Verification pipeline */}
          <div>
            <div className="section-header section-header-soft">
              <span className="section-title">Verification Pipeline</span>
            </div>
            <div className="pipeline" aria-label="Verification pipeline stages">
              {pipelineStages.map((stage) => (
                <div
                  key={stage.key}
                  className={`pipeline-stage ${stage.status !== 'default' ? stage.status : ''}`}
                  title={stage.label}
                >
                  <div className="pipeline-stage-name">{stage.label}</div>
                  <div className="pipeline-stage-count">{metricsLoading ? '…' : stage.count}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Review signals — attention items */}
          <div>
            <div className="section-header section-header-soft">
              <span className="section-title">Review Signals</span>
              {(metrics?.attention_documents?.length ?? 0) > 0 && (
                <span className="status-badge badge-danger size-sm">
                  {metrics.attention_documents.length}
                </span>
              )}
            </div>
            <div className="card card-flush">
              {!metrics?.attention_documents?.length ? (
                <div className="state-wrapper" style={{ padding: '20px' }}>
                  <CheckCircle2 size={20} style={{ color: 'var(--success)' }} aria-hidden="true" />
                  <div className="state-title" style={{ color: 'var(--success)' }}>No flags</div>
                  <div className="state-desc">All documents are clear</div>
                </div>
              ) : (
                <div style={{ padding: '4px 0' }}>
                  {metrics.attention_documents.slice(0, 4).map((item: any) => (
                    <Link
                      key={item.document_id}
                      href={`/bidders/${item.bidder_id}?tender=1`}
                      className="report-row"
                      style={{ textDecoration: 'none' }}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="td-primary" style={{ fontSize: '12.5px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {item.bidder_name}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '1px' }}>
                          {item.document_type} · {item.notes}
                        </div>
                      </div>
                      <StatusBadge status={item.status} size="sm" />
                    </Link>
                  ))}
                  <div style={{ padding: '8px 14px', textAlign: 'center' }}>
                    <Link href="/verification" className="btn btn-ghost btn-sm" style={{ width: '100%', justifyContent: 'center' }}>
                      Open Verification Center <ArrowRight size={12} aria-hidden="true" />
                    </Link>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Recent activity — timeline */}
          <div>
            <div className="section-header section-header-soft">
              <span className="section-title">Recent Activity</span>
              <Link href="/audit" className="btn btn-ghost btn-sm">
                <History size={12} aria-hidden="true" /> Audit
              </Link>
            </div>
            <div className="card" style={{ padding: '2px 14px' }}>
              {!metrics?.recent_activity?.length ? (
                <div className="state-wrapper" style={{ padding: '20px' }}>
                  <Activity size={20} className="state-icon" aria-hidden="true" />
                  <div className="state-desc">No audit events recorded yet.</div>
                </div>
              ) : (
                <div className="timeline" style={{ padding: '6px 0' }}>
                  {metrics.recent_activity.slice(0, 5).map((act: any) => (
                    <div key={act.id} className="timeline-item">
                      <div className="timeline-dot info" />
                      <div className="timeline-content">
                        <div className="timeline-label">
                          <span className="mono" style={{ fontSize: '11.5px', fontWeight: 600 }}>{act.action}</span>
                          {' '}<span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>by {act.username}</span>
                        </div>
                        <div className="timeline-meta">
                          {act.entity_type} ·{' '}
                          {new Date(act.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Reports */}
          <div>
            <div className="section-header section-header-soft">
              <span className="section-title">Reports</span>
            </div>
            <div className="card">
              <div style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginBottom: '10px', lineHeight: '1.5' }}>
                Generate a consolidated bidder evaluation PDF for the first active tender.
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <Link href="/reports" className="btn btn-outline btn-sm" style={{ flex: 1, justifyContent: 'center' }}>
                  <FileBarChart size={12} aria-hidden="true" /> Archive
                </Link>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => handleQuickReport(tenders[0]?.id)}
                  disabled={generatingReport === 'QUICK' || tenders.length === 0}
                  title={tenders.length === 0 ? 'Create a tender first' : 'Generate Quick List PDF'}
                  style={{ flex: 1, justifyContent: 'center' }}
                >
                  <Download size={12} aria-hidden="true" />
                  {generatingReport === 'QUICK' ? 'Generating…' : 'Generate PDF'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Create Tender Modal ───────────────────────────────── */}
      {showCreateModal && (
        <div
          className="modal-overlay"
          onClick={() => setShowCreateModal(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Create new tender"
        >
          <div className="modal-container modal-md" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="modal-pretitle">Tender Management</div>
                <h2 className="modal-title">Publish New GeM Tender</h2>
              </div>
              <button className="btn-close" onClick={() => setShowCreateModal(false)} aria-label="Close dialog">
                ×
              </button>
            </div>
            <form onSubmit={handleCreateTenderSubmit}>
              <div className="modal-body">
                <div className="grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="nt-ref">
                      Tender Reference ID <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    <input
                      id="nt-ref"
                      type="text" className="form-input"
                      value={newTender.tender_ref}
                      onChange={e => setNewTender({ ...newTender, tender_ref: e.target.value })}
                      required aria-required="true"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="nt-gem">GeM Portal Reference</label>
                    <input
                      id="nt-gem"
                      type="text" className="form-input"
                      value={newTender.gem_ref}
                      onChange={e => setNewTender({ ...newTender, gem_ref: e.target.value })}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="nt-title">
                    Tender Title <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                  </label>
                  <input
                    id="nt-title"
                    type="text" className="form-input"
                    value={newTender.title}
                    onChange={e => setNewTender({ ...newTender, title: e.target.value })}
                    placeholder="e.g. Supply of Advanced Workstations and IT Hardware"
                    required aria-required="true"
                  />
                </div>

                <div className="grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="nt-dept">
                      Ministry / Department <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    <input
                      id="nt-dept"
                      type="text" className="form-input"
                      value={newTender.department}
                      onChange={e => setNewTender({ ...newTender, department: e.target.value })}
                      required aria-required="true"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="nt-cat">Procurement Category</label>
                    <select id="nt-cat" className="form-select" value={newTender.category} onChange={e => setNewTender({ ...newTender, category: e.target.value })}>
                      <option>IT Equipment &amp; Hardware</option>
                      <option>Cloud &amp; Cybersecurity Services</option>
                      <option>Medical Devices &amp; Hospital Equipment</option>
                      <option>Heavy Electrical &amp; Power Equipment</option>
                      <option>Solar &amp; Renewable Energy</option>
                    </select>
                  </div>
                </div>

                <div className="grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="nt-value">
                      Estimated Value (₹ Crores) <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    <input
                      id="nt-value"
                      type="number" step="0.1" min="0" className="form-input"
                      value={newTender.estimated_value_cr}
                      onChange={e => setNewTender({ ...newTender, estimated_value_cr: parseFloat(e.target.value) || 1 })}
                      required aria-required="true"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="nt-close">
                      Bid Closing Date <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    <input
                      id="nt-close"
                      type="date" className="form-input"
                      value={newTender.closing_date}
                      onChange={e => setNewTender({ ...newTender, closing_date: e.target.value })}
                      required aria-required="true"
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="nt-desc">Scope &amp; Compliance Conditions</label>
                  <textarea
                    id="nt-desc"
                    className="form-textarea" rows={3}
                    value={newTender.description}
                    onChange={e => setNewTender({ ...newTender, description: e.target.value })}
                    placeholder="Specify requirements: GST, PAN, OEM Authorization, Make in India local content..."
                  />
                  <span className="form-hint">System will extract initial compliance rules for officer review.</span>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowCreateModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={creatingTender} aria-busy={creatingTender}>
                  {creatingTender ? 'Publishing…' : 'Publish Tender & Extract Criteria'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

/* ================================================================
   ROLE ROUTER — must be at the bottom to avoid hook violations
   ================================================================ */
export default function DashboardPage() {
  const user = useCurrentUser();

  if (user?.role === 'VERIFICATION_OFFICER') return <VerificationDashboard />;
  if (user?.role === 'AUDITOR')              return <AuditorDashboard />;
  if (user?.role === 'SUPER_ADMIN')          return <AdminDashboard />;

  return <ProcurementDashboard />;
}
