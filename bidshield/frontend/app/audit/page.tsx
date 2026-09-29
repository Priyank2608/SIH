'use client';
import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../lib/api';
import PermissionGate from '../../components/PermissionGate';
import {
  History,
  RotateCw,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Search,
  Lock,
  ShieldCheck,
  X,
} from 'lucide-react';

/* ── Action badge colour coding ───────────────────────────────── */
function getActionStyle(action: string): { bg: string; color: string } {
  const u = action.toUpperCase();
  if (u.includes('DECISION'))                    return { bg: 'var(--blue-100)',   color: 'var(--blue-700)' };
  if (u.includes('REPORT'))                      return { bg: 'var(--purple-100)', color: 'var(--purple-700)' };
  if (u.includes('VERIFIED') || u.includes('VERIFICATION')) return { bg: 'var(--green-100)', color: 'var(--green-700)' };
  if (u.includes('MISMATCH') || u.includes('FAILURE') || u.includes('ERROR')) return { bg: 'var(--red-100)', color: 'var(--red-700)' };
  if (u.includes('REJECTED'))                    return { bg: 'var(--red-100)',    color: 'var(--red-700)' };
  if (u.includes('APPROVED'))                    return { bg: 'var(--green-100)',  color: 'var(--green-700)' };
  if (u.includes('UPLOAD'))                      return { bg: 'var(--amber-100)',  color: 'var(--amber-700)' };
  if (u.includes('LOGIN') || u.includes('SIGN')) return { bg: 'var(--ink-50)',    color: 'var(--ink-400)' };
  return { bg: 'var(--ivory-200)', color: 'var(--text-secondary)' };
}

/* ── Integrity result display ─────────────────────────────────── */
interface IntegrityResult {
  status: 'ok' | 'error' | string;
  checked: number;
  message?: string;
}

const ACTION_FILTER_OPTIONS = [
  '',
  'DECISION',
  'REPORT_GENERATED',
  'REPORT_DOWNLOADED',
  'DOCUMENT_UPLOADED',
  'VERIFICATION_RETRIED',
  'LOGIN',
];

