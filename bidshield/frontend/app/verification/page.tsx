'use client';
import React, { useState } from 'react';
import Link from 'next/link';
import StatusBadge from '../../components/StatusBadge';
import OCRInspectorModal from '../../components/OCRInspectorModal';
import PermissionGate from '../../components/PermissionGate';
import { api, API_BASE, getToken } from '../../lib/api';
import { useApi } from '../../lib/useApi';
import {
  ShieldCheck,
  RotateCw,
  FileSearch,
  AlertCircle,
  ExternalLink,
  Info,
} from 'lucide-react';

const STATUS_OPTIONS = ['ALL', 'VERIFIED', 'MISMATCH', 'EXPIRED', 'MANUAL_REVIEW', 'RETRY_REQUIRED', 'PENDING'];

export default function VerificationPage() {
  const [statusFilter, setStatusFilter] = useState('ALL');
  const {
    data: records = [],
    loading: recordsLoading,
    error: recordsError,
    mutate: refreshRecords,
  } = useApi<any[]>(`/verification?status=${statusFilter}`);
  const {
    data: providers = [],
    loading: providersLoading,
    error: providersError,
    mutate: refreshProviders,
  } = useApi<any[]>('/verification/providers');

  const [inspectDocId, setInspectDocId] = useState<number | null>(null);
  const [busyDocId, setBusyDocId]       = useState<number | null>(null);
  const [fileError, setFileError]       = useState('');

  const previewDocument = async (documentId: number) => {
    const preview = window.open('', '_blank');
    if (!preview) { setFileError('Allow pop-ups to preview this document.'); return; }
    setFileError('');
    try {
      const token = getToken();
      const response = await fetch(`${API_BASE}/documents/${documentId}/file`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) throw new Error('Document preview unavailable.');
      const blobUrl = URL.createObjectURL(await response.blob());
      preview.location.href = blobUrl;
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    } catch (err: any) {
      preview.close();
      setFileError(err.message || 'Unable to preview this document.');
    }
  };

  const handleRetry = async (documentId: number) => {
    try {
      setBusyDocId(documentId);
      await api(`/verification/${documentId}/retry`, { method: 'POST' });
      await refreshRecords(true);
    } catch (err: any) {
      alert(err.message || 'Retry failed');
    } finally {
      setBusyDocId(null);
    }
  };

  const loading = recordsLoading || providersLoading;

  return (
    <div className="main-wrapper">
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header-text">
          <div className="page-eyebrow">Verification Operations</div>
          <h1 className="page-title">Document Verification Center</h1>
          <p className="page-desc">
            Multi-provider verification pipeline — GSTN, PAN, Udyam, and OEM gateways.
            Results are system findings; officer determination is required for final compliance decisions.
          </p>
        </div>
        <div className="page-actions">
          <button
            className="btn btn-outline"
            onClick={() => { refreshRecords(true); refreshProviders(true); }}
            aria-label="Refresh verification data"
          >
            <RotateCw size={13} aria-hidden="true" /> Refresh
          </button>
        </div>
      </div>
      <hr className="page-rule" />

      {/* Important notice */}
      <div className="alert alert-info mb-4" role="note">
        <Info size={15} aria-hidden="true" style={{ flexShrink: 0 }} />
        <span>
          <strong>System Finding only.</strong> Verification results are evidence for officer review.
          A provider returning <strong>NOT AVAILABLE</strong> means the external gateway could not be queried —
          it does <em>not</em> imply the document is invalid.
        </span>
      </div>

      {/* Provider registry strip */}
      <div className="section-header section-header-soft">
        <div>
          <span className="section-title">Registered Verification Providers</span>
        </div>
        {providersError && (
          <button className="btn btn-sm btn-outline" onClick={() => refreshProviders(true)}>
            Retry
          </button>
        )}
      </div>

      {providersError && (
        <div className="alert alert-danger" role="alert" style={{ marginBottom: '10px' }}>
          <AlertCircle size={14} aria-hidden="true" style={{ flexShrink: 0 }} />
          Unable to load provider registry.
        </div>
      )}

      {!providersLoading && !providersError && providers.length === 0 && (
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '10px' }}>No providers configured.</p>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))', gap: '8px', marginBottom: '22px' }}>
        {providers.map((p: any) => (
          <div
            key={p.provider_code}
            style={{
              background: 'var(--surface-base)',
              border: '1px solid var(--border)',
              borderLeft: '3px solid var(--role-accent)',
              borderRadius: 'var(--radius-md)',
              padding: '10px 12px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', gap: '8px' }}>
              <span style={{ fontWeight: 600, fontSize: '12.5px', color: 'var(--text-primary)' }}>
                {p.provider_name}
              </span>
              <span className="section-kicker">{p.auth_type}</span>
            </div>
            <div className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              {p.document_type} · Timeout: {p.timeout_seconds}s
            </div>
          </div>
        ))}
      </div>

      {/* Status filter bar */}
      <div className="filter-bar" style={{ marginBottom: '14px' }}>
        {STATUS_OPTIONS.map((st) => (
          <button
            key={st}
            className={`scenario-pill${statusFilter === st ? ' active' : ''}`}
            onClick={() => setStatusFilter(st)}
            aria-pressed={statusFilter === st}
          >
            {st === 'ALL' ? 'All' : st.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {/* Errors */}
      {fileError && (
        <div className="alert alert-danger mb-3" role="alert">
          <AlertCircle size={14} aria-hidden="true" style={{ flexShrink: 0 }} />
          {fileError}
        </div>
      )}
      {recordsError && (
        <div className="alert alert-danger mb-4" role="alert">
          <AlertCircle size={14} aria-hidden="true" style={{ flexShrink: 0 }} />
          <span>Unable to load verification records.</span>
          <button className="btn btn-sm btn-outline" onClick={() => refreshRecords(true)} style={{ marginLeft: 'auto' }}>
            Retry
          </button>
        </div>
      )}

      {/* Records table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div aria-busy="true" aria-label="Loading verification records">
            {[1,2,3,4,5].map((i) => <div key={i} className="skeleton skeleton-row" />)}
          </div>
        ) : (
          <div className="table-wrapper" style={{ border: 'none', borderRadius: 0 }}>
            <table className="data-table" aria-label="Verification records">
              <thead>
                <tr>
                  <th scope="col">Doc #</th>
                  <th scope="col">Bidder</th>
                  <th scope="col">Document Type</th>
                  <th scope="col">Ver.</th>
                  <th scope="col">OCR Confidence</th>
                  <th scope="col">Provider / Source</th>
                  <th scope="col">Verification Status</th>
                  <th scope="col">Discrepancy Notes</th>
                  <th scope="col"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {records.length === 0 ? (
                  <tr>
                    <td colSpan={9}>
                      <div className="state-wrapper">
                        <ShieldCheck size={32} className="state-icon" aria-hidden="true" />
                        <div className="state-title">No verification records</div>
                        <div className="state-desc">
                          {statusFilter === 'ALL'
                            ? 'No verification records found yet.'
                            : `No records with status "${statusFilter.replace(/_/g, ' ')}".`
                          }
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : records.map((r: any) => (
                  <tr key={r.document_id}>
                    <td>
                      <span className="mono" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>#{r.document_id}</span>
                    </td>
                    <td>
                      <Link href={`/bidders/${r.bidder_id}`} style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {r.bidder_name}
                      </Link>
                    </td>
                    <td style={{ fontWeight: 600, fontSize: '12.5px' }}>{r.document_type}</td>
                    <td style={{ fontSize: '12.5px' }}>v{r.version}</td>
                    <td>
                      <span className="mono td-mono" style={{ color: r.ocr_confidence >= 0.8 ? 'var(--green-700)' : r.ocr_confidence >= 0.6 ? 'var(--amber-700)' : 'var(--red-700)' }}>
                        {(r.ocr_confidence * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td><span className="mono" style={{ fontSize: '11.5px' }}>{r.verification_provider}</span></td>
                    <td><StatusBadge status={r.verification_status} size="sm" /></td>
                    <td style={{ maxWidth: '240px', fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                      {r.discrepancy_notes
                        ? r.discrepancy_notes
                        : <span className="text-success" style={{ fontSize: '12px' }}>No discrepancies found</span>
                      }
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'nowrap' }}>
                        <PermissionGate permission="verification.retry">
                          <button
                            className="btn btn-sm btn-outline"
                            onClick={() => handleRetry(r.document_id)}
                            disabled={busyDocId === r.document_id}
                            aria-label={`Retry verification for document #${r.document_id}`}
                          >
                            <RotateCw size={12} aria-hidden />
                            {busyDocId === r.document_id ? '…' : 'Retry'}
                          </button>
                        </PermissionGate>
                        <button
                          className="btn btn-sm btn-outline"
                          onClick={() => setInspectDocId(r.document_id)}
                          aria-label={`Open OCR inspector for document #${r.document_id}`}
                        >
                          <FileSearch size={12} aria-hidden="true" /> OCR
                        </button>
                        <button
                          className="btn btn-sm btn-ghost"
                          onClick={() => previewDocument(r.document_id)}
                          aria-label={`Preview document #${r.document_id}`}
                        >
                          <ExternalLink size={12} aria-hidden="true" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && records.length > 0 && (
          <div className="table-footer">
            {records.length} records · Filter: {statusFilter}
          </div>
        )}
      </div>

      {/* OCR Inspector Modal */}
      {inspectDocId && (
        <OCRInspectorModal
          documentId={inspectDocId}
          onClose={() => setInspectDocId(null)}
        />
      )}
    </div>
  );
}
