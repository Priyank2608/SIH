"""Layer 2 — Intrusion & Anomaly Detection.

Tracks failed logins (account-scoped lockout, never IP-scoped), repeated
authorization violations, and injection-pattern hits. Every detection is
written to the queryable security_events table. Confirmed anomalies request
an out-of-band snapshot from the Layer 4 vault through a debounce timer that
is independent of scheduled/startup snapshots, so an attack burst cannot fill
the disk but a routine backup also cannot silently swallow the next attack's
snapshot.
"""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import LoginAttempt, SecurityEvent

logger = logging.getLogger("bidshield.security")

# Kinds of security events that warrant an out-of-band snapshot request.
SNAPSHOT_TRIGGERS = {"LOGIN_LOCKOUT", "VIOLATION_BURST", "INJECTION_PATTERN"}

# ── Anomaly-snapshot debounce (independent of scheduled snapshots) ────────
_debounce_lock = threading.Lock()
_last_anomaly_snapshot: Optional[float] = None  # monotonic clock; None = never


def reset_debounce_for_tests() -> None:
    """Test helper: forget that a recent anomaly snapshot happened."""
    global _last_anomaly_snapshot
    with _debounce_lock:
        _last_anomaly_snapshot = None


def _request_anomaly_snapshot() -> bool:
    """Ask the Layer 4 vault for an out-of-band snapshot, debounced per-attack.

    Returns True when a snapshot was actually taken. The debounce timer is
    shared across consecutive anomaly events (60s gap by default) but is NOT
    consulted by — and does not reset — scheduled/startup snapshots.
    """
    global _last_anomaly_snapshot
    now = time.monotonic()
    gap = max(1, settings.anomaly_snapshot_debounce_seconds)
    with _debounce_lock:
        if _last_anomaly_snapshot is not None and (now - _last_anomaly_snapshot) < gap:
            return False
        _last_anomaly_snapshot = now
    try:
        # Imported lazily to avoid a circular import (vault reads settings only).
        from app.services.backup_service import take_snapshot
        path, meta = take_snapshot(reason="ANOMALY_TRIGGER")
        logger.info("Anomaly-triggered vault snapshot: %s", path)
        return True
    except Exception:
        # Snapshotting must never take down request handling; the security
        # event itself has already been persisted by the caller.
        logger.exception("Anomaly-triggered snapshot failed")
        return False


def log_security_event(
    db: Session,
    kind: str,
    source_ip: str = "0.0.0.0",
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> SecurityEvent:
    """Persist a detection to the queryable security log, then decide whether
    this confirmed anomaly should also request a vault snapshot. Logging ALWAYS
    happens; the snapshot itself may be debounced, never the record."""
    event = SecurityEvent(
        kind=kind,
        source_ip=source_ip or "0.0.0.0",
        username=username,
        user_id=user_id,
        tenant_id=tenant_id,
        detail=detail or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    if kind in SNAPSHOT_TRIGGERS:
        _request_anomaly_snapshot()
    return event


# ── Account-scoped login lockout ────────────────────────────────────────────
# Scope is the USERNAME ONLY. Office NAT / corporate VPN / factory networks
# put many legitimate users behind one outbound IP, so an IP-wide lockout
# would let one bad password deny service to an entire site. Rapid-fire
# guessing per IP is Layer 1's plain rate limiter's job.

def record_login_attempt(db: Session, username: str, successful: bool,
                         source_ip: str = "0.0.0.0") -> None:
    db.add(LoginAttempt(
        username=username or "",
        source_ip=source_ip or "0.0.0.0",
        successful=bool(successful),
    ))
    db.commit()


def is_locked_out(db: Session, username: str) -> bool:
    """True when the account itself is serving a lockout penalty."""
    if not username:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.lockout_minutes)
    failed = (db.query(LoginAttempt)
              .filter(LoginAttempt.username == username,
                      LoginAttempt.successful.is_(False),
                      LoginAttempt.created_at >= cutoff)
              .count())
    return failed >= settings.lockout_threshold


def lockout_expiry(db: Session, username: str) -> Optional[datetime]:
    """When the current lockout lifts, or None. The penalty window starts at
    the failed attempt that crossed the threshold."""
    if not is_locked_out(db, username):
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.lockout_minutes)
    fails = (db.query(LoginAttempt)
             .filter(LoginAttempt.username == username,
                     LoginAttempt.successful.is_(False),
                     LoginAttempt.created_at >= cutoff)
             .order_by(LoginAttempt.created_at.desc())
             .limit(settings.lockout_threshold)
             .all())
    if not fails:
        return None
    oldest = min(f.created_at for f in fails)
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    return oldest + timedelta(minutes=settings.lockout_minutes)


def check_login_lockout(db: Session, username: str, source_ip: str = "0.0.0.0") -> Optional[datetime]:
    """Log and report an active lockout for this ACCOUNT (returns expiry)."""
    expiry = lockout_expiry(db, username)
    if expiry is not None:
        log_security_event(
            db, kind="LOGIN_LOCKOUT", source_ip=source_ip, username=username,
            detail={
                "message": "Account lockout tripped: too many failed sign-ins",
                "threshold": settings.lockout_threshold,
                "window_minutes": settings.lockout_window_minutes,
                "lockout_minutes": settings.lockout_minutes,
                "expires_at": expiry.isoformat(),
            },
        )
    return expiry


# ── Authorization-violation burst detection ────────────────────────────────

def check_violation_burst(db: Session, user_id: int, tenant_id: Optional[int],
                          username: str, source_ip: str = "0.0.0.0") -> bool:
    """Treat a rapid burst of authorization violations (endpoints outside the
    caller's role/scope) as a possible account-scanning attempt. Returns True
    when this call confirmed a burst."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.violation_burst_minutes)
    recent = (db.query(SecurityEvent)
              .filter(SecurityEvent.kind == "SCOPE_VIOLATION",
                      SecurityEvent.user_id == user_id,
                      SecurityEvent.created_at >= cutoff)
              .count())
    if recent >= settings.violation_burst_threshold:
        log_security_event(
            db, kind="VIOLATION_BURST", source_ip=source_ip, username=username,
            user_id=user_id, tenant_id=tenant_id,
            detail={
                "message": "Repeated authorization violations — possible account scan",
                "violations_in_window": recent,
                "window_minutes": settings.violation_burst_minutes,
            },
        )
        return True
    return False
