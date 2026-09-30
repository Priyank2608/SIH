'use client';
/**
 * BulkBidderUpload — bulk bid-document intake for a tender workspace.
 *
 * Groups queued files by bidder (bidder picker + document type + optional
 * filename pattern), uploads through one shared bounded-concurrency worker
 * pool, and reports progressive per-bidder status so an officer can see at a
 * glance which bidders' submissions are complete, in-flight, or failing.
 */
import React, { useState, useRef, useMemo, useCallback } from 'react';
import { api } from '../lib/api';
import {
  Upload, FileText, CheckCircle2, XCircle, AlertTriangle, RotateCw, X,
  Loader2, Users, ChevronDown, ChevronRight, FolderOpen,
} from 'lucide-react';
import { DOCUMENT_TYPES } from './MultiDocUpload';

export type FileStatus = 'queued' | 'uploading' | 'success' | 'error';

export interface BulkQueuedFile {
  id: string;
  file: File;
  bidderId: number;
  bidderName: string;
  documentType: string;
  status: FileStatus;
  error?: string;
  resultDocId?: number;
}

export interface BidderGroupSummary {
  bidderId: number;
  bidderName: string;
  total: number;
  done: number;
  failed: number;
  active: number;
  queued: number;
}

interface Props {
  /** Bidders enrolled against this tender (from GET /tenders/{id}). */
  bidders: Array<{ id: number; legal_name: string }>;
  tenderId: number;
  onComplete?: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Files with a "123456_" or "123456-" prefix auto-assign to that bidder id. */
function parseBidderPrefix(name: string): number | null {
  const m = /^(\d{1,6})[_\- ]/.exec(name);
  return m ? parseInt(m[1], 10) || null : null;
}

export default function BulkBidderUpload({ bidders, tenderId, onComplete }: Props) {
  const [queue, setQueue] = useState<BulkQueuedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedBidder, setSelectedBidder] = useState<number | ''>('');
  const [defaultType, setDefaultType] = useState('GST');
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const inputRef = useRef<HTMLInputElement>(null);

  const bidderById = useMemo(
    () => new Map(bidders.map(b => [b.id, b.legal_name] as const)),
    [bidders]
  );

  /** Group-level progressive status, recomputed from the live queue. */
  const groups: BidderGroupSummary[] = useMemo(() => {
    const map = new Map<number, BidderGroupSummary>();
    for (const f of queue) {
      let g = map.get(f.bidderId);
      if (!g) {
        g = {
          bidderId: f.bidderId,
          bidderName: bidderById.get(f.bidderId) || `Bidder #${f.bidderId}`,
          total: 0, done: 0, failed: 0, active: 0, queued: 0,
        };
        map.set(f.bidderId, g);
      }
      g.total += 1;
      if (f.status === 'success') g.done += 1;
      else if (f.status === 'error') g.failed += 1;
      else if (f.status === 'uploading') g.active += 1;
      else g.queued += 1;
    }
    return Array.from(map.values());
  }, [queue, bidderById]);

  const overall = useMemo(() => ({
    total: queue.length,
    done: queue.filter(f => f.status === 'success').length,
    failed: queue.filter(f => f.status === 'error').length,
    active: queue.filter(f => f.status === 'uploading').length,
    queued: queue.filter(f => f.status === 'queued').length,
  }), [queue]);

