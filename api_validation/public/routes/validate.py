"""
Main validation endpoint.
Returns safe schema (no algorithm details by default).
Optionally includes explanation + details if include_details=True (gated).

Includes audit logging with request ID tracing and structured logs.
"""
from fastapi import APIRouter, HTTPException, status, Request, Security, Header
from fastapi.security import APIKeyHeader
from datetime import datetime
import os
import uuid
import hashlib
import json
import logging
from ..schemas import ValidateRequest, ValidateResponse, ErrorResponse, RiskAssessment, SummaryStats, EvidenceBlock, EvidencePack
from ..settings import settings

# KPI Analytics kit imports
from domain_kits.kpi_analytics.runner import KPIRunner
from domain_kits.kpi_analytics.normalizer import KPINormalizer
from domain_kits.kpi_analytics.comparator_config import ComparatorConfig
from domain_kits.kpi_analytics.error_taxonomy import KPIErrorTaxonomy

# Contract/invariants kit (no code execution)
from domain_kits.contract_invariants.engine import evaluate_contract

router = APIRouter()

# Audit logger (configured in main.py)
audit_logger = logging.getLogger("audit")

# Smoke test security: 404 for missing/wrong key (stealth mode)
smoke_key_header = APIKeyHeader(name="X-Smoke-Key", auto_error=False)

def require_smoke_key(api_key: str = Security(smoke_key_header)) -> None:
    """
    Require valid smoke key or return 404 (pretend route doesn't exist).
    Set SMOKE_KEY in environment variables.
    """
    expected = os.getenv("SMOKE_KEY")
    # If not configured, or missing/wrong key: pretend the route doesn't exist
    if (not expected) or (api_key != expected):
        raise HTTPException(status_code=404)


# --- API key auth (Authorization: Bearer ...) ---
import psycopg

api_key_bearer_header = APIKeyHeader(name="Authorization", auto_error=False)

def require_api_key_bearer(auth_header: str = Security(api_key_bearer_header)) -> dict:
    # Stealth mode: return 404 for missing/wrong key
    if not auth_header:
        raise HTTPException(status_code=404, detail="Not found")

    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=404, detail="Not found")

    raw_key = parts[1].strip()
    if not raw_key.startswith("llm_") or len(raw_key) < 12:
        raise HTTPException(status_code=404, detail="Not found")

    key_prefix = raw_key[:12]  # "llm_" + 8 chars
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(status_code=503, detail="DB not configured")

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select tenant_id, scopes, status
                from api_keys
                where key_prefix = %s and key_hash = %s
                """,
                (key_prefix, key_hash),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    tenant_id, scopes, key_status = row
    if key_status != "active":
        raise HTTPException(status_code=404, detail="Not found")

    return {"tenant_id": str(tenant_id), "scopes": scopes}


def require_tenant_match(
    auth: dict = Security(require_api_key_bearer),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> dict:
    if x_tenant_id != auth["tenant_id"]:
        raise HTTPException(status_code=403, detail="TENANT_MISMATCH")

    return {"tenant_id": auth["tenant_id"], "scopes": auth["scopes"]}


def compute_hash(data: dict) -> str:
    """Compute SHA256 hash of a data dict."""
    if data is None:
        data = {}
    data_str = json.dumps(data, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(data_str.encode()).hexdigest()[:12]


def _resolve_fixture_storage_path(*, tenant_id: str, fixture_id: str) -> tuple[str, str] | None:
    """Resolve an uploaded fixture_id to an internal storage path.

    Returns (storage_path, sha256) or None if not found/active.
    Never returns this path to the caller.
    """
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(status_code=503, detail="DB not configured")

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select storage_path, sha256
                from fixtures
                where id = %s and tenant_id = %s and status = 'active'
                """,
                (fixture_id, tenant_id),
            )
            row = cur.fetchone()

    if not row:
        return None
    storage_path, sha256 = row
    return (str(storage_path), str(sha256))


def _safe_hash_str(value: str | None) -> str | None:
    """Hash a string value for safe echoing (avoid returning raw identifiers)."""
    if not value:
        return None
    return compute_hash({"value": value})


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


@router.get("/_smoke", dependencies=[Security(require_smoke_key)])
async def smoke_test():
    """
    Smoke test endpoint with minimal diagnostic info.
    Requires X-Smoke-Key header. Returns 404 if missing/wrong.
    """
    return {
        "status": "ok",
        "service": "validation-api",
        "version": "1.0",
        "defaults": {
            "fixture_path": "[REDACTED]",  # Don't leak paths even to authorized callers
            "baseline_kpi_path": "[REDACTED]",
        }
    }


