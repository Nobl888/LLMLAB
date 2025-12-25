"""
FastAPI application for validation API.

This is the public wrapper. The actual scoring logic (private/core_scoring.py) 
never goes here—it stays on our servers.

Security features enabled:
- Audit logging (request ID, payload hash, latency, status)
- Rate limiting (per-API-key, configurable)
- Payload size enforcement
- Request redaction (removes PII, secrets)
"""
from fastapi import FastAPI, status, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
import sys
import logging
import uuid
import time
from contextvars import ContextVar
from pathlib import Path
import psycopg

# Initialize private modules before importing routes
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from api_validation.startup import setup_private_modules
setup_private_modules()

from api_validation.public.routes import health, validate
from api_validation.public.middleware.audit_logging import AuditLoggingMiddleware, RequestIDMiddleware
from api_validation.public.middleware.rate_limiting import RateLimitingMiddleware
from api_validation.public.db_init import init_db_if_enabled

# Context var for trace_id (used in logging)
trace_id_ctx: ContextVar[str] = ContextVar('trace_id', default='-')

# Logging filter to inject trace_id into all log records
class TraceIdFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_ctx.get()
        return True

# Configure logging (audit logs to stdout, rotated by log handler)
root_logger = logging.getLogger()
if not root_logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='[%(trace_id)s] %(message)s',
    )

# Add trace_id filter to root logger
for handler in logging.root.handlers:
    if not any(isinstance(f, TraceIdFilter) for f in handler.filters):
        handler.addFilter(TraceIdFilter())

# Load environment
API_VERSION = os.getenv("API_VERSION", "1.0.0")
BUILD_COMMIT = os.getenv("BUILD_COMMIT", "abc1234def567")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ENABLE_AUDIT_LOGGING = os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() == "true"
ENABLE_RATE_LIMITING = os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"
ENABLE_REDACTION = os.getenv("ENABLE_REDACTION", "true").lower() == "true"

# Create FastAPI app
app = FastAPI(
    title="LLMlab Validation API",
    description="Validate code changes against baseline with cryptographic evidence.",
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

from api_validation.public.key_admin import router as key_admin_router
app.include_router(key_admin_router)

if os.getenv("ENABLE_FIXTURE_UPLOAD", "false").lower() == "true":
    from api_validation.public.routes.fixtures import router as fixtures_router
    app.include_router(fixtures_router)

# Hosted-safe contract templates + evidence verification are safe to expose in hosted mode.
if os.getenv("ENABLE_CONTRACTS_API", "true").lower() == "true":
    from api_validation.public.routes.contracts import router as contracts_router
    app.include_router(contracts_router)

if os.getenv("ENABLE_EVIDENCE_API", "true").lower() == "true":
    from api_validation.public.routes.evidence import router as evidence_router
    app.include_router(evidence_router)

# Ensemble routes can be enabled explicitly (may involve code execution depending on configuration).
if os.getenv("ENABLE_ENSEMBLE_API", "false").lower() == "true":
    from api_validation.public.routes.ensemble import router as ensemble_router
    app.include_router(ensemble_router)

@app.get("/")
def root():
    return {"name": "LLMlab Validation API", "status": "running"}

@app.get("/whoami", include_in_schema=False)
def whoami():
    return {"module": __name__}

@app.get("/health/db", include_in_schema=False)
def health_db():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        return {"ok": False, "error": "DATABASE_URL not set"}
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        return {"ok": True}
    except Exception as e:
        # Avoid leaking internal driver/network details in a public health endpoint.
        return {"ok": False, "error": "DB_UNREACHABLE"}

@app.on_event("startup")
def _startup():
    init_db_if_enabled()

# Trace ID middleware (sets request.state.trace_id and adds response headers)
@app.middleware("http")
async def add_trace_id_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.trace_id = trace_id
    
    # Set context var for logging
    token = trace_id_ctx.set(trace_id)
    try:
        start = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start

        response.headers["X-Request-ID"] = trace_id
        response.headers["X-Process-Time"] = str(process_time)
        return response
    finally:
        # Reset context var after response
        trace_id_ctx.reset(token)

# Security middleware stack (order matters: rate limit -> audit log -> request ID)
if ENABLE_RATE_LIMITING:
    app.add_middleware(RateLimitingMiddleware)

if ENABLE_AUDIT_LOGGING:
    app.add_middleware(AuditLoggingMiddleware, enable_redaction=ENABLE_REDACTION)

app.add_middleware(RequestIDMiddleware)

# CORS is disabled by default (server-to-server API). Enable only if explicitly configured.
cors_origins_raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
if cors_origins_raw:
    cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
    allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"

    # Never allow credentials with wildcard origins.
    if "*" in cors_origins:
        allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"] if os.getenv("CORS_ALLOW_METHODS") is None else [m.strip() for m in os.getenv("CORS_ALLOW_METHODS", "").split(",") if m.strip()],
        allow_headers=["*"] if os.getenv("CORS_ALLOW_HEADERS") is None else [h.strip() for h in os.getenv("CORS_ALLOW_HEADERS", "").split(",") if h.strip()],
    )

# Include routes
app.include_router(health.router)
app.include_router(validate.router)

# NOTE: api_validation.public.routes.auth contains placeholder/insecure admin flows
# and must not be exposed in production.

# HTTPException handler (wraps all HTTPException into ErrorResponse format)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    trace_id = getattr(request.state, "trace_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    # Normalize error payload into ErrorResponse.error shape
    if isinstance(exc.detail, dict):
        err = exc.detail
    else:
        err = {"code": str(exc.detail), "message": str(exc.detail)}

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "trace_id": trace_id,
            "status": "error",
            "error": err,
        },
    )

# RequestValidationError handler (wraps 422 validation errors into ErrorResponse format)
@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    trace_id = getattr(request.state, "trace_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    return JSONResponse(
        status_code=422,
        content={
            "trace_id": trace_id,
            "status": "error",
            "error": {
                "code": "REQUEST_VALIDATION_ERROR",
                "message": "Request validation failed",
                "detail": jsonable_encoder(exc.errors()),
            },
        },
    )

# Global exception handler (optional, for cleaner error responses)
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred."
            }
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=ENVIRONMENT == "development"
    )
