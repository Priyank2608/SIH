import base64
import binascii
import re
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from PIL import Image
from io import BytesIO
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import User, Tenant
from app.schemas.schemas import LoginRequest, TokenResponse, UserOut
from app.core.security import verify_password, create_access_token, get_current_user, AuthenticatedUser
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication"])

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
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.hashed_password):
        log_audit_event(
            db,
            action="LOGIN_FAILURE",
            entity_type="USER",
            entity_id=req.username,
            username=req.username,
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

