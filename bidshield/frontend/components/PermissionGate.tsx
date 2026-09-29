'use client';
import React from 'react';
import { useCurrentUser } from '../lib/userContext';
import { can, canAny, Permission } from '../lib/permissions';

interface PermissionGateProps {
  /** Single permission required */
  permission?: Permission;
  /** Any of these permissions grants access */
  anyOf?: Permission[];
  /** Fallback to render when access is denied (default: null) */
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * PermissionGate
 * --------------
 * Renders children only if the current user has the required permission(s).
 * Use this to conditionally show/hide UI elements based on role.
 *
 * IMPORTANT: This is a UX convenience only.
 * The backend must independently enforce all permissions.
 *
 * Usage:
 *   <PermissionGate permission="decision.create">
 *     <DecisionButton />
 *   </PermissionGate>
 *
 *   <PermissionGate anyOf={['report.generate', 'report.view']}>
 *     <ReportPanel />
 *   </PermissionGate>
 */
export default function PermissionGate({
  permission,
  anyOf,
  fallback = null,
  children,
}: PermissionGateProps) {
  const user = useCurrentUser();
  const role = user?.role;

  let allowed = false;
  if (permission) {
    allowed = can(role, permission);
  } else if (anyOf && anyOf.length > 0) {
    allowed = canAny(role, anyOf);
  } else {
    // No permission specified — allow by default
    allowed = true;
  }

  return allowed ? <>{children}</> : <>{fallback}</>;
}
