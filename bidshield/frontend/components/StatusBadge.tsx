'use client';
import React from 'react';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  RefreshCw,
  Ban,
  AlertCircle,
  HelpCircle,
  MinusCircle,
  FileWarning,
} from 'lucide-react';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
}

interface BadgeConfig {
  className: string;
  Icon: React.ElementType;
  label: string;
  ariaLabel: string;
}

function getConfig(norm: string): BadgeConfig {
  switch (norm) {
    /* ---- VERIFIED / SUCCESS states ---- */
    case 'VERIFIED':
    case 'PASS':
    case 'ACCEPTED':
    case 'APPROVED':
      return {
        className: 'badge-success',
        Icon: CheckCircle2,
        label: norm === 'APPROVED' ? 'Approved' : norm === 'ACCEPTED' ? 'Accepted' : norm === 'PASS' ? 'Pass' : 'Verified',
        ariaLabel: 'Status: Verified',
      };

    case 'LOW':
      return {
        className: 'badge-success',
        Icon: CheckCircle2,
        label: 'Low Risk',
        ariaLabel: 'Risk level: Low',
      };

    case 'ACTIVE':
    case 'PUBLISHED':
      return {
        className: 'badge-info',
        Icon: CheckCircle2,
        label: norm === 'ACTIVE' ? 'Active' : 'Published',
        ariaLabel: `Status: ${norm}`,
      };

    /* ---- WARNING / ATTENTION states ---- */
    case 'REVIEW_REQUIRED':
    case 'MANUAL_REVIEW':
    case 'MANUAL_REVIEW_REQUESTED':
    case 'REVIEW':
      return {
        className: 'badge-warning',
        Icon: AlertTriangle,
        label: 'Manual Review',
        ariaLabel: 'Status: Manual review required',
      };

    case 'CONDITIONAL':
    case 'MODIFIED':
      return {
        className: 'badge-warning',
        Icon: AlertTriangle,
        label: norm === 'MODIFIED' ? 'Modified' : 'Conditional',
        ariaLabel: `Status: ${norm}`,
      };

    case 'MEDIUM':
      return {
        className: 'badge-warning',
        Icon: AlertTriangle,
        label: 'Medium Risk',
        ariaLabel: 'Risk level: Medium',
      };

    /* ---- DANGER / HIGH RISK states ---- */
    case 'FAILED':
    case 'FAIL':
    case 'REJECTED':
    case 'NON_COMPLIANT':
    case 'ERROR':
      return {
        className: 'badge-danger',
        Icon: XCircle,
        label:
          norm === 'REJECTED' ? 'Rejected'
          : norm === 'NON_COMPLIANT' ? 'Non-Compliant'
          : norm === 'ERROR' ? 'Error'
          : 'Failed',
        ariaLabel: `Status: ${norm}`,
      };

    case 'HIGH':
      return {
        className: 'badge-danger',
        Icon: XCircle,
        label: 'High Risk',
        ariaLabel: 'Risk level: High',
      };

    /* ---- MISMATCH ---- */
    case 'MISMATCH':
    case 'INCONSISTENT':
      return {
        className: 'badge-mismatch',
        Icon: AlertCircle,
        label: 'Mismatch',
        ariaLabel: 'Status: Data mismatch detected',
      };

    /* ---- EXPIRED ---- */
    case 'EXPIRED':
      return {
        className: 'badge-expired',
        Icon: FileWarning,
        label: 'Expired',
        ariaLabel: 'Status: Expired',
      };

    /* ---- MISSING ---- */
    case 'MISSING':
    case 'NOT_APPLICABLE':
      return {
        className: 'badge-missing',
        Icon: MinusCircle,
        label: norm === 'NOT_APPLICABLE' ? 'Not Applicable' : 'Missing',
        ariaLabel: `Status: ${norm === 'NOT_APPLICABLE' ? 'Not applicable' : 'Missing'}`,
      };

    /* ---- RETRY REQUIRED ---- */
    case 'RETRY_REQUIRED':
      return {
        className: 'badge-retry',
        Icon: RefreshCw,
        label: 'Retry Required',
        ariaLabel: 'Status: Retry required',
      };

    /* ---- INSUFFICIENT EVIDENCE ---- */
    case 'INSUFFICIENT_EVIDENCE':
      return {
        className: 'badge-insufficient',
        Icon: HelpCircle,
        label: 'Insufficient Evidence',
        ariaLabel: 'Status: Insufficient evidence — not the same as low risk',
      };

    /* ---- NOT AVAILABLE ---- */
    case 'NOT_AVAILABLE':
    case 'UNAVAILABLE':
      return {
        className: 'badge-unavailable',
        Icon: Ban,
        label: 'Not Available',
        ariaLabel: 'Status: Provider data not available',
      };

    /* ---- PENDING / NEUTRAL (default) ---- */
    case 'PENDING':
    case 'DRAFT':
    case 'SUBMITTED':
    default: {
      const label =
        norm === 'DRAFT' ? 'Draft'
        : norm === 'SUBMITTED' ? 'Submitted'
        : 'Pending';
      return {
        className: 'badge-neutral',
        Icon: Clock,
        label,
        ariaLabel: `Status: ${label}`,
      };
    }
  }
}

export default function StatusBadge({
  status,
  size = 'md',
  showIcon = true,
}: StatusBadgeProps) {
  const norm = (status || 'PENDING').toUpperCase().replace(/-/g, '_');
  const config = getConfig(norm);
  const { className, Icon, label, ariaLabel } = config;

  return (
    <span
      className={`status-badge ${className} size-${size}`}
      role="img"
      aria-label={ariaLabel}
      title={ariaLabel}
    >
      {showIcon && (
        <Icon
          size={size === 'lg' ? 13 : size === 'sm' ? 10 : 11}
          className="badge-icon"
          aria-hidden="true"
          strokeWidth={2.2}
        />
      )}
      <span className="badge-label">{label}</span>
    </span>
  );
}
