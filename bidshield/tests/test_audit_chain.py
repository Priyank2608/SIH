import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.entities import AuditChainHead, AuditLog
from app.services.audit_service import log_audit_event, verify_tenant_chain


@pytest.fixture
def audit_db():
    engine = create_engine("sqlite:///:memory:")
    AuditLog.__table__.create(engine)
    AuditChainHead.__table__.create(engine)
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


def test_modified_event_breaks_chain(audit_db):
    event = _append(audit_db, 10, "CREATE")
    event.details = {"value": "changed"}
    audit_db.commit()
    assert not verify_tenant_chain(audit_db, 10)["valid"]


def test_modified_previous_hash_breaks_chain(audit_db):
    _append(audit_db, 10, "A1")
    event = _append(audit_db, 10, "A2")
    event.previous_hash = "0" * 64
    audit_db.commit()
    assert not verify_tenant_chain(audit_db, 10)["valid"]


def test_deleted_intermediate_event_is_detected(audit_db):
    _append(audit_db, 10, "A1")
    middle = _append(audit_db, 10, "A2")
    _append(audit_db, 10, "A3")
    audit_db.delete(middle)
    audit_db.commit()
    assert not verify_tenant_chain(audit_db, 10)["valid"]


def test_reordered_events_are_detected(audit_db):
    first = _append(audit_db, 10, "A1")
    second = _append(audit_db, 10, "A2")
    first.id = 99
    audit_db.flush()
    second.id = 1
    audit_db.flush()
    first.id = 2
    audit_db.commit()
    assert not verify_tenant_chain(audit_db, 10)["valid"]
