import hashlib
import hmac
import re
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

# ── Layer 3 — Password hashing (memory-hard scrypt) ────────────────────────
# Format: scrypt$N$r$p$salt_hex$key_hex. Old PBKDF2 hashes ("salt_hex$key_hex")
# verify on sight and are transparently re-hashed at next successful login so
# the demo database keeps working without a reset.
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1

# A fixed dummy scrypt hash: verify_password compares against it when the
# username does not exist, so response timing does not leak account existence.
DUMMY_HASH = "scrypt$16384$8$1$" + secrets.token_hex(16) + "$" + secrets.token_hex(64)


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt_bytes = secrets.token_bytes(16)
    key = hashlib_scrypt(password, salt_bytes)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt_bytes.hex()}${key.hex()}"


def hashlib_scrypt(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt,
                          n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=64)


def _is_legacy_pbkdf2(stored_hash: str) -> bool:
    return "$" in stored_hash and not stored_hash.startswith("scrypt$")


def verify_password(plain_password: str, stored_hash: str) -> bool:
    try:
        if stored_hash.startswith("scrypt$"):
            _scheme, n_s, r_s, p_s, salt_hex, key_hex = stored_hash.split("$", 5)
            expected_key = bytes.fromhex(key_hex)
            candidate_key = hashlib.scrypt(
                plain_password.encode("utf-8"),
                salt=bytes.fromhex(salt_hex),
                n=int(n_s), r=int(r_s), p=int(p_s),
                dklen=len(expected_key),
            )
            return hmac.compare_digest(candidate_key, expected_key)
        if _is_legacy_pbkdf2(stored_hash):
            salt, key_hex = stored_hash.split("$", 1)
            expected_key = bytes.fromhex(key_hex)
            candidate_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"),
                                                salt.encode("utf-8"), 100000)
            return hmac.compare_digest(candidate_key, expected_key)
        return False
    except Exception:
        return False


def needs_rehash(stored_hash: str) -> bool:
    """True when the stored hash predates the current scrypt parameters."""
    return not stored_hash.startswith(f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}$")


# ── Layer 3 — Server-side password policy ─────────────────────────────────
PASSWORD_POLICY_MESSAGE = (
    "Password must be at least 10 characters and contain an uppercase letter, "
    "a lowercase letter, and a digit"
)


def validate_password_policy(password: str) -> List[str]:
    problems: List[str] = []
    if len(password or "") < settings.password_min_length:
        problems.append(f"at least {settings.password_min_length} characters")
    if not re.search(r"[A-Z]", password or ""):
        problems.append("an uppercase letter")
    if not re.search(r"[a-z]", password or ""):
        problems.append("a lowercase letter")
    if not re.search(r"[0-9]", password or ""):
        problems.append("a digit")
    return problems


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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication credentials required")
    payload = decode_access_token(creds.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    # Role, tenant, and active status are re-derived from the database on EVERY
    # request — never trusted from JWT claims — so deactivation is instant:
    # a disabled account loses access on its very next request.
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is unavailable")
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
