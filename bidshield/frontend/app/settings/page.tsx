'use client';
import React, { useEffect, useState } from 'react';
import { useCurrentUser } from '../../lib/userContext';
import { Settings2, ShieldAlert, Cpu, BellRing, Database, CheckCircle2 } from 'lucide-react';

const NAV = [
  { id: 'general',       label: 'General',       icon: Settings2 },
  { id: 'notifications', label: 'Notifications', icon: BellRing },
  { id: 'security',      label: 'Security',      icon: ShieldAlert },
  { id: 'engine',        label: 'OCR & ML Engine', icon: Cpu },
  { id: 'data',          label: 'Data Management', icon: Database },
];

export default function SettingsPage() {
  const user = useCurrentUser();
  const isAdmin = user?.role === 'SUPER_ADMIN';

  const [activeTab, setActiveTab] = useState('general');
  const [timezone, setTimezone] = useState('Asia/Kolkata');
  const [notifications, setNotifications] = useState({ tender: true, verification: true, digest: true });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    try {
      const prefs = JSON.parse(localStorage.getItem('bidshield_preferences') || '{}');
      if (prefs.timezone) setTimezone(prefs.timezone);
      if (prefs.notifications) setNotifications((current) => ({ ...current, ...prefs.notifications }));
    } catch { /* Invalid local preferences are ignored. */ }
  }, []);

  const savePreferences = () => {
    localStorage.setItem('bidshield_preferences', JSON.stringify({ timezone, notifications }));
    setSaved(true);
  };

  const visibleNav = NAV.filter(n => isAdmin || (n.id !== 'engine' && n.id !== 'data'));

  return (
    <main className="main-wrapper">
      <div className="page-header">
        <div className="page-header-text">
          <div className="page-eyebrow">Preferences</div>
          <h1 className="page-title">Settings</h1>
          <p className="page-desc">
            Personal timezone and notification preferences are stored in this browser.
            Runtime, engine, and security policies are managed by the deployment.
          </p>
        </div>
      </div>
      <hr className="page-rule" />

      <div className="grid-side-main" style={{ gridTemplateColumns: '220px minmax(0, 1fr)' }}>
        {/* Section nav */}
        <nav aria-label="Settings sections" style={{ display: 'flex', flexDirection: 'column', gap: '2px', borderRight: '1px solid var(--border)', paddingRight: '12px' }}>
          {visibleNav.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={`settings-nav-btn${activeTab === id ? ' active' : ''}`}
              onClick={() => setActiveTab(id)}
              aria-current={activeTab === id ? 'true' : undefined}
            >
              <Icon size={15} aria-hidden="true" />
              {label}
            </button>
          ))}
        </nav>

        {/* Section content */}
        <div style={{ minWidth: 0 }}>
          {activeTab === 'general' && (
            <div>
              <div className="settings-section">
                <h2 className="settings-section-title">Application Mode</h2>
                <p className="settings-section-desc">
                  The deployment mode is fixed by the backend configuration and cannot be changed from the console.
                </p>
                <select className="form-input" style={{ maxWidth: '400px' }} value="demo" disabled aria-label="Application mode">
                  <option value="demo">Prototype / Demo Mode</option>
                  <option value="prod">Production (Live GeM Integration)</option>
                </select>
                <p className="text-xs text-muted" style={{ marginTop: '6px' }}>
                  Switching to production requires active GeM VPN certificates and is performed by the deployment operator.
                </p>
              </div>

              <div className="settings-section">
                <h2 className="settings-section-title">Timezone</h2>
                <p className="settings-section-desc">Used for displaying timestamps in this browser.</p>
                <select
                  className="form-input"
                  style={{ maxWidth: '400px' }}
                  value={timezone}
                  onChange={(event) => { setTimezone(event.target.value); setSaved(false); }}
                  aria-label="Timezone"
                >
                  <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
                  <option value="utc">UTC</option>
                </select>
              </div>

              <button className="btn btn-primary" onClick={savePreferences}>Save Personal Preferences</button>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div>
              <div className="settings-section">
                <h2 className="settings-section-title">Notification Preferences</h2>
                <p className="settings-section-desc">
                  Choices are saved in this browser only. Email, push, and digest delivery are not connected to a backend
                  notification service, so these toggles record intent but do not dispatch messages.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', maxWidth: '480px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <input
                      type="checkbox"
                      checked={notifications.tender}
                      onChange={(event) => { setNotifications({ ...notifications, tender: event.target.checked }); setSaved(false); }}
                    />
                    Alert me when new tenders are submitted
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <input
                      type="checkbox"
                      checked={notifications.verification}
                      onChange={(event) => { setNotifications({ ...notifications, verification: event.target.checked }); setSaved(false); }}
                    />
                    Alert me when a verification job fails
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <input
                      type="checkbox"
                      checked={notifications.digest}
                      onChange={(event) => { setNotifications({ ...notifications, digest: event.target.checked }); setSaved(false); }}
                    />
                    Include me in weekly compliance report digests
                  </label>
                </div>
                <button className="btn btn-primary" style={{ marginTop: '20px' }} onClick={savePreferences}>Save Preferences</button>
              </div>
            </div>
          )}

          {activeTab === 'security' && (
            <div>
              <div className="settings-section">
                <h2 className="settings-section-title">Immutable Audit Ledger</h2>
                <div className="alert alert-danger" style={{ marginBottom: '14px', maxWidth: '560px' }}>
                  <ShieldAlert size={15} aria-hidden="true" style={{ flexShrink: 0 }} />
                  <span>
                    The audit trail cannot be disabled. All actions by procurement officers, system verifications,
                    and model inferences are permanently written to the ledger as per GeM compliance policies.
                  </span>
                </div>
              </div>

              <div className="settings-section">
                <h2 className="settings-section-title">Session Timeout</h2>
                <p className="settings-section-desc">Controlled by the backend; enforced on every API request.</p>
                <input type="number" className="form-input" defaultValue={120} disabled style={{ maxWidth: '200px' }} aria-label="Session timeout (read only)" />
                <p className="text-xs text-muted" style={{ marginTop: '6px' }}>Minutes · read only.</p>
              </div>
            </div>
          )}

          {isAdmin && activeTab === 'engine' && (
            <div>
              <div className="settings-section">
                <h2 className="settings-section-title">OCR &amp; AI Verification Engine</h2>
                <p className="settings-section-desc">
                  Engine thresholds and models are configured at deployment time; no backend settings API is wired to this console.
                </p>
                <div style={{ marginBottom: '22px', maxWidth: '480px' }}>
                  <label style={{ display: 'block', fontWeight: 500, marginBottom: '8px' }} htmlFor="conf-slider">
                    Minimum Acceptable Confidence Threshold
                  </label>
                  <input id="conf-slider" type="range" min="50" max="99" defaultValue="85" disabled style={{ width: '100%' }} />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    <span>50% (Loose)</span>
                    <span>85% (Current)</span>
                    <span>99% (Strict)</span>
                  </div>
                </div>

                <div style={{ marginBottom: '22px', maxWidth: '480px' }}>
                  <label style={{ display: 'block', fontWeight: 500, marginBottom: '8px' }} htmlFor="llm-select">
                    Active LLM Model for Semantic Checking
                  </label>
                  <select id="llm-select" className="form-input" style={{ maxWidth: '400px' }} defaultValue="llama3" disabled>
                    <option value="llama3">Llama 3 8B (Fastest)</option>
                    <option value="gemini">Gemini 1.5 Pro (Most Accurate)</option>
                    <option value="openai">GPT-4o (Fallback)</option>
                  </select>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', maxWidth: '480px' }}>
                  <input type="checkbox" id="auto_flag" defaultChecked disabled />
                  <label htmlFor="auto_flag">Automatically flag bids with confidence below threshold for manual review</label>
                </div>

                <p className="text-xs text-muted" style={{ marginTop: '16px' }}>
                  Read only. These settings are not connected to a backend configuration API.
                </p>
              </div>
            </div>
          )}

          {isAdmin && activeTab === 'data' && (
            <div>
              <div className="settings-section">
                <h2 className="settings-section-title">Data Management &amp; Maintenance</h2>
                <p className="settings-section-desc">
                  Maintenance jobs would re-index OCR records and clear caches. No backend jobs API is configured, so
                  these controls are disabled rather than pretending to run.
                </p>
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                  <button disabled className="btn btn-outline">Re-index Documents</button>
                  <button disabled className="btn btn-outline">Clear Cache</button>
                  <button disabled className="btn btn-danger">Purge Training Sync Data</button>
                </div>
                <p className="text-xs text-muted" style={{ marginTop: '16px' }}>
                  Maintenance actions are unavailable in this frontend because no backend jobs API is configured.
                </p>
              </div>
            </div>
          )}

          {saved && (
            <p role="status" className="text-sm text-success" style={{ marginTop: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle2 size={14} aria-hidden="true" />
              Personal preferences saved in this browser.
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
