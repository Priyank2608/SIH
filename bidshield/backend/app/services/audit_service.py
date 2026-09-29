"""Append-only event writes and per-tenant tamper-evident chain verification."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.entities import AuditChainHead, AuditLog, User


def genesis_hash(tenant_id: int) -> str:
    return hashlib.sha256(f"BIDSHIELD_AUDIT_GENESIS_V1:{tenant_id}".encode("utf-8")).hexdigest()


def canonical_event(event: AuditLog, previous_hash: str) -> bytes:
    created_at = event.created_at
    if created_at is not None:
        # SQLite drops timezone metadata on round trips. Treat stored naive
        # timestamps as UTC so append and verification serialize identically.
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_at = created_at.astimezone(timezone.utc)
    payload = {
        "id": event.id,
        "tenant_id": event.tenant_id,
        "user_id": event.user_id,
        "username": event.username,
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "ip_address": event.ip_address,
        "details": event.details or {},
        "created_at": created_at.isoformat() if created_at else None,
        "previous_hash": previous_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def calculate_event_hash(event: AuditLog, previous_hash: str) -> str:
    return hashlib.sha256(canonical_event(event, previous_hash)).hexdigest()


def log_audit_event(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    user_id: Optional[int] = None,
    username: str = "system",
    tenant_id: Optional[int] = None,
    ip_address: str = "127.0.0.1",
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    if tenant_id is None:
        actor = db.query(User).filter(User.id == user_id).first() if user_id else None
        if actor is None and username != "system":
            actor = db.query(User).filter(User.username == username).first()
        tenant_id = actor.tenant_id if actor else 1
    # Lock the tenant head while appending so concurrent requests cannot fork a chain.
    head = (db.query(AuditChainHead).filter(AuditChainHead.tenant_id == tenant_id)
            .with_for_update().first())
    if head is None:
        head = AuditChainHead(tenant_id=tenant_id, last_event_id=None, last_hash=genesis_hash(tenant_id))
        db.add(head)
        db.flush()

    previous_hash = head.last_hash
    event = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        username=username,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        ip_address=ip_address,
        details=details or {},
        created_at=datetime.now(timezone.utc),
        previous_hash=previous_hash,
    )
    db.add(event)
    db.flush()
    event.current_hash = calculate_event_hash(event, previous_hash)
    head.last_event_id = event.id
    head.last_hash = event.current_hash
    head.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(event)
    return event


def verify_tenant_chain(db: Session, tenant_id: int) -> Dict[str, Any]:
    events = (db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id)
              .order_by(AuditLog.id.asc()).all())
    expected_previous = genesis_hash(tenant_id)
    issues = []
    for event in events:
        if event.previous_hash != expected_previous:
            issues.append({"event_id": event.id, "problem": "PREVIOUS_HASH_MISMATCH"})
        computed = calculate_event_hash(event, event.previous_hash or "")
        if not event.current_hash or computed != event.current_hash:
            issues.append({"event_id": event.id, "problem": "CURRENT_HASH_MISMATCH"})
        expected_previous = event.current_hash or ""

    head = db.query(AuditChainHead).filter(AuditChainHead.tenant_id == tenant_id).first()
    if events:
        if not head or head.last_event_id != events[-1].id or head.last_hash != events[-1].current_hash:
            issues.append({"event_id": events[-1].id, "problem": "CHAIN_HEAD_MISMATCH"})
    elif head and head.last_event_id is not None:
        issues.append({"event_id": head.last_event_id, "problem": "CHAIN_TAIL_MISSING"})

    return {"tenant_id": tenant_id, "valid": not issues, "checked_events": len(events),
            "head_hash": head.last_hash if head else genesis_hash(tenant_id), "issues": issues}