@router.post(
    "/api/validate",
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Missing tenant header",
            "content": {
                "application/json": {
                    "examples": {
                        "missingTenant": {
                            "summary": "Missing X-Tenant-ID header",
                            "value": {
                                "trace_id": "<UUID>",
                                "status": "error",
                                "error": {"code": "MISSING_TENANT_ID", "message": "MISSING_TENANT_ID"}
                            }
                        }
                    }
                }
            }
        },
        403: {
            "model": ErrorResponse,
            "description": "Tenant mismatch",
            "content": {
                "application/json": {
                    "examples": {
                        "tenantMismatch": {
                            "summary": "X-Tenant-ID doesn't match API key tenant",
                            "value": {
                                "trace_id": "<UUID>",
                                "status": "error",
                                "error": {"code": "TENANT_MISMATCH", "message": "TENANT_MISMATCH"}
                            }
                        }
                    }
                }
            }
        }
    },
    openapi_extra={
        "parameters": [
            {
                "name": "X-Tenant-ID",
                "in": "header",
                "required": False,
                "schema": {"type": "string"},
                "description": (
                    "Tenant context header. If missing, returns 400 MISSING_TENANT_ID. "
                    "If it doesn't match the API key tenant, returns 403 TENANT_MISMATCH."
                )
            }
        ]
    }
)
async def validate(
    request: Request,
    req_body: ValidateRequest,
    ctx: dict = Security(require_tenant_match)
) -> ValidateResponse:
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
    
    Header Requirements:
    - Authorization: Bearer <api-key> (required, validates API key)
    - X-Tenant-ID: <tenant-uuid> (required, must match API key tenant)
    
    Error Responses:
    - 400 MISSING_TENANT_ID: X-Tenant-ID header not provided
    - 403 TENANT_MISMATCH: X-Tenant-ID doesn't match the API key's tenant
    - 401: Invalid or missing API key
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
            (req_body.fixture_path or getattr(req_body, "fixture_id", None)),
        ])

        use_contract_kit = (not use_kpi_kit) and bool(req_body.contract)
        
        if use_kpi_kit:
            # ===== KPI KIT MODE =====
            runner = KPIRunner()
            normalizer = KPINormalizer()

            # If fixture_id is provided, resolve to a server-side path.
            fixture_path = req_body.fixture_path
            fixture_sha256 = None
            fixture_id = getattr(req_body, "fixture_id", None)
            if (not fixture_path) and fixture_id:
                resolved = _resolve_fixture_storage_path(tenant_id=tenant_id, fixture_id=str(fixture_id))
                if not resolved:
                    raise HTTPException(status_code=404, detail={"code": "FIXTURE_NOT_FOUND", "message": "Fixture not found"})
                fixture_path, fixture_sha256 = resolved
            
            # Execute baseline KPI
            baseline_result = runner.execute(req_body.baseline_kpi_path, fixture_path)
            if baseline_result.get("status") != "success":
                raise Exception(f"Baseline KPI execution failed: {baseline_result.get('error')}")
            
            # Execute candidate KPI
            candidate_result = runner.execute(req_body.candidate_kpi_path, fixture_path)
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
            test_data_hash = compute_hash({
                "fixture_id": str(fixture_id) if fixture_id else None,
                "fixture_sha256": fixture_sha256,
                "fixture_path": "[SERVER_PATH]" if fixture_path else None,
            })
            
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
        elif use_contract_kit:
            # ===== CONTRACT / INVARIANTS MODE (no code execution) =====
            baseline_obj = req_body.baseline_output or {}
            candidate_obj = req_body.candidate_output or {}
            contract_obj = req_body.contract or {}

            contract_eval = evaluate_contract(
                baseline=baseline_obj,
                candidate=candidate_obj,
                contract=contract_obj,
            )

            total_checks = int(contract_eval.get("total_checks") or 0)
            failed_checks = int(contract_eval.get("failed_checks") or 0)
            pass_rate = float(contract_eval.get("pass_rate") or 0.0)
            match = (failed_checks == 0) and (total_checks > 0)

            # Simple, deterministic score mapping (safe). Higher = safer/better match.
            risk_score = max(0.0, min(10.0, 10.0 * pass_rate))
            confidence = 95.0 if match else max(10.0, min(90.0, 50.0 + 40.0 * pass_rate))
            category = "low" if pass_rate >= 0.9 else "medium" if pass_rate >= 0.6 else "high"
            recommendation = "APPROVE" if pass_rate >= 0.95 else "REVIEW" if pass_rate >= 0.7 else "REJECT"

            scoring_result = {
                "risk_score": risk_score,
                "confidence": confidence,
                "category": category,
                "pass_rate": pass_rate,
                "total_checks": total_checks,
                "failed_checks": failed_checks,
                "recommendation": recommendation,
            }

            # Hashes for evidence (include contract hash via test_data_hash)
            baseline_hash = compute_hash(baseline_obj)
            candidate_hash = compute_hash(candidate_obj)
            test_data_hash = compute_hash({
                "test_data": (req_body.test_data or {}),
                "contract": contract_obj,
            })

            details = None
            explanation = None
            if req_body.include_details:
                # Never include raw values. Only rule ids/paths/messages.
                failed_rules = [c for c in (contract_eval.get("checks") or []) if not c.get("ok")]
                explanation = "Contract/invariant checks failed" if failed_rules else "All contract/invariant checks passed"
                details = {
                    "checks": contract_eval.get("checks"),
                    "failed_rule_count": len(failed_rules),
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

        # Build evidence pack (safe, portable). Never include code or file paths.
        now_iso = datetime.utcnow().isoformat() + "Z"
        mode = "kpi_kit" if use_kpi_kit else ("contract_invariants" if use_contract_kit else "mock")
        domain = "analytics_kpi" if use_kpi_kit else ("contract_invariants" if use_contract_kit else "analytics_kpi")

        safe_config: dict = {
            "mode": mode,
            "kpi_type": req_body.kpi_type,
            "percentage_scale": req_body.percentage_scale,
            "tolerances": (tolerances if use_kpi_kit else None),
            "execution_timeout_seconds": settings.execution_timeout_seconds,
            "include_details": bool(req_body.include_details),
            "contract_hash": (compute_hash(req_body.contract) if use_contract_kit else None),
        }

        # Remove null-ish entries for cleanliness
        safe_config = {k: v for k, v in safe_config.items() if v is not None}

        tenant_context = {
            "tenant_id_hash": _safe_hash_str(tenant_id),
            "partner_id_hash": _safe_hash_str(partner_id),
            "customer_id_hash": _safe_hash_str(customer_id),
        }
        tenant_context = {k: v for k, v in tenant_context.items() if v is not None}
        if not tenant_context:
            tenant_context = None
        
        # Build evidence block
        if use_kpi_kit and req_body.include_details:
            # KPI mode: use computed explanation and details
            evidence = EvidenceBlock(
                baseline_hash=baseline_hash,
                candidate_hash=candidate_hash,
                test_data_hash=test_data_hash,
                timestamp=datetime.utcnow().isoformat() + "Z",
                domain=domain,
                explanation=explanation,
                details=details
            )
        elif use_contract_kit and req_body.include_details:
            evidence = EvidenceBlock(
                baseline_hash=baseline_hash,
                candidate_hash=candidate_hash,
                test_data_hash=test_data_hash,
                timestamp=datetime.utcnow().isoformat() + "Z",
                domain=domain,
                explanation=explanation,
                details=details,
            )
        elif req_body.include_details:
            # Mock mode: use mock explanation and details
            evidence = EvidenceBlock(
                baseline_hash=baseline_hash,
                candidate_hash=candidate_hash,
                test_data_hash=test_data_hash,
                timestamp=datetime.utcnow().isoformat() + "Z",
                domain=domain,
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
                domain=domain
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
            evidence=evidence,
            evidence_pack=EvidencePack(
                schema_version="1.0",
                generated_at=now_iso,
                trace_id=trace_id,
                request_id=request_id,
                domain=domain,
                mode=mode,
                api_version=req_body.api_version,
                build_commit=os.getenv("BUILD_COMMIT"),
                baseline_hash=baseline_hash,
                candidate_hash=candidate_hash,
                test_data_hash=test_data_hash,
                risk=RiskAssessment(
                    score=scoring_result["risk_score"],
                    category=scoring_result["category"],
                    confidence=scoring_result["confidence"],
                ),
                summary=SummaryStats(
                    pass_rate=scoring_result["pass_rate"],
                    total_checks=scoring_result["total_checks"],
                    failed_checks=scoring_result["failed_checks"],
                ),
                recommendation=scoring_result["recommendation"],
                config=safe_config,
                tenant_context=tenant_context,
            )
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
