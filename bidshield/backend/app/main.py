from fastapi import FastAPI, Request, status
from fastapi import Depends
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.security import get_current_user
from app.core.gateway import GatewayMiddleware
import app.models.entities # Register all models

# ── Layer 1 — interactive API docs are OFF unless explicitly enabled ────────
docs_enabled = settings.demo_mode and settings.docs_enabled
openapi_url = f"{settings.api_prefix}/openapi.json" if docs_enabled else None
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="BidShield — AI-Assisted Procurement Compliance Platform. Internal procurement-authority verification workspace.",
    openapi_url=openapi_url,
    docs_url=f"{settings.api_prefix}/docs" if docs_enabled else None,
    redoc_url=f"{settings.api_prefix}/redoc" if docs_enabled else None,
)
logger = logging.getLogger("bidshield")

# ── Layer 1 — CORS: explicit allow-list (default: none beyond configured) ───
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Layer 1 — perimeter gateway (rate limit, body cap, injection scan,
#    security headers). Outermost ASGI wrapper so it sees every byte. ────────
if settings.gateway_enabled:
    app.add_middleware(GatewayMiddleware)

# Structured error handler to never expose internal traces or sensitive errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log internally, return sanitized response
    logger.exception("Unhandled request failure for %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal verification processing exception occurred. This incident has been logged for audit."}
    )

# Include API routers
from app.api.auth import router as auth_router
from app.api.tenders import router as tenders_router
from app.api.bidders import router as bidders_router
from app.api.documents import router as documents_router
from app.api.verification import router as verification_router
from app.api.reports import router as reports_router
from app.api.audit import router as audit_router
from app.api.dashboard import router as dashboard_router
from app.api.admin import router as admin_router

# Mount all routers under /api/v1
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(admin_router, prefix=settings.api_prefix)
app.include_router(tenders_router, prefix=settings.api_prefix, dependencies=[Depends(get_current_user)])
app.include_router(bidders_router, prefix=settings.api_prefix, dependencies=[Depends(get_current_user)])
app.include_router(documents_router, prefix=settings.api_prefix, dependencies=[Depends(get_current_user)])
app.include_router(verification_router, prefix=settings.api_prefix, dependencies=[Depends(get_current_user)])
app.include_router(reports_router, prefix=settings.api_prefix, dependencies=[Depends(get_current_user)])
app.include_router(audit_router, prefix=settings.api_prefix, dependencies=[Depends(get_current_user)])
app.include_router(dashboard_router, prefix=settings.api_prefix, dependencies=[Depends(get_current_user)])

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "demo_mode": settings.demo_mode,
        "rules_version": settings.rule_engine_version,
        "risk_version": settings.risk_engine_version
    }

# ── Layer 4/6 — startup vault snapshot, backup scheduler, DB-level audit
#    append-only enforcement. Skipped when imported for tests unless the env
#    explicitly requests runtime startup (uvicorn target uses `if __name__`). ─
def _runtime_startup() -> None:
    from app.db.audit_protection import install_audit_protection
    from app.db.session import engine
    from app.services import backup_service

    install_audit_protection(engine)
    backup_service.startup_snapshot()
    backup_service.start_scheduler()

if __name__ == "__main__":
    _runtime_startup()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
