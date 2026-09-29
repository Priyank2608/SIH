'use client';
import React, { useState, useEffect } from 'react';
import { api, API_BASE } from '../lib/api';
import StatusBadge from './StatusBadge';

interface OCRInspectorModalProps {
  documentId: number;
  onClose: () => void;
}

export default function OCRInspectorModal({ documentId, onClose }: OCRInspectorModalProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'FIELDS' | 'RAW_TEXT' | 'BOXES'>('FIELDS');

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const res = await api(`/documents/${documentId}`);
        setData(res);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [documentId]);

  if (!documentId) return null;

  const doc = data?.document;
  const ocr = data?.ocr;
  const verif = data?.verification;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container ocr-modal-wide" role="dialog" aria-modal="true" aria-label="OCR document inspector" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="modal-pretitle">Document AI & OCR Inspection</div>
            <h2 className="modal-title">{doc?.filename || `Document #${documentId}`}</h2>
            <div className="modal-meta">
              <span>Type: <b>{doc?.document_type}</b></span>
              <span>Version: <b>v{doc?.version}</b></span>
              <span>Bidder: <b>{doc?.bidder_name}</b></span>
              <span>Hash: <code className="code-hash">{doc?.file_hash?.substring(0, 16)}...</code></span>
            </div>
          </div>
          <button className="btn-close" onClick={onClose} aria-label="Close modal">×</button>
        </div>

        {loading ? (
          <div className="modal-body">
            <div className="state-wrapper">
              <div className="spinner" aria-hidden="true" />
              <p className="state-desc">Loading document analysis…</p>
            </div>
          </div>
        ) : (
          <div className="modal-body ocr-split-view">
            {/* Left: Document View / Embed */}
            <div className="ocr-doc-pane">
              <div className="pane-header">
                <h3>Document Preview</h3>
                <a
                  href={`${API_BASE}/documents/${documentId}/file`}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-sm btn-outline"
                >
                  Open in New Tab →
                </a>
              </div>
              <div className="doc-embed-frame">
                <iframe
                  src={`${API_BASE}/documents/${documentId}/file#toolbar=0`}
                  title="Document Preview"
                  className="doc-iframe"
                />
              </div>
            </div>

            {/* Right: OCR Extraction Details */}
            <div className="ocr-meta-pane">
              <div className="ocr-summary-card">
                <div className="ocr-stat-item">
                  <span className="stat-label">OCR Status</span>
                  <StatusBadge status={ocr ? 'VERIFIED' : 'PENDING'} size="sm" />
                </div>
                <div className="ocr-stat-item">
                  <span className="stat-label">Extraction Confidence</span>
                  <span className={`confidence-val ${ocr?.confidence >= 0.8 ? 'high' : ocr?.confidence >= 0.6 ? 'med' : 'low'}`}>
                    {ocr?.confidence !== undefined ? `${(ocr.confidence * 100).toFixed(1)}%` : 'N/A'}
                  </span>
                </div>
                <div className="ocr-stat-item">
                  <span className="stat-label">Engine</span>
                  <span className="engine-name">{ocr?.engine || 'TesseractOCR'}</span>
                </div>
                <div className="ocr-stat-item">
                  <span className="stat-label">Verification Outcome</span>
                  <StatusBadge status={verif?.status || 'PENDING'} size="sm" />
                </div>
              </div>

              {verif?.discrepancy_notes && (
                <div className="alert-discrepancy">
                  <strong>Verification Discrepancy Note:</strong>
                  <p>{verif.discrepancy_notes}</p>
                </div>
              )}

              {/* Subtabs */}
              <div className="subtabs">
                <button
                  className={`subtab ${activeTab === 'FIELDS' ? 'active' : ''}`}
                  onClick={() => setActiveTab('FIELDS')}
                >
                  Extracted Structured Fields ({Object.keys(ocr?.fields || {}).length})
                </button>
                <button
                  className={`subtab ${activeTab === 'BOXES' ? 'active' : ''}`}
                  onClick={() => setActiveTab('BOXES')}
                >
                  Bounding Boxes ({ocr?.bounding_boxes?.length || 0})
                </button>
                <button
                  className={`subtab ${activeTab === 'RAW_TEXT' ? 'active' : ''}`}
                  onClick={() => setActiveTab('RAW_TEXT')}
                >
                  Raw OCR Text
                </button>
              </div>

              <div className="subtab-content">
                {activeTab === 'FIELDS' && (
                  <div className="fields-table-wrapper">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Structured Field Key</th>
                          <th>Extracted Field Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ocr?.fields && Object.keys(ocr.fields).length > 0 ? (
                          Object.entries(ocr.fields).map(([key, val]) => (
                            <tr key={key}>
                              <td className="field-key font-mono">{key}</td>
                              <td className="field-val font-semibold">{String(val)}</td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={2} className="text-muted text-center p-4">
                              No structured procurement fields detected.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}

                {activeTab === 'BOXES' && (
                  <div className="boxes-list">
                    <p className="text-xs text-muted mb-2">Detected text coordinates [x0, y0, x1, y1]:</p>
                    {ocr?.bounding_boxes && ocr.bounding_boxes.length > 0 ? (
                      <div className="box-items-scroll">
                        {ocr.bounding_boxes.map((b: any, idx: number) => (
                          <div key={idx} className="box-item">
                            <span className="box-coords font-mono">[{b.box?.join(', ')}]</span>
                            <span className="box-text">{b.text}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-muted text-sm">No bounding box data available.</p>
                    )}
                  </div>
                )}

                {activeTab === 'RAW_TEXT' && (
                  <div className="raw-text-block">
                    <pre className="raw-ocr-pre">{ocr?.extracted_text || 'No text extracted.'}</pre>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose}>Close Inspector</button>
        </div>
      </div>
    </div>
  );
}
