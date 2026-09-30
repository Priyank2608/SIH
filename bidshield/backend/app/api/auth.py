import base64
import binascii
import re
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request, status
from PIL import Image
from io import BytesIO
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import User, Tenant
from app.schemas.schemas import LoginRequest, TokenResponse, UserOut
from app.core.security import (
    verify_password, create_access_token, get_current_user, AuthenticatedUser,
    hash_password, needs_rehash, DUMMY_HASH, validate_password_policy,
    PASSWORD_POLICY_MESSAGE,
)
from app.services.audit_service import log_audit_event
from app.services import anomaly_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


def datetime_now():
    return datetime.now(timezone.utc)

class SignatureUpdate(BaseModel):
    signature_data: str = Field(min_length=40, max_length=700000)

@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    user = db.query(User).filter(User.id == current_user.id, User.tenant_id == current_user.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "organization": tenant.name if tenant else None,
        "is_active": user.is_active,
    }

@router.get("/signature")
def get_signature(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    record = db.query(User).filter(User.id == user.id, User.tenant_id == user.tenant_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="User not found")
    return {"signature_data": record.signature_data}

@router.put("/signature")
def save_signature(
    payload: SignatureUpdate,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
):
    match = re.fullmatch(r"data:image/png;base64,([A-Za-z0-9+/]+={0,2})", payload.signature_data)
    if not match:
        raise HTTPException(status_code=422, detail="Signature must be a PNG image")
    try:
        image_bytes = base64.b64decode(match.group(1), validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="Invalid signature image")
    if len(image_bytes) > 512_000 or not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=422, detail="Invalid or oversized signature image")
    try:
        image = Image.open(BytesIO(image_bytes))
        if image.format != "PNG" or image.width < 300 or image.height < 60 or image.width > 2000 or image.height > 1000:
            raise ValueError("Unexpected signature image dimensions")
        image.verify()
        image = Image.open(BytesIO(image_bytes))
        alpha = image.convert("RGBA").getchannel("A")
        if alpha.getbbox() is None:
            raise ValueError("Empty signature image")
    except Exception:
        raise HTTPException(status_code=422, detail="Signature image must be a valid, non-empty PNG")
    record = db.query(User).filter(User.id == user.id, User.tenant_id == user.tenant_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="User not found")
    record.signature_data = payload.signature_data
    db.commit()
    log_audit_event(db, action="OFFICER_SIGNATURE_UPDATED", entity_type="USER", entity_id=str(user.id),
                    user_id=user.id, username=user.username, tenant_id=user.tenant_id,
                    details={"signature_saved": True})
    return {"saved": True}

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    source_ip = request.client.host if request.client else "0.0.0.0"

    # Layer 2 — account-scoped lockout (username ONLY, never IP). Office NAT,
    # corporate VPNs, and factory networks share one outbound IP, so an IP-wide
    # lockout would let one bad password deny service to everyone behind that
    # gateway. Per-IP rapid-fire limiting is Layer 1's plain rate limiter.
    expiry = anomaly_service.check_login_lockout(db, req.username, source_ip)
    if expiry is not None:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked after repeated failed sign-ins. Try again later.",
            headers={"Retry-After": str(max(1, int((expiry - datetime_now()).total_seconds())) + 1)},
        )

    # Layer 3 — timing defense: unknown usernames still run a full scrypt
    # comparison against a fixed dummy hash so response time does not reveal
    # whether the account exists.
    user = db.query(User).filter(User.username == req.username).first()
    stored_hash = user.hashed_password if user else DUMMY_HASH
    password_ok = verify_password(req.password, stored_hash)

    if not user or not password_ok:
        anomaly_service.record_login_attempt(db, req.username, successful=False, source_ip=source_ip)
        log_audit_event(
            db,
            action="LOGIN_FAILURE",
            entity_type="USER",
            entity_id=req.username,
            username=req.username,
            ip_address=source_ip,
            details={"reason": "Invalid credentials provided"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive. Contact Administrator."
        )

    # Transparent hash upgrade: PBKDF2-era demo accounts migrate to scrypt on
    # their next successful login.
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(req.password)
        db.commit()

    anomaly_service.record_login_attempt(db, req.username, successful=True, source_ip=source_ip)

    token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "tenant_id": user.tenant_id
    })

    log_audit_event(
        db,
        action="LOGIN_SUCCESS",
        entity_type="USER",
        entity_id=str(user.id),
        user_id=user.id,
        username=user.username,
        tenant_id=user.tenant_id,
        details={"role": user.role}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "tenant_id": user.tenant_id
        }
    }

