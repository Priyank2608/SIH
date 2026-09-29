from fastapi import FastAPI, Request, status
from fastapi import Depends
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.security import get_current_user
import app.models.entities # Register all models

# Include API routers
from app.api.auth import router as auth_router
from app.api.tenders import router as tenders_router
from app.api.bidders import router as bidders_router
from app.api.documents import router as documents_router
from app.api.verification import router as verification_router
from app.api.reports import router as reports_router
from app.api.audit import router as audit_router
from app.api.dashboard import router as dashboard_router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Internal Procurement-Authority AI Compliance Verification Platform for GeM Procurement (SIH26100).",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
)
logger = logging.getLogger("bidshield")

# CORS configuration
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured error handler to never expose internal traces or sensitive errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log internally, return sanitized response
    logger.exception("Unhandled request failure for %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal verification processing exception occurred. This incident has been logged for audit."}
    )

# Mount all routers under /api/v1
app.include_router(auth_router, prefix=settings.api_prefix)
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
