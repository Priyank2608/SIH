'use client';
import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, clearToken, getToken, getCurrentUser } from '../lib/api';
import { UserContext, CurrentUser } from '../lib/userContext';
import { ShieldCheck } from 'lucide-react';

interface AuthGuardProps {
  children: React.ReactNode;
}

/**
 * AuthGuard
 * ---------
 * Verifies the JWT is valid by calling /auth/me.
 * Exposes the authenticated user via UserContext so child components
 * can call useCurrentUser() to get role/permissions.
 * Also sets data-role on <html> so CSS role-accent variables activate.
 */
export default function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace('/login');
      return;
    }

    // Check session storage first for fast render
    const cached = getCurrentUser();
    if (cached) {
      setUser(cached);
      // Apply role accent immediately from cache
      document.documentElement.setAttribute('data-role', cached.role || '');
    }

    // Always verify with backend (token may have expired)
    api('/auth/me')
      .then((me: CurrentUser) => {
        setUser(me);
        // Apply role accent on html element for CSS custom property cascade
        document.documentElement.setAttribute('data-role', me.role || '');
        // Refresh cached user
        if (typeof window !== 'undefined') {
          sessionStorage.setItem('bidshield_user', JSON.stringify(me));
        }
        setChecking(false);
      })
      .catch(() => {
        clearToken();
        router.replace('/login');
      });
  }, [router]);

  if (checking && !user) {
    return (
      <div className="auth-loading-screen" aria-busy="true" role="status">
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '12px',
        }}>
          <div style={{
            width: '48px',
            height: '48px',
            borderRadius: '12px',
            background: 'var(--primary)',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <ShieldCheck size={24} aria-hidden="true" />
          </div>
          <div className="spinner" aria-hidden="true" />
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
            Verifying credentials…
          </p>
        </div>
      </div>
    );
  }

  return (
    <UserContext.Provider value={user}>
      {children}
    </UserContext.Provider>
  );
}
