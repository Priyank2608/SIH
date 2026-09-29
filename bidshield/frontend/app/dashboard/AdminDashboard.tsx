'use client';
import React from 'react';
import Link from 'next/link';
import { useApi } from '../../lib/useApi';
import {
  Users,
  ShieldCheck,
  Settings,
  Lock,
  History,
  Server,
  FileBarChart,
  ChevronRight,
  FileText,
} from 'lucide-react';

/* ================================================================
   SUPER ADMIN DASHBOARD
   System administration console — module directory, platform
   figures, honest status board (values drawn from live endpoints).
   ================================================================ */

const ADMIN_MODULES = [
  {
    icon: FileText,
    title: 'Tenders Register',
    desc: 'Create, edit, and manage all GeM tenders. Set requirements and close bids.',
    href: '/tenders',
    tag: 'WRITE',
  },
  {
    icon: Users,
    title: 'Bidder Registry',
    desc: 'View and manage all enrolled bidders, documents, and compliance status.',
    href: '/bidders',
    tag: 'WRITE',
  },
  {
    icon: ShieldCheck,
    title: 'Verification Center',
    desc: 'OCR verification pipeline, retry gateway, officer inspection tools.',
    href: '/verification',
    tag: 'WRITE',
  },
  {
    icon: FileBarChart,
    title: 'Reports Archive',
    desc: 'Generate and download structured PDF reports for all tenders and bidders.',
    href: '/reports',
    tag: 'WRITE',
  },
  {
    icon: History,
    title: 'Audit Trail',
    desc: 'Immutable event ledger of all officer actions. Full accountability chain.',
    href: '/audit',
    tag: 'READ',
  },
  {
    icon: Settings,
    title: 'System Settings',
    desc: 'Configure platform behaviour, thresholds, notifications, and permissions.',
    href: '/settings',
    tag: 'ADMIN',
  },
];

/* Status values are drawn from live data; unknown → shown as unknown. */
const SYSTEM_COMPONENTS = [
  { label: 'API Server',       key: 'api' },
  { label: 'Database',         key: 'db' },
  { label: 'OCR Engine',       key: 'ocr' },
  { label: 'Verification GW',  key: 'gw' },
  { label: 'Audit Logger',     key: 'audit' },
] as const;

