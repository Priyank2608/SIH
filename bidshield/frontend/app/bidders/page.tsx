'use client';
import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import StatusBadge from '../../components/StatusBadge';
import { useApi } from '../../lib/useApi';
import {
  Search,
  ChevronRight,
  AlertCircle,
  Users,
  Filter,
  RotateCw,
} from 'lucide-react';

export default function BiddersListPage() {
  const { data: bidders = [], loading, error, mutate: refreshBidders } = useApi<any[]>('/bidders');
  const [search, setSearch] = useState('');
  const [enterpriseFilter, setEnterpriseFilter] = useState('');

  const enterpriseTypes = useMemo(() =>
    Array.from(new Set(bidders.map((b: any) => String(b.enterprise_type || '').toUpperCase()).filter(Boolean))),
    [bidders]
  );

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return bidders.filter((b: any) => {
      const matchSearch = !q || [b.legal_name, b.pan, b.gstin, b.state, b.contact_email]
        .some((v) => String(v || '').toLowerCase().includes(q));
      const matchType = !enterpriseFilter || String(b.enterprise_type || '').toUpperCase() === enterpriseFilter;
      return matchSearch && matchType;
    });
  }, [bidders, search, enterpriseFilter]);

  return (
    <div className="main-wrapper">
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header-text">
          <h1 className="page-title">Bidder Registry</h1>
          <p className="page-desc">
            Internal procurement authority registry of participating bidders. Click any bidder to open their full dossier.
          </p>
        </div>
        <div className="page-actions">
          <button
            className="btn btn-outline btn-sm"
            onClick={() => refreshBidders(true)}
            aria-label="Refresh bidders list"
          >
            <RotateCw size={13} aria-hidden="true" /> Refresh
          </button>
        </div>
      </div>
      <hr className="page-rule" />

      {/* Error state */}
      {error && (
        <div className="alert alert-danger mb-4" role="alert">
          <AlertCircle size={15} aria-hidden="true" style={{ flexShrink: 0 }} />
          <span>Unable to load bidder data.</span>
          <button
            className="btn btn-sm btn-outline"
            onClick={() => refreshBidders(true)}
            style={{ marginLeft: 'auto' }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Filter bar */}
      <div className="filter-bar">
        <div className="search-input-wrapper" style={{ flex: '1 1 280px', maxWidth: '420px' }}>
          <Search size={14} className="search-icon" aria-hidden="true" />
          <input
            id="bidder-search"
            type="search"
            className="form-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, PAN, GSTIN, state�"
            aria-label="Search bidders"
          />
        </div>

        {enterpriseTypes.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <Filter size={13} color="var(--text-muted)" aria-hidden="true" />
            <button
              className={`scenario-pill${!enterpriseFilter ? ' active' : ''}`}
              onClick={() => setEnterpriseFilter('')}
            >
              All Types
            </button>
            {enterpriseTypes.map((et) => (
              <button
                key={et}
                className={`scenario-pill${enterpriseFilter === et ? ' active' : ''}`}
                onClick={() => setEnterpriseFilter(enterpriseFilter === et ? '' : et)}
              >
                {et}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div aria-busy="true" aria-label="Loading bidders">
            {[1,2,3,4,5].map((i) => (
              <div key={i} className="skeleton skeleton-row" />
            ))}
          </div>
        ) : (
          <div className="table-wrapper" style={{ border: 'none', borderRadius: 0 }}>
            <table className="data-table" aria-label="Bidder registry">
              <thead>
                <tr>
                  <th scope="col">Legal Name</th>
                  <th scope="col">PAN</th>
                  <th scope="col">GSTIN</th>
                  <th scope="col">Classification</th>
                  <th scope="col">Location</th>
                  <th scope="col">Contact</th>
                  <th scope="col">Compliance</th>
                  <th scope="col">Risk Level</th>
                  <th scope="col"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={9}>
                      <div className="state-wrapper">
                        <Users size={32} className="state-icon" aria-hidden="true" />
                        <div className="state-title">
                          {bidders.length ? 'No bidders match this search.' : 'No bidders enrolled yet.'}
                        </div>
                        <div className="state-desc">
                          {bidders.length
                            ? 'Try adjusting your search or filter criteria.'
                            : 'Bidders will appear here once enrolled in a tender.'
                          }
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filtered.map((b: any) => (
                    <tr key={b.id}>
                      <td>
                        <Link
                          href={`/bidders/${b.id}`}
                          style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '13px' }}
                        >
                          {b.legal_name}
                        </Link>
                        {b.trade_name && (
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                            t/a {b.trade_name}
                          </div>
                        )}
                      </td>
                      <td className="td-mono" style={{ fontSize: '12.5px', fontWeight: 600 }}>
                        {b.pan}
                      </td>
                      <td className="td-mono" style={{ fontSize: '12.5px' }}>
                        {b.gstin}
                      </td>
                      <td>
                        <span className="status-badge badge-neutral size-sm" style={{ marginBottom: '2px' }}>
                          {b.enterprise_type}
                        </span>
                        {b.is_startup && (
                          <span className="status-badge badge-success size-sm" style={{ marginLeft: '4px' }}>
                            DPIIT Startup
                          </span>
                        )}
                      </td>
                      <td style={{ fontSize: '12.5px' }}>
                        {b.district ? `${b.district}, ` : ''}{b.state}
                      </td>
                      <td>
                        <div style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--text-primary)' }}>
                          {b.contact_person}
                        </div>
                        <div style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                          {b.contact_email}
                        </div>
                      </td>
                      <td>
                        {b.compliance_status
                          ? <StatusBadge status={b.compliance_status} size="sm" />
                          : <span className="status-badge badge-neutral size-sm">�</span>
                        }
                      </td>
                      <td>
                        {b.risk_level
                          ? <StatusBadge status={b.risk_level} size="sm" />
                          : <span className="status-badge badge-neutral size-sm">�</span>
                        }
                      </td>
                      <td>
                        <Link
                          href={`/bidders/${b.id}`}
                          className="btn btn-sm btn-primary"
                          aria-label={`Open dossier for ${b.legal_name}`}
                        >
                          Dossier <ChevronRight size={13} aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer count */}
        {!loading && filtered.length > 0 && (
          <div style={{
            padding: '10px 14px',
            borderTop: '1px solid var(--border)',
            fontSize: '12px',
            color: 'var(--text-muted)',
            background: 'var(--ivory-200)',
          }}>
            Showing {filtered.length} of {bidders.length} bidders
            {(search || enterpriseFilter) && ' � filtered'}
          </div>
        )}
      </div>
    </div>
  );
}
