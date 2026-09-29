import os
import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

class Settings(BaseSettings):
    app_name: str = "BidShield: AI-Powered GeM Bid Compliance Verification Platform"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    
    # Standalone demo SQLite default, easily overridable by BIDSHIELD_DATABASE_URL
    database_url: str = "sqlite:///./storage/bidshield.db"
    
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 120
    
    demo_mode: bool = True
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    storage_dir: str = "./storage"
    
    max_upload_mb: int = 25
    ocr_language: str = "eng"
    ocr_engine: str = "tesseract"
    
    # AI model and rule versions
    rule_engine_version: str = "bidshield-rules-v2.1"
    risk_engine_version: str = "bidshield-risk-v1.8"
    ocr_model_version: str = "bidshield-ocr-v2.0"
    
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BIDSHIELD_", extra="ignore")

    @model_validator(mode="after")
    def validate_security_settings(self):
        if self.jwt_algorithm != "HS256":
            raise ValueError("Only HS256 JWT signing is supported")
        if not self.jwt_secret:
            if not self.demo_mode:
                raise ValueError("BIDSHIELD_JWT_SECRET must be set when demo mode is disabled")
            self.jwt_secret = secrets.token_urlsafe(48)
        if len(self.jwt_secret) < 32:
            raise ValueError("BIDSHIELD_JWT_SECRET must contain at least 32 characters")
        return self

settings = Settings()
os.makedirs(settings.storage_dir, exist_ok=True)
os.makedirs(os.path.join(settings.storage_dir, "generated"), exist_ok=True)
os.makedirs(os.path.join(settings.storage_dir, "reports"), exist_ok=True)
os.makedirs(os.path.join(settings.storage_dir, "uploads"), exist_ok=True)
