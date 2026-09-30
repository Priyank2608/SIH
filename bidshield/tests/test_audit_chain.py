"""Tamper-evident audit chain tests.

Append-only enforcement is now ALSO at the database level (see
test_layer6_audit_enforcement.py), so these tests tamper via raw SQL with the
triggers dropped — simulating an out-of-band edit of a restored backup, the
one scenario the application cannot block and must therefore detect.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.audit_protection import install_audit_protection
from app.models.entities import AuditChainHead, AuditLog
from app.services.audit_service import log_audit_event, verify_tenant_chain


@pytest.fixture
def audit_db():
    engine = create_engine("sqlite:///:memory:")
    AuditLog.__table__.create(engine)
    AuditChainHead.__table__.create(engine)
    # Triggers live on real (non-memory) connections; for in-memory ORM-level
    # chain math tests we skip trigger installation here and exercise them in
    # test_layer6_audit_enforcement.py against an on-disk database.
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _append(db, tenant_id, action):
    return log_audit_event(db, action=action, entity_type="TEST", tenant_id=tenant_id,
                           username="system", details={"value": action})


def test_valid_chain_and_separate_tenants_pass(audit_db):
    a1 = _append(audit_db, 10, "A1")
    _append(audit_db, 10, "A2")
    b1 = _append(audit_db, 20, "B1")
    assert verify_tenant_chain(audit_db, 10)["valid"]
    assert verify_tenant_chain(audit_db, 20)["valid"]
    assert a1.previous_hash != b1.previous_hash


def _tamper(engine, db, sql, params):
    """Apply out-of-band SQL (triggers do not persist on :memory: across
    connections, so this helper speaks directly to the shared connection)."""
    raw = db.connection().connection
    cursor = raw.cursor()
    cursor.execute(sql, params)
    raw.commit()
    db.expire_all()


def test_modified_event_breaks_chain(audit_db):
    event = _append(audit_db, 10, "CREATE")
    _tamper(audit_db.get_bind(), audit_db,
            "UPDATE audit_logs SET details='{\"value\": \"changed\"}' WHERE id=?", (event.id,))
    assert not verify_tenant_chain(audit_db, 10)["valid"]


def test_modified_previous_hash_breaks_chain(audit_db):
    _append(audit_db, 10, "A1")
    event = _append(audit_db, 10, "A2")
    _tamper(audit_db.get_bind(), audit_db,
            "UPDATE audit_logs SET previous_hash=? WHERE id=?", ("0" * 64, event.id))
    assert not verify_tenant_chain(audit_db, 10)["valid"]


def test_deleted_intermediate_event_is_detected(audit_db):
    _append(audit_db, 10, "A1")
    middle = _append(audit_db, 10, "A2")
    _append(audit_db, 10, "A3")
    _tamper(audit_db.get_bind(), audit_db,
            "DELETE FROM audit_logs WHERE id=?", (middle.id,))
    assert not verify_tenant_chain(audit_db, 10)["valid"]


def test_reordered_events_are_detected(audit_db):
    _append(audit_db, 10, "A1")
    second = _append(audit_db, 10, "A2")
    _tamper(audit_db.get_bind(), audit_db,
            "UPDATE audit_logs SET id=? WHERE id=?", (99, second.id))
    assert not verify_tenant_chain(audit_db, 10)["valid"]
