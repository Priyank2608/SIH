'use client';
import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import StatusBadge from '../../components/StatusBadge';
import { api } from '../../lib/api';
import { useApi } from '../../lib/useApi';
import {
  Search,
  PlusCircle,
  RotateCw,
  FileText,
  ChevronRight,
  AlertCircle,
  InboxIcon,
  X,
  Filter,
} from 'lucide-react';

const CATEGORIES = [
  'IT Equipment & Hardware',
  'Cloud & Cybersecurity Services',
  'Medical Devices & Hospital Equipment',
  'Heavy Electrical & Power Equipment',
  'Solar & Renewable Energy',
];

export default function TendersListPage() {
  const { data: tenders = [], loading, error, mutate: refreshTenders } = useApi<any[]>('/tenders');
  const [search, setSearch]             = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTender, setNewTender] = useState({
    tender_ref:         '',
    gem_ref:            '',
    title:              '',
    department:         '',
    category:           'IT Equipment & Hardware',
    estimated_value_cr: 1.0,
    issue_date:         new Date().toISOString().slice(0, 10),
    closing_date:       new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
    description:        '',
  });
  const [creating, setCreating] = useState(false);

  /* Filtered list */
  const filteredTenders = useMemo(() => {
    const q = search.trim().toLowerCase();
    return tenders.filter((t) => {
      const matchSearch = !q || [t.tender_ref, t.gem_ref, t.title, t.department, t.category]
        .some((v) => String(v || '').toLowerCase().includes(q));
      const matchStatus = !statusFilter || String(t.status || '').toUpperCase() === statusFilter.toUpperCase();
      return matchSearch && matchStatus;
    });
  }, [search, statusFilter, tenders]);

  /* Distinct statuses for filter */
  const statuses = useMemo(() =>
    Array.from(new Set(tenders.map((t) => String(t.status || '').toUpperCase()).filter(Boolean))),
    [tenders]
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setCreating(true);
      await api('/tenders', {
        method: 'POST',
        body: JSON.stringify(newTender),
      });
      setShowCreateModal(false);
      await refreshTenders(true);
    } catch (err: any) {
      alert(err.message || 'Failed to create tender');
    } finally {
      setCreating(false);
    }
  };

  function openCreateModal() {
    setNewTender({
      tender_ref:         `GEM/2026/B/00${Math.floor(10000 + Math.random() * 90000)}`,
      gem_ref:            `GEM-REF-${Math.floor(10000 + Math.random() * 90000)}`,
      title:              '',
      department:         'Ministry of Communications',
      category:           'IT Equipment & Hardware',
      estimated_value_cr: 5.0,
      issue_date:         new Date().toISOString().slice(0, 10),
      closing_date:       new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
      description:        '',
    });
    setShowCreateModal(true);
  }

  return (
    <div className="main-wrapper">
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header-text">
          <div className="page-eyebrow">Procurement Register</div>
          <h1 className="page-title">Tenders Register</h1>
          <p className="page-desc">
            Review and manage procurement tenders. Click a tender to open the full workspace.
          </p>
        </div>
        <div className="page-actions">
          <button
            className="btn btn-outline btn-sm"
            onClick={() => refreshTenders(true)}
            aria-label="Refresh tenders list"
          >
            <RotateCw size={13} aria-hidden="true" /> Refresh
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={openCreateModal}
          >
            <PlusCircle size={13} aria-hidden="true" /> Create Tender
          </button>
        </div>
      </div>
      <hr className="page-rule" />

      {/* Error state */}
      {error && (
        <div className="alert alert-danger mb-4" role="alert">
          <AlertCircle size={15} aria-hidden="true" style={{ flexShrink: 0 }} />
          <span>Unable to load tenders.</span>
          <button
            className="btn btn-sm btn-outline"
            onClick={() => refreshTenders(true)}
            style={{ marginLeft: 'auto' }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Filter bar */}
      <div className="filter-bar">
        {/* Search */}
        <div className="search-input-wrapper" style={{ flex: '1 1 280px', maxWidth: '420px' }}>
          <Search size={14} className="search-icon" aria-hidden="true" />
          <input
            id="tender-search"
            type="search"
            className="form-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by reference, title, department…"
            aria-label="Search tenders"
          />
        </div>

        {/* Status filter */}
        {statuses.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <Filter size={13} color="var(--text-muted)" aria-hidden="true" />
            <button
              className={`scenario-pill${!statusFilter ? ' active' : ''}`}
              onClick={() => setStatusFilter('')}
            >
              All
            </button>
            {statuses.map((s) => (
              <button
                key={s}
                className={`scenario-pill${statusFilter === s ? ' active' : ''}`}
                onClick={() => setStatusFilter(statusFilter === s ? '' : s)}
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Table / Loading / Empty */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          /* Skeleton loading */
          <div aria-busy="true" aria-label="Loading tenders">
            <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', background: 'var(--paper-200)' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr 160px 100px 100px 100px 110px 90px', gap: '14px' }}>
                {['Reference', 'Title', 'Department', 'Value', 'Deadline', 'Req.', 'Bidders', 'Status'].map((h) => (
                  <div key={h} className="skeleton skeleton-text" style={{ height: '10px' }} />
                ))}
              </div>
            </div>
            {[1,2,3,4].map((i) => (
              <div key={i} className="skeleton skeleton-row" />
            ))}
          </div>
        ) : (
          <div className="table-wrapper" style={{ border: 'none', borderRadius: 0 }}>
            <table className="data-table" aria-label="Tenders register">
              <thead>
                <tr>
                  <th scope="col">Tender Reference</th>
                  <th scope="col">Title &amp; Category</th>
                  <th scope="col">Department</th>
                  <th scope="col" style={{ textAlign: 'right' }}>Value</th>
                  <th scope="col">Deadline</th>
                  <th scope="col" style={{ textAlign: 'center' }}>Requirements</th>
                  <th scope="col" style={{ textAlign: 'center' }}>Bidders</th>
                  <th scope="col">Status</th>
                  <th scope="col"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {filteredTenders.length === 0 ? (
                  <tr>
                    <td colSpan={9}>
                      <div className="state-wrapper">
                        <InboxIcon size={32} className="state-icon" aria-hidden="true" />
                        <div className="state-title">
                          {tenders.length ? 'No tenders match this search.' : 'No tenders yet.'}
                        </div>
                        <div className="state-desc">
                          {tenders.length
                            ? 'Try adjusting your search or filter.'
                            : 'Create the first tender to begin the compliance review workflow.'
                          }
                        </div>
                        {!tenders.length && (
                          <button className="btn btn-primary btn-sm" onClick={openCreateModal}>
                            <PlusCircle size={13} aria-hidden="true" /> Create Tender
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredTenders.map((t) => (
                    <tr key={t.id}>
                      <td>
                        <Link href={`/tenders/${t.id}`} className="td-primary font-mono" style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--primary-text)' }}>
                          {t.tender_ref}
                        </Link>
                        {t.gem_ref && (
                          <div className="td-mono td-muted" style={{ fontSize: '11px', marginTop: '2px' }}>
                            GeM: {t.gem_ref}
                          </div>
                        )}
                      </td>
                      <td>
                        <Link href={`/tenders/${t.id}`} style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '13px' }}>
                          {t.title}
                        </Link>
                        <div className="td-muted" style={{ fontSize: '11.5px', marginTop: '2px' }}>{t.category}</div>
                      </td>
                      <td style={{ fontSize: '12.5px' }}>{t.department}</td>
                      <td style={{ textAlign: 'right', fontWeight: 700, fontSize: '13px', whiteSpace: 'nowrap' }}>
                        ₹{t.estimated_value_cr} Cr
                      </td>
                      <td style={{ whiteSpace: 'nowrap', fontSize: '12.5px' }}>{t.closing_date}</td>
                      <td style={{ textAlign: 'center' }}>
                        <span className="status-badge badge-neutral size-sm">
                          {t.requirements?.length ?? 0}
                        </span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span className="status-badge badge-neutral size-sm">
                          {t.bidders_count ?? 0}
                        </span>
                      </td>
                      <td><StatusBadge status={t.status} size="sm" /></td>
                      <td>
                        <Link
                          href={`/tenders/${t.id}`}
                          className="btn btn-sm btn-primary"
                          style={{ whiteSpace: 'nowrap' }}
                          aria-label={`Open workspace for ${t.tender_ref}`}
                        >
                          Open <ChevronRight size={13} aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Result count */}
        {!loading && filteredTenders.length > 0 && (
          <div style={{
            padding: '10px 14px',
            borderTop: '1px solid var(--border)',
            fontSize: '12px',
            color: 'var(--text-muted)',
            background: 'var(--ivory-200)',
          }}>
            Showing {filteredTenders.length} of {tenders.length} tenders
            {(search || statusFilter) && ' — filtered'}
          </div>
        )}
      </div>

      {/* ========== Create Tender Modal ========== */}
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
              <button
                className="btn-close"
                onClick={() => setShowCreateModal(false)}
                aria-label="Close"
              >
                <X size={16} aria-hidden="true" />
              </button>
            </div>

            <form onSubmit={handleCreate}>
              <div className="modal-body">
                <div className="grid-2">
                  <div className="form-group">
                    <label className="form-label">
                      Tender Reference ID <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    <input
                      type="text"
                      className="form-input"
                      value={newTender.tender_ref}
                      onChange={(e) => setNewTender({ ...newTender, tender_ref: e.target.value })}
                      required
                      aria-required="true"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">GeM Portal Reference</label>
                    <input
                      type="text"
                      className="form-input"
                      value={newTender.gem_ref}
                      onChange={(e) => setNewTender({ ...newTender, gem_ref: e.target.value })}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">
                    Tender Title <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                  </label>
                  <input
                    type="text"
                    className="form-input"
                    value={newTender.title}
                    onChange={(e) => setNewTender({ ...newTender, title: e.target.value })}
                    placeholder="e.g. Supply of Advanced Workstations and IT Hardware"
                    required
                    aria-required="true"
                  />
                </div>

                <div className="grid-2">
                  <div className="form-group">
                    <label className="form-label">
                      Ministry / Department <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    <input
                      type="text"
                      className="form-input"
                      value={newTender.department}
                      onChange={(e) => setNewTender({ ...newTender, department: e.target.value })}
                      required
                      aria-required="true"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Procurement Category</label>
                    <select
                      className="form-select"
                      value={newTender.category}
                      onChange={(e) => setNewTender({ ...newTender, category: e.target.value })}
                    >
                      {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                </div>

                <div className="grid-2">
                  <div className="form-group">
                    <label className="form-label">
                      Estimated Value (₹ Crores) <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      className="form-input"
                      value={newTender.estimated_value_cr}
                      onChange={(e) => setNewTender({ ...newTender, estimated_value_cr: parseFloat(e.target.value) || 1.0 })}
                      required
                      aria-required="true"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">
                      Bid Closing Date <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    <input
                      type="date"
                      className="form-input"
                      value={newTender.closing_date}
                      onChange={(e) => setNewTender({ ...newTender, closing_date: e.target.value })}
                      required
                      aria-required="true"
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Scope &amp; Mandatory Compliance Conditions</label>
                  <textarea
                    className="form-textarea"
                    rows={3}
                    value={newTender.description}
                    onChange={(e) => setNewTender({ ...newTender, description: e.target.value })}
                    placeholder="Specify requirements like GST, PAN, OEM Authorization, Make in India local content..."
                  />
                  <span className="form-hint">
                    The system will extract initial compliance rules from this scope for officer review.
                  </span>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={creating}
                  aria-busy={creating}
                >
                  {creating ? 'Publishing…' : 'Publish Tender & Extract Criteria'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
