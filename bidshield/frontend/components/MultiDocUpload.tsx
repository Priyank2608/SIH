'use client';
import React, { useState, useRef, useCallback } from 'react';
import { api } from '../lib/api';
import {
  Upload,
  FileText,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RotateCw,
  X,
  Loader2,
} from 'lucide-react';

/* ── Document type options (backed by what the API accepts) ─────── */
export const DOCUMENT_TYPES = [
  { value: 'GST',        label: 'GST Registration Certificate' },
  { value: 'PAN',        label: 'PAN Certificate' },
  { value: 'UDYAM',      label: 'Udyam Registration (MSME)' },
  { value: 'OEM',        label: 'OEM Authorization Letter' },
  { value: 'TURNOVER',   label: 'Financial Turnover Statement' },
  { value: 'EXPERIENCE', label: 'Work Order / Completion Certificate' },
  { value: 'TECHNICAL',  label: 'Technical Compliance Document' },
  { value: 'OTHER',      label: 'Other Supporting Document' },
];

/* ── Document category groups for display ──────────────────────── */
export const DOCUMENT_GROUPS = [
  { label: 'Identity & Registration', types: ['GST', 'PAN', 'UDYAM'] },
  { label: 'Authorization',           types: ['OEM'] },
  { label: 'Financial',               types: ['TURNOVER'] },
  { label: 'Experience & Technical',  types: ['EXPERIENCE', 'TECHNICAL'] },
  { label: 'Other',                   types: ['OTHER'] },
];

type UploadStatus = 'queued' | 'uploading' | 'success' | 'error';

interface QueuedFile {
  id: string;
  file: File;
  documentType: string;
  status: UploadStatus;
  error?: string;
  resultDocId?: number;
  verificationStatus?: string;
}

interface Props {
  bidderId: number;
  tenderId?: number;
  onComplete?: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function MultiDocUpload({ bidderId, tenderId, onComplete }: Props) {
  const [queue, setQueue] = useState<QueuedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [defaultType, setDefaultType] = useState('GST');
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((files: FileList | File[]) => {
    const newItems: QueuedFile[] = Array.from(files)
      .filter(f => f.type === 'application/pdf')
      .map(f => ({
        id: `${f.name}-${Date.now()}-${Math.random()}`,
        file: f,
        documentType: defaultType,
        status: 'queued' as UploadStatus,
      }));
    if (newItems.length === 0) return;
    setQueue(prev => [...prev, ...newItems]);
  }, [defaultType]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    addFiles(e.dataTransfer.files);
  }, [addFiles]);

  const handleBrowse = () => inputRef.current?.click();

  const removeFile = (id: string) => {
    setQueue(prev => prev.filter(f => f.id !== id));
  };

  const updateType = (id: string, documentType: string) => {
    setQueue(prev => prev.map(f => f.id === id ? { ...f, documentType } : f));
  };

  const retryFile = (id: string) => {
    setQueue(prev => prev.map(f => f.id === id ? { ...f, status: 'queued', error: undefined } : f));
  };

  const processAll = async () => {
    const toProcess = queue.filter(f => f.status === 'queued');
    if (toProcess.length === 0) return;

    setIsProcessing(true);

    // Bounded-concurrency worker pool: keeps the UI responsive for large
    // batches (hundreds of files) without hammering the backend with one
    // synchronous flood of requests.
    const CONCURRENCY = 3;
    let cursor = 0;

    const worker = async () => {
      while (cursor < toProcess.length) {
        const item = toProcess[cursor++];
        setQueue(prev => prev.map(f => f.id === item.id ? { ...f, status: 'uploading' } : f));

        try {
          const formData = new FormData();
          formData.append('bidder_id', String(bidderId));
          formData.append('document_type', item.documentType);
          if (tenderId) formData.append('tender_id', String(tenderId));
          formData.append('file', item.file);

          const result = await api('/documents/upload', {
            method: 'POST',
            body: formData,
          });
          setQueue(prev => prev.map(f =>
            f.id === item.id
              ? { ...f, status: 'success', resultDocId: result.document_id }
              : f
          ));
        } catch (err: any) {
          setQueue(prev => prev.map(f =>
            f.id === item.id
              ? { ...f, status: 'error', error: err.message || 'Upload failed' }
              : f
          ));
        }
      }
    };

    await Promise.all(Array.from({ length: Math.min(CONCURRENCY, toProcess.length) }, worker));

    setIsProcessing(false);
    onComplete?.();
  };

  /* ── Derived summary ────────────────────────────────── */
  const total    = queue.length;
  const uploaded = queue.filter(f => f.status === 'success').length;
  const failed   = queue.filter(f => f.status === 'error').length;
  const pending  = queue.filter(f => f.status === 'queued').length;
  // Verified/mismatch/manual-review buckets come from the backend after
  // processing; they are surfaced via the dossier refresh, never invented here.

