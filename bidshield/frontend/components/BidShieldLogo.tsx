'use client';
import React from 'react';

/**
 * BidShield mark — shield + document + verification tick.
 *
 * Construction: a shield silhouette whose upper field carries a ruled
 * document leaf (three text rules), with a bold evidence-tick across
 * the lower field. Drawn on a 32×32 grid, 2px strokes.
 * Deliberately NOT a government emblem — a neutral operational mark.
 */

interface ShieldMarkProps {
  size?: number;
  /** color of the shield stroke/detail — defaults to currentColor */
  color?: string;
  /** fill of the shield interior */
  fill?: string;
  /** color of the verification tick */
  tickColor?: string;
  title?: string;
}

export function ShieldMark({
  size = 24,
  color = 'currentColor',
  fill = 'none',
  tickColor,
  title,
}: ShieldMarkProps) {
  const tick = tickColor ?? color;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
      focusable="false"
    >
      {title ? <title>{title}</title> : null}
      {/* Shield body */}
      <path
        d="M16 2.75 26.5 6.4v9.1c0 6.9-4.4 11.4-10.5 13.75C9.9 26.9 5.5 22.4 5.5 15.5V6.4L16 2.75Z"
        stroke={color}
        strokeWidth={2}
        strokeLinejoin="round"
        fill={fill}
      />
      {/* Document rules (upper field) */}
      <path d="M11.4 9.75h9.2" stroke={color} strokeWidth={1.8} strokeLinecap="round" />
      <path d="M11.4 13.4h6.2" stroke={color} strokeWidth={1.8} strokeLinecap="round" />
      {/* Verification tick (lower field) */}
      <path
        d="m11.2 18.9 3.4 3.4 6.2-6.6"
        stroke={tick}
        strokeWidth={2.4}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface BidShieldLogoProps {
  /** overall height in px; width scales with the wordmark */
  size?: number;
  variant?: 'full' | 'compact';
  /** color scheme for dark (ink) backgrounds */
  onDark?: boolean;
  className?: string;
}

/**
 * Full lockup: mark + "BidShield" wordmark + "PROCUREMENT CONSOLE" subline.
 * Compact: mark only.
 */
export default function BidShieldLogo({
  size = 30,
  variant = 'full',
  onDark = false,
  className,
}: BidShieldLogoProps) {
  const markColor = onDark ? '#7cccbd' : '#0d7264';
  const textColor = onDark ? '#eef2f8' : '#141b26';
  const subColor = onDark ? '#94a3ba' : '#57677e';

  if (variant === 'compact') {
    return (
      <span className={className} style={{ display: 'inline-flex', flexShrink: 0 }}>
        <ShieldMark size={size} color={markColor} title="BidShield" />
      </span>
    );
  }

  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: Math.round(size * 0.36),
        flexShrink: 0,
      }}
    >
      <ShieldMark size={size} color={markColor} />
      <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1 }}>
        <span
          style={{
            fontSize: Math.round(size * 0.48),
            fontWeight: 600,
            letterSpacing: '0.04em',
            color: textColor,
            whiteSpace: 'nowrap',
          }}
        >
          Bid<b style={{ fontWeight: 700 }}>Shield</b>
        </span>
        <span
          style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: Math.max(8, Math.round(size * 0.23)),
            letterSpacing: '0.16em',
            textTransform: 'uppercase',
            color: subColor,
            marginTop: Math.max(2, Math.round(size * 0.1)),
            whiteSpace: 'nowrap',
          }}
        >
          Procurement Console
        </span>
      </span>
    </span>
  );
}
