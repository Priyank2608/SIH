'use client';
import React, { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, setToken, getToken } from '../../lib/api';
import BidShieldLogo from '../../components/BidShieldLogo';
import {
  AlertCircle,
  Eye,
  EyeOff,
  Lock,
  User,
} from 'lucide-react';

/* ── Demo accounts ─────────────────────────────────────────── */
const DEMO_ACCOUNTS = [
  { label: 'Procurement Officer',  username: 'officer',  password: 'BidShield@123' },
  { label: 'Verification Officer', username: 'verifier', password: 'BidShield@123' },
  { label: 'Auditor',              username: 'auditor',  password: 'BidShield@123' },
  { label: 'Administrator',        username: 'admin',    password: 'BidShield@123' },
];
const showDemoAccounts = process.env.NEXT_PUBLIC_DEMO_MODE !== 'false';

/* Evidence workflow trace — Submission → Decision */
const WORKFLOW_STEPS = [
  'Submission',
  'OCR',
  'Verification',
  'Compliance',
  'Review',
  'Decision',
];

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [activeStep, setActiveStep] = useState(2);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (getToken()) { router.replace('/'); return; }
    const params = new URLSearchParams(window.location.search);
    if (params.get('expired') === '1') {
      setExpired(true);
      window.history.replaceState(null, '', '/login');
    }
    // Advance the evidence trace while idle — a living pipeline, not decoration
    timerRef.current = setInterval(() => {
      setActiveStep(prev => (prev + 1) % WORKFLOW_STEPS.length);
    }, 2200);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [router]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('Enter your officer username and password.');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const res = await api('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: username.trim(), password }),
      });
      setToken(res.access_token);
      sessionStorage.setItem('bidshield_user', JSON.stringify(res.user));
      router.push('/');
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Verify your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-root" role="main">
      {/* ── Left: ink operations wall ─────────────────────────────────── */}
      <div className="login-left">
        <div className="login-brand">
          <div className="login-mark">
            <span className="login-mark-icon">
              <BidShieldLogo size={38} variant="compact" onDark />
            </span>
            <span className="login-mark-text">
              Bid<b>Shield</b>
            </span>
          </div>

          <div className="login-restricted-pill">
            Authorized Access Only
          </div>

          <h1 className="login-headline">
            Procurement
            <br />
            <span className="login-headline-accent">Intelligence</span>
            <br />
            Console
          </h1>

          <p className="login-subheadline">
            Evidence-backed review of GeM bid submissions for authorized
            procurement officers, verification officers, and auditors.
            Every finding is traceable to a document, a field, and a rule.
          </p>

          {/* Evidence trace — pipeline visual */}
          <div className="login-workflow" aria-hidden="true">
            <div className="login-workflow-track">
              {WORKFLOW_STEPS.map((step, i) => (
                <React.Fragment key={step}>
                  {i > 0 && (
                    <div
                      className={`login-workflow-line${
                        i <= activeStep ? ' active' : ''
                      }`}
                    />
                  )}
                  <div
                    className={`login-workflow-dot${
                      i === activeStep ? ' active' : i < activeStep ? ' passed' : ''
                    }`}
                  />
                </React.Fragment>
              ))}
            </div>
            <div className="login-workflow-steps">
              {WORKFLOW_STEPS.map((step, i) => (
                <span
                  key={step}
                  className={`login-workflow-step-name${
                    i === activeStep ? ' active' : i < activeStep ? ' passed' : ''
                  }`}
                >
                  {step}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom meta */}
        <p className="login-meta">
          <b>Session notice.</b> All sign-ins, reviews, and decisions are
          recorded in a tamper-evident audit chain. BidShield is an internal
          evaluation platform — it is not an official Government
          e-Marketplace (GeM) product.
        </p>
      </div>

      {/* ── Right: paper registry panel ───────────────────────────────── */}
      <div className="login-right">
        <div className="login-auth-eyebrow">Secure Access</div>
        <h2 className="login-auth-title">Officer Sign-In</h2>
        <p className="login-auth-subtitle">BidShield Procurement Review Console</p>

        {/* Session expired notice */}
        {expired && !error && (
          <div className="alert alert-warning mb-4" role="alert" aria-live="polite">
            <AlertCircle size={15} aria-hidden="true" style={{ flexShrink: 0 }} />
            <span>Your session has expired. Please sign in again.</span>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="alert alert-danger mb-4" role="alert" aria-live="assertive">
            <AlertCircle size={15} aria-hidden="true" style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form
          className="login-form"
          onSubmit={handleLogin}
          aria-label="Officer authentication"
          noValidate
        >
          <div className="login-field">
            <label className="login-field-label" htmlFor="login-username">
              Officer Username
            </label>
            <div style={{ position: 'relative' }}>
              <User
                size={14}
                aria-hidden="true"
                style={{
                  position: 'absolute', left: '12px', top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-faint)', pointerEvents: 'none',
                }}
              />
              <input
                id="login-username"
                type="text"
                className="login-field-input"
                value={username}
                onChange={e => { setUsername(e.target.value); setError(null); }}
                autoComplete="username"
                required
                disabled={loading}
                placeholder="Enter your officer ID"
                aria-required="true"
                style={{ paddingLeft: '36px' }}
              />
            </div>
          </div>

          <div className="login-field">
            <label className="login-field-label" htmlFor="login-password">
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <Lock
                size={14}
                aria-hidden="true"
                style={{
                  position: 'absolute', left: '12px', top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-faint)', pointerEvents: 'none',
                }}
              />
              <input
                id="login-password"
                type={showPass ? 'text' : 'password'}
                className="login-field-input"
                value={password}
                onChange={e => { setPassword(e.target.value); setError(null); }}
                autoComplete="current-password"
                required
                disabled={loading}
                placeholder="Enter your password"
                aria-required="true"
                style={{ paddingLeft: '36px', paddingRight: '40px' }}
              />
              <button
                type="button"
                onClick={() => setShowPass(!showPass)}
                aria-label={showPass ? 'Hide password' : 'Show password'}
                style={{
                  position: 'absolute', right: '10px', top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--text-faint)', padding: '2px', lineHeight: 1,
                }}
              >
                {showPass
                  ? <EyeOff size={14} aria-hidden="true" />
                  : <Eye size={14} aria-hidden="true" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="login-submit-btn"
            disabled={loading}
            aria-busy={loading}
          >
            {loading ? 'Authenticating…' : 'Sign In →'}
          </button>
        </form>

        {showDemoAccounts && (
          <>
            <hr className="login-divider" />
            <div className="login-demo-box">
              <div className="login-demo-title">
                <AlertCircle size={11} aria-hidden="true" />
                Demo Mode — Development Accounts
              </div>
              <div className="login-demo-buttons">
                {DEMO_ACCOUNTS.map(({ label, username: u, password: p }) => (
                  <button
                    key={u}
                    type="button"
                    className="login-demo-btn"
                    onClick={() => {
                      setUsername(u);
                      setPassword(p);
                      setError(null);
                    }}
                    aria-label={`Fill demo credentials for ${label}`}
                  >
                    <span className="login-demo-btn-role">{label}</span>
                    <span className="login-demo-btn-user">{u}</span>
                  </button>
                ))}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-faint)', lineHeight: '1.4' }}>
                All demo accounts use password: <code>BidShield@123</code>
              </div>
            </div>
          </>
        )}

        <p className="login-disclaimer">
          Access restricted to authorized BidShield evaluation personnel.
          Unauthorized access is prohibited. Not an official GeM product.
        </p>
      </div>
    </div>
  );
}
