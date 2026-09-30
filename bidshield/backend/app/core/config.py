import os
import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

class Settings(BaseSettings):
    app_name: str = "BidShield: AI-Assisted Procurement Compliance Verification Platform"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"

    # Standalone demo SQLite default, easily overridable by BIDSHIELD_DATABASE_URL
    database_url: str = "sqlite:///./storage/bidshield.db"

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 120
    initial_user_password: str = ""
    reset_demo_passwords: bool = False

    demo_mode: bool = True
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    storage_dir: str = "./storage"

    max_upload_mb: int = 25
    ocr_language: str = "eng"
    ocr_engine: str = "tesseract"

    # ── Layer 1 — Perimeter & API Gateway ────────────────────────────────
    gateway_enabled: bool = True
    rate_limit_per_minute: int = 120
    login_rate_limit_per_minute: int = 10
    max_body_bytes: int = 1 * 1024 * 1024          # JSON bodies are hard-capped at 1 MB;
    max_body_bytes_exempt_prefixes: str = ""        # /api/v1/documents/upload etc. use max_upload_mb instead
    docs_enabled: bool = False                      # Swagger/ReDoc/OpenAPI are OFF unless explicitly enabled

    # ── Layer 2 — Intrusion & Anomaly Detection ─────────────────────────
    lockout_threshold: int = 5
    lockout_window_minutes: int = 5
    lockout_minutes: int = 15
    violation_burst_threshold: int = 8
    violation_burst_minutes: int = 10
    anomaly_snapshot_debounce_seconds: int = 60

    # ── Layer 3 — Authentication & Access Control ───────────────────────
    password_min_length: int = 10
    require_dummy_hash_lookup: bool = True

    # ── Layer 4 — Snapshot & Backup Vault ───────────────────────────────
    backup_vault_dir: str = "./storage/backups"
    backup_interval_minutes: int = 180
    backup_enabled: bool = True
    backup_keep_count: int = 20

    # ── Layer 7 — Input Validation ──────────────────────────────────────
    strict_schemas: bool = True

    # Explicit "I know this is insecure" escape hatch. Never set in production.
    insecure_demo_mode: bool = False

    # AI model and rule versions
    rule_engine_version: str = "bidshield-rules-v2.1"
    risk_engine_version: str = "bidshield-risk-v1.8"
    ocr_model_version: str = "bidshield-ocr-v2.0"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="BIDSHIELD_", extra="ignore")

    @model_validator(mode="after")
    def validate_security_settings(self):
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        if self.jwt_algorithm != "HS256":
            raise ValueError("Only HS256 JWT signing is supported")
        if not self.demo_mode and len(self.initial_user_password) < 12:
            raise ValueError("BIDSHIELD_INITIAL_USER_PASSWORD must contain at least 12 characters when demo mode is disabled")
        # Fail closed: refuse to boot without a signing key unless the explicit
        # insecure escape hatch is set (never for production deployments).
        if not self.jwt_secret:
            if not self.demo_mode and not self.insecure_demo_mode:
                raise ValueError("BIDSHIELD_JWT_SECRET must be set when demo mode is disabled")
            self.jwt_secret = secrets.token_urlsafe(48)
        if len(self.jwt_secret) < 32:
            raise ValueError("BIDSHIELD_JWT_SECRET must contain at least 32 characters")
        if self.rate_limit_per_minute < 1 or self.login_rate_limit_per_minute < 1:
            raise ValueError("Rate limits must be positive integers")
        if self.max_body_bytes < 1024:
            raise ValueError("BIDSHIELD_MAX_BODY_BYTES must be at least 1024")
        if self.lockout_threshold < 1 or self.lockout_minutes < 1:
            raise ValueError("Lockout settings must be positive")
        return self

settings = Settings()
os.makedirs(settings.storage_dir, exist_ok=True)
os.makedirs(os.path.join(settings.storage_dir, "generated"), exist_ok=True)
os.makedirs(os.path.join(settings.storage_dir, "reports"), exist_ok=True)
os.makedirs(os.path.join(settings.storage_dir, "uploads"), exist_ok=True)
os.makedirs(settings.backup_vault_dir, exist_ok=True)
