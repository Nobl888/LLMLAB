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


class EvidencePack(BaseModel):
    """Portable evidence bundle suitable for CI artifacts and audit trails."""

    schema_version: str = Field("1.0", description="Evidence pack schema version")
    generated_at: datetime = Field(..., description="When the evidence pack was generated (ISO8601)")

    # Traceability
    trace_id: str = Field(..., description="Validation trace ID")
    request_id: Optional[str] = Field(None, description="Echo of X-Request-ID header")

    # Execution context (safe metadata)
    domain: str = Field(..., description="Domain tag")
    mode: str = Field(..., description="One of: mock, kpi_kit")
    api_version: str = Field(..., description="Client-declared api_version from request")
    build_commit: Optional[str] = Field(None, description="Deployed build commit (if available)")

    # Inputs (hashes only)
    baseline_hash: str = Field(..., description="SHA256 hash of baseline input")
    candidate_hash: str = Field(..., description="SHA256 hash of candidate input")
    test_data_hash: str = Field(..., description="SHA256 hash of test data input")

    # Comparison/scoring summary
    risk: RiskAssessment
    summary: SummaryStats
    recommendation: str = Field(..., description="Recommendation string")

    # Safe configuration snapshot (no file paths, no code)
    config: Dict[str, Any] = Field(default_factory=dict, description="Safe config snapshot (tolerances, timeouts, kpi_type, etc.)")
    tenant_context: Optional[Dict[str, Any]] = Field(None, description="Optional tenant context (hashed identifiers only)")


class ValidateResponse(BaseModel):
    """Safe default response (no algorithm details exposed)."""
    trace_id: str = Field(..., description="Unique request ID for audit trail")
    request_id: Optional[str] = Field(None, description="Echo of X-Request-ID header for tracing")
    status: str = Field(..., description="Always 'ok' on success, 'error' on failure")
    risk: RiskAssessment
    summary: SummaryStats
    recommendation: str = Field(..., description="One of: APPROVE_WITH_MONITORING, APPROVE, REVIEW, REJECT")
    evidence: EvidenceBlock
    evidence_pack: Optional[EvidencePack] = Field(
        None,
        description=(
            "Portable evidence bundle for CI/audit use. Contains hashes + config + summary; "
            "does not include proprietary algorithm details."
        ),
    )


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
    fixture_id: Optional[str] = Field(
        None,
        description=(
            "Identifier for an uploaded CSV fixture. If provided, the server resolves fixture_id -> stored fixture path "
            "internally (preferred for external/self-serve). Do not send server file paths from clients."
        ),
    )
    kpi_type: Optional[str] = Field("profitmetrics", description="profitmetrics|countmetrics|percentagemetrics|aggregationmetrics")
    percentage_scale: Optional[str] = Field(None, description="For percentagemetrics: 'ratio_0_1' (0-1) or 'percent_0_100' (0-100); auto-detected if omitted")

    # Contract/invariant mode (high-leverage, cross-vertical)
    # If provided, the API will run deterministic contract checks against the
    # provided baseline_output/candidate_output payloads (no code execution).
    contract: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Optional contract definition for deterministic invariant checks. "
            "When present, validation runs in 'contract_invariants' mode using baseline_output/candidate_output. "
            "Details never include raw values; only rule ids/paths/messages."
        ),
    )
    
    include_details: bool = Field(False, description="If True, return explanation + details (requires agreement)")
    api_version: str = Field("1.0", description="API version for forward compatibility")
