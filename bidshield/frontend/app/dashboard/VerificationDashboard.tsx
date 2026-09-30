'use client';
import React, { useState } from 'react';
import Link from 'next/link';
import { useApi } from '../../lib/useApi';
import { api } from '../../lib/api';
import StatusBadge from '../../components/StatusBadge';
import {
  AlertTriangle,
  RotateCw,
  CheckCircle2,
  ChevronRight,
  RefreshCw,
  FileSearch,
  FileScan,
} from 'lucide-react';

/* ================================================================
   VERIFICATION OFFICER DASHBOARD
   A work queue — documents, status, confidence, action.
   ================================================================ */
export default function VerificationDashboard() {
  const { data: verifications = [], loading, error, mutate: refresh } = useApi<any[]>('/verification');
  const [busyDoc, setBusyDoc] = useState<number | null>(null);
  const [filter, setFilter] = useState<string>('ALL');

  const handleRetry = async (docId: number) => {
    try {
      setBusyDoc(docId);
      await api(`/verification/${docId}/retry`, { method: 'POST' });
      await refresh(true);
    } catch {
      // status shown via re-fetch
    } finally {
      setBusyDoc(null);
    }
  };

  // Trigger real OCR extraction for a document that has no OCR result yet.
  const handleRunOcr = async (docId: number) => {
    try {
      setBusyDoc(docId);
      await api(`/documents/${docId}/ocr`, { method: 'POST' });
      await refresh(true);
    } catch {
      // status shown via re-fetch
    } finally {
      setBusyDoc(null);
    }
  };

  // Queue figures
  const total    = verifications.length;
  const verified = verifications.filter(v => v.verification_status === 'VERIFIED').length;
  const pending  = verifications.filter(v => v.verification_status === 'PENDING').length;

  // OCR extraction figures — read straight from the live /verification payload
  const ocrPendingDocs = verifications.filter(v => v.ocr_status === 'PENDING');
  const ocrPending = ocrPendingDocs.length;
  const lowConfidence = verifications.filter(v =>
    v.ocr_status === 'COMPLETED' && typeof v.ocr_confidence === 'number' && v.ocr_confidence < 0.6
  ).length;
  const manual   = verifications.filter(v => v.verification_status === 'MANUAL_REVIEW').length;
  const mismatch = verifications.filter(v => v.verification_status === 'MISMATCH').length;
  const expired  = verifications.filter(v => v.verification_status === 'EXPIRED').length;
  const retry    = verifications.filter(v => v.verification_status === 'RETRY_REQUIRED').length;

  const needsAction = verifications.filter(v =>
    ['MANUAL_REVIEW', 'MISMATCH', 'EXPIRED', 'RETRY_REQUIRED', 'PENDING'].includes(v.verification_status)
  );

  const filters = [
    { id: 'ALL',            label: 'All',           count: total },
    { id: 'MANUAL_REVIEW',  label: 'Manual Review', count: manual },
    { id: 'MISMATCH',       label: 'Mismatch',      count: mismatch },
    { id: 'PENDING',        label: 'Pending',       count: pending },
    { id: 'RETRY_REQUIRED', label: 'Retry',         count: retry },
    { id: 'EXPIRED',        label: 'Expired',       count: expired },
    { id: 'VERIFIED',       label: 'Verified',      count: verified },
  ];

  const displayed = filter === 'ALL'
    ? verifications
    : verifications.filter(v => v.verification_status === filter);

  function confColor(score?: number) {
    if (score === undefined || score === null) return 'var(--text-faint)';
    if (score >= 0.85) return 'var(--success)';
    if (score >= 0.6)  return 'var(--warning)';
    return 'var(--danger)';
  }

  return (
    <div className="main-wrapper">
      {/* Page header */}
      <div className="page-header">
        <div className="page-header-text">
          <div className="page-eyebrow">Verification Operations · Work Queue</div>
          <h1 className="page-title">Verification Queue</h1>
          <p className="page-desc">
            OCR extraction · cross-reference matching · statutory validation · confidence scoring
          </p>
        </div>
        <div className="page-actions">
          <button
            className="btn btn-outline"
            onClick={() => refresh(true)}
            aria-label="Refresh verification queue"
          >
            <RotateCw size={13} aria-hidden="true" />
            Refresh Queue
          </button>
          <Link href="/verification" className="btn btn-primary">
            <FileSearch size={13} aria-hidden="true" />
            Full Verification
          </Link>
        </div>
      </div>
      <hr className="page-rule" />

      {/* Metric index row */}
      <div className="metric-strip" aria-label="Verification metrics">
        <div className="metric-cell">
          <div className="metric-value">{loading ? '…' : total}</div>
          <div className="metric-label">Total Documents</div>
          <div className="metric-change">In verification scope</div>
        </div>
        <div className="metric-cell ok">
          <div className="metric-value">{loading ? '…' : verified}</div>
          <div className="metric-label">Verified</div>
          <div className="metric-change">
            {total > 0 ? `${((verified / total) * 100).toFixed(0)}%` : '—'} pass rate
          </div>
        </div>
        <div className={`metric-cell${manual > 0 ? ' alert' : ''}`}>
          <div className="metric-value">{loading ? '…' : manual}</div>
          <div className="metric-label">Manual Review</div>
          <div className="metric-change">Awaiting officer decision</div>
        </div>
        <div className={`metric-cell${mismatch > 0 ? ' alert' : ''}`}>
          <div className="metric-value">{loading ? '…' : mismatch}</div>
          <div className="metric-label">Mismatch</div>
          <div className="metric-change">Data inconsistency</div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">{loading ? '…' : retry}</div>
          <div className="metric-label">Retry Required</div>
          <div className="metric-change">Gateway failures</div>
        </div>
        <div className={`metric-cell${ocrPending > 0 ? ' alert' : ''}`}>
          <div className="metric-value">{loading ? '…' : ocrPending}</div>
          <div className="metric-label">Awaiting OCR</div>
          <div className="metric-change">No extraction result yet</div>
        </div>
      </div>

      {/* Pipeline */}
      <div className="section" style={{ marginBottom: '20px' }}>
        <div className="section-header section-header-soft">
          <span className="section-title">Pipeline</span>
          <span className="section-kicker">Submitted → OCR → Verified → Manual → Retry</span>
        </div>
        <div className="pipeline" aria-label="Verification pipeline">
          {[
            { label: 'Submitted',     count: total,           status: 'default' },
            { label: 'OCR Extracted', count: total - ocrPending, status: 'default' },
            { label: 'Verified',      count: verified,        status: 'done' },
            { label: 'Manual Review', count: manual,          status: manual > 0 ? 'active' : 'default' },
            { label: 'Retry',         count: retry,           status: retry  > 0 ? 'error' : 'default' },
          ].map((stage) => (
            <div key={stage.label} className={`pipeline-stage${stage.status !== 'default' ? ` ${stage.status}` : ''}`}>
              <div className="pipeline-stage-name">{stage.label}</div>
              <div className="pipeline-stage-count">{loading ? '…' : stage.count}</div>
            </div>
          ))}
        </div>
      </div>

      {/* OCR intake — real extraction status straight from /verification */}
      {ocrPendingDocs.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <div className="section-header section-header-soft">
            <div>
              <span className="section-title">OCR Intake</span>
              <div className="section-sub">Documents awaiting text extraction — verification cannot run until OCR completes</div>
            </div>
            <div className="section-actions">
              {lowConfidence > 0 && (
                <span className="status-badge badge-warning size-sm">{lowConfidence} low confidence</span>
              )}
              <span className="status-badge badge-neutral size-sm">{ocrPendingDocs.length}</span>
            </div>
          </div>
          <div className="table-wrapper">
            <table className="data-table" aria-label="Documents awaiting OCR extraction">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Bidder</th>
                  <th>Doc Type</th>
                  <th>Filename</th>
                  <th>OCR Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {ocrPendingDocs.slice(0, 8).map((v: any) => (
                  <tr key={`ocr-${v.document_id}`}>
                    <td><span className="mono td-mono" style={{ fontWeight: 500 }}>DOC-{String(v.document_id).padStart(4, '0')}</span></td>
                    <td><span className="td-primary">{v.bidder_name || `Bidder #${v.bidder_id}`}</span></td>
                    <td className="td-muted" style={{ fontSize: '12px' }}>{v.document_type}</td>
                    <td className="td-muted td-truncate" style={{ fontSize: '12px', maxWidth: '220px' }}>{v.filename}</td>
                    <td>
                      <span className="status-badge badge-neutral size-sm">Pending extraction</span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <button
                          className="btn btn-outline btn-sm"
                          onClick={() => handleRunOcr(v.document_id)}
                          disabled={busyDoc === v.document_id}
                          aria-label={`Run OCR extraction for document ${v.document_id}`}
                          title="Run OCR extraction"
                        >
                          <FileScan size={11} aria-hidden="true" className={busyDoc === v.document_id ? 'animate-spin' : ''} />
                          {busyDoc === v.document_id ? 'Extracting…' : 'Run OCR'}
                        </button>
                        <Link
                          href={`/bidders/${v.bidder_id}?tender=1`}
                          className="btn btn-ghost btn-sm btn-icon"
                          aria-label="Open bidder dossier"
                          title="Open dossier"
                        >
                          <ChevronRight size={13} aria-hidden="true" />
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {ocrPendingDocs.length > 8 && (
              <div className="table-footer">
                Showing 8 of {ocrPendingDocs.length} awaiting OCR — run extraction to move them into the queue
              </div>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="alert alert-warning mb-4" role="alert">
          <AlertTriangle size={14} style={{ flexShrink: 0 }} aria-hidden="true" />
          <span>Could not load verification data. Retry in a moment.</span>
        </div>
      )}

      {/* Filter bar */}
      <div className="filter-bar" role="tablist" aria-label="Filter queue by status">
        {filters.map(f => (
          <button
            key={f.id}
            className={`filter-pill${filter === f.id ? ' active' : ''}`}
            onClick={() => setFilter(f.id)}
            aria-pressed={filter === f.id}
          >
            {f.label}
            {f.count > 0 && (
              <span className="mono" style={{ fontSize: '10px', color: filter === f.id ? 'var(--role-accent-text)' : 'var(--text-faint)' }}>
                {f.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Main verification queue table */}
      <div className="table-wrapper">
        <table className="data-table" aria-label="Document verification queue">
          <thead>
            <tr>
              <th>Document</th>
              <th>Bidder</th>
              <th>Doc Type</th>
              <th>Version</th>
              <th>Status</th>
              <th>OCR Confidence</th>
              <th>Last Checked</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <>
                {[1,2,3,4].map(i => <tr key={i}><td colSpan={8}><div className="skeleton-row" /></td></tr>)}
              </>
            )}
            {!loading && displayed.length === 0 && (
              <tr>
                <td colSpan={8}>
                  <div className="state-wrapper">
                    <CheckCircle2 size={28} style={{ color: 'var(--success)' }} aria-hidden="true" />
                    <div className="state-title" style={{ color: 'var(--success)' }}>
                      {filter === 'ALL' ? 'No documents in queue' : `No ${filter.replace('_', ' ').toLowerCase()} documents`}
                    </div>
                    <div className="state-desc">All documents in this filter are clear.</div>
                  </div>
                </td>
              </tr>
            )}
            {displayed.map((v: any) => (
              <tr key={v.document_id}>
                <td><span className="mono td-mono" style={{ fontWeight: 500 }}>DOC-{String(v.document_id).padStart(4, '0')}</span></td>
                <td><span className="td-primary">{v.bidder_name || `Bidder #${v.bidder_id}`}</span></td>
                <td className="td-muted" style={{ fontSize: '12px' }}>{v.document_type}</td>
                <td>
                  {v.version && <span className="mono td-mono td-muted">v{v.version}</span>}
                </td>
                <td><StatusBadge status={v.verification_status} size="sm" /></td>
                <td>
                  {v.ocr_status !== 'COMPLETED' ? (
                    <span className="td-muted" style={{ fontSize: '12px' }}>Awaiting OCR</span>
                  ) : typeof v.ocr_confidence === 'number' ? (
                    <span className="mono td-mono" style={{ fontWeight: 500, color: confColor(v.ocr_confidence) }}>
                      {(v.ocr_confidence * 100).toFixed(0)}%
                      {v.ocr_confidence < 0.6 && (
                        <span className="status-badge badge-warning size-sm" style={{ marginLeft: '6px' }}>Low</span>
                      )}
                    </span>
                  ) : (
                    <span className="td-muted" style={{ fontSize: '12px' }}>—</span>
                  )}
                </td>
                <td className="td-mono td-muted" style={{ whiteSpace: 'nowrap' }}>
                  {v.last_verified_at
                    ? new Date(v.last_verified_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
                    : '—'}
                </td>
                <td>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {['RETRY_REQUIRED', 'PENDING', 'MANUAL_REVIEW', 'MISMATCH'].includes(v.verification_status) && (
                      <button
                        className="btn btn-outline btn-sm"
                        onClick={() => handleRetry(v.document_id)}
                        disabled={busyDoc === v.document_id}
                        aria-label={`Retry verification for document ${v.document_id}`}
                        title="Retry verification"
                      >
                        <RefreshCw size={11} aria-hidden="true" className={busyDoc === v.document_id ? 'animate-spin' : ''} />
                        {busyDoc === v.document_id ? 'Retrying…' : 'Retry'}
                      </button>
                    )}
                    <Link
                      href={`/bidders/${v.bidder_id}?tender=1`}
                      className="btn btn-ghost btn-sm btn-icon"
                      aria-label="Open bidder dossier"
                      title="Open dossier"
                    >
                      <ChevronRight size={13} aria-hidden="true" />
                    </Link>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {displayed.length > 0 && (
          <div className="table-footer">
            Showing {displayed.length} of {total} verification records
          </div>
        )}
      </div>

      {/* Needs action panel */}
      {needsAction.length > 0 && (
        <div style={{ marginTop: '22px' }}>
          <div className="section-header section-header-soft">
            <span className="section-title">Requires Action</span>
            <span className="status-badge badge-danger size-sm">{needsAction.length}</span>
          </div>
          <div className="alert alert-warning" role="alert" style={{ marginBottom: '12px' }}>
            <AlertTriangle size={14} aria-hidden="true" style={{ flexShrink: 0 }} />
            <span>
              {needsAction.length} document{needsAction.length !== 1 ? 's' : ''} require officer action
              (manual review, retry, or mismatch resolution) before the submission can be cleared.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
