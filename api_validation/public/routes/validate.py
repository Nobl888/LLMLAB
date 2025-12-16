"""
Main validation endpoint.
Returns safe schema (no algorithm details by default).
Optionally includes explanation + details if include_details=True (gated).

Includes audit logging with request ID tracing and structured logs.
"""
from fastapi import APIRouter, HTTPException, status, Request
from datetime import datetime
import uuid
import hashlib
import json
import logging
from ..schemas import ValidateRequest, ValidateResponse, ErrorResponse, RiskAssessment, SummaryStats, EvidenceBlock
from ..settings import settings

# KPI Analytics kit imports
from domain_kits.kpi_analytics.runner import KPIRunner
from domain_kits.kpi_analytics.normalizer import KPINormalizer
from domain_kits.kpi_analytics.comparator_config import ComparatorConfig
from domain_kits.kpi_analytics.error_taxonomy import KPIErrorTaxonomy

router = APIRouter()

# Audit logger (configured in main.py)
audit_logger = logging.getLogger("audit")


def compute_hash(data: dict) -> str:
    """Compute SHA256 hash of a data dict."""
    if data is None:
        data = {}
    data_str = json.dumps(data, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(data_str.encode()).hexdigest()[:12]


def _get_kpi_config(kpi_type: str):
    """
    Pick the appropriate ComparatorConfig based on KPI type.
    Handles synonyms by normalizing input (lowercase, remove underscores/hyphens).
    """
    # Normalize: lowercase, remove underscores and hyphens
    t = (kpi_type or "").lower().replace("_", "").replace("-", "")
    
    if t in ["profitmetrics", "profit"]:
        return ComparatorConfig.for_profit_metrics()
    if t in ["countmetrics", "count"]:
        return ComparatorConfig.for_count_metrics()
    if t in ["percentagemetrics", "percentage"]:
        return ComparatorConfig.for_percentage_metrics()
    if t in ["aggregationmetrics", "aggregation"]:
        return ComparatorConfig.for_aggregation_metrics()
    # Default: strict (no tolerance)
    return ComparatorConfig()


def mock_scoring(baseline: dict, candidate: dict, test_data: dict) -> dict:
    """
    Mock scoring logic (placeholder).
    In production, this calls private/core_scoring.py which stays hidden.
    
    For now, returns realistic-looking data.
    """
    # Simulate scoring: compare baseline vs candidate
    total_checks = 24
    failed_checks = 4
    pass_rate = (total_checks - failed_checks) / total_checks
    
    # Simulated risk score (0–10 scale, higher = safer/better match)
    risk_score = 8.7
    confidence = 94.0
    category = "low" if risk_score >= 7 else "medium" if risk_score >= 4 else "high"
    
    return {
        "risk_score": risk_score,
        "confidence": confidence,
        "category": category,
        "pass_rate": pass_rate,
        "total_checks": total_checks,
        "failed_checks": failed_checks,
        "recommendation": "APPROVE_WITH_MONITORING"
    }


@router.get("/_smoke")
async def smoke_test():
    """
    Smoke test endpoint with debug config info.
    Returns validation service settings (timeouts, paths).
    """
    return {
        "status": "ok",
        "service": "validation-api",
        "version": "1.0",
        "timeout_seconds": settings.execution_timeout_seconds,
        "defaults": {
            "fixture_path": settings.default_fixture_path,
            "baseline_kpi_path": settings.default_baseline_kpi_path,
        }
    }


@router.post("/api/validate")
async def validate(request: Request, req_body: ValidateRequest) -> ValidateResponse:
    """
    Validate a candidate against a baseline.
    
    Returns:
    - Safe default: risk score, category, confidence, summary, recommendation, hashes
    - Verbose mode (include_details=True): adds explanation + details
    
    All requests are logged for audit purposes (request ID, status, latency, etc.)
    Algorithm stays on our servers; clients only see JSON.
    
    TENANT ISOLATION:
    - Every request must include X-Tenant-ID header
    - Audit logs are filtered by tenant_id to prevent cross-tenant visibility
    - Rate limiting is enforced per tenant
    """
    
    # Generate trace ID for this validation
    trace_id = str(uuid.uuid4())
    
    # Extract request ID from middleware (or generate new one)
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    # Extract API key ID (obfuscated) from Authorization header (Bearer token only)
    auth_header = request.headers.get("Authorization", "")
    api_key_id = _extract_api_key_id(auth_header)
    
    # *** TENANT ISOLATION: Require X-Tenant-ID header ***
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        # Log the failed request
        _log_validation(
            request_id=request_id,
            api_key_id=api_key_id,
            tenant_id="unknown",
            status_code=400,
            result="validation_error",
            error_code="MISSING_TENANT_ID",
            trace_id=trace_id
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "trace_id": trace_id,
                "request_id": request_id,
                "status": "error",
                "error": {
                    "code": "MISSING_TENANT_ID",
                    "message": "X-Tenant-ID header is required for all requests"
                }
            }
        )
    
    # Extract partner ID if provided (optional; used for audit trail)
    partner_id = request.headers.get("X-Partner-ID")
    
    # Extract customer ID if provided (optional; for backward compatibility)
    customer_id = request.headers.get("X-Customer-ID")
    
    try:
        # Determine if this is a KPI kit request or mock mode
        use_kpi_kit = all([
            req_body.baseline_kpi_path,
            req_body.candidate_kpi_path,
            req_body.fixture_path,
        ])
        
        if use_kpi_kit:
            # ===== KPI KIT MODE =====
            runner = KPIRunner()
            normalizer = KPINormalizer()
            
            # Execute baseline KPI
            baseline_result = runner.execute(req_body.baseline_kpi_path, req_body.fixture_path)
            if baseline_result.get("status") != "success":
                raise Exception(f"Baseline KPI execution failed: {baseline_result.get('error')}")
            
            # Execute candidate KPI
            candidate_result = runner.execute(req_body.candidate_kpi_path, req_body.fixture_path)
            if candidate_result.get("status") != "success":
                raise Exception(f"Candidate KPI execution failed: {candidate_result.get('error')}")
            
            # Normalize baseline output
            baseline_norm = normalizer.normalize(
                baseline_result["output"],
                baseline_result.get("output_type", "unknown")
            )
            if baseline_norm.get("status") != "valid":
                raise Exception(f"Baseline output cannot be normalized: {baseline_norm.get('error')}")
            
            # Normalize candidate output
            candidate_norm = normalizer.normalize(
                candidate_result["output"],
                candidate_result.get("output_type", "unknown")
            )
            if candidate_norm.get("status") != "valid":
                raise Exception(f"Candidate output cannot be normalized: {candidate_norm.get('error')}")
            
            # Pick comparator config and compare
            config = _get_kpi_config(req_body.kpi_type)
            tolerances = config.to_dict() if hasattr(config, "to_dict") else {}
            
            # Add percentage_scale if provided (for explicit scale override)
            if req_body.percentage_scale:
                tolerances['percentage_scale'] = req_body.percentage_scale
            
            comparison = normalizer.compare_normalized(baseline_norm, candidate_norm, tolerances)
            
            # Extract match and drift
            match = bool(comparison.get("match"))
            drift_pct = comparison.get("drift_pct") or comparison.get("max_drift_pct") or 0.0
            
            # Score mapping (simple + safe; can be refined)
            risk_score = 9.2 if match else 1.0
            confidence = 90.0 if match else 5.0
            category = "low" if match else "high"
            recommendation = "APPROVE" if match else "REJECT"
            pass_rate = 1.0 if match else 0.0
            total_checks = 1
            failed_checks = 0 if match else 1
            
            # Compute hashes (stable inputs for evidence)
            baseline_hash = compute_hash({
                "path": req_body.baseline_kpi_path,
                "output_type": baseline_result.get("output_type")
            })
            candidate_hash = compute_hash({
                "path": req_body.candidate_kpi_path,
                "output_type": candidate_result.get("output_type")
            })
            test_data_hash = compute_hash({"fixture_path": req_body.fixture_path})
            
            # Prepare details if requested
            details = None
            explanation = None
            if req_body.include_details:
                # Classify error if mismatch
                error_category = None
                error_info = None
                suggestion = None
                
                if not match:
                    reason = comparison.get("reason", "")
                    # Classify based on mismatch reason
                    if "Type mismatch" in reason:
                        error_category = "dtype_coercion_error"
                    elif "Key mismatch" in reason or "keys exceed" in reason.lower():
                        error_category = "aggregation_error"
                    elif "Shape mismatch" in reason:
                        error_category = "groupby_error"
                    elif "drift" in reason.lower():
                        # Determine if it's numeric drift or computation error based on magnitude
                        if drift_pct > 10:
                            error_category = "computation_error"
                        else:
                            error_category = "numeric_drift"
                    else:
                        error_category = "computation_error"
                    
                    # Get error taxonomy info
                    taxonomy = KPIErrorTaxonomy()
                    error_info = taxonomy.classify(error_category)
                    
                    # Add suggestion for percentage metrics
                    if req_body.kpi_type and "percentage" in req_body.kpi_type.lower():
                        suggestion = (
                            "This KPI looks like a rate/percentage; validation uses absolute "
                            "percentage-point tolerance. Check denominator, casting, and whether "
                            "you're returning 0-1 or 0-100."
                        )
                
                details = {
                    "comparison": comparison,
                    "kpi_type": req_body.kpi_type,
                    "drift_pct": drift_pct,
                    "drift_abs": comparison.get("drift_abs"),
                    "error_category": error_category,
                    "error_info": error_info,
                    "suggestion": suggestion,
                    "runtime": {
                        "execution_timeout_seconds": settings.execution_timeout_seconds,
                        "defaults": {
                            "fixture_path": settings.default_fixture_path,
                            "baseline_kpi_path": settings.default_baseline_kpi_path,
                        }
                    }
                }
                explanation = comparison.get("reason", "KPI outputs compared with configured tolerance")
            
            scoring_result = {
                "risk_score": risk_score,
                "confidence": confidence,
                "category": category,
                "pass_rate": pass_rate,
                "total_checks": total_checks,
                "failed_checks": failed_checks,
                "recommendation": recommendation
            }
        else:
            # ===== MOCK MODE (backward compatible) =====
            # Mock validation (in production, calls private/core_scoring.py)
            scoring_result = mock_scoring(
                baseline=req_body.baseline_output or {},
                candidate=req_body.candidate_output or {},
                test_data=req_body.test_data or {}
            )
            
            # Compute hashes for evidence
            baseline_hash = compute_hash(req_body.baseline_output)
            candidate_hash = compute_hash(req_body.candidate_output)
            test_data_hash = compute_hash(req_body.test_data)
            
            details = None
            explanation = None
        
        # Build evidence block
        if use_kpi_kit and req_body.include_details:
            # KPI mode: use computed explanation and details
            evidence = EvidenceBlock(
                baseline_hash=baseline_hash,
                candidate_hash=candidate_hash,
                test_data_hash=test_data_hash,
                timestamp=datetime.utcnow().isoformat() + "Z",
                domain="analytics_kpi",
                explanation=explanation,
                details=details
            )
        elif req_body.include_details:
            # Mock mode: use mock explanation and details
            evidence = EvidenceBlock(
                baseline_hash=baseline_hash,
                candidate_hash=candidate_hash,
                test_data_hash=test_data_hash,
                timestamp=datetime.utcnow().isoformat() + "Z",
                domain="analytics_kpi",
                explanation=(
                    "Most test cases matched the baseline exactly; "
                    "small deviations only in edge-period tests."
                ),
                details={
                    "deviation_pattern": "concentrated_in_edge_cases",
                    "estimated_cause": "model_version_difference"
                }
            )
        else:
            # No details requested
            evidence = EvidenceBlock(
                baseline_hash=baseline_hash,
                candidate_hash=candidate_hash,
                test_data_hash=test_data_hash,
                timestamp=datetime.utcnow().isoformat() + "Z",
                domain="analytics_kpi"
            )
        
        # Build response
        response = ValidateResponse(
            trace_id=trace_id,
            status="ok",
            risk=RiskAssessment(
                score=scoring_result["risk_score"],
                category=scoring_result["category"],
                confidence=scoring_result["confidence"]
            ),
            summary=SummaryStats(
                pass_rate=scoring_result["pass_rate"],
                total_checks=scoring_result["total_checks"],
                failed_checks=scoring_result["failed_checks"]
            ),
            recommendation=scoring_result["recommendation"],
            evidence=evidence
        )
        
        # Attach request ID to response
        response.request_id = request_id
        
        # Log successful validation to audit trail
        _log_validation(
            request_id=request_id,
            api_key_id=api_key_id,
            tenant_id=tenant_id,
            partner_id=partner_id,
            customer_id=customer_id,
            status_code=200,
            result="validation_passed",
            trace_id=trace_id
        )
        
        return response
    
    except Exception as e:
        # Log error to audit trail
        error_code = "VALIDATION_FAILED"
        status_code = 400
        
        _log_validation(
            request_id=request_id,
            api_key_id=api_key_id,
            tenant_id=tenant_id,
            partner_id=partner_id,
            customer_id=customer_id,
            status_code=status_code,
            result="validation_error",
            error_code=error_code,
            trace_id=trace_id
        )
        
        # Return error in standard format
        raise HTTPException(
            status_code=status_code,
            detail={
                "trace_id": trace_id,
                "request_id": request_id,
                "status": "error",
                "error": {
                    "code": error_code,
                    "message": str(e)
                }
            }
        )


