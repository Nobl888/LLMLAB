"""
Health check endpoint. Minimal, stable, no business logic.
"""
from fastapi import APIRouter
from datetime import datetime
from schemas import HealthResponse

router = APIRouter()


@router.get("/health")
async def health_check() -> HealthResponse:
    """
    Simple health check. Returns service status, version, commit.
    
    No scoring logic, no secrets, just a heartbeat.
    """
    return HealthResponse(
        status="ok",
        service="llmlab-validation-api",
        version="1.0.0",
        commit="abc1234def567",
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