  const toggleGroup = (bidderId: number) => {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(bidderId)) next.delete(bidderId); else next.add(bidderId);
      return next;
    });
  };

  const addFiles = useCallback((files: FileList | File[]) => {
    const incoming = Array.from(files);
    const accepted: BulkQueuedFile[] = [];
    let skipped = 0;
    for (const f of incoming) {
      if (f.type !== 'application/pdf') { skipped += 1; continue; }
      const prefixBidder = parseBidderPrefix(f.name);
      const bidderId = prefixBidder && bidderById.has(prefixBidder)
        ? prefixBidder
        : (selectedBidder || bidders[0]?.id);
      if (!bidderId) continue; // no bidder to attach to
      accepted.push({
        id: `${f.name}-${Date.now()}-${Math.random()}`,
        file: f,
        bidderId,
        bidderName: bidderById.get(bidderId) || `Bidder #${bidderId}`,
        documentType: defaultType,
        status: 'queued',
      });
    }
    if (accepted.length) setQueue(prev => [...prev, ...accepted]);
    if (skipped) {
      alert(`${skipped} non-PDF file${skipped !== 1 ? 's were' : ' was'} skipped — only application/pdf documents are accepted.`);
    }
  }, [selectedBidder, defaultType, bidderById, bidders]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    addFiles(e.dataTransfer.files);
  }, [addFiles]);

  const handleBrowseClick = () => inputRef.current?.click();

  const removeFile = (id: string) => setQueue(prev => prev.filter(f => f.id !== id));

  const updateField = (id: string, patch: Partial<Pick<BulkQueuedFile, 'bidderId' | 'documentType'>>) => {
    setQueue(prev => prev.map(f => {
      if (f.id !== id || f.status !== 'queued') return f;
      const bidderId = patch.bidderId ?? f.bidderId;
      return {
        ...f,
        ...patch,
        bidderId,
        bidderName: bidderById.get(bidderId) || `Bidder #${bidderId}`,
      };
    }));
  };

  const retryFile = (id: string) => {
    setQueue(prev => prev.map(f => f.id === id ? { ...f, status: 'queued', error: undefined } : f));
  };

  const processAll = async () => {
    const toProcess = queue.filter(f => f.status === 'queued');
    if (toProcess.length === 0) return;

    setIsProcessing(true);

    // One shared bounded-concurrency pool across ALL bidders — the same
    // policy as the per-bidder uploader, so the backend never sees a
    // synchronous flood regardless of how the intake is organized.
    const CONCURRENCY = 3;
    let cursor = 0;

    const worker = async () => {
      while (cursor < toProcess.length) {
        const item = toProcess[cursor++];
        setQueue(prev => prev.map(f => f.id === item.id ? { ...f, status: 'uploading' } : f));
        try {
          const formData = new FormData();
          formData.append('bidder_id', String(item.bidderId));
          formData.append('document_type', item.documentType);
          formData.append('tender_id', String(tenderId));
          formData.append('file', item.file);

          const result = await api('/documents/upload', { method: 'POST', body: formData });
          setQueue(prev => prev.map(f =>
            f.id === item.id ? { ...f, status: 'success', resultDocId: result.document_id } : f
          ));
        } catch (err: any) {
          setQueue(prev => prev.map(f =>
            f.id === item.id ? { ...f, status: 'error', error: err.message || 'Upload failed' } : f
          ));
        }
      }
    };

    await Promise.all(Array.from({ length: Math.min(CONCURRENCY, toProcess.length) }, worker));

    setIsProcessing(false);
    onComplete?.();
  };

  const groupState = (g: BidderGroupSummary): { label: string; cls: string } => {
    if (g.failed === g.total) return { label: 'Failed', cls: 'error' };
    if (g.failed > 0) return { label: 'Partial', cls: 'error' };
    if (g.active > 0) return { label: 'Uploading', cls: 'active' };
    if (g.queued > 0) return { label: isProcessing ? 'Waiting' : 'Queued', cls: 'default' };
    return { label: 'Complete', cls: 'done' };
  };

  const statusIcon = (status: FileStatus) => {
    if (status === 'success')   return <CheckCircle2 size={14} style={{ color: 'var(--green-600)' }} aria-hidden />;
    if (status === 'error')     return <XCircle size={14} style={{ color: 'var(--red-600)' }} aria-hidden />;
    if (status === 'uploading') return <Loader2 size={14} className="animate-spin" style={{ color: 'var(--primary)' }} aria-hidden />;
    return <FileText size={14} style={{ color: 'var(--text-muted)' }} aria-hidden />;
  };

  return (
    <div className="multi-doc-upload">
      {/* ── Intake controls ─────────────────────────────────────── */}
      <div className="bulk-intake-controls">
        <div className="form-group" style={{ margin: 0, flex: '1 1 220px' }}>
          <label className="form-label" htmlFor="bulk-bidder-select" style={{ fontSize: '11px' }}>
            Assign dropped files to bidder
          </label>
          <select
            id="bulk-bidder-select"
            className="form-input"
            value={selectedBidder}
            onChange={e => setSelectedBidder(e.target.value ? Number(e.target.value) : '')}
            style={{ fontSize: '12px', padding: '5px 8px' }}
          >
            <option value="">Auto from filename prefix (e.g. 12_GST.pdf)</option>
            {bidders.map(b => (
              <option key={b.id} value={b.id}>{b.legal_name} (#{b.id})</option>
            ))}
          </select>
        </div>
        <div className="form-group" style={{ margin: 0, flex: '1 1 200px' }}>
          <label className="form-label" htmlFor="bulk-type-select" style={{ fontSize: '11px' }}>
            Default document type
          </label>
          <select
            id="bulk-type-select"
            className="form-input"
            value={defaultType}
            onChange={e => setDefaultType(e.target.value)}
            style={{ fontSize: '12px', padding: '5px 8px' }}
          >
            {DOCUMENT_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* ── Drop zone ───────────────────────────────────────────── */}
      <div
        className={`doc-drop-zone${isDragging ? ' drag-over' : ''}`}
        onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={handleBrowseClick}
        role="button"
        tabIndex={0}
        aria-label="Bulk upload bid documents — click or drag PDF files here"
        onKeyDown={e => e.key === 'Enter' && handleBrowseClick()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          multiple
          style={{ display: 'none' }}
          onChange={e => { if (e.target.files) addFiles(e.target.files); e.target.value = ''; }}
          aria-hidden
        />
        <FolderOpen size={22} style={{ color: 'var(--text-faint)', marginBottom: '8px' }} aria-hidden />
        <p style={{ fontWeight: 600, fontSize: '13px', margin: 0 }}>
          {isDragging ? 'Drop files here…' : 'Drop bid PDFs for all bidders here, or click to browse'}
        </p>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '4px 0 0' }}>
          Grouped by bidder below · name files <span className="mono">&lt;bidder#&gt;_&lt;type&gt;.pdf</span> to auto-assign · Max {process.env.NEXT_PUBLIC_MAX_UPLOAD_MB || '10'} MB per file
        </p>
      </div>

      {/* ── Per-bidder groups with progressive status ──────────── */}
      {groups.length > 0 && (
        <div className="bulk-groups" style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {groups.map(g => {
            const st = groupState(g);
            const pct = g.total ? Math.round(((g.done + g.failed) / g.total) * 100) : 0;
            const isCollapsed = collapsed.has(g.bidderId);
            const groupFiles = queue.filter(f => f.bidderId === g.bidderId);
            return (
              <div key={g.bidderId} className={`card bulk-bidder-group state-${st.cls}`} style={{ padding: 0 }}>
                {/* Group header — always visible progressive status */}
                <button
                  type="button"
                  className="bulk-group-header"
                  onClick={() => toggleGroup(g.bidderId)}
                  aria-expanded={!isCollapsed}
                  aria-controls={`bulk-group-${g.bidderId}`}
                >
                  {isCollapsed
                    ? <ChevronRight size={14} aria-hidden style={{ flexShrink: 0 }} />
                    : <ChevronDown size={14} aria-hidden style={{ flexShrink: 0 }} />}
                  <Users size={13} aria-hidden style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                  <span className="bulk-group-name" title={g.bidderName}>{g.bidderName}</span>
                  <span className="bulk-group-badge">
                    {st.label}
                    <span className="bulk-group-progress mono">{g.done}/{g.total}</span>
                  </span>
                  <div className="bulk-group-bar" aria-hidden>
                    <div
                      className={`bulk-group-bar-fill ${st.cls}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </button>

                {/* Files in this group */}
                {!isCollapsed && (
                  <div id={`bulk-group-${g.bidderId}`} className="doc-queue" style={{ marginTop: 0, padding: '0 12px 10px' }}>
                    {groupFiles.map(item => (
                      <div key={item.id} className={`doc-queue-item doc-queue-item-${item.status}`}>
                        <div className="doc-queue-icon">{statusIcon(item.status)}</div>
                        <div className="doc-queue-info">
                          <span className="doc-queue-name">{item.file.name}</span>
                          <span className="doc-queue-meta">
                            {formatBytes(item.file.size)} · {DOCUMENT_TYPES.find(t => t.value === item.documentType)?.label || item.documentType}
                            {item.status === 'success' && ` · Doc #${item.resultDocId}`}
                            {item.status === 'error' && item.error && (
                              <span style={{ color: 'var(--red-600)' }}> · {item.error}</span>
                            )}
                            {item.status === 'uploading' && ' · Uploading…'}
                          </span>
                        </div>
                        <div className="doc-queue-actions">
                          {item.status === 'queued' && (
                            <>
                              <select
                                className="form-input"
                                style={{ fontSize: '11px', padding: '3px 6px', width: '150px' }}
                                value={item.bidderId}
                                onChange={e => updateField(item.id, { bidderId: Number(e.target.value) })}
                                aria-label={`Bidder for ${item.file.name}`}
                              >
                                {bidders.map(b => (
                                  <option key={b.id} value={b.id}>{b.legal_name}</option>
                                ))}
                              </select>
                              <select
                                className="form-input"
                                style={{ fontSize: '11px', padding: '3px 6px', width: '150px' }}
                                value={item.documentType}
                                onChange={e => updateField(item.id, { documentType: e.target.value })}
                                aria-label={`Document type for ${item.file.name}`}
                              >
                                {DOCUMENT_TYPES.map(t => (
                                  <option key={t.value} value={t.value}>{t.label}</option>
                                ))}
                              </select>
                            </>
                          )}
                          {item.status === 'error' && (
                            <button
                              className="btn btn-outline btn-sm"
                              onClick={() => retryFile(item.id)}
                              aria-label={`Retry upload for ${item.file.name}`}
                            >
                              <RotateCw size={12} aria-hidden /> Retry
                            </button>
                          )}
                          {(item.status === 'queued' || item.status === 'error') && (
                            <button
                              className="btn btn-ghost btn-sm"
                              onClick={() => removeFile(item.id)}
                              aria-label={`Remove ${item.file.name} from queue`}
                            >
                              <X size={14} aria-hidden />
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Overall summary / control bar ──────────────────────── */}
      {queue.length > 0 && (
        <div className="doc-upload-summary">
          <div className="doc-upload-summary-stats">
            <span>{overall.total} file{overall.total !== 1 ? 's' : ''} · {groups.length} bidder{groups.length !== 1 ? 's' : ''}</span>
            {overall.done > 0 && <span style={{ color: 'var(--green-600)' }}>· {overall.done} uploaded</span>}
            {overall.active > 0 && <span style={{ color: 'var(--primary)' }}>· {overall.active} uploading</span>}
            {overall.queued > 0 && <span style={{ color: 'var(--text-muted)' }}>· {overall.queued} waiting</span>}
            {overall.failed > 0 && <span style={{ color: 'var(--red-600)' }}>· {overall.failed} failed</span>}
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              className="btn btn-outline btn-sm"
              onClick={() => setQueue([])}
              disabled={isProcessing}
              aria-label="Clear all files from the bulk queue"
            >
              Clear All
            </button>
            <button
              className="btn btn-primary"
              onClick={processAll}
              disabled={isProcessing || overall.queued === 0}
              aria-label="Upload all queued bid documents"
            >
              {isProcessing ? (
                <>
                  <Loader2 size={13} className="animate-spin" aria-hidden />
                  Uploading…
                </>
              ) : (
                <>
                  <Upload size={13} aria-hidden />
                  Upload {overall.queued} Document{overall.queued !== 1 ? 's' : ''}
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ── Failure alert ──────────────────────────────────────── */}
      {overall.failed > 0 && !isProcessing && (
        <div className="alert alert-warning" style={{ marginTop: '8px' }} role="alert">
          <AlertTriangle size={14} aria-hidden style={{ flexShrink: 0 }} />
          <span>
            {overall.failed} upload{overall.failed !== 1 ? 's' : ''} failed
            {groups.some(g => g.failed > 0) && ` for ${groups.filter(g => g.failed > 0).map(g => g.bidderName).join(', ')}`}.
            Use per-file Retry or remove the file.
          </span>
        </div>
      )}
    </div>
  );
}
