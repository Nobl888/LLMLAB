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
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
import sys
import logging
from pathlib import Path

# Initialize private modules before importing routes
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from startup import setup_private_modules
setup_private_modules()

from routes import health, validate, auth
from middleware.audit_logging import AuditLoggingMiddleware, RequestIDMiddleware
from middleware.rate_limiting import RateLimitingMiddleware

# Configure logging (audit logs to stdout, rotated by log handler)
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # Just the message (should be JSON)
)

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

@app.get("/")
def root():
    return {"name": "LLMlab Validation API", "status": "running"}

@app.get("/whoami")
def whoami():
    return {"module": __name__, "file": __file__}

# Security middleware stack (order matters: rate limit -> audit log -> request ID)
if ENABLE_RATE_LIMITING:
    app.add_middleware(RateLimitingMiddleware)

if ENABLE_AUDIT_LOGGING:
    app.add_middleware(AuditLoggingMiddleware, enable_redaction=ENABLE_REDACTION)

app.add_middleware(RequestIDMiddleware)

# CORS middleware (adjust for your domain)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(health.router)
app.include_router(validate.router)
app.include_router(auth.router)  # Admin key management endpoints

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