export default function AdminDashboard() {
  const { data: metrics, loading: metricsLoading } = useApi<any>('/dashboard');
  const { data: auditEvents = [], loading: auditLoading } = useApi<any[]>('/audit');
  const { data: tenders  = [] } = useApi<any[]>('/tenders');
  const { data: bidders  = [] } = useApi<any[]>('/bidders');

  const totalValue = (tenders as any[]).reduce((a, t) => a + (t.estimated_value_cr || 0), 0);

  return (
    <div className="main-wrapper">
      {/* Page header */}
      <div className="page-header">
        <div className="page-header-text">
          <div className="page-eyebrow">Administration</div>
          <h1 className="page-title">Platform Administration</h1>
          <p className="page-desc">
            System health · user management · full module access · audit oversight
          </p>
        </div>
        <div className="page-actions">
          <Link href="/settings" className="btn btn-outline">
            <Settings size={13} aria-hidden="true" />
            Settings
          </Link>
          <Link href="/audit" className="btn btn-primary">
            <Lock size={13} aria-hidden="true" />
            Audit Trail
          </Link>
        </div>
      </div>
      <hr className="page-rule" />

      {/* Platform metric index */}
      <div className="metric-strip" aria-label="Platform metrics">
        <div className="metric-cell">
          <div className="metric-value">{metricsLoading ? '…' : (metrics?.active_tenders ?? tenders.length)}</div>
          <div className="metric-label">Active Tenders</div>
          <div className="metric-change">₹{totalValue.toFixed(1)} Cr total value</div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">{metricsLoading ? '…' : (metrics?.total_bidders ?? bidders.length)}</div>
          <div className="metric-label">Bidders</div>
          <div className="metric-change">Enrolled in platform</div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">{metricsLoading ? '…' : (metrics?.completed_verifications ?? '—')}</div>
          <div className="metric-label">Verifications Done</div>
          <div className="metric-change">{metrics?.overall_compliance_rate ?? '—'}% compliance</div>
        </div>
        <div className={`metric-cell${(metrics?.manual_reviews_required ?? 0) > 0 ? ' alert' : ''}`}>
          <div className="metric-value">
            {metricsLoading ? '…' : (metrics?.manual_reviews_required ?? 0)}
          </div>
          <div className="metric-label">Pending Reviews</div>
          <div className="metric-change">Awaiting officer action</div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">{metricsLoading ? '…' : (metrics?.risk_distribution?.HIGH ?? 0)}</div>
          <div className="metric-label">High Risk</div>
          <div className="metric-change">Critical flags</div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">{auditLoading ? '…' : auditEvents.length}</div>
          <div className="metric-label">Audit Events</div>
          <div className="metric-change">Immutable ledger</div>
        </div>
      </div>

      {/* Two-column: module directory + status rail */}
      <div className="grid-main-side">

        {/* Module directory */}
        <div style={{ minWidth: 0 }}>
          <div className="section-header">
            <div>
              <span className="section-title">Platform Modules</span>
              <div className="section-sub">Full access — operations and records</div>
            </div>
            <span className="status-badge badge-active size-sm">Full Access</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
            {ADMIN_MODULES.map((mod) => (
              <Link
                key={mod.href}
                href={mod.href}
                className="panel"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  textDecoration: 'none',
                  transition: 'background 0.12s, box-shadow 0.12s',
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.background = 'var(--paper-200)';
                  (e.currentTarget as HTMLElement).style.boxShadow = 'var(--shadow)';
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.background = '';
                  (e.currentTarget as HTMLElement).style.boxShadow = '';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <mod.icon size={16} aria-hidden="true" style={{ color: 'var(--role-accent-text)' }} />
                  <span className="section-kicker">{mod.tag}</span>
                </div>
                <div>
                  <div className="td-primary" style={{ fontSize: '13.5px', marginBottom: '2px' }}>
                    {mod.title}
                  </div>
                  <div className="td-muted" style={{ fontSize: '12px', lineHeight: '1.45' }}>
                    {mod.desc}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '12px', color: 'var(--role-accent-text)', fontWeight: 600 }}>
                  Open module <ChevronRight size={12} aria-hidden="true" />
                </div>
              </Link>
            ))}
          </div>

          {/* Recent events */}
          <div style={{ marginTop: '28px' }}>
            <div className="section-header">
              <span className="section-title">Recent Events</span>
              <Link href="/audit" className="btn btn-ghost btn-sm">View all</Link>
            </div>
            <div className="card" style={{ padding: '2px 14px' }}>
              {auditLoading ? (
                <div style={{ padding: '12px 0' }}>
                  {[1,2,3].map(i => <div key={i} className="skeleton skeleton-text" />)}
                </div>
              ) : auditEvents.length === 0 ? (
                <div className="state-wrapper" style={{ padding: '16px' }}>
                  <div className="state-desc">No audit events recorded yet.</div>
                </div>
              ) : (
                <div className="timeline" style={{ padding: '6px 0' }}>
                  {auditEvents.slice(0, 6).map((evt: any) => (
                    <div key={evt.id} className="timeline-item">
                      <div className="timeline-dot info" />
                      <div className="timeline-content">
                        <div className="timeline-label">
                          <span className="mono" style={{ fontSize: '11.5px', fontWeight: 600 }}>{evt.action}</span>
                          {' '}<span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>by {evt.username}</span>
                        </div>
                        <div className="timeline-meta">
                          {evt.entity_type} · {new Date(evt.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT: status rail */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '26px', minWidth: 0 }}>
          {/* Status board — reports what the running platform reports */}
          <div>
            <div className="section-header section-header-soft">
              <span className="section-title">System Status</span>
              <span className="section-kicker">Live platform</span>
            </div>
            <div className="card" style={{ padding: '6px 16px' }}>
              {SYSTEM_COMPONENTS.map(s => {
                const healthy = !metricsLoading && metrics !== undefined;
                return (
                  <div key={s.label} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '9px 0',
                    borderBottom: '1px solid var(--border-faint)',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Server size={12} aria-hidden="true" color="var(--text-muted)" />
                      <span style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>{s.label}</span>
                    </div>
                    <span style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '10.5px',
                      letterSpacing: '0.05em',
                      textTransform: 'uppercase',
                      color: healthy ? 'var(--green-700)' : 'var(--text-faint)',
                    }}>
                      {healthy ? 'Operational' : 'Unknown'}
                    </span>
                  </div>
                );
              })}
              <div style={{ padding: '9px 0', fontSize: '11px', color: 'var(--text-faint)', lineHeight: '1.5' }}>
                Status is inferred from live API responses. Per-service health endpoints are not
                exposed by the backend.
              </div>
            </div>
          </div>

          {/* Risk distribution */}
          <div>
            <div className="section-header section-header-soft">
              <span className="section-title">Risk Profile</span>
            </div>
            <div className="card" style={{ padding: '14px 16px' }}>
              {metrics?.risk_distribution
                ? Object.entries(metrics.risk_distribution as Record<string, number>).map(([level, count]) => {
                    const total = Object.values(metrics.risk_distribution as Record<string, number>).reduce((a, b) => a + b, 0) || 1;
                    return (
                      <div key={level} className="risk-dimension-row">
                        <div className="risk-dim-label" style={{ width: '120px' }}>
                          {level.replace('_', ' ')}
                        </div>
                        <div className="risk-bar-track">
                          <div
                            className={`risk-bar-fill ${level === 'HIGH' ? 'risk-bar-high' : level === 'MEDIUM' ? 'risk-bar-medium' : 'risk-bar-low'}`}
                            style={{ width: `${Math.min(100, (count / total) * 100)}%` }}
                            aria-label={`${count} ${level} risk`}
                          />
                        </div>
                        <div className="risk-dim-score">{count}</div>
                      </div>
                    );
                  })
                : <div className="state-desc" style={{ textAlign: 'center', padding: '12px 0' }}>Loading…</div>
              }
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
