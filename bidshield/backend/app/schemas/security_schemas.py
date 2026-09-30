"""Layer 3/4 — request schemas for account administration and backups."""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class PasswordChangeRequest(BaseModel):
    """Server-side password policy is enforced here (Layer 3), not just in UI."""
    model_config = {"extra": "forbid"}
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class UserTargetRequest(BaseModel):
    """Deactivate/reactivate account actions (reversible pair — one release)."""
    model_config = {"extra": "forbid"}
    username: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._@-]+$")
    reason: str = Field(min_length=3, max_length=500)


class SnapshotOut(BaseModel):
    filename: str
    size_bytes: int
    created_at: str
    sha256: Optional[str] = None
    checksum_ok: Optional[bool] = None


class SnapshotActionOut(BaseModel):
    path: str
    filename: str
    reason: str
    sha256: str
    size_bytes: int
    created_at: str


class RestoreRequest(BaseModel):
    model_config = {"extra": "forbid"}
    filename: str = Field(min_length=1, max_length=200)