export default function AuditTrailPage() {
  const [logs, setLogs]             = useState<any[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [searchText, setSearchText] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [integrity, setIntegrity]   = useState<IntegrityResult | null>(null);
  const [checkingIntegrity, setCheckingIntegrity] = useState(false);

  const loadLogs = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params = new URLSearchParams({ limit: '100' });
      if (actionFilter) params.set('action', actionFilter);
      const data = await api(`/audit?${params.toString()}`);
      setLogs(data);
    } catch (err: any) {
      setError(err.message || 'Unable to load audit events.');
    } finally {
      setLoading(false);
    }
  }, [actionFilter]);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  const checkIntegrity = async () => {
    try {
      setCheckingIntegrity(true);
      const result = await api('/audit/integrity');
      setIntegrity(result);
    } catch (err: any) {
      setIntegrity({ status: 'error', checked: 0, message: err.message || 'Integrity check failed' });
    } finally {
      setCheckingIntegrity(false);
    }
  };

  // Client-side text search (on top of action filter)
  const displayed = searchText.trim()
    ? logs.filter(l => {
        const q = searchText.toLowerCase();
        return (
          String(l.action).toLowerCase().includes(q) ||
          String(l.username || '').toLowerCase().includes(q) ||
          String(l.entity_type || '').toLowerCase().includes(q) ||
          String(l.entity_id || '').toLowerCase().includes(q) ||
          JSON.stringify(l.details || {}).toLowerCase().includes(q)
        );
      })
    : logs;

  return (
    <div className="main-wrapper">
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header-text">
          <div className="page-eyebrow">Audit Oversight</div>
          <h1 className="page-title">Audit Trail</h1>
          <p className="page-desc">
            Immutable, tamper-evident event ledger — every authentication, OCR job, verification, requirement approval,
            and officer determination is permanently recorded.
          </p>
        </div>
        <div className="page-actions">
          <PermissionGate permission="audit.view">
            <button
              className="btn btn-outline btn-sm"
              onClick={checkIntegrity}
              disabled={checkingIntegrity}
              aria-label="Run audit chain integrity check"
            >
              <ShieldCheck size={13} aria-hidden />
              {checkingIntegrity ? 'Checking…' : 'Integrity Check'}
            </button>
          </PermissionGate>
          <button
            className="btn btn-outline"
            onClick={loadLogs}
            disabled={loading}
            aria-label="Refresh audit log"
          >
            <RotateCw size={13} aria-hidden className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>
      <hr className="page-rule" />

      {/* Immutability notice */}
      <div className="alert alert-info mb-4" role="note">
        <Lock size={14} aria-hidden style={{ flexShrink: 0 }} />
        <span>
          Records in this ledger are immutable. Every officer action, system verification, and compliance determination
          is permanently recorded and cannot be modified.
        </span>
      </div>

      {/* Integrity result */}
      {integrity && (
        <div
          className={`alert mb-4 ${integrity.status === 'ok' ? 'alert-success' : 'alert-danger'}`}
          role="status"
          style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {integrity.status === 'ok'
              ? <ShieldCheck size={15} aria-hidden />
              : <AlertCircle size={15} aria-hidden />}
            <span>
              {integrity.status === 'ok'
                ? `Integrity OK — ${integrity.checked} events verified`
                : `Integrity issue detected — ${integrity.message || 'chain broken'}`}
            </span>
          </div>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setIntegrity(null)}
            aria-label="Dismiss integrity result"
          >
            <X size={13} aria-hidden />
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="filter-bar mb-4" style={{ flexWrap: 'wrap', gap: '10px' }}>
        <div className="search-input-wrapper" style={{ flex: '1 1 240px', maxWidth: '360px' }}>
          <Search size={14} className="search-icon" aria-hidden />
          <input
            id="audit-search"
            type="search"
            className="form-input"
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            placeholder="Search officer, action, entity…"
            aria-label="Search audit events"
          />
        </div>
        <select
          id="audit-action-filter"
          className="form-select"
          style={{ width: 'auto', minWidth: '200px' }}
          value={actionFilter}
          onChange={e => setActionFilter(e.target.value)}
          aria-label="Filter by action type"
        >
          <option value="">All actions</option>
          {ACTION_FILTER_OPTIONS.filter(Boolean).map(a => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-danger mb-4" role="alert">
          <AlertCircle size={15} aria-hidden style={{ flexShrink: 0 }} />
          <span>{error}</span>
          <button className="btn btn-sm btn-outline" onClick={loadLogs} style={{ marginLeft: 'auto' }}>Retry</button>
        </div>
      )}

      {/* Table */}
      <div className="card card-flush">
        {loading ? (
          <div aria-busy="true" aria-label="Loading audit events">
            {[1, 2, 3, 4, 5, 6].map(i => <div key={i} className="skeleton skeleton-row" />)}
          </div>
        ) : (
          <div className="table-wrapper" style={{ border: 'none', borderRadius: 0 }}>
            <table className="data-table" aria-label="Audit trail ledger">
              <thead>
                <tr>
                  <th scope="col">Event #</th>
                  <th scope="col">Timestamp</th>
                  <th scope="col">Officer</th>
                  <th scope="col">Action</th>
                  <th scope="col">Entity</th>
                  <th scope="col">Entity ID</th>
                  <th scope="col"><span className="sr-only">Details</span></th>
                </tr>
              </thead>
              <tbody>
                {displayed.length === 0 ? (
                  <tr>
                    <td colSpan={7}>
                      <div className="state-wrapper">
                        <History size={32} className="state-icon" aria-hidden />
                        <div className="state-title">No audit events found</div>
                        <div className="state-desc">
                          {searchText || actionFilter
                            ? 'No events match the current filters. Clear them to see all events.'
                            : 'No audit events have been recorded yet.'}
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : displayed.map((log: any) => {
                  const { bg, color } = getActionStyle(log.action);
                  const isExpanded = expandedId === log.id;
                  return (
                    <React.Fragment key={log.id}>
                      <tr>
                        <td>
                          <span className="mono" style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                            #{log.id}
                          </span>
                        </td>
                        <td>
                          <span className="mono" style={{ fontSize: '12px', whiteSpace: 'nowrap' }}>
                            {new Date(log.created_at).toLocaleString('en-IN', {
                              day: '2-digit', month: 'short', year: 'numeric',
                              hour: '2-digit', minute: '2-digit', second: '2-digit',
                            })}
                          </span>
                        </td>
                        <td style={{ fontWeight: 600, fontSize: '13px' }}>{log.username || '—'}</td>
                        <td>
                          <span style={{
                            display: 'inline-block',
                            background: bg,
                            color,
                            padding: '2px 7px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 700,
                            fontFamily: 'var(--font-mono)',
                            letterSpacing: '0.02em',
                          }}>
                            {log.action}
                          </span>
                        </td>
                        <td style={{ fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
                          {log.entity_type || '—'}
                        </td>
                        <td>
                          <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)', maxWidth: '120px', display: 'inline-block', overflow: 'hidden', textOverflow: 'ellipsis', verticalAlign: 'middle' }}>
                            {log.entity_id || '—'}
                          </span>
                        </td>
                        <td>
                          <button
                            className="btn btn-sm btn-ghost"
                            onClick={() => setExpandedId(isExpanded ? null : log.id)}
                            aria-expanded={isExpanded}
                            aria-label={isExpanded ? 'Collapse event details' : 'Expand event details'}
                          >
                            {isExpanded
                              ? <ChevronDown size={14} aria-hidden />
                              : <ChevronRight size={14} aria-hidden />}
                            {isExpanded ? 'Hide' : 'Details'}
                          </button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr>
                          <td
                            colSpan={7}
                            style={{ background: 'var(--paper-200)', padding: '12px 20px', borderBottom: '1px solid var(--border)' }}
                          >
                            <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px' }}>
                              Raw Audit Record Payload
                            </div>
                            <pre className="raw-ocr-pre" style={{ maxHeight: '200px', fontFamily: 'var(--font-mono)', fontSize: '11.5px' }}>
                              {JSON.stringify(log.details, null, 2)}
                            </pre>
                            {log.ip_address && (
                              <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
                                IP Address: <span className="mono">{log.ip_address}</span>
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {!loading && displayed.length > 0 && (
          <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border)', fontSize: '12px', color: 'var(--text-muted)', background: 'var(--ivory-200)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>
              {displayed.length} event{displayed.length !== 1 ? 's' : ''}
              {(searchText || actionFilter) && ` — filtered`}
            </span>
            {(searchText || actionFilter) && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => { setSearchText(''); setActionFilter(''); }}
              >
                Clear filters
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
