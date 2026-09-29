'use client';
import React, { useState } from 'react';
import Link from 'next/link';
import { useApi } from '../../lib/useApi';
import StatusBadge from '../../components/StatusBadge';
import {
  Shield,
  History,
  FileBarChart,
  ChevronRight,
  RotateCw,
  Search,
} from 'lucide-react';

/* ================================================================
   AUDITOR DASHBOARD
   Read-only oversight — event ledger, integrity, evidence lineage.
   ================================================================ */
export default function AuditorDashboard() {
  const { data: auditEvents = [], loading: auditLoading, mutate: refreshAudit } = useApi<any[]>('/audit');
  const { data: metrics, loading: metricsLoading } = useApi<any>('/dashboard');
  const [search, setSearch] = useState('');
  const [filterAction, setFilterAction] = useState<string>('ALL');

  // Action types from event data
  const actionTypes = Array.from(new Set(auditEvents.map((e: any) => e.action))).slice(0, 10) as string[];

  const filtered = auditEvents.filter((e: any) => {
    const matchSearch =
      !search ||
      e.action?.toLowerCase().includes(search.toLowerCase()) ||
      e.username?.toLowerCase().includes(search.toLowerCase()) ||
      e.entity_type?.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filterAction === 'ALL' || e.action === filterAction;
    return matchSearch && matchFilter;
  });

  function severityDot(action: string): string {
    const a = action?.toUpperCase() || '';
    if (a.includes('REJECT') || a.includes('DELETE') || a.includes('FAIL')) return 'danger';
    if (a.includes('APPROVE') || a.includes('VERIFY') || a.includes('SIGN')) return 'success';
    if (a.includes('REVIEW') || a.includes('FLAG') || a.includes('MANUAL')) return 'warning';
    return 'info';
  }

  return (
    <div className="main-wrapper">
      {/* Page header */}
      <div className="page-header">
        <div className="page-header-text">
          <div className="page-eyebrow">Audit Oversight · Evidence Console</div>
          <h1 className="page-title">Audit &amp; Evidence Ledger</h1>
          <p className="page-desc">
            Immutable event ledger · officer decision trail · evidence lineage · report archive
          </p>
        </div>
        <div className="page-actions">
          <button
            className="btn btn-outline"
            onClick={() => refreshAudit(true)}
            aria-label="Refresh audit log"
          >
            <RotateCw size={13} aria-hidden="true" />
            Refresh
          </button>
          <Link href="/audit" className="btn btn-primary">
            <History size={13} aria-hidden="true" />
            Full Audit Trail
          </Link>
        </div>
      </div>
      <hr className="page-rule" />

      {/* Metric index row */}
      <div className="metric-strip" aria-label="Audit metrics">
        <div className="metric-cell">
          <div className="metric-value">{auditLoading ? '…' : auditEvents.length}</div>
          <div className="metric-label">Total Events</div>
          <div className="metric-change">Immutable audit records</div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">{metricsLoading ? '…' : (metrics?.active_tenders ?? '—')}</div>
          <div className="metric-label">Active Tenders</div>
          <div className="metric-change">Under audit scope</div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">{metricsLoading ? '…' : (metrics?.total_bidders ?? '—')}</div>
          <div className="metric-label">Bidders</div>
          <div className="metric-change">In scope</div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">
            {metricsLoading ? '…' : (metrics?.overall_compliance_rate ?? '—')}
            {!metricsLoading && metrics?.overall_compliance_rate !== undefined ? '%' : ''}
          </div>
          <div className="metric-label">Compliance Rate</div>
          <div className="metric-change">Across all bidders</div>
        </div>
        <div className={`metric-cell${(metrics?.risk_distribution?.HIGH ?? 0) > 0 ? ' alert' : ''}`}>
          <div className="metric-value">
            {metricsLoading ? '…' : (metrics?.risk_distribution?.HIGH ?? 0)}
          </div>
          <div className="metric-label">High Risk</div>
          <div className="metric-change">Flagged submissions</div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">{metricsLoading ? '…' : (metrics?.manual_reviews_required ?? 0)}</div>
          <div className="metric-label">Pending Decisions</div>
          <div className="metric-change">Officer review required</div>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid-main-side">

        {/* LEFT: Main audit event ledger */}
        <div style={{ minWidth: 0 }}>
          {/* Filter / search bar */}
          <div style={{ display: 'flex', gap: '10px', marginBottom: '14px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div className="search-input-wrapper" style={{ flex: 1, minWidth: '220px' }}>
              <Search size={13} className="search-icon" aria-hidden="true" />
              <input
                type="text"
                className="form-input"
                placeholder="Search events, officers, entity types…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                aria-label="Search audit events"
              />
            </div>
            <select
              className="form-select"
              style={{ width: '190px' }}
              value={filterAction}
              onChange={e => setFilterAction(e.target.value)}
              aria-label="Filter by action type"
            >
              <option value="ALL">All Actions</option>
              {actionTypes.map(a => (
                <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>

          <div className="section-header">
            <div>
              <span className="section-title">Audit Event Ledger</span>
              <div className="section-sub">{filtered.length} of {auditEvents.length} events</div>
            </div>
          </div>

          <div className="table-wrapper">
            <table className="data-table" aria-label="Audit event ledger">
              <thead>
                <tr>
                  <th>Event ID</th>
                  <th>Action</th>
                  <th>Officer</th>
                  <th>Entity</th>
                  <th>Record</th>
                  <th>Timestamp</th>
                  <th><span className="sr-only">View</span></th>
                </tr>
              </thead>
              <tbody>
                {auditLoading && (
                  <>{[1,2,3,4,5].map(i => <tr key={i}><td colSpan={7}><div className="skeleton-row" /></td></tr>)}</>
                )}
                {!auditLoading && filtered.length === 0 && (
                  <tr>
                    <td colSpan={7}>
                      <div className="state-wrapper">
                        <History size={28} className="state-icon" aria-hidden="true" />
                        <div className="state-title">No events found</div>
                        <div className="state-desc">
                          {search || filterAction !== 'ALL'
                            ? 'Try adjusting your filters.'
                            : 'Audit events will appear as officers take actions.'}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
                {filtered.slice(0, 25).map((evt: any) => (
                  <tr key={evt.id}>
                    <td><span className="mono td-mono td-muted">#{String(evt.id).padStart(6, '0')}</span></td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                        <div className={`timeline-dot ${severityDot(evt.action)}`} style={{ margin: 0, flexShrink: 0 }} />
                        <span className="mono td-mono" style={{ fontWeight: 500 }}>{evt.action}</span>
                      </div>
                    </td>
                    <td><span className="td-primary" style={{ fontSize: '12.5px' }}>{evt.username}</span></td>
                    <td>
                      <span className="status-badge badge-neutral size-sm">{evt.entity_type}</span>
                    </td>
                    <td className="td-mono td-muted">
                      {evt.entity_id ? `ID:${evt.entity_id}` : '—'}
                    </td>
                    <td className="td-mono td-muted" style={{ whiteSpace: 'nowrap' }}>
                      {new Date(evt.created_at).toLocaleString('en-IN', {
                        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
                      })}
                    </td>
                    <td>
                      {evt.entity_type === 'BIDDER' && evt.entity_id && (
                        <Link
                          href={`/bidders/${evt.entity_id}?tender=1`}
                          className="btn btn-ghost btn-sm btn-icon"
                          aria-label="View entity"
                        >
                          <ChevronRight size={13} aria-hidden="true" />
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filtered.length > 25 && (
              <div className="table-footer">
                Showing 25 of {filtered.length} events
                <Link href="/audit" className="btn btn-ghost btn-sm">View full audit trail</Link>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: Oversight rail */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '26px', minWidth: 0 }}>

          {/* Integrity notice */}
          <div className="card" style={{ borderLeft: '3px solid var(--role-accent)', padding: '14px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <Shield size={14} color="var(--role-accent)" aria-hidden="true" />
              <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                Audit Integrity
              </span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.6' }}>
              All events are immutable and cryptographically chained. This ledger cannot be modified
              after creation. Any modification attempt is itself logged.
            </div>
            <Link href="/audit" className="btn btn-outline btn-sm" style={{ marginTop: '10px', width: '100%', justifyContent: 'center' }}>
              Verify chain integrity
            </Link>
          </div>

          {/* Risk distribution */}
          <div>
            <div className="section-header section-header-soft">
              <span className="section-title">Risk Distribution</span>
            </div>
            <div className="card" style={{ padding: '14px 16px' }}>
              {metrics?.risk_distribution ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {Object.entries(metrics.risk_distribution as Record<string, number>).map(([level, count]) => (
                    <div key={level} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{
                        width: '84px', fontSize: '10.5px', fontWeight: 600, color: 'var(--text-muted)',
                        textTransform: 'uppercase', letterSpacing: '0.05em', flexShrink: 0,
                      }}>{level.replace('_', ' ')}</div>
                      <div className="risk-bar-track">
                        <div style={{
                          height: '100%',
                          width: `${Math.min(100, (count / (metrics.total_bidders || 1)) * 100)}%`,
                          background: level === 'HIGH' ? 'var(--red-600)' : level === 'MEDIUM' ? 'var(--amber-600)' : level === 'LOW' ? 'var(--green-600)' : 'var(--ink-200)',
                          borderRadius: '1px',
                          transition: 'width 0.5s ease',
                        }} />
                      </div>
                      <span className="mono td-mono" style={{ fontWeight: 500, width: '24px', textAlign: 'right', flexShrink: 0 }}>
                        {count}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="state-desc" style={{ textAlign: 'center', padding: '12px 0' }}>No risk data available.</div>
              )}
            </div>
          </div>

          {/* Records shortcuts */}
          <div>
            <div className="section-header section-header-soft">
              <span className="section-title">Records</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <Link href="/reports" className="btn btn-outline" style={{ justifyContent: 'flex-start', width: '100%' }}>
                <FileBarChart size={13} aria-hidden="true" />
                Report Archive
              </Link>
              <Link href="/verification" className="btn btn-outline" style={{ justifyContent: 'flex-start', width: '100%' }}>
                <Shield size={13} aria-hidden="true" />
                Verification Records
              </Link>
              <Link href="/bidders" className="btn btn-outline" style={{ justifyContent: 'flex-start', width: '100%' }}>
                <ChevronRight size={13} aria-hidden="true" />
                Bidder Registry
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