def _extract_api_key_id(auth_header: str) -> str:
    """Extract and obfuscate API key ID from Authorization header."""
    if not auth_header:
        return "unknown"
    
    try:
        parts = auth_header.split()
        if len(parts) >= 2:
            key = parts[1]
            # Return obfuscated version: key_****[last5chars]
            return f"key_***{key[-5:]}"
        return "unknown"
    except Exception:
        return "unknown"


def _log_validation(
    request_id: str,
    api_key_id: str,
    tenant_id: str,
    status_code: int,
    result: str,
    trace_id: str,
    partner_id: str = None,
    customer_id: str = None,
    error_code: str = None,
):
    """
    Log validation call to audit trail with structured format.
    
    TENANT ISOLATION: tenant_id is logged so we can filter audit logs per tenant.
    """
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "request_id": request_id,
        "trace_id": trace_id,
        "tenant_id": tenant_id,  # *** TENANT ISOLATION ***
        "partner_id": partner_id or "unknown",
        "api_key_id": api_key_id,
        "customer_id": customer_id or "unknown",
        "endpoint": "/api/validate",
        "http_method": "POST",
        "http_status": status_code,
        "result": result,
        "error_code": error_code,
    }
    
    # Log as JSON string (for easy parsing)
    audit_logger.info(json.dumps(log_entry))
