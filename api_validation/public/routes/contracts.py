"""Contract templates endpoints.

High leverage for self-serve JSON automation:
- Customers can start with a vetted contract template
- Then send baseline_output/candidate_output + template_id to /api/contracts/validate

Security posture:
- Requires tenant auth (Authorization + X-Tenant-ID)
- Templates are static and contain no customer data
"""

from datetime import datetime
import os
import uuid

from fastapi import APIRouter, Security, HTTPException, Request, status

from api_validation.public.routes.validate import require_tenant_match
from api_validation.public.routes.validate import (
    compute_hash,
    _safe_hash_str,
    _scopes_allow_details,
    _details_enforcement_mode,
)
from api_validation.public.routes.topology import get_topology_indicator
from api_validation.public.evidence_signing import sign_payload
from api_validation.public.schemas import (
    ContractTemplateValidateRequest,
    ValidateResponse,
    RiskAssessment,
    SummaryStats,
    EvidenceBlock,
    EvidencePack,
)

from domain_kits.contract_invariants.engine import evaluate_contract

router = APIRouter(tags=["contracts"])


# Minimal, general-purpose templates to accelerate adoption.
# These are intended as starting points, not a compliance certification.
CONTRACT_TEMPLATES: dict[str, dict] = {
    "json_output_basic_v1": {
        "schema_version": "1.0",
        "template_version": "1.0.0",
        "description": "Basic JSON output contract: required fields + types + safe run_id format.",
        "rules": [
            {"id": "exists_meta", "type": "exists", "path": "meta"},
            {"id": "exists_meta_run_id", "type": "exists", "path": "meta.run_id"},
            {"id": "type_meta_run_id", "type": "type_is", "path": "meta.run_id", "expected": "string"},
            {"id": "regex_meta_run_id", "type": "regex", "path": "meta.run_id", "pattern": "^[a-z0-9_-]{6,64}$"},
        ],
    },
    "no_pii_guard_v1": {
        "schema_version": "1.0",
        "template_version": "1.0.0",
        "description": "Best-effort PII leakage guard (hash-only reporting; no raw values returned).",
        "rules": [
            {"id": "no_pii_global", "type": "no_pii", "paths": ["*"], "patterns": ["email", "phone", "ssn", "credit_card"]},
        ],
    },
    "tool_result_envelope_v1": {
        "schema_version": "1.0",
        "template_version": "1.0.0",
        "description": "Agent/tool JSON result envelope: stable fields + status enum + safe identifiers + optional PII guard.",
        "rules": [
            {"id": "exists_status", "type": "exists", "path": "status"},
            {"id": "type_status", "type": "type_is", "path": "status", "expected": "string"},
            {"id": "regex_status", "type": "regex", "path": "status", "pattern": "^(ok|error)$"},

            {"id": "exists_tool", "type": "exists", "path": "tool"},
            {"id": "type_tool", "type": "type_is", "path": "tool", "expected": "string"},
            {"id": "regex_tool", "type": "regex", "path": "tool", "pattern": "^[a-z0-9_\\-]{2,64}$"},

            {"id": "exists_run_id", "type": "exists", "path": "run_id"},
            {"id": "type_run_id", "type": "type_is", "path": "run_id", "expected": "string"},
            {"id": "regex_run_id", "type": "regex", "path": "run_id", "pattern": "^[a-z0-9_\\-]{6,64}$"},

            {"id": "exists_result", "type": "exists", "path": "result"},

            {"id": "no_pii_result", "type": "no_pii", "paths": ["result"], "patterns": ["email", "phone", "ssn", "credit_card"]},
        ],
    },
    "csv_profile_quality_v1": {
        "schema_version": "1.0",
        "template_version": "1.0.0",
        "description": "Contract for deterministic CSV profile JSON (from tools/csv_profile_to_json.py). Ensures shape/nulls/types/samples exist and are sane.",
        "rules": [
            {"id": "exists_schema_version", "type": "exists", "path": "schema_version"},
            {"id": "type_schema_version", "type": "type_is", "path": "schema_version", "expected": "string"},
            {"id": "eq_schema_version", "type": "eq", "path": "schema_version", "value": "1.0"},

            {"id": "exists_source", "type": "exists", "path": "source"},
            {"id": "type_source", "type": "type_is", "path": "source", "expected": "object"},
            {"id": "exists_source_filename", "type": "exists", "path": "source.filename"},
            {"id": "type_source_filename", "type": "type_is", "path": "source.filename", "expected": "string"},
            {"id": "regex_source_filename", "type": "regex", "path": "source.filename", "pattern": "^.{1,255}$"},

            {"id": "exists_shape", "type": "exists", "path": "shape"},
            {"id": "type_shape", "type": "type_is", "path": "shape", "expected": "object"},
            {"id": "exists_shape_rows", "type": "exists", "path": "shape.rows"},
            {"id": "type_shape_rows", "type": "type_is", "path": "shape.rows", "expected": "number"},
            {"id": "range_shape_rows", "type": "range", "path": "shape.rows", "min": 1},
            {"id": "exists_shape_cols", "type": "exists", "path": "shape.cols"},
            {"id": "type_shape_cols", "type": "type_is", "path": "shape.cols", "expected": "number"},
            {"id": "range_shape_cols", "type": "range", "path": "shape.cols", "min": 1},
            {"id": "exists_shape_columns", "type": "exists", "path": "shape.columns"},
            {"id": "type_shape_columns", "type": "type_is", "path": "shape.columns", "expected": "array"},

            {"id": "exists_nulls", "type": "exists", "path": "nulls"},
            {"id": "type_nulls", "type": "type_is", "path": "nulls", "expected": "object"},
            {"id": "exists_nulls_by_column", "type": "exists", "path": "nulls.by_column"},
            {"id": "type_nulls_by_column", "type": "type_is", "path": "nulls.by_column", "expected": "object"},

            {"id": "exists_types", "type": "exists", "path": "types"},
            {"id": "type_types", "type": "type_is", "path": "types", "expected": "object"},

            {"id": "exists_samples", "type": "exists", "path": "samples"},
            {"id": "type_samples", "type": "type_is", "path": "samples", "expected": "object"},
            {"id": "exists_samples_preview", "type": "exists", "path": "samples.unique_values_preview"},
            {"id": "type_samples_preview", "type": "type_is", "path": "samples.unique_values_preview", "expected": "object"},

            {"id": "no_pii_global", "type": "no_pii", "paths": ["*"], "patterns": ["email", "phone"]},
        ],
    },
}


