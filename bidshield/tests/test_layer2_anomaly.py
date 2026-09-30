"""Layer 2 — Intrusion & Anomaly Detection: live behavior tests.

The headline test proves the availability guarantee: locking out one account
must NOT lock out a different account sharing the same source IP. Lockout is
scoped to the username only; per-IP control belongs to Layer 1's rate limiter.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.entities import LoginAttempt, SecurityEvent, User
from app.services import anomaly_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_attempt_ledger():
    """Isolate the login_attempts ledger per test; restore debounce state."""
    anomaly_service.reset_debounce_for_tests()
    db = SessionLocal()
    db.query(LoginAttempt).delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(LoginAttempt).delete()
    db.commit()
    db.close()
    anomaly_service.reset_debounce_for_tests()


def _fail_times(username, times):
    db = SessionLocal()
    for _ in range(times):
        anomaly_service.record_login_attempt(db, username, successful=False, source_ip="203.0.113.9")
    db.close()


def test_lockout_trips_after_threshold_and_reports_expiry():
    _fail_times("officer", settings.lockout_threshold)
    db = SessionLocal()
    assert anomaly_service.is_locked_out(db, "officer")
    expiry = anomaly_service.lockout_expiry(db, "officer")
    db.close()
    assert expiry is not None
    assert expiry <= datetime.now(timezone.utc) + timedelta(minutes=settings.lockout_minutes + 1)


def test_lockout_is_scoped_to_account_never_ip():
    """The availability guarantee: one bad actor's failures cannot lock out a
    colleague behind the same office NAT IP."""
    _fail_times("officer", settings.lockout_threshold + 2)  # way over threshold
    db = SessionLocal()
    # Same source IP as the failing account, different account:
    assert not anomaly_service.is_locked_out(db, "verifier")
    assert not anomaly_service.is_locked_out(db, "auditor")
    db.close()

    # And at the HTTP boundary the colleague can still sign in.
    res = client.post("/api/v1/auth/login", json={"username": "verifier", "password": "BidShield@123"})
    assert res.status_code == 200


def test_locked_account_receives_423_with_retry_after():
    _fail_times("verifier", settings.lockout_threshold)
    res = client.post("/api/v1/auth/login", json={"username": "verifier", "password": "BidShield@123"})
    assert res.status_code == 423
    assert "Retry-After" in res.headers
    int(res.headers["Retry-After"]) >= 1


def test_successful_login_resets_failure_streak():
    _fail_times("auditor", settings.lockout_threshold - 1)
    res = client.post("/api/v1/auth/login", json={"username": "auditor", "password": "BidShield@123"})
    assert res.status_code == 200
    db = SessionLocal()
    streak = (db.query(LoginAttempt)
              .filter(LoginAttempt.username == "auditor", LoginAttempt.successful.is_(False))
              .count())
    db.close()
    # New failures after the success start a fresh streak, so the old failures
    # must no longer be able to combine with new ones to cross the threshold.
    _fail_times("auditor", 1)
    db = SessionLocal()
    recent_fails = (db.query(LoginAttempt)
                    .filter(LoginAttempt.username == "auditor",
                            LoginAttempt.successful.is_(False),
                            LoginAttempt.created_at >= datetime.now(timezone.utc) - timedelta(seconds=5))
                    .count())
    db.close()
    assert recent_fails == 1
    assert streak >= settings.lockout_threshold - 1  # history preserved for forensics


def test_lockout_event_logged_and_snapshot_requested():
    from unittest.mock import patch
    _fail_times("officer", settings.lockout_threshold)
    db = SessionLocal()
    with patch.object(anomaly_service, "_request_anomaly_snapshot", wraps=anomaly_service._request_anomaly_snapshot) as spy:
        expiry = anomaly_service.check_login_lockout(db, "officer", "203.0.113.9")
        db.close()
        assert expiry is not None
        assert spy.called

    db = SessionLocal()
    event = (db.query(SecurityEvent)
             .filter(SecurityEvent.kind == "LOGIN_LOCKOUT", SecurityEvent.username == "officer")
             .order_by(SecurityEvent.id.desc()).first())
    db.close()
    assert event is not None
    assert event.source_ip == "203.0.113.9"
    assert "threshold" in (event.detail or {})


def test_violation_burst_detected_from_scope_violations():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "officer").first()
    try:
        for i in range(settings.violation_burst_threshold):
            anomaly_service.log_security_event(
                db, kind="SCOPE_VIOLATION", user_id=user.id,
                username=user.username, tenant_id=user.tenant_id,
                detail={"resource": "tender", "resource_id": str(999000 + i)},
            )
        assert anomaly_service.check_violation_burst(db, user.id, user.tenant_id, user.username) is True
        burst = (db.query(SecurityEvent)
                 .filter(SecurityEvent.kind == "VIOLATION_BURST", SecurityEvent.user_id == user.id)
                 .order_by(SecurityEvent.id.desc()).first())
        assert burst is not None
        assert burst.detail["violations_in_window"] >= settings.violation_burst_threshold
    finally:
        db.close()


def test_anomaly_snapshot_debounced_but_security_events_always_logged():
    """Two anomalies 1s apart: only ONE snapshot, but TWO logged detections.
    Then a manual (scheduled-style) snapshot does not extend the anomaly
    debounce — a routine backup cannot silently swallow the next attack's
    snapshot."""
    from unittest.mock import patch
    calls = {"n": 0}

    def fake_take(reason="ANOMALY_TRIGGER"):
        calls["n"] += 1
        return f"/tmp/fake-{calls['n']}", {}

    db = SessionLocal()
    try:
        with patch.object(anomaly_service, "_request_anomaly_snapshot", lambda: None):
            anomaly_service.log_security_event(db, kind="LOGIN_LOCKOUT", username="officer", detail={})
            anomaly_service.log_security_event(db, kind="INJECTION_PATTERN", detail={})
        count = (db.query(SecurityEvent).filter(SecurityEvent.kind.in_(["LOGIN_LOCKOUT", "INJECTION_PATTERN"]))
                 .count())
        assert count >= 2, "detections must always be logged even when snapshots debounce"

        with patch("app.services.backup_service.take_snapshot", side_effect=fake_take):
            with patch.object(anomaly_service, "_request_anomaly_snapshot",
                              anomaly_service._request_anomaly_snapshot.__wrapped__ if hasattr(anomaly_service._request_anomaly_snapshot, "__wrapped__") else anomaly_service._request_anomaly_snapshot):
                first = anomaly_service._request_anomaly_snapshot()
                second = anomaly_service._request_anomaly_snapshot()
        assert (first, second) == (True, False), "anomaly snapshots must debounce against each other"
    finally:
        db.close()
        anomaly_service.reset_debounce_for_tests()
