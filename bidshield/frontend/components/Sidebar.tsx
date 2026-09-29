'use client';
import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useCurrentUser } from '../lib/userContext';
import { getNavItems, getRoleLabel, Permission } from '../lib/permissions';
import BidShieldLogo from './BidShieldLogo';
import {
  LayoutDashboard,
  FileText,
  Users,
  ShieldCheck,
  FileBarChart,
  History,
  Settings,
  UserRound,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

const ICON_MAP: Record<string, React.ElementType> = {
  LayoutDashboard,
  FileText,
  Users,
  ShieldCheck,
  FileBarChart,
  History,
};

interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

/**
 * Navigation rail — permission-filtered, grouped into
 * OPERATE / OVERSIGHT bands generated from the role's nav items.
 */
export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();
  const user = useCurrentUser();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
    const saved = localStorage.getItem('bidshield_sidebar_collapsed');
    if (saved === 'true') setIsCollapsed(true);
  }, []);

  const toggleCollapse = () => {
    const next = !isCollapsed;
    setIsCollapsed(next);
    localStorage.setItem('bidshield_sidebar_collapsed', String(next));
    onToggle?.();
  };

  // Build navigation from user's role permissions
  const navItems = user ? getNavItems(user.role) : [];

  function isActive(href: string) {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  }

  const roleLabel = getRoleLabel(user?.role);

  // Group nav into two bands: daily work vs oversight records
  const operational = navItems.filter((i) =>
    ['/', '/tenders', '/bidders', '/verification'].includes(i.href)
  );
  const records = navItems.filter(
    (i) => !['/', '/tenders', '/bidders', '/verification'].includes(i.href)
  );

  const renderItem = (item: (typeof navItems)[number]) => {
    const Icon = ICON_MAP[item.icon] ?? FileText;
    const active = isActive(item.href);
    return (
      <Link
        key={item.href}
        href={item.href}
        className={`rail-item${active ? ' active' : ''}`}
        aria-current={active ? 'page' : undefined}
        title={isCollapsed ? item.label : undefined}
      >
        <Icon size={17} className="rail-item-icon" aria-hidden="true" />
        {!isCollapsed && <span className="rail-item-label">{item.label}</span>}
      </Link>
    );
  };

  return (
    <aside
      className={`app-rail${isCollapsed ? ' rail-collapsed' : ''}`}
      aria-label="Main navigation"
    >
      {/* Brand */}
      <div className="rail-brand">
        <span className="rail-brand-icon">
          <BidShieldLogo size={28} variant="compact" onDark />
        </span>
        {!isCollapsed && (
          <span className="rail-brand-text">
            <span className="rail-brand-name">BidShield</span>
            <span className="rail-brand-sub">Procurement Console</span>
          </span>
        )}
      </div>

      {/* Navigation — grouped by function */}
      <nav className="rail-nav" aria-label="Application navigation">
        {hydrated && operational.length > 0 && (
          <>
            <div className="rail-section-label" aria-hidden="true">
              Operations
            </div>
            {operational.map(renderItem)}
          </>
        )}
        {hydrated && records.length > 0 && (
          <>
            <div className="rail-section-label" aria-hidden="true">
              Records
            </div>
            {records.map(renderItem)}
          </>
        )}
      </nav>

      {/* Bottom section */}
      <div className="rail-bottom">
        <Link
          href="/profile"
          className={`rail-item${pathname === '/profile' ? ' active' : ''}`}
          title={isCollapsed ? 'Profile' : undefined}
          aria-label="Officer profile"
        >
          <UserRound size={17} className="rail-item-icon" aria-hidden="true" />
          {!isCollapsed && <span className="rail-item-label">Profile</span>}
        </Link>

        <Link
          href="/settings"
          className={`rail-item${pathname === '/settings' ? ' active' : ''}`}
          title={isCollapsed ? 'Settings' : undefined}
        >
          <Settings size={17} className="rail-item-icon" aria-hidden="true" />
          {!isCollapsed && <span className="rail-item-label">Settings</span>}
        </Link>

        {!isCollapsed && user && (
          <div className="rail-officer" aria-label={`Signed in as ${roleLabel}`}>
            <div className="rail-officer-avatar" aria-hidden="true">
              {(user.full_name || user.username || 'U')[0].toUpperCase()}
            </div>
            <div className="rail-officer-info">
              <span className="rail-officer-name">
                {user.full_name?.split('(')[0].trim() || user.username}
              </span>
              <span className="rail-officer-role">{roleLabel}</span>
            </div>
          </div>
        )}

        <button
          className="rail-collapse-btn"
          onClick={toggleCollapse}
          aria-label={isCollapsed ? 'Expand navigation' : 'Collapse navigation'}
          aria-expanded={!isCollapsed}
        >
          {isCollapsed
            ? <ChevronRight size={14} aria-hidden="true" />
            : <ChevronLeft size={14} aria-hidden="true" />}
          {!isCollapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}
