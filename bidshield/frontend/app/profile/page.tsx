'use client';
import React, { PointerEvent, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { api } from '../../lib/api';
import { getRoleLabel } from '../../lib/permissions';
import {
  UserRound,
  PenLine,
  CheckCircle2,
  AlertCircle,
  Trash2,
  Save,
  X,
  Info,
  FileBarChart,
  Lock,
} from 'lucide-react';

type OfficerProfile = {
  id: number;
  username: string;
  full_name: string;
  email: string;
  role: string;
  tenant_id: number;
  organization?: string;
  is_active: boolean;
};

export default function ProfilePage() {
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const drawingRef = useRef(false);

  const [profile,   setProfile]   = useState<OfficerProfile | null>(null);
  const [signature, setSignature] = useState<string | null>(null);
  const [drawing,   setDrawing]   = useState(false);
  const [hasInk,    setHasInk]    = useState(false);
  const [busy,      setBusy]      = useState(true);
  const [saving,    setSaving]    = useState(false);
  const [message,   setMessage]   = useState('');
  const [error,     setError]     = useState('');

  useEffect(() => {
    Promise.all([api('/auth/me'), api('/auth/signature')])
      .then(([user, saved]) => {
        setProfile(user);
        setSignature(saved.signature_data);
      })
      .catch((err) => setError(err.message || 'Unable to load profile'))
      .finally(() => setBusy(false));
  }, []);

  /* ---- Signature drawing handlers ---- */
  const pt = (e: PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) * canvas.width / rect.width,
      y: (e.clientY - rect.top)  * canvas.height / rect.height,
    };
  };

  const startDrawing = (e: PointerEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.setPointerCapture(e.pointerId);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const p = pt(e);
    ctx.beginPath(); ctx.moveTo(p.x, p.y);
    ctx.lineWidth = 3; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.strokeStyle = '#141b26';
    drawingRef.current = true; setHasInk(true);
  };

  const draw = (e: PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current || !canvasRef.current) return;
    e.preventDefault();
    const p = pt(e);
    const ctx = canvasRef.current.getContext('2d');
    if (ctx) { ctx.lineTo(p.x, p.y); ctx.stroke(); }
  };

  const endDrawing = () => { drawingRef.current = false; };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (canvas) canvas.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height);
    setHasInk(false);
  };

  const beginReplace = () => {
    setDrawing(true); setHasInk(false); setMessage(''); setError('');
    requestAnimationFrame(clearCanvas);
  };

  const saveSignature = async () => {
    const canvas = canvasRef.current;
    if (!canvas || !hasInk) { setError('Draw your signature before saving.'); return; }
    try {
      setSaving(true); setError('');
      const data = canvas.toDataURL('image/png');
      await api('/auth/signature', { method: 'PUT', body: JSON.stringify({ signature_data: data }) });
      setSignature(data); setDrawing(false);
      setMessage('Signature saved to your officer account. It will appear on generated reports.');
    } catch (err: any) { setError(err.message || 'Unable to save signature'); }
    finally { setSaving(false); }
  };

  /* ---- Profile field helper ---- */
  const ProfileField = ({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) => (
    <div className="profile-field">
      <span className="profile-field-label">{label}</span>
      <span className={`profile-field-value readonly${mono ? ' mono' : ''}`}>{value}</span>
    </div>
  );

  if (busy) {
    return (
      <div className="state-wrapper">
        <div className="spinner" aria-hidden="true" />
        <div className="state-title">Loading officer profile…</div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="alert alert-danger" role="alert">
        <AlertCircle size={15} aria-hidden="true" style={{ flexShrink: 0 }} />
        {error || 'Unable to load officer profile.'}
      </div>
    );
  }

  return (
    <div className="main-wrapper">
      {/* Page header */}
      <div className="page-header">
        <div className="page-header-text">
          <div className="page-eyebrow">Identity Record</div>
          <h1 className="page-title">Officer Profile</h1>
          <p className="page-desc">
            Your account identity and the digital signature applied to generated procurement reports.
          </p>
        </div>
        <div className="page-actions">
          <Link href="/reports" className="btn btn-outline btn-sm">
            <FileBarChart size={13} aria-hidden="true" /> Reports
          </Link>
        </div>
      </div>
      <hr className="page-rule" />

      {/* OFFICER IDENTITY */}
      <section className="profile-section">
        <div className="profile-section-title">
          <UserRound size={14} aria-hidden="true" />
          Officer Identity
        </div>

        {/* Identity strip */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '16px', padding: '14px 16px', background: 'var(--surface-base)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: 'var(--radius-md)', background: 'var(--role-accent)', color: '#fff', fontSize: '18px', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }} aria-hidden="true">
            {(profile.full_name || profile.username || 'O')[0].toUpperCase()}
          </div>
          <div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>{profile.full_name}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px', flexWrap: 'wrap' }}>
              <span className="profile-role-tag" style={{ marginTop: 0 }}>
                {getRoleLabel(profile.role)}
              </span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                {profile.organization || `Tenant ${profile.tenant_id}`}
              </span>
            </div>
          </div>
          <div style={{ marginLeft: 'auto', flexShrink: 0 }}>
            {profile.is_active
              ? <span className="status-badge badge-success size-sm"><CheckCircle2 size={11} aria-hidden="true" /> Active Account</span>
              : <span className="status-badge badge-danger size-sm">Inactive</span>
            }
          </div>
        </div>

        <ProfileField label="Full Name"         value={profile.full_name} />
        <ProfileField label="Email Address"     value={profile.email} />
        <ProfileField label="Officer ID"        value={profile.username} mono />
        <ProfileField label="System Role"       value={getRoleLabel(profile.role)} />
        <ProfileField label="Organization"      value={profile.organization || `Tenant ${profile.tenant_id}`} />
        <ProfileField label="Account Status"    value={profile.is_active ? 'Active' : 'Inactive'} />

        <div style={{ marginTop: '12px', padding: '8px 12px', background: 'var(--paper-200)', borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Info size={13} aria-hidden="true" />
          Account identity, role, and organization are managed by system administrators.
        </div>
      </section>

      {/* OFFICER SIGNATURE */}
      <section className="profile-section" id="signature">
        <div className="profile-section-title">
          <PenLine size={14} aria-hidden="true" />
          Officer Signature
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', marginBottom: '14px', flexWrap: 'wrap' }}>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.55', flex: '1 1 240px', maxWidth: '640px' }}>
            Your saved signature is embedded in PDF reports you generate. It identifies authorship but does
            <em> not</em> constitute an approval or rejection decision.
          </p>
          {!drawing && (
            <button className="btn btn-primary btn-sm" onClick={beginReplace}>
              <PenLine size={13} aria-hidden="true" />
              {signature ? 'Replace Signature' : 'Draw Signature'}
            </button>
          )}
        </div>

        {/* Feedback messages */}
        {error && (
          <div className="alert alert-danger mb-3" role="alert">
            <AlertCircle size={14} aria-hidden="true" style={{ flexShrink: 0 }} />
            {error}
          </div>
        )}
        {message && (
          <div className="alert alert-success mb-3" role="status">
            <CheckCircle2 size={14} aria-hidden="true" style={{ flexShrink: 0 }} />
            {message}
          </div>
        )}

        {/* Current saved signature */}
        {!drawing && signature && (
          <div className="signature-preview-area" style={{ marginBottom: '10px', maxWidth: '480px' }}>
            <img
              src={signature}
              alt="Saved officer digital signature"
              style={{ maxWidth: '100%', width: '360px', height: '110px', objectFit: 'contain', objectPosition: 'left center', display: 'block' }}
            />
          </div>
        )}

        {/* No signature state */}
        {!drawing && !signature && (
          <div className="alert alert-warning">
            <AlertCircle size={14} aria-hidden="true" style={{ flexShrink: 0 }} />
            No signature configured. Signed report generation is disabled until you save a signature.
          </div>
        )}

        {/* Drawing canvas */}
        {drawing && (
          <div>
            <label htmlFor="signature-canvas" className="form-label" style={{ marginBottom: '8px' }}>
              Draw here using a mouse, touchscreen, or stylus
            </label>
            <canvas
              id="signature-canvas"
              ref={canvasRef}
              width={1000}
              height={280}
              onPointerDown={startDrawing}
              onPointerMove={draw}
              onPointerUp={endDrawing}
              onPointerCancel={endDrawing}
              onPointerLeave={endDrawing}
              style={{
                display: 'block',
                width: '100%',
                maxWidth: '720px',
                height: '200px',
                background: '#fff',
                border: '1px solid var(--border-strong)',
                borderRadius: 'var(--radius-md)',
                touchAction: 'none',
                cursor: 'crosshair',
              }}
              aria-label="Signature drawing canvas"
            />
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
              <button className="btn btn-outline btn-sm" onClick={clearCanvas}>
                <Trash2 size={13} aria-hidden="true" /> Clear
              </button>
              <button
                className="btn btn-primary btn-sm"
                onClick={saveSignature}
                disabled={saving || !hasInk}
                aria-busy={saving}
              >
                <Save size={13} aria-hidden="true" />
                {saving ? 'Saving…' : 'Save Signature'}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => setDrawing(false)}>
                <X size={13} aria-hidden="true" /> Cancel
              </button>
            </div>
          </div>
        )}
      </section>

      {/* SECURITY */}
      <section className="profile-section">
        <div className="profile-section-title">
          <Lock size={14} aria-hidden="true" />
          Security
        </div>
        <ProfileField label="Session" value="Bearer JWT · expires after 120 minutes of issue" />
        <ProfileField label="Storage" value="Session-scoped (cleared when the browser tab closes)" mono={false} />
        <ProfileField label="Audit" value="Sign-ins and all officer actions are recorded in the audit chain" />
      </section>
    </div>
  );
}
