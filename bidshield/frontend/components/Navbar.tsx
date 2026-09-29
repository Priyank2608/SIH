'use client';
import React, { useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useCurrentUser } from '../lib/userContext';
import { clearToken } from '../lib/api';
import { getRoleLabel } from '../lib/permissions';
import {
  ChevronRight,
  LogOut,
  UserRound,
  Settings,
  ChevronDown,
  Search,
} from 'lucide-react';

/* ── Breadcrumb label map ────────────────────────────────────────────────── */
const SEGMENT_LABELS: Record<string, string> = {
  '':           'Dashboard',
  tenders:      'Tenders',
  bidders:      'Bidders',
  verification: 'Verification',
  compliance:   'Compliance',
  reports:      'Reports',
  audit:        'Audit Trail',
  profile:      'Profile',
  settings:     'Settings',
};

function buildBreadcrumbs(pathname: string) {
  const segments = pathname.split('/').filter(Boolean);
  const crumbs: { label: string; href: string }[] = [
    { label: 'Home', href: '/' },
  ];
  let path = '';
  for (const seg of segments) {
    path += `/${seg}`;
    const label = SEGMENT_LABELS[seg] ?? (seg.startsWith('[') ? 'Detail' : `#${seg}`);
    crumbs.push({ label, href: path });
  }
  return crumbs;
}

/**
 * Command bar — a ledger masthead: breadcrumbs on the left,
 * quiet global search, and officer identity on the right.
 */
export default function Navbar() {
  const pathname = usePathname();
  const router   = useRouter();
  const user     = useCurrentUser();
  const [menuOpen, setMenuOpen] = useState(false);
  const [query, setQuery] = useState('');

  const breadcrumbs = buildBreadcrumbs(pathname);
  const roleLabel   = getRoleLabel(user?.role);

  const handleLogout = () => {
    clearToken();
    router.push('/login');
  };

  // Quiet global jump — enters the first matching workspace section
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim().toLowerCase();
    if (!q) return;
    const targets: [string, string][] = [
      ['tender', '/tenders'],
      ['bid', '/tenders'],
      ['bidder', '/bidders'],
      ['verif', '/verification'],
      ['report', '/reports'],
      ['audit', '/audit'],
    ];
    const match = targets.find(([needle]) => q.includes(needle));
    router.push(match ? match[1] : '/');
    setQuery('');
  };

  return (
    <header className="app-navbar" role="banner">
      {/* ── Left: breadcrumbs ───────────────────────────────────────── */}
      <div className="commandbar-left">
        <nav aria-label="Breadcrumb" className="commandbar-breadcrumb">
          {breadcrumbs.map((crumb, i) => (
            <React.Fragment key={crumb.href}>
              {i > 0 && (
                <ChevronRight
                  size={12}
                  className="breadcrumb-sep"
                  aria-hidden="true"
                />
              )}
              {i === breadcrumbs.length - 1 ? (
                <span className="breadcrumb-current" aria-current="page">
                  {crumb.label}
                </span>
              ) : (
                <Link href={crumb.href} className="breadcrumb-link">
                  {crumb.label}
                </Link>
              )}
            </React.Fragment>
          ))}
        </nav>
      </div>

      {/* ── Right: search + identity ────────────────────────────────── */}
      <div className="commandbar-right">
        <form
          className="commandbar-search"
          onSubmit={handleSearchSubmit}
          role="search"
          aria-label="Global workspace search"
        >
          <Search size={13} className="search-icon" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search workspace…"
            aria-label="Search workspace"
          />
        </form>

        {/* Role badge */}
        {user && (
          <span className="navbar-role-badge" aria-label={`Role: ${roleLabel}`}>
            {roleLabel}
          </span>
        )}

        {/* User menu */}
        <div style={{ position: 'relative' }}>
          <button
            className="navbar-user-btn"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-haspopup="true"
            aria-expanded={menuOpen}
            aria-label="User menu"
          >
            <span className="navbar-avatar" aria-hidden="true">
              {(user?.full_name || user?.username || 'U')[0].toUpperCase()}
            </span>
            <span className="navbar-username" aria-hidden="true">
              {user?.full_name?.split('(')[0].trim() || user?.username || 'Officer'}
            </span>
            <ChevronDown size={13} aria-hidden="true" className={menuOpen ? 'rotate-180' : ''} style={{ transition: 'transform 0.15s' }} />
          </button>

          {/* Dropdown */}
          {menuOpen && (
            <>
              {/* Backdrop */}
              <div
                style={{ position: 'fixed', inset: 0, zIndex: 49 }}
                onClick={() => setMenuOpen(false)}
                aria-hidden="true"
              />
              <div
                className="navbar-dropdown"
                role="menu"
                aria-label="User options"
              >
                {/* Officer info header */}
                <div className="navbar-dropdown-header">
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {user?.full_name?.split('(')[0].trim() || user?.username}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '1px', fontFamily: 'var(--font-mono)' }}>
                    {user?.email}
                  </div>
                  <div style={{ marginTop: '5px' }}>
                    <span className="navbar-role-badge" style={{ display: 'inline-block' }}>
                      {roleLabel}
                    </span>
                  </div>
                </div>

                <div className="navbar-dropdown-divider" />

                <Link
                  href="/profile"
                  className="navbar-dropdown-item"
                  role="menuitem"
                  onClick={() => setMenuOpen(false)}
                >
                  <UserRound size={14} aria-hidden="true" />
                  Officer Profile
                </Link>
                <Link
                  href="/settings"
                  className="navbar-dropdown-item"
                  role="menuitem"
                  onClick={() => setMenuOpen(false)}
                >
                  <Settings size={14} aria-hidden="true" />
                  Settings
                </Link>

                <div className="navbar-dropdown-divider" />

                <button
                  className="navbar-dropdown-item danger"
                  role="menuitem"
                  onClick={() => { setMenuOpen(false); handleLogout(); }}
                  aria-label="Sign out of BidShield"
                >
                  <LogOut size={14} aria-hidden="true" />
                  Sign Out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