  const statusIcon = (status: UploadStatus) => {
    if (status === 'success')   return <CheckCircle2 size={15} style={{ color: 'var(--green-600)' }} aria-hidden />;
    if (status === 'error')     return <XCircle size={15} style={{ color: 'var(--red-600)' }} aria-hidden />;
    if (status === 'uploading') return <Loader2 size={15} className="animate-spin" style={{ color: 'var(--primary)' }} aria-hidden />;
    return <FileText size={15} style={{ color: 'var(--text-muted)' }} aria-hidden />;
  };

  return (
    <div className="multi-doc-upload">
      {/* Drop zone */}
      <div
        className={`doc-drop-zone${isDragging ? ' drag-over' : ''}`}
        onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={handleBrowse}
        role="button"
        tabIndex={0}
        aria-label="Upload documents — click or drag PDF files here"
        onKeyDown={e => e.key === 'Enter' && handleBrowse()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          multiple
          style={{ display: 'none' }}
          onChange={e => e.target.files && addFiles(e.target.files)}
          aria-hidden
        />
        <Upload size={22} style={{ color: 'var(--text-faint)', marginBottom: '8px' }} aria-hidden />
        <p style={{ fontWeight: 600, fontSize: '13px', margin: 0 }}>
          {isDragging ? 'Drop files here…' : 'Drag PDF files here or click to browse'}
        </p>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '4px 0 0' }}>
          Only PDF documents accepted · Max {process.env.NEXT_PUBLIC_MAX_UPLOAD_MB || '10'} MB per file · Processed 3 at a time
        </p>
      </div>

      {/* Default doc type selector (applies to newly added files) */}
      {queue.length === 0 && (
        <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <label style={{ fontSize: '12px', color: 'var(--text-muted)', flexShrink: 0 }}>
            Default type for new files:
          </label>
          <select
            className="form-input"
            style={{ fontSize: '12px', padding: '4px 8px', flex: 1, maxWidth: '260px' }}
            value={defaultType}
            onChange={e => setDefaultType(e.target.value)}
          >
            {DOCUMENT_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
      )}

      {/* File queue */}
      {queue.length > 0 && (
        <>
          <div className="doc-queue" style={{ marginTop: '12px' }}>
            {queue.map(item => (
              <div key={item.id} className={`doc-queue-item doc-queue-item-${item.status}`}>
                <div className="doc-queue-icon">{statusIcon(item.status)}</div>
                <div className="doc-queue-info">
                  <span className="doc-queue-name">{item.file.name}</span>
                  <span className="doc-queue-meta">
                    {formatBytes(item.file.size)}
                    {item.status === 'success' && ' · Uploaded → OCR complete → Verification queued'}
                    {item.status === 'error' && item.error && (
                      <span style={{ color: 'var(--red-600)' }}> · {item.error}</span>
                    )}
                    {item.status === 'uploading' && ' · Uploading…'}
                  </span>
                </div>

                <div className="doc-queue-actions">
                  {item.status === 'queued' && (
                    <select
                      className="form-input"
                      style={{ fontSize: '11px', padding: '3px 6px', width: '160px' }}
                      value={item.documentType}
                      onChange={e => updateType(item.id, e.target.value)}
                      aria-label={`Document type for ${item.file.name}`}
                    >
                      {DOCUMENT_TYPES.map(t => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                  )}
                  {item.status === 'success' && (
                    <span className="badge badge-green" style={{ fontSize: '11px' }}>
                      {item.documentType}
                    </span>
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

          {/* Summary bar */}
          <div className="doc-upload-summary">
            <div className="doc-upload-summary-stats">
              <span>{total} file{total !== 1 ? 's' : ''} queued</span>
              {uploaded > 0 && <span style={{ color: 'var(--green-600)' }}>· {uploaded} uploaded</span>}
              {failed > 0 && <span style={{ color: 'var(--red-600)' }}>· {failed} failed</span>}
              {pending > 0 && <span style={{ color: 'var(--text-muted)' }}>· {pending} pending</span>}
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => setQueue([])}
                disabled={isProcessing}
                aria-label="Clear all files from queue"
              >
                Clear All
              </button>
              <button
                className="btn btn-primary"
                onClick={processAll}
                disabled={isProcessing || pending === 0}
                aria-label="Process and upload all queued documents"
              >
                {isProcessing ? (
                  <>
                    <Loader2 size={13} className="animate-spin" aria-hidden />
                    Uploading…
                  </>
                ) : (
                  <>
                    <Upload size={13} aria-hidden />
                    Process {pending} Document{pending !== 1 ? 's' : ''}
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Non-PDF warning */}
          {Array.from({ length: 0 }).length === 0 && failed > 0 && (
            <div className="alert alert-warning" style={{ marginTop: '8px' }} role="alert">
              <AlertTriangle size={14} aria-hidden style={{ flexShrink: 0 }} />
              <span>
                {failed} upload{failed !== 1 ? 's' : ''} failed. Correct the error and use Retry, or remove the file.
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
