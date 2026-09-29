'use client';
import React, { useState } from 'react';
import { api } from '../lib/api';

interface DecisionModalProps {
  tenderId: number;
  bidderId: number;
  bidderName: string;
  currentDecision?: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function DecisionModal({
  tenderId,
  bidderId,
  bidderName,
  currentDecision,
  onClose,
  onSuccess
}: DecisionModalProps) {
  const [decision, setDecision] = useState<'ACCEPTED' | 'REJECTED' | 'MANUAL_REVIEW_REQUESTED' | ''>('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!decision) {
      setError('Select the determination you are recording.');
      return;
    }
    if (!notes.trim()) {
      setError('Please provide officer justification notes for this official procurement record.');
      return;
    }

    if (!window.confirm(`Confirm recording ${decision.replaceAll('_', ' ')} for ${bidderName}? This action will be added to the audit trail.`)) {
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      await api(`/tenders/${tenderId}/bidders/${bidderId}/decision`, {
        method: 'POST',
        body: JSON.stringify({
          decision,
          decision_notes: notes.trim()
        })
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to record decision');
    } finally {
      setSubmitting(false);
    }
  };


  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container modal-md" role="dialog" aria-modal="true" aria-labelledby="decision-modal-title" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="modal-pretitle">Human-in-the-Loop Authority Action</div>
            <h2 className="modal-title" id="decision-modal-title">Record Official Procurement Decision</h2>
            <div className="modal-meta"><span>Bidder: <b>{bidderName}</b></span></div>
          </div>
          <button className="btn-close" onClick={onClose} aria-label="Close decision dialog" aria-hidden="false">×</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {/* Formal review flow: SYSTEM FINDINGS → EVIDENCE → DETERMINATION → JUSTIFICATION → CONFIRM */}
            <div
              className="mono"
              style={{
                display: 'flex', flexWrap: 'wrap', gap: '6px 0', alignItems: 'center',
                fontSize: '10px', letterSpacing: '0.08em', textTransform: 'uppercase',
                color: 'var(--text-faint)', marginBottom: '16px',
              }}
              aria-hidden="true"
            >
              {['System Findings', 'Evidence', 'Determination', 'Justification', 'Confirm'].map((step, i) => (
                <React.Fragment key={step}>
                  {i > 0 && <span style={{ margin: '0 8px', color: 'var(--border-strong)' }}>→</span>}
                  <span style={{ color: i <= 1 ? 'var(--text-muted)' : i === 2 ? 'var(--role-accent-text)' : 'var(--text-faint)', fontWeight: i === 2 ? 600 : 500 }}>
                    {step}
                  </span>
                </React.Fragment>
              ))}
            </div>

            <div className="officer-mandate-notice">
              <span className="mandate-icon">§</span>
              <p>
                <b>Statutory Procurement Governance:</b> BidShield enforces automated statutory validation.
                The official determination of eligibility or disqualification is permanently sealed into the audit trail.
              </p>
            </div>

            {error && <div className="alert alert-danger mb-4" role="alert">{error}</div>}

            {currentDecision && <div className="alert alert-info mb-4" role="status">Currently recorded determination: <b>{currentDecision.replaceAll('_', ' ')}</b>. A submitted decision will replace it and create an audit event.</div>}

            <div className="decision-panel-section">
              <div className="decision-section-label">Officer Determination — no option is preselected</div>
              <div className="decision-radio-group">
                <label className={`decision-option ${decision === 'ACCEPTED' ? 'selected-approve' : ''}`}>
                  <input
                    type="radio"
                    name="decision"
                    value="ACCEPTED"
                    checked={decision === 'ACCEPTED'}
                    onChange={() => setDecision('ACCEPTED')}
                    className="decision-option-radio"
                  />
                  <div>
                    <span className="decision-option-label text-success">Accept / Technically Qualify</span>
                    <p className="text-xs text-muted">
                      Review the record and enter your own rationale before deciding.
                    </p>
                  </div>
                </label>

                <label className={`decision-option ${decision === 'MANUAL_REVIEW_REQUESTED' ? 'selected-review' : ''}`}>
                  <input
                    type="radio"
                    name="decision"
                    value="MANUAL_REVIEW_REQUESTED"
                    checked={decision === 'MANUAL_REVIEW_REQUESTED'}
                    onChange={() => setDecision('MANUAL_REVIEW_REQUESTED')}
                    className="decision-option-radio"
                  />
                  <div>
                    <span className="decision-option-label text-warning">Refer for Detailed Scrutiny</span>
                    <p className="text-xs text-muted">Refer the record for additional officer or committee scrutiny.</p>
                  </div>
                </label>

                <label className={`decision-option ${decision === 'REJECTED' ? 'selected-reject' : ''}`}>
                  <input
                    type="radio"
                    name="decision"
                    value="REJECTED"
                    checked={decision === 'REJECTED'}
                    onChange={() => setDecision('REJECTED')}
                    className="decision-option-radio"
                  />
                  <div>
                    <span className="decision-option-label text-danger">Reject / Technically Disqualify</span>
                    <p className="text-xs text-muted">Bidder fails mandatory statutory criteria or submitted non-compliant documents.</p>
                  </div>
                </label>
              </div>
            </div>

            <div className="decision-panel-section">
              <div className="decision-section-label">Written Justification — required</div>
              <label className="form-label" htmlFor="decision-notes" style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }}>
                Officer Justification and Evaluation Notes
              </label>
              <textarea
                id="decision-notes"
                className="form-textarea"
                rows={4}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Enter justification citing verified certificates, compliance results, or discrepancy grounds..."
                required
              />
              <span className="form-hint">Risk and compliance findings inform your review but do not select your decision. Your submitted decision and rationale are recorded in the audit trail.</span>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-outline" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting || !decision}>
              {submitting ? 'Recording Decision...' : 'Commit Official Decision'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
