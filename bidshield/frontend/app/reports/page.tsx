'use client';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { api, downloadFile, fetchFileBlob, recordReportDownload, startBlobDownload } from '../../lib/api';
import PermissionGate from '../../components/PermissionGate';
import {
  FileBarChart,
  Download,
  Eye,
  AlertCircle,
  Info,
  Printer,
  X,
  PenLine,
} from 'lucide-react';
import StatusBadge from '../../components/StatusBadge';

type TenderOption  = { id: number; tender_ref: string; title: string; category?: string };
type BidderOption  = { bidder_id: number; legal_name: string; compliance_status: string; risk_level: string; final_decision: string };
type ReportRecord  = { report_uid: string; report_type: string; filename: string; file_hash: string; tender_id: number; bidder_id?: number; download_count: number; created_at: string };

export default function ReportsPage() {
  const [reports,    setReports]    = useState<ReportRecord[]>([]);
  const [tenders,    setTenders]    = useState<TenderOption[]>([]);
  const [bidders,    setBidders]    = useState<BidderOption[]>([]);
  const [type,       setType]       = useState<'consolidated' | 'individual'>('consolidated');
  const [tenderId,   setTenderId]   = useState('');
  const [bidderId,   setBidderId]   = useState('');
  const [signatureConfigured, setSignatureConfigured] = useState<boolean | null>(null);
  const [loading,        setLoading]        = useState(true);
  const [loadingBidders, setLoadingBidders] = useState(false);
  const [generating,     setGenerating]     = useState(false);
  const [openingUid,     setOpeningUid]     = useState<string | null>(null);
  const [error,          setError]          = useState('');
  const [signaturePrompt, setSignaturePrompt] = useState(false);
  const [preview,        setPreview]        = useState<{ url: string; blob: Blob; filename: string; uid: string } | null>(null);

  const loadReports = useCallback(async () => {
    const rows = await api('/reports');
    setReports(rows);
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([api('/reports'), api('/tenders'), api('/auth/signature')])
      .then(([rows, tenderRows, sig]) => {
        if (!active) return;
        setReports(rows);
        setTenders(tenderRows);
        setTenderId(tenderRows[0] ? String(tenderRows[0].id) : '');
        setSignatureConfigured(Boolean(sig.signature_data));
      })
      .catch((err) => { if (active) setError(err.message || 'Unable to load reports'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!tenderId) { setBidders([]); setBidderId(''); return; }
    let active = true;
    setLoadingBidders(true);
    api(`/tenders/${tenderId}/compliance-matrix`)
      .then((result) => {
        if (!active) return;
        const rows = result.matrix || [];
        setBidders(rows);
        setBidderId((cur) => rows.some((r: BidderOption) => String(r.bidder_id) === cur) ? cur : String(rows[0]?.bidder_id || ''));
      })
      .catch((err) => { if (active) { setBidders([]); setBidderId(''); setError(err.message || 'Unable to load bidders for this tender'); } })
      .finally(() => { if (active) setLoadingBidders(false); });
    return () => { active = false; };
  }, [tenderId]);

  useEffect(() => () => { if (preview?.url) URL.revokeObjectURL(preview.url); }, [preview]);

  const stats = useMemo(() => ({
    total:        reports.length,
    consolidated: reports.filter((r) => r.report_type === 'QUICK_LIST').length,
    individual:   reports.filter((r) => r.report_type === 'DETAILED_ASSESSMENT').length,
  }), [reports]);

  const openReport = async (report: ReportRecord) => {
    try {
      setOpeningUid(report.report_uid); setError('');
      const blob = await fetchFileBlob(`/reports/${report.report_uid}/view`);
      const url  = URL.createObjectURL(blob);
      setPreview({ url, blob, filename: report.filename, uid: report.report_uid });
    } catch (err: any) { setError(err.message || 'Unable to open report'); }
    finally { setOpeningUid(null); }
  };

  const generateReport = async () => {
    if (!tenderId) { setError('Select a tender first.'); return; }
    if (type === 'individual' && !bidderId) { setError('Select a bidder.'); return; }
    if (!signatureConfigured) { setSignaturePrompt(true); return; }
    try {
      setGenerating(true); setError(''); setSignaturePrompt(false);
      const result: ReportRecord = type === 'consolidated'
        ? await api('/reports/quick-list', { method: 'POST', body: JSON.stringify({ tender_id: Number(tenderId) }) })
        : await api('/reports/detailed-assessment', { method: 'POST', body: JSON.stringify({ tender_id: Number(tenderId), bidder_id: Number(bidderId) }) });
      await loadReports();
      await openReport(result);
    } catch (err: any) {
      if (err.message === 'Officer signature is not configured') { setSignatureConfigured(false); setSignaturePrompt(true); }
      else setError(err.message || 'Report generation failed.');
    } finally { setGenerating(false); }
  };

  const handleDownload = async (report: ReportRecord) => {
    try { setError(''); await downloadFile(`/reports/${report.report_uid}/download`, report.filename); await loadReports(); }
    catch (err: any) { setError(err.message || 'Unable to download report'); }
  };

  const handlePreviewDownload = () => {
    if (!preview) return;
    const dUrl = URL.createObjectURL(preview.blob);
    startBlobDownload(dUrl, preview.filename);
    void recordReportDownload(`/reports/${preview.uid}/download`).then(loadReports).catch((e: any) => setError(e.message));
  };

  const printReport = () => {
    const frame = document.getElementById('report-pdf-frame') as HTMLIFrameElement | null;
    frame?.contentWindow?.focus();
    frame?.contentWindow?.print();
  };

  const selectedTender = tenders.find((t) => String(t.id) === tenderId);


  return (
    <div className="main-wrapper">
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header-text">
          <div className="page-eyebrow">Reporting</div>
          <h1 className="page-title">Report Archive</h1>
          <p className="page-desc">
            Generate, preview, and retrieve signed procurement assessment reports.
            Reports are signed with your officer signature and logged in the audit trail.
          </p>
        </div>
        <div className="page-actions">
          <Link href="/profile#signature" className="btn btn-outline">
            <PenLine size={13} aria-hidden="true" /> Manage Signature
          </Link>
        </div>
      </div>
      <hr className="page-rule" />

      {/* Metric index row */}
      <div className="metric-strip" aria-label="Report metrics" style={{ marginBottom: '22px' }}>
        <div className="metric-cell">
          <div className="metric-value">{loading ? '…' : stats.total}</div>
          <div className="metric-label">Total Reports</div>
          <div className="metric-change">Generated in archive</div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">{loading ? '…' : stats.consolidated}</div>
          <div className="metric-label">Consolidated</div>
          <div className="metric-change">Quick list evaluations</div>
        </div>
        <div className="metric-cell">
          <div className="metric-value">{loading ? '…' : stats.individual}</div>
          <div className="metric-label">Individual</div>
          <div className="metric-change">Detailed assessments</div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-danger mb-4" role="alert">
          <AlertCircle size={15} aria-hidden="true" style={{ flexShrink: 0 }} />
          <span>{error}</span>
        </div>
      )}

      {/* Signature prompt */}
      {signaturePrompt && (
        <div className="alert alert-warning mb-4" role="alert" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertCircle size={15} aria-hidden="true" style={{ flexShrink: 0 }} />
            Officer signature is not configured. Save a signature before generating signed reports.
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            <Link href="/profile#signature" className="btn btn-primary btn-sm">Set Up Signature</Link>
            <button className="btn btn-outline btn-sm" onClick={() => setSignaturePrompt(false)}>Dismiss</button>
          </div>
        </div>
      )}

      {/* Generate Report Panel */}
      <div className="section-header">
        <div>
          <span className="section-title">Generate Report</span>
          <div className="section-sub">
            Reports include the authenticated officer's name and digital signature.
          </div>
        </div>
      </div>
      <div className="panel mb-4">
        {/* Report type radio */}
        <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
          {[
            { val: 'consolidated', label: 'Consolidated Tender Evaluation', desc: 'All bidders for a tender' },
            { val: 'individual',   label: 'Individual Bidder Assessment',   desc: 'Single bidder deep-dive' },
          ].map(({ val, label, desc }) => (
            <label
              key={val}
              className={`radio-card${type === val ? ' selected' : ''}`}
            >
              <input
                type="radio"
                name="report-type"
                value={val}
                checked={type === val}
                onChange={() => setType(val as any)}
                style={{ marginTop: '2px', flexShrink: 0, accentColor: 'var(--primary)' }}
              />
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>{label}</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>{desc}</div>
              </div>
            </label>
          ))}
        </div>

        {/* Tender + Bidder selectors */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', alignItems: 'end', marginBottom: '14px' }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" htmlFor="report-tender-select">Tender</label>
            <select
              id="report-tender-select"
              className="form-select"
              value={tenderId}
              onChange={(e) => setTenderId(e.target.value)}
              disabled={loading || !tenders.length}
            >
              {!tenders.length && <option value="">No tenders available</option>}
              {tenders.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.tender_ref} — {t.title}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" htmlFor="report-bidder-select">Bidder</label>
            <select
              id="report-bidder-select"
              className="form-select"
              value={bidderId}
              onChange={(e) => setBidderId(e.target.value)}
              disabled={type !== 'individual' || loadingBidders || !bidders.length}
            >
              {type === 'individual' && !bidders.length && <option value="">—</option>}
              {bidders.map((b) => (
                <option key={b.bidder_id} value={b.bidder_id}>{b.legal_name}</option>
              ))}
            </select>
            {type === 'individual' && !loadingBidders && !bidders.length && (
              <span className="form-hint">No bidders for this tender.</span>
            )}
          </div>

          <PermissionGate permission="report.generate" fallback={
            <div className="alert alert-neutral" style={{ fontSize: '12.5px' }} role="note">
              Report generation is restricted to Procurement Officers. You may view and download existing reports.
            </div>
          }>
            <button
              className="btn btn-primary"
              onClick={generateReport}
              disabled={generating || loading || !tenderId || (type === 'individual' && (!bidderId || loadingBidders))}
              aria-busy={generating}
              style={{ height: '38px' }}
            >
              <FileBarChart size={14} aria-hidden="true" />
              {generating ? 'Generating…' : 'Generate Report'}
            </button>
          </PermissionGate>
        </div>

        {generating && (
          <div className="alert alert-info" role="status">
            <div className="spinner" style={{ width: '16px', height: '16px', flexShrink: 0 }} aria-hidden="true" />
            Collecting verified data, building the assessment, applying officer signature, and finalizing PDF…
          </div>
        )}
      </div>

      {/* Report history table */}
      <div className="section-header">
        <div>
          <span className="section-title">Report History</span>
          <div className="section-sub">Previously generated reports available to your organization.</div>
        </div>
      </div>
      <div className="card card-flush">
        {loading ? (
          <div aria-busy="true" aria-label="Loading reports">
            {[1,2,3].map((i) => <div key={i} className="skeleton skeleton-row" />)}
          </div>
        ) : (
          <div className="table-wrapper" style={{ border: 'none', borderRadius: 0 }}>
            <table className="data-table" aria-label="Report history">
              <thead>
                <tr>
                  <th scope="col">Report ID / Type</th>
                  <th scope="col">Tender / Bidder</th>
                  <th scope="col">Generated</th>
                  <th scope="col" style={{ textAlign: 'center' }}>Downloads</th>
                  <th scope="col"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {reports.length === 0 ? (
                  <tr>
                    <td colSpan={5}>
                      <div className="state-wrapper">
                        <FileBarChart size={32} className="state-icon" aria-hidden="true" />
                        <div className="state-title">No reports yet</div>
                        <div className="state-desc">Generate a report using the panel above.</div>
                      </div>
                    </td>
                  </tr>
                ) : reports.map((report) => (
                  <tr key={report.report_uid}>
                    <td>
                      <div style={{ fontWeight: 700, fontSize: '12px' }} className="mono">
                        BS-RPT-{report.report_uid.slice(0, 12).toUpperCase()}
                      </div>
                      <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {report.report_type === 'QUICK_LIST' ? 'Consolidated evaluation' : 'Individual assessment'}
                      </div>
                    </td>
                    <td style={{ fontSize: '12.5px' }}>
                      Tender #{report.tender_id}
                      {report.bidder_id ? ` · Bidder #${report.bidder_id}` : ' · All bidders'}
                    </td>
                    <td className="td-mono" style={{ fontSize: '12px', whiteSpace: 'nowrap' }}>
                      {new Date(report.created_at).toLocaleString('en-IN', {
                        day: '2-digit', month: 'short', year: 'numeric',
                        hour: '2-digit', minute: '2-digit',
                      })}
                    </td>
                    <td style={{ textAlign: 'center', fontSize: '13px', fontWeight: 600 }}>
                      {report.download_count}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'nowrap' }}>
                        <button
                          className="btn btn-sm btn-outline"
                          onClick={() => openReport(report)}
                          disabled={openingUid === report.report_uid}
                          aria-label={`View report ${report.filename}`}
                        >
                          <Eye size={12} aria-hidden="true" />
                          {openingUid === report.report_uid ? 'Opening…' : 'View'}
                        </button>
                        <button
                          className="btn btn-sm btn-primary"
                          onClick={() => handleDownload(report)}
                          aria-label={`Download report ${report.filename}`}
                        >
                          <Download size={12} aria-hidden="true" /> PDF
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedTender && (
        <span className="sr-only">Selected tender: {selectedTender.tender_ref}</span>
      )}

      {/* PDF Preview Modal */}
      {preview && (
        <div
          className="modal-overlay"
          onClick={() => setPreview(null)}
          role="dialog"
          aria-modal="true"
          aria-label="Report preview"
        >
          <div
            className="modal-container modal-lg"
            onClick={(e) => e.stopPropagation()}
            style={{ width: 'min(1180px, 96vw)', height: '92vh', maxHeight: '92vh' }}
          >
            <div className="modal-header">
              <div>
                <div className="modal-pretitle">Report Preview</div>
                <h2 className="modal-title">{preview.filename}</h2>
              </div>
              <button
                className="btn-close"
                onClick={() => setPreview(null)}
                aria-label="Close preview"
              >
                <X size={16} aria-hidden="true" />
              </button>
            </div>
            <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
              <iframe
                id="report-pdf-frame"
                title={`PDF preview: ${preview.filename}`}
                src={preview.url}
                style={{ width: '100%', height: '100%', border: 'none', background: 'var(--ink-800)' }}
              />
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={printReport}>
                <Printer size={14} aria-hidden="true" /> Print
              </button>
              <button className="btn btn-primary" onClick={handlePreviewDownload}>
                <Download size={14} aria-hidden="true" /> Download PDF
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
