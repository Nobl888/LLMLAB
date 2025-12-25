"""
Health check endpoint. Minimal, stable, no business logic.
"""
from fastapi import APIRouter
from datetime import datetime
import os
from api_validation.public.schemas import HealthResponse

router = APIRouter()

# Render sets RENDER_GIT_COMMIT (and sometimes RENDER_GIT_COMIT). Prefer those.
build_commit = (
    os.getenv("RENDER_GIT_COMMIT")
    or os.getenv("RENDER_GIT_COMIT")
    or os.getenv("BUILD_COMMIT")
    or "unknown"
)

@router.get("/health")
async def health_check() -> HealthResponse:
    """
    Simple health check. Returns service status, version, commit.
    No scoring logic, no secrets, just a heartbeat.
    """
    return HealthResponse(
        status="ok",
        service="llmlab-validation-api",
        version=os.getenv("API_VERSION", "1.0.0"),
        commit=build_commit,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
