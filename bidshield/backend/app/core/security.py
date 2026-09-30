import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import User
from sqlalchemy.orm import Session

security_bearer = HTTPBearer(auto_error=False)

def hash_password(password: str, salt: Optional[str] = None) -> str:
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${key.hex()}"

def verify_password(plain_password: str, stored_hash: str) -> bool:
    try:
        salt, key_hex = stored_hash.split("$", 1)
        expected_key = bytes.fromhex(key_hex)
        candidate_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return hmac.compare_digest(candidate_key, expected_key)
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_minutes))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization token.")

class AuthenticatedUser:
    def __init__(self, id: int, username: str, full_name: str, role: str, tenant_id: int):
        self.id = id
        self.username = username
        self.full_name = full_name
        self.role = role
        self.tenant_id = tenant_id

async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    if not creds:
        # In demo mode, provide standard authorized procurement officer if token absent, or require login
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication credentials required")
    payload = decode_access_token(creds.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is unavailable")
    # Roles and tenant membership are read from the database, never trusted from JWT claims.
    return AuthenticatedUser(user.id, user.username, user.full_name, user.role, user.tenant_id)

def require_roles(*allowed_roles: str):
    """Strict role gate: authorization is granted only to the listed roles.

    NOTE: There is intentionally NO implicit SUPER_ADMIN bypass. Administration
    authority does not confer procurement decision authority (or any other
    operational role) unless the role is explicitly listed by the endpoint.
    """
    def role_checker(user: AuthenticatedUser = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient operational permissions")
        return user
    return role_checker
