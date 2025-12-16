"""
Pydantic models for request/response validation.
These define the exact contract between client and API.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class RiskAssessment(BaseModel):
    """Risk evaluation component."""
    score: float = Field(..., ge=0, le=10, description="Risk score from 0–10")
    category: str = Field(..., description="One of: critical, high, medium, low, none")
    confidence: float = Field(..., ge=0, le=100, description="Confidence as percentage (0–100)")


class SummaryStats(BaseModel):
    """Summary of validation results."""
    pass_rate: float = Field(..., ge=0, le=1, description="Fraction of checks passed (0–1)")
    total_checks: int = Field(..., ge=0, description="Total number of checks run")
    failed_checks: int = Field(..., ge=0, description="Number of checks that failed")


class EvidenceBlock(BaseModel):
    """Cryptographic evidence for audit trail."""
    baseline_hash: str = Field(..., description="SHA256 hash of baseline")
    candidate_hash: str = Field(..., description="SHA256 hash of candidate")
    test_data_hash: str = Field(..., description="SHA256 hash of test data")
    timestamp: datetime = Field(..., description="When this validation ran (ISO8601)")
    domain: str = Field(..., description="Domain tag (e.g., 'analytics_kpi', 'fraud_detection')")
    explanation: Optional[str] = Field(None, description="Human-readable explanation (verbose mode only)")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional detail dict (verbose mode only)")


class ValidateResponse(BaseModel):
    """Safe default response (no algorithm details exposed)."""
    trace_id: str = Field(..., description="Unique request ID for audit trail")
    request_id: Optional[str] = Field(None, description="Echo of X-Request-ID header for tracing")
    status: str = Field(..., description="Always 'ok' on success, 'error' on failure")
    risk: RiskAssessment
    summary: SummaryStats
    recommendation: str = Field(..., description="One of: APPROVE_WITH_MONITORING, APPROVE, REVIEW, REJECT")
    evidence: EvidenceBlock


class ErrorResponse(BaseModel):
    """Standard error response."""
    trace_id: str = Field(..., description="Unique request ID")
    status: str = Field(default="error", description="Always 'error'")
    error: Dict[str, Any] = Field(..., description="Error details with 'code', 'message', optional 'field'")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="'ok' if healthy")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="API version")
    commit: str = Field(..., description="Git commit hash")
    timestamp: datetime = Field(..., description="Current time (ISO8601)")


class ValidateRequest(BaseModel):
    """
    Request to validate a candidate against baseline.
    
    Supports two modes:
    1. Mock mode: baseline_output/candidate_output are provided directly
    2. KPI kit mode: baseline_kpi_path/candidate_kpi_path are executed against fixture_path
    
    KPI kit mode uses automated execution, validation, and tolerance-based comparison.
    Old clients using mock mode continue to work for backward compatibility.
    """
    # Mock mode (backward compatible)
    baseline_output: Optional[Dict[str, Any]] = Field(None, description="Baseline output data (mock mode)")
    candidate_output: Optional[Dict[str, Any]] = Field(None, description="Candidate output data (mock mode)")
    test_data: Optional[Dict[str, Any]] = Field(None, description="Test cases/data used (mock mode)")
    
    # KPI kit mode (new; optional so old payloads still work)
    baseline_kpi_path: Optional[str] = Field(None, description="Path to baseline KPI .py file")
    candidate_kpi_path: Optional[str] = Field(None, description="Path to candidate KPI .py file")
    fixture_path: Optional[str] = Field(None, description="Path to CSV fixture used to execute KPIs")
    kpi_type: Optional[str] = Field("profitmetrics", description="profitmetrics|countmetrics|percentagemetrics|aggregationmetrics")
    percentage_scale: Optional[str] = Field(None, description="For percentagemetrics: 'ratio_0_1' (0-1) or 'percent_0_100' (0-100); auto-detected if omitted")
    
    include_details: bool = Field(False, description="If True, return explanation + details (requires agreement)")
    api_version: str = Field("1.0", description="API version for forward compatibility")
