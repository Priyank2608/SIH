'use client';
import React, { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import AuthGuard from './AuthGuard';
import Navbar from './Navbar';
import Sidebar from './Sidebar';

/**
 * AppShellWrapper
 * - Login page: full-screen (no sidebar / navbar)
 * - All other pages: AuthGuard + Sidebar + Navbar + content
 * Tracks sidebar collapsed state so body margin stays in sync.
 */
export default function AppShellWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLoginPage = pathname === '/login';
  const [collapsed, setCollapsed] = useState(false);

  // Hydrate collapse state from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('bidshield_sidebar_collapsed');
    if (saved === 'true') setCollapsed(true);
  }, []);

  const handleToggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem('bidshield_sidebar_collapsed', String(next));
  };

  if (isLoginPage) {
    return <>{children}</>;
  }

  return (
    <AuthGuard>
      <Sidebar collapsed={collapsed} onToggle={handleToggle} />
      <div className={`app-body${collapsed ? ' rail-collapsed-body' : ''}`}>
        <Navbar />
        <main className="page-content" id="main-content">
          {children}
        </main>
      </div>
    </AuthGuard>
  );
}
