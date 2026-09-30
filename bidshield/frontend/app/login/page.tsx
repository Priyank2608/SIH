'use client';
import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, setToken, getToken } from '../../lib/api';
import BidShieldLogo from '../../components/BidShieldLogo';
import {
  AlertCircle,
  Eye,
  EyeOff,
  Lock,
  User,
  FileText,
  ScanLine,
  ShieldCheck,
  AlertOctagon,
  GitBranch,
  UserCheck,
  FileBarChart,
  MousePointerClick,
} from 'lucide-react';

/* ── Demo accounts ─────────────────────────────────────────── */
const DEMO_ACCOUNTS = [
  { label: 'Procurement Officer',  username: 'officer',  password: 'BidShield@123' },
  { label: 'Verification Officer', username: 'verifier', password: 'BidShield@123' },
  { label: 'Auditor',              username: 'auditor',  password: 'BidShield@123' },
  { label: 'Administrator',        username: 'admin',    password: 'BidShield@123' },
];
// Development credentials are never advertised by default. A local test/demo
// environment can opt in explicitly with NEXT_PUBLIC_DEMO_MODE=true.
const showDemoAccounts = process.env.NEXT_PUBLIC_DEMO_MODE === 'true';

/* Flip-card back: concise product capability list */
const CAPABILITIES = [
  { icon: FileText,      label: 'Tender Analysis' },
  { icon: ScanLine,      label: 'Document OCR' },
  { icon: ShieldCheck,   label: 'Compliance Verification' },
  { icon: AlertOctagon,  label: 'Risk Intelligence' },
  { icon: GitBranch,     label: 'Evidence Lineage' },
  { icon: UserCheck,     label: 'Officer Review' },
  { icon: FileBarChart,  label: 'Formal Reports' },
];

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    if (getToken()) { router.replace('/'); return; }
    const params = new URLSearchParams(window.location.search);
    if (params.get('expired') === '1') {
      setExpired(true);
      window.history.replaceState(null, '', '/login');
    }
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
      {/* ── Left: interactive information panel ─────────────────────── */}
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
        </div>

        {/* 3D flip card — front: brand statement · back: capabilities.
            Hover flips on desktop; click/tap and keyboard toggle everywhere.
            The login form never depends on the card being revealed. */}
        <div
          className={`flip-scene${flipped ? ' is-flipped' : ''}`}
          onMouseEnter={() => setFlipped(true)}
          onMouseLeave={() => setFlipped(false)}
        >
          <div
            className="flip-card"
            role="button"
            tabIndex={0}
            aria-pressed={flipped}
            aria-label={`BidShield product information card — ${flipped ? 'showing capabilities' : 'showing overview'}. Activate to flip.`}
            onClick={() => setFlipped(f => !f)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setFlipped(f => !f);
              }
            }}
          >
            {/* FRONT */}
            <div className="flip-face flip-front" aria-hidden={flipped}>
              <div className="flip-front-logo">
                <BidShieldLogo size={56} variant="compact" onDark />
              </div>
              <h1 className="flip-front-title">BIDSHIELD</h1>
              <p className="flip-front-statement">
                AI-Assisted Procurement
                <br />
                Compliance Intelligence
              </p>
              <span className="flip-hint" aria-hidden="true">
                <MousePointerClick size={12} />
                Hover or tap for capabilities
              </span>
            </div>

            {/* BACK */}
            <div className="flip-face flip-back" aria-hidden={!flipped}>
              <div className="flip-back-title">BidShield Capabilities</div>
              <ul className="flip-capability-list">
                {CAPABILITIES.map(({ icon: Icon, label }) => (
                  <li key={label} className="flip-capability-item">
                    <span className="flip-capability-icon">
                      <Icon size={14} aria-hidden="true" />
                    </span>
                    <span className="flip-capability-label">{label}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom meta */}
        <p className="login-meta">
          <b>Session notice.</b> All sign-ins, reviews, and decisions are
          recorded in a tamper-evident audit chain. BidShield is an independent
          AI-assisted procurement compliance platform — it is not an official
          government marketplace product.
        </p>
      </div>

      {/* ── Right: sign-in panel ────────────────────────────────────── */}
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
          Unauthorized access is prohibited. BidShield is an independent
          platform and is not affiliated with any government marketplace.
        </p>
      </div>
    </div>
  );
}
