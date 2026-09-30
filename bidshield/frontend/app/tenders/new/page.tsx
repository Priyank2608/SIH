'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api } from '../../../lib/api';
import { useCurrentUser } from '../../../lib/userContext';
import { can } from '../../../lib/permissions';
import {
  ArrowLeft, FileText, CalendarDays, Building2, ListChecks,
  AlertCircle, CheckCircle2, Loader2,
} from 'lucide-react';

/**
 * TENDER CREATION — Procurement Officer entry point of the real workflow:
 * Create Tender → Define Requirements → Upload Tender Document →
 * Upload Bidder Documents → Run Analysis → Review → Decide → Report.
 *
 * No dummy defaults: every tender field is entered by the officer.
 * The department is tender/organization context, not a managed module.
 */
export default function CreateTenderPage() {
  const router = useRouter();
  const user = useCurrentUser();
  const canCreate = can(user?.role, 'tender.create');

  const [form, setForm] = useState({
    tender_ref: '',
    title: '',
    department: '',
    description: '',
    estimated_value_cr: '',
    issue_date: new Date().toISOString().slice(0, 10),
    closing_date: '',
  });
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);

  const set = (key: keyof typeof form) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => setForm(prev => ({ ...prev, [key]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!form.tender_ref.trim() || !form.title.trim() || !form.department.trim() || !form.closing_date) {
      setError('Tender reference, title, department, and submission due date are required.');
      return;
    }
    try {
      setCreating(true);
      const tender = await api('/tenders', {
        method: 'POST',
        body: JSON.stringify({
          tender_ref: form.tender_ref.trim(),
          title: form.title.trim(),
          department: form.department.trim(),
          category: 'General',
          description: form.description.trim() || null,
          estimated_value_cr: parseFloat(form.estimated_value_cr) || 0,
          issue_date: form.issue_date,
          closing_date: form.closing_date,
        }),
      });
      router.push(`/tenders/${tender.id}?created=1`);
    } catch (err: any) {
      setError(err.message || 'Failed to create tender');
    } finally {
      setCreating(false);
    }
  };

  if (user && !canCreate) {
    return (
      <main className="main-wrapper">
        <div className="alert alert-danger" role="alert">
          <AlertCircle size={15} aria-hidden="true" style={{ flexShrink: 0 }} />
          <span>Tender creation is restricted to the Procurement Officer role.</span>
        </div>
      </main>
    );
  }

  return (
    <main className="main-wrapper">
      <div className="page-header">
        <div className="page-header-text">
          <div className="page-eyebrow">Procurement Workflow · Step 1</div>
          <h1 className="page-title">Create New Tender</h1>
          <p className="page-desc">
            Register the tender and its organization context. Requirements, the tender
            document, and bidder submissions are added on the tender workspace next.
          </p>
        </div>
        <div className="page-actions">
          <Link href="/tenders" className="btn btn-outline">
            <ArrowLeft size={13} aria-hidden="true" /> Back to Tenders
          </Link>
        </div>
      </div>
      <hr className="page-rule" />

      <form onSubmit={handleSubmit} aria-label="Create tender form" style={{ maxWidth: '780px' }}>
        {error && (
          <div className="alert alert-danger mb-4" role="alert" aria-live="assertive">
            <AlertCircle size={15} aria-hidden="true" style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        {/* Identification */}
        <div className="section">
          <div className="section-header">
            <div>
              <span className="section-title">Tender Identification</span>
              <div className="section-sub">Reference and title exactly as published</div>
            </div>
            <FileText size={16} aria-hidden="true" style={{ color: 'var(--text-faint)' }} />
          </div>
          <div className="card">
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label" htmlFor="ct-ref">
                  Tender Reference Number <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                </label>
                <input
                  id="ct-ref" type="text" className="form-input"
                  value={form.tender_ref} onChange={set('tender_ref')}
                  placeholder="e.g. 2026_DPHG_GASCYL_001"
                  required aria-required="true" maxLength={100}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="ct-title">
                  Tender Title <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                </label>
                <input
                  id="ct-title" type="text" className="form-input"
                  value={form.title} onChange={set('title')}
                  placeholder="e.g. Supply of Gas Cylinders"
                  required aria-required="true" maxLength={300}
                />
              </div>
            </div>
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label" htmlFor="ct-dept">
                  Department / Organization <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                </label>
                <input
                  id="ct-dept" type="text" className="form-input"
                  value={form.department} onChange={set('department')}
                  placeholder="e.g. Department of Petroleum and Natural Gas"
                  required aria-required="true" maxLength={200}
                />
                <span className="form-hint">
                  Part of this tender&apos;s organization context — entered per tender, no department module.
                </span>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="ct-value">Estimated Value (₹ Crores)</label>
                <input
                  id="ct-value" type="number" step="0.01" min="0" className="form-input"
                  value={form.estimated_value_cr} onChange={set('estimated_value_cr')}
                  placeholder="e.g. 4.5"
                />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="ct-desc">Tender Description</label>
              <textarea
                id="ct-desc" className="form-textarea" rows={4}
                value={form.description} onChange={set('description')}
                placeholder="Scope of supply, delivery terms, and evaluation conditions from the tender notice…"
                maxLength={4000}
              />
              <span className="form-hint">
                After creation, AI may suggest draft requirements from this text and the tender
                document — every suggestion stays <b>PENDING</b> until you approve it.
              </span>
            </div>
          </div>
        </div>

        {/* Dates */}
        <div className="section">
          <div className="section-header">
            <div>
              <span className="section-title">Key Dates</span>
              <div className="section-sub">Publication and submission window</div>
            </div>
            <CalendarDays size={16} aria-hidden="true" style={{ color: 'var(--text-faint)' }} />
          </div>
          <div className="card">
            <div className="grid-2">
              <div className="form-group">
                <label className="form-label" htmlFor="ct-issue">
                  Issue Date <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                </label>
                <input
                  id="ct-issue" type="date" className="form-input"
                  value={form.issue_date} onChange={set('issue_date')}
                  required aria-required="true"
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="ct-close">
                  Submission Due Date <span aria-hidden="true" style={{ color: 'var(--danger)' }}>*</span>
                </label>
                <input
                  id="ct-close" type="date" className="form-input"
                  value={form.closing_date} onChange={set('closing_date')}
                  required aria-required="true"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Workflow preview */}
        <div className="section">
          <div className="section-header section-header-soft">
            <span className="section-title">After Creation</span>
          </div>
          <div className="card" style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
            <ListChecks size={16} aria-hidden="true" style={{ color: 'var(--role-accent)', flexShrink: 0, marginTop: 2 }} />
            <div style={{ fontSize: '12.5px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
              Create Tender → <b>Define &amp; approve requirements</b> → Upload tender document →
              Upload bidder documents → Run analysis → Review results → Officer determination → Generate report.
              The tender workspace opens with these steps in order.
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '18px' }}>
          <Link href="/tenders" className="btn btn-outline">Cancel</Link>
          <button type="submit" className="btn btn-primary btn-lg" disabled={creating} aria-busy={creating}>
            {creating ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
            {creating ? 'Creating…' : 'Create Tender'}
          </button>
        </div>
      </form>
    </main>
  );
}
