/**
 * BidShield — Centralized Permission System
 *
 * All frontend permission checks go through this module.
 * NOTE: Frontend permissions are UX helpers only.
 * Every sensitive action MUST also be enforced by the backend.
 */

// ─── Backend role strings (must match DB values exactly) ──────────────────────
export const ROLES = {
  PROCUREMENT_OFFICER: 'PROCUREMENT_OFFICER',
  VERIFICATION_OFFICER: 'VERIFICATION_OFFICER',
  AUDITOR: 'AUDITOR',
  SUPER_ADMIN: 'SUPER_ADMIN',
} as const;

export type Role = typeof ROLES[keyof typeof ROLES];

// ─── Permission identifiers ────────────────────────────────────────────────────
export type Permission =
  // Tender
  | 'tender.view'
  | 'tender.create'
  | 'tender.edit'
  | 'tender.requirements.approve'
  // Bidder
  | 'bidder.view'
  | 'bidder.dossier'
  // Documents
  | 'document.view'
  | 'document.upload'
  | 'document.ocr.view'
  // Verification
  | 'verification.view'
  | 'verification.retry'
  // Compliance
  | 'compliance.view'
  // Risk
  | 'risk.view'
  // Evidence
  | 'evidence.view'
  // Officer Decision
  | 'decision.create'
  // Reports
  | 'report.view'
  | 'report.generate'
  // Audit
  | 'audit.view'
  // Admin
  | 'admin.users'
  | 'admin.roles'
  | 'admin.system';

// ─── Role → Permissions map ────────────────────────────────────────────────────
const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  PROCUREMENT_OFFICER: [
    'tender.view', 'tender.create', 'tender.edit', 'tender.requirements.approve',
    'bidder.view', 'bidder.dossier',
    'document.view', 'document.upload', 'document.ocr.view',
    'verification.view',
    'compliance.view',
    'risk.view',
    'evidence.view',
    'decision.create',
    'report.view', 'report.generate',
    'audit.view',
  ],
  VERIFICATION_OFFICER: [
    'tender.view',
    'bidder.view', 'bidder.dossier',
    'document.view', 'document.ocr.view',
    'verification.view', 'verification.retry',
    'compliance.view',
    'evidence.view',
    'report.view',
    'audit.view',
  ],
  AUDITOR: [
    'tender.view',
    'bidder.view', 'bidder.dossier',
    'document.view', 'document.ocr.view',
    'verification.view',
    'compliance.view',
    'risk.view',
    'evidence.view',
    'report.view',
    'audit.view',
  ],
  // Administration authority does NOT confer procurement decision or intake
  // authority. The admin role sees system/oversight views only; procurement
  // write actions remain exclusive to the Procurement Officer.
  SUPER_ADMIN: [
    'tender.view',
    'bidder.view', 'bidder.dossier',
    'document.view', 'document.ocr.view',
    'verification.view', 'verification.retry',
    'compliance.view',
    'risk.view',
    'evidence.view',
    'report.view',
    'audit.view',
    'admin.users', 'admin.roles', 'admin.system',
  ],
};

// ─── Permission checker ────────────────────────────────────────────────────────
export function can(role: Role | string | undefined, permission: Permission): boolean {
  if (!role) return false;
  const perms = ROLE_PERMISSIONS[role as Role];
  if (!perms) return false;
  return perms.includes(permission);
}

export function canAny(role: Role | string | undefined, permissions: Permission[]): boolean {
  return permissions.some((p) => can(role, p));
}

export function canAll(role: Role | string | undefined, permissions: Permission[]): boolean {
  return permissions.every((p) => can(role, p));
}

// ─── Navigation items ─────────────────────────────────────────────────────────
export interface NavItem {
  label: string;
  href: string;
  icon: string;
  permission: Permission;
  badge?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard',     href: '/',             icon: 'LayoutDashboard', permission: 'tender.view' },
  { label: 'Tenders',       href: '/tenders',      icon: 'FileText',        permission: 'tender.view' },
  { label: 'Bidders',       href: '/bidders',      icon: 'Users',           permission: 'bidder.view' },
  { label: 'Documents',     href: '/verification', icon: 'ShieldCheck',     permission: 'document.view' },
  { label: 'Reports',       href: '/reports',      icon: 'FileBarChart',    permission: 'report.view' },
  { label: 'Audit Trail',   href: '/audit',        icon: 'History',         permission: 'audit.view' },
];

export function getNavItems(role: Role | string | undefined): NavItem[] {
  return NAV_ITEMS.filter((item) => can(role, item.permission));
}

// ─── Display labels ───────────────────────────────────────────────────────────
export const ROLE_LABELS: Record<string, string> = {
  PROCUREMENT_OFFICER: 'Procurement Officer',
  VERIFICATION_OFFICER: 'Verification Officer',
  AUDITOR: 'Auditor',
  SUPER_ADMIN: 'Administrator',
};

export function getRoleLabel(role: string | undefined): string {
  if (!role) return 'Unknown';
  return ROLE_LABELS[role] ?? role.replace(/_/g, ' ');
}
