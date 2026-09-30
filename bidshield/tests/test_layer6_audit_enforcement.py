"""Layer 6 — Audit & Compliance Logging: live behavior tests.

Proves the audit ledger is append-only AT THE DATABASE LEVEL: the normal
seal-once UPDATE (NULL -> hash) is the only modification ever permitted;
sealed rows are immutable and nothing can be deleted. Verification routine
detects and locates tampering that predates the triggers (e.g. a forged
backup restored over the live DB).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.audit_protection import install_audit_protection
from app.models.entities import AuditChainHead, AuditLog
from app.services.audit_service import log_audit_event, verify_tenant_chain


@pytest.fixture
def audit_engine(tmp_path):
    """Real on-disk SQLite (tmp dir) so triggers behave exactly as in
    production; tmp_path teardown avoids Windows file-lock issues."""
    path = tmp_path / "layer6-audit-test.db"
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    AuditLog.__table__.create(engine)
    AuditChainHead.__table__.create(engine)
    install_audit_protection(engine)
    yield engine
    engine.dispose()


def _session(engine):
    return sessionmaker(bind=engine)()


def test_seal_once_update_allowed_then_row_is_immutable(audit_engine):
    """The one legitimate UPDATE (NULL -> hash seal) must succeed; a second
    modification of the now-sealed row must be rejected BY THE DATABASE."""
    db = _session(audit_engine)
    event = log_audit_event(db, action="SEAL-PROBE", entity_type="TEST", tenant_id=99)
    assert event.current_hash  # sealed by the service
    sealed_hash = event.current_hash
    event_id = event.id
    db.close()

    # Any further UPDATE on the sealed row is blocked:
    db = _session(audit_engine)
    row = db.query(AuditLog).filter(AuditLog.id == event_id).first()
    row.action = "REWRITTEN"
    with pytest.raises((DBAPIError, IntegrityError), match="append-only"):
        db.commit()
    db.rollback()
    db.close()

    db = _session(audit_engine)
    stored = db.query(AuditLog).filter(AuditLog.id == event_id).first()
    assert stored.action == "SEAL-PROBE", "sealed row must be unchanged"
    assert stored.current_hash == sealed_hash
    db.close()


def test_deletes_are_blocked_by_database_trigger(audit_engine):
    db = _session(audit_engine)
    event = log_audit_event(db, action="DELETE-PROBE", entity_type="TEST", tenant_id=99)
    db.close()

    raw = audit_engine.raw_connection()
    cursor = raw.cursor()
    with pytest.raises(Exception, match="append-only"):
        cursor.execute("DELETE FROM audit_logs WHERE id=?", (event.id,))
    raw.rollback()
    raw.close()

    db = _session(audit_engine)
    assert db.query(AuditLog).filter(AuditLog.id == event.id).first() is not None
    db.close()


def test_orm_delete_is_also_blocked(audit_engine):
    db = _session(audit_engine)
    event = log_audit_event(db, action="ORM-DELETE-PROBE", entity_type="TEST", tenant_id=99)
    db.commit()
    db.delete(event)
    with pytest.raises((DBAPIError, IntegrityError)):
        db.commit()
    db.rollback()
    db.close()


def test_chain_verification_walks_and_reports_intact(audit_engine):
    db = _session(audit_engine)
    for i in range(5):
        log_audit_event(db, action=f"EV-{i}", entity_type="TEST", tenant_id=77)
    report = verify_tenant_chain(db, 77)
    db.close()
    assert report["valid"] is True
    assert report["checked_events"] == 5
    assert report["issues"] == []


def test_chain_verification_locates_tampering(audit_engine):
    """Simulate an out-of-band edit that predates trigger protection (a
    forged backup restored over the live DB): drop triggers, edit, reinstall.
    Verification must catch it and say WHERE the chain broke."""
    db = _session(audit_engine)
    log_audit_event(db, action="EV-1", entity_type="TEST", tenant_id=66)
    middle = log_audit_event(db, action="EV-2", entity_type="TEST", tenant_id=66)
    log_audit_event(db, action="EV-3", entity_type="TEST", tenant_id=66)
    middle_id = middle.id
    db.close()

    raw = audit_engine.raw_connection()
    cursor = raw.cursor()
    cursor.execute("DROP TRIGGER audit_logs_no_update")
    cursor.execute("UPDATE audit_logs SET details='{\"forged\": true}' WHERE id=?", (middle_id,))
    raw.commit()
    install_audit_protection(audit_engine)  # restore protections
    raw.close()

    db = _session(audit_engine)
    report = verify_tenant_chain(db, 66)
    db.close()
    assert report["valid"] is False
    assert report["issues"], "verification must say WHERE the chain broke"
    assert any(i["event_id"] == middle_id for i in report["issues"])


def test_chain_head_mismatch_is_detected(audit_engine):
    db = _session(audit_engine)
    log_audit_event(db, action="EV-A", entity_type="TEST", tenant_id=55)
    log_audit_event(db, action="EV-B", entity_type="TEST", tenant_id=55)
    db.close()

    raw = audit_engine.raw_connection()
    cursor = raw.cursor()
    cursor.execute("DROP TRIGGER audit_logs_no_update")
    cursor.execute("UPDATE audit_chain_heads SET last_hash=?", ("f" * 64,))
    raw.commit()
    install_audit_protection(audit_engine)
    raw.close()

    db = _session(audit_engine)
    report = verify_tenant_chain(db, 55)
    db.close()
    assert report["valid"] is False
    assert any(i["problem"] == "CHAIN_HEAD_MISMATCH" for i in report["issues"])


def test_production_audit_logs_table_has_triggers_installed():
    """The app database itself (not just the fixture) must be protected."""
    from app.db.session import engine
    install_audit_protection(engine)
    if engine.dialect.name != "sqlite":
        pytest.skip("trigger listing is SQLite-specific")
    raw = engine.raw_connection()
    cursor = raw.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='audit_logs'")
    names = {row[0] for row in cursor.fetchall()}
    raw.close()
    assert {"audit_logs_no_update", "audit_logs_no_unseal", "audit_logs_no_delete"} <= names
