from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import AuditLog
from app.schemas.schemas import AuditLogOut
from app.core.security import get_current_user, require_roles, AuthenticatedUser
from app.services.audit_service import verify_tenant_chain

router = APIRouter(prefix="/audit", tags=["Audit Trail"])

@router.get("", response_model=List[AuditLogOut])
def get_audit_logs(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    query = db.query(AuditLog).filter(AuditLog.tenant_id == user.tenant_id)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type.upper())

    return query.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()

@router.get("/integrity")
def get_audit_integrity(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles("AUDITOR")),
):
    return verify_tenant_chain(db, user.tenant_id)
