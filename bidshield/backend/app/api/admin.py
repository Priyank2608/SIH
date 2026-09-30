"""Layer 3 + Layer 4 — account administration and backup vault endpoints.

Deactivate and reactivate ship together: a one-way disable is an operational
trap. Both directions are audit-logged, and the deactivated account loses
access on its very next request because roles/active status are re-derived
from the database per request (see core/security.get_current_user).
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    AuthenticatedUser, get_current_user, hash_password, needs_rehash,
    validate_password_policy, verify_password, PASSWORD_POLICY_MESSAGE,
)
from app.db.session import get_db
from app.models.entities import User
from app.schemas.security_schemas import (
    PasswordChangeRequest, RestoreRequest, SnapshotActionOut, SnapshotOut,
    UserTargetRequest,
)
from app.services import backup_service
from app.services.anomaly_service import check_violation_burst, log_security_event
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/admin", tags=["Administration"])
logger = logging.getLogger("bidshield.admin")


def _require_super_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Insufficient operational permissions")
    return user


@router.post("/users/deactivate")
def deactivate_user(
    payload: UserTargetRequest,
    db: Session = Depends(get_db),
    admin: AuthenticatedUser = Depends(_require_super_admin),
):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if not user.is_active:
        raise HTTPException(status_code=409, detail="User is already deactivated")
    user.is_active = False
    db.commit()
    log_audit_event(db, action="USER_DEACTIVATED", entity_type="USER", entity_id=str(user.id),
                    user_id=admin.id, username=admin.username, tenant_id=admin.tenant_id,
                    details={"target": user.username, "reason": payload.reason})
    return {"username": user.username, "is_active": False,
            "message": "Account deactivated. Access ends on the account's next request. Reactivate with /admin/users/reactivate."}


@router.post("/users/reactivate")
def reactivate_user(
    payload: UserTargetRequest,
    db: Session = Depends(get_db),
    admin: AuthenticatedUser = Depends(_require_super_admin),
):
    """Reversible counterpart to deactivate — ships in the same release."""
    user = db.query(User).filter(User.username == payload.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_active:
        raise HTTPException(status_code=409, detail="User is already active")
    user.is_active = True
    db.commit()
    log_audit_event(db, action="USER_REACTIVATED", entity_type="USER", entity_id=str(user.id),
                    user_id=admin.id, username=admin.username, tenant_id=admin.tenant_id,
                    details={"target": user.username, "reason": payload.reason})
    return {"username": user.username, "is_active": True, "message": "Account reactivated."}


@router.post("/password")
def change_own_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    record = db.query(User).filter(User.id == user.id).first()
    if not record or not verify_password(payload.current_password, record.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    problems = validate_password_policy(payload.new_password)
    if problems:
        raise HTTPException(status_code=422, detail=f"Password policy not met: requires {', '.join(problems)}")
    record.hashed_password = hash_password(payload.new_password)
    db.commit()
    log_audit_event(db, action="PASSWORD_CHANGED", entity_type="USER", entity_id=str(user.id),
                    user_id=user.id, username=user.username, tenant_id=user.tenant_id,
                    details={"self_service": True})
    return {"changed": True}


# ── Layer 4 — backup vault endpoints ────────────────────────────────────────

@router.get("/backups", response_model=List[SnapshotOut])
def list_backups(
    db: Session = Depends(get_db),
    admin: AuthenticatedUser = Depends(_require_super_admin),
):
    return backup_service.list_snapshots(verify=True)


@router.post("/backups", response_model=SnapshotActionOut)
def create_backup(
    db: Session = Depends(get_db),
    admin: AuthenticatedUser = Depends(_require_super_admin),
):
    path, meta = backup_service.take_snapshot(reason="MANUAL")
    log_audit_event(db, action="BACKUP_CREATED", entity_type="BACKUP", entity_id=meta["filename"],
                    user_id=admin.id, username=admin.username, tenant_id=admin.tenant_id,
                    details={"sha256": meta["sha256"], "reason": "MANUAL"})
    return meta


@router.post("/backups/restore")
def restore_backup(
    payload: RestoreRequest,
    db: Session = Depends(get_db),
    admin: AuthenticatedUser = Depends(_require_super_admin),
):
    try:
        path = backup_service.restore_snapshot(payload.filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Snapshot not found in vault")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    log_audit_event(db, action="BACKUP_RESTORED", entity_type="BACKUP", entity_id=payload.filename,
                    user_id=admin.id, username=admin.username, tenant_id=admin.tenant_id,
                    details={"sha256_verified": True})
    return {"restored": payload.filename, "path": path}


@router.get("/security-events")
def list_security_events(
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: AuthenticatedUser = Depends(_require_super_admin),
):
    """Queryable Layer 2 detection log (kind, timestamp, source IP, detail)."""
    from app.models.entities import SecurityEvent
    rows = (db.query(SecurityEvent)
            .order_by(SecurityEvent.id.desc())
            .limit(max(1, min(limit, 500)))
            .all())
    return [
        {
            "id": e.id, "kind": e.kind, "source_ip": e.source_ip,
            "username": e.username, "detail": e.detail or {},
            "created_at": e.created_at,
        }
        for e in rows
    ]
