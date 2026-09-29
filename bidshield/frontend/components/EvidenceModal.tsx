'use client';
import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';

interface EvidenceModalProps {
  bidderId: number;
  bidderName: string;
  onClose: () => void;
}

export default function EvidenceModal({ bidderId, bidderName, onClose }: EvidenceModalProps) {
  const [evidenceList, setEvidenceList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const res = await api(`/bidders/${bidderId}/evidence`);
        setEvidenceList(res);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [bidderId]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container modal-lg" role="dialog" aria-modal="true" aria-label="Bidder evidence" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="modal-pretitle">Cryptographic & Traceable Audit Lineage</div>
            <h2 className="modal-title">Evidence Graph & Traceability Chain</h2>
            <div className="modal-meta">
              <span>Bidder: <b>{bidderName}</b></span>
              <span>Evidence Nodes: <b>{evidenceList.length}</b></span>
            </div>
          </div>
          <button className="btn-close" onClick={onClose} aria-label="Close evidence dialog">×</button>
        </div>

        <div className="modal-body">
          {/* Chain: DOCUMENT → FIELD → VERIFICATION → COMPLIANCE → RISK → OFFICER REVIEW */}
          <div
            className="mono"
            style={{
              display: 'flex', flexWrap: 'wrap', alignItems: 'center',
              fontSize: '9.5px', letterSpacing: '0.09em', textTransform: 'uppercase',
              color: 'var(--text-faint)', marginBottom: '16px',
            }}
            aria-hidden="true"
          >
            {['Document', 'Field', 'Verification', 'Compliance', 'Risk Signal', 'Officer Review'].map((step, i) => (
              <React.Fragment key={step}>
                {i > 0 && <span style={{ margin: '0 7px', color: 'var(--border-strong)' }}>↓</span>}
                <span>{step}</span>
              </React.Fragment>
            ))}
          </div>

          {loading ? (
            <div className="state-wrapper">
              <div className="spinner" aria-hidden="true" />
              <p className="state-desc">Traversing evidence graph…</p>
            </div>
          ) : evidenceList.length === 0 ? (
            <div className="state-wrapper">
              <p className="state-desc">No evidence records currently linked to this bidder profile.</p>
            </div>
          ) : (
            <div className="evidence-timeline">
              {evidenceList.map((ev, idx) => (
                <div key={ev.id || idx} className="evidence-card">
                  <div className="evidence-header">
                    <span className="evidence-tag">{ev.claim_type}</span>
                    <span className="evidence-conf">Confidence: {(ev.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <p className="evidence-text">{ev.evidence_text}</p>
                  <div className="evidence-footer">
                    <span className="evidence-source">
                      Source Ref: <b>{ev.source_reference}</b>
                    </span>
                    <span className="evidence-date">
                      {ev.created_at ? new Date(ev.created_at).toLocaleString() : ''}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose}>Close Evidence View</button>
        </div>
      </div>
    </div>
  );
}