@router.get("/api/contracts/templates")
def list_contract_templates(ctx: dict = Security(require_tenant_match)) -> dict:
    templates = []
    for template_id, tmpl in CONTRACT_TEMPLATES.items():
        rules = tmpl.get("rules") or []
        templates.append(
            {
                "id": template_id,
                "schema_version": tmpl.get("schema_version", "1.0"),
                "template_version": tmpl.get("template_version", ""),
                "description": tmpl.get("description", ""),
                "rules_count": len(rules) if isinstance(rules, list) else 0,
            }
        )
    return {"templates": templates}


@router.get("/api/contracts/templates/{template_id}")
def get_contract_template(template_id: str, ctx: dict = Security(require_tenant_match)) -> dict:
    tmpl = CONTRACT_TEMPLATES.get(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail={"code": "TEMPLATE_NOT_FOUND", "message": "Template not found"})

    # Return full template (safe: static, no customer data)
    return {"id": template_id, "template": tmpl}


@router.post("/api/contracts/validate", response_model=ValidateResponse)
def validate_with_contract_template(
    request: Request,
    req_body: ContractTemplateValidateRequest,
    ctx: dict = Security(require_tenant_match),
) -> ValidateResponse:
    """Validate baseline vs candidate using a stored contract template.

    This is a convenience endpoint for JSON automation onboarding.
    Internally it runs the deterministic contract engine (domain_kits/contract_invariants).
    """

    template = CONTRACT_TEMPLATES.get(req_body.template_id)
    if not template:
        raise HTTPException(
            status_code=404,
            detail={"code": "TEMPLATE_NOT_FOUND", "message": "Template not found"},
        )

    # Traceability
    trace_id = str(uuid.uuid4())
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    # Scope-gate verbose mode
    include_details_requested = bool(getattr(req_body, "include_details", False))
    include_details_allowed = _scopes_allow_details(ctx.get("scopes"))
    include_details_effective = include_details_requested and include_details_allowed

    enforcement_mode = _details_enforcement_mode()
    if include_details_requested and (not include_details_allowed) and enforcement_mode == "strict":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "DETAILS_NOT_ALLOWED",
                "message": "include_details requires an API key scope (details/verbose/debug)",
            },
        )

    baseline_obj = req_body.baseline_output or {}
    candidate_obj = req_body.candidate_output or {}
    contract_obj = dict(template)

    contract_eval = evaluate_contract(
        baseline=baseline_obj,
        candidate=candidate_obj,
        contract=contract_obj,
    )

    total_checks = int(contract_eval.get("total_checks") or 0)
    failed_checks = int(contract_eval.get("failed_checks") or 0)
    pass_rate = float(contract_eval.get("pass_rate") or 0.0)
    match = (failed_checks == 0) and (total_checks > 0)

    # Deterministic, safe scoring mapping
    risk_score = max(0.0, min(10.0, 10.0 * pass_rate))
    confidence = 95.0 if match else max(10.0, min(90.0, 50.0 + 40.0 * pass_rate))
    category = "low" if pass_rate >= 0.9 else "medium" if pass_rate >= 0.6 else "high"
    recommendation = "APPROVE" if pass_rate >= 0.95 else "REVIEW" if pass_rate >= 0.7 else "REJECT"

    # Hashes for evidence
    baseline_hash = compute_hash(baseline_obj)
    candidate_hash = compute_hash(candidate_obj)
    test_data_hash = compute_hash(
        {
            "test_data": (req_body.test_data or {}),
            "template_id": req_body.template_id,
            "contract": contract_obj,
        }
    )

    details = None
    explanation = None
    if include_details_effective:
        failed_rules = [c for c in (contract_eval.get("checks") or []) if not c.get("ok")]
        explanation = "Contract/invariant checks failed" if failed_rules else "All contract/invariant checks passed"
        details = {
            "template_id": req_body.template_id,
            "checks": contract_eval.get("checks"),
            "failed_rule_count": len(failed_rules),
        }

    evidence = EvidenceBlock(
        baseline_hash=baseline_hash,
        candidate_hash=candidate_hash,
        test_data_hash=test_data_hash,
        timestamp=datetime.utcnow().isoformat() + "Z",
        domain="contract_invariants",
        explanation=explanation if include_details_effective else None,
        details=details if include_details_effective else None,
    )

    safe_config: dict = {
        "mode": "contract_invariants",
        # Optional policy stamping (metadata-only).
        "policy_id": (os.getenv("LLMLAB_POLICY_ID") or None),
        "policy_version": (os.getenv("LLMLAB_POLICY_VERSION") or None),
        "template_id": req_body.template_id,
        "template_schema_version": str(contract_obj.get("schema_version") or ""),
        "template_version": str(contract_obj.get("template_version") or ""),
        "include_details": bool(include_details_effective),
        "include_details_requested": bool(include_details_requested),
        "details_enforcement": enforcement_mode,
        "contract_hash": compute_hash(contract_obj),
    }
    safe_config = {k: v for k, v in safe_config.items() if v}

    tenant_id = ctx.get("tenant_id")
    partner_id = request.headers.get("X-Partner-ID")
    customer_id = request.headers.get("X-Customer-ID")
    tenant_context = {
        "tenant_id_hash": _safe_hash_str(tenant_id),
        "partner_id_hash": _safe_hash_str(partner_id),
        "customer_id_hash": _safe_hash_str(customer_id),
    }
    tenant_context = {k: v for k, v in tenant_context.items() if v is not None}
    if not tenant_context:
        tenant_context = None

    evidence_pack = EvidencePack(
        schema_version="1.0",
        generated_at=datetime.utcnow().isoformat() + "Z",
        trace_id=trace_id,
        request_id=request_id,
        domain="contract_invariants",
        mode="contract_invariants",
        api_version=req_body.api_version,
        build_commit=os.getenv("BUILD_COMMIT"),
        baseline_hash=baseline_hash,
        candidate_hash=candidate_hash,
        test_data_hash=test_data_hash,
        risk=RiskAssessment(score=risk_score, category=category, confidence=confidence),
        summary=SummaryStats(pass_rate=pass_rate, total_checks=total_checks, failed_checks=failed_checks),
        recommendation=recommendation,
        config=safe_config,
        tenant_context=tenant_context,
        topology=get_topology_indicator(),
    )

    payload_for_signing = evidence_pack.model_dump(mode="json")
    payload_for_signing.pop("signature", None)
    payload_for_signing.pop("signature_alg", None)
    signed = sign_payload(payload_for_signing)
    if signed:
        alg, sig = signed
        evidence_pack.signature_alg = alg
        evidence_pack.signature = sig

    resp = ValidateResponse(
        trace_id=trace_id,
        request_id=request_id,
        status="ok",
        risk=RiskAssessment(score=risk_score, category=category, confidence=confidence),
        summary=SummaryStats(pass_rate=pass_rate, total_checks=total_checks, failed_checks=failed_checks),
        recommendation=recommendation,
        evidence=evidence,
        evidence_pack=evidence_pack,
    )
    return resp
