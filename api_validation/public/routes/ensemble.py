"""Ensemble regression gates.

Purpose:
- Provide a vendor-grade, portfolio-style regression gate (suite-based)
- Ship with two low-friction built-in suites:
  - Superstore KPI (total profit)
  - QQQ SMA crossover oracle agreement

Security posture:
- Requires tenant auth (Authorization + X-Tenant-ID)
- Returns hashes and aggregate diffs by default
- Verbose details are scope-gated (details/verbose/debug)

Notes:
- QQQ suite compares a candidate output CSV (uploaded fixture) against a packaged oracle CSV.
- Superstore suite runs baseline/candidate KPI modules against a packaged fixture.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import hashlib
import os
import uuid

import pandas as pd
from fastapi import APIRouter, HTTPException, Request, Security, status
from pydantic import BaseModel, Field
from typing import Any

from api_validation.public.routes.validate import (
    require_tenant_match,
    _resolve_fixture_storage_path,
    _safe_hash_str,
    _scopes_allow_details,
    _details_enforcement_mode,
    compute_hash,
)
from api_validation.public.evidence_signing import sign_payload
from api_validation.public.schemas import (
    ValidateResponse,
    RiskAssessment,
    SummaryStats,
    EvidenceBlock,
    EvidencePack,
)

from domain_kits.kpi_analytics.runner import KPIRunner
from domain_kits.kpi_analytics.normalizer import KPINormalizer
from domain_kits.kpi_analytics.comparator_config import ComparatorConfig

router = APIRouter(tags=["ensemble"])


@dataclass(frozen=True)
class SuiteDef:
    suite_id: str
    suite_version: str
    suite_type: str
    description: str


def _repo_root() -> Path:
    # api_validation/public/routes/ensemble.py -> repo root is 4 parents up
    return Path(__file__).resolve().parents[4]


def _sha256_file_fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()[:12]


SUITES: dict[str, SuiteDef] = {
    "superstore_kpi_total_profit_v1": SuiteDef(
        suite_id="superstore_kpi_total_profit_v1",
        suite_version="1.0.0",
        suite_type="kpi_analytics",
        description="(Self-hosted) Runs baseline vs candidate KPI module on packaged superstore_sales.csv and compares output with profit tolerances.",
    ),
    "superstore_kpi_profit_artifact_v1": SuiteDef(
        suite_id="superstore_kpi_profit_artifact_v1",
        suite_version="1.0.0",
        suite_type="kpi_artifact",
        description="(Hosted-safe) Compares submitted baseline_output vs candidate_output KPI artifacts using profit tolerances. No code execution.",
    ),
    "qqq_sma_crossover_oracle_v1": SuiteDef(
        suite_id="qqq_sma_crossover_oracle_v1",
        suite_version="1.0.0",
        suite_type="csv_oracle",
        description="Compares uploaded candidate QQQ strategy output CSV vs packaged qqq_strategy_oracle.csv (numeric column diffs under tolerance).",
    ),
}


class EnsembleValidateRequest(BaseModel):
    suite_id: str = Field(..., description="One of: superstore_kpi_total_profit_v1, qqq_sma_crossover_oracle_v1")

    # Superstore KPI suite inputs (server-side paths; intended for self-hosted or trusted environments)
    candidate_kpi_path: str | None = Field(None, description="Path to candidate KPI .py module with compute_kpi(df)")
    baseline_kpi_path: str | None = Field(None, description="Optional baseline KPI module path override")

    # Hosted-safe KPI artifacts (no code execution). Intended for SaaS mode.
    baseline_output: Any | None = Field(None, description="Baseline KPI artifact (e.g., scalar number or dict of numbers)")
    candidate_output: Any | None = Field(None, description="Candidate KPI artifact (e.g., scalar number or dict of numbers)")

    # QQQ suite inputs
    candidate_fixture_id: str | None = Field(None, description="Uploaded fixture_id pointing to candidate output CSV")

    include_details: bool = Field(False, description="If True, return suite-level details (scope-gated)")
    api_version: str = Field("1.0", description="API version for forward compatibility")


@router.get("/api/ensemble/suites")
def list_suites(ctx: dict = Security(require_tenant_match)) -> dict:
    out = []
    for suite_id, s in SUITES.items():
        if (
            suite_id == "superstore_kpi_total_profit_v1"
            and os.getenv("ALLOW_KPI_CODE_EXECUTION", "false").lower() != "true"
        ):
            continue
        out.append(
            {
                "id": suite_id,
                "suite_version": s.suite_version,
                "type": s.suite_type,
                "description": s.description,
            }
        )
    return {"suites": out}


def _risk_from_pass_rate(pass_rate: float) -> tuple[float, float, str, str]:
    pass_rate = max(0.0, min(1.0, float(pass_rate)))
    risk_score = max(0.0, min(10.0, 10.0 * pass_rate))
    category = "low" if pass_rate >= 0.9 else "medium" if pass_rate >= 0.6 else "high"
    confidence = 95.0 if pass_rate >= 0.999 else max(10.0, min(90.0, 50.0 + 40.0 * pass_rate))
    recommendation = "APPROVE" if pass_rate >= 0.95 else "REVIEW" if pass_rate >= 0.7 else "REJECT"
    return (risk_score, confidence, category, recommendation)


@router.post("/api/ensemble/validate", response_model=ValidateResponse)
def validate_ensemble(
    request: Request,
    req_body: EnsembleValidateRequest,
    ctx: dict = Security(require_tenant_match),
) -> ValidateResponse:
    suite = SUITES.get(req_body.suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail={"code": "SUITE_NOT_FOUND", "message": "Suite not found"})

    trace_id = str(uuid.uuid4())
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    include_details_requested = bool(req_body.include_details)
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

    repo_root = _repo_root()

    def _infer_artifact_type(value: Any) -> str:
        if value is None:
            return "unknown"
        if isinstance(value, bool):
            return "unknown"
        if isinstance(value, (int, float)):
            return "float"
        if isinstance(value, dict):
            return "dict"
        if isinstance(value, list):
            return "Series"
        return type(value).__name__

    if suite.suite_id == "qqq_sma_crossover_oracle_v1":
        if not req_body.candidate_fixture_id:
            raise HTTPException(status_code=400, detail={"code": "MISSING_CANDIDATE", "message": "candidate_fixture_id is required"})

        resolved = _resolve_fixture_storage_path(tenant_id=str(tenant_id), fixture_id=str(req_body.candidate_fixture_id))
        if not resolved:
            raise HTTPException(status_code=404, detail={"code": "FIXTURE_NOT_FOUND", "message": "Candidate fixture not found"})

        candidate_path, candidate_sha = resolved
        oracle_path = repo_root / "qqq_strategy_oracle.csv"
        if not oracle_path.exists():
            raise HTTPException(status_code=503, detail={"code": "ORACLE_NOT_AVAILABLE", "message": "QQQ oracle is not packaged on this service"})

        try:
            df_oracle = pd.read_csv(str(oracle_path))
            df_candidate = pd.read_csv(str(candidate_path))
        except Exception:
            raise HTTPException(status_code=400, detail={"code": "CSV_READ_FAILED", "message": "Failed to read oracle/candidate CSV"})

        expected_cols = ["Date", "AdjClose", "ret", "sma20", "sma50", "pos", "strat_ret", "equity"]
        numeric_cols = ["AdjClose", "ret", "sma20", "sma50", "pos", "strat_ret", "equity"]

        missing = [c for c in expected_cols if c not in df_candidate.columns]
        if missing:
            raise HTTPException(status_code=400, detail={"code": "CANDIDATE_SCHEMA_MISMATCH", "message": "Candidate missing required columns", "missing": missing})

        # Keep this deterministic. If length differs, we fail.
        if len(df_oracle) != len(df_candidate):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ROW_COUNT_MISMATCH",
                    "message": "Candidate row count does not match oracle",
                    "oracle_rows": int(len(df_oracle)),
                    "candidate_rows": int(len(df_candidate)),
                },
            )

        tol = float(os.getenv("QQQ_ORACLE_TOLERANCE", "1e-10"))

        per_col = []
        passed = 0
        for col in numeric_cols:
            if col not in df_oracle.columns or col not in df_candidate.columns:
                per_col.append({"col": col, "ok": False, "reason": "missing"})
                continue

            a = pd.to_numeric(df_oracle[col], errors="coerce")
            b = pd.to_numeric(df_candidate[col], errors="coerce")
            diff = (a - b).abs()
            max_abs = float(diff.max(skipna=True)) if len(diff) else 0.0
            mean_abs = float(diff.mean(skipna=True)) if len(diff) else 0.0
            ok = bool(max_abs <= tol)
            if ok:
                passed += 1
            per_col.append({"col": col, "ok": ok, "max_abs_diff": max_abs, "mean_abs_diff": mean_abs})

        total_checks = len(numeric_cols)
        failed_checks = total_checks - passed
        pass_rate = 0.0 if total_checks == 0 else passed / total_checks

        risk_score, confidence, category, recommendation = _risk_from_pass_rate(pass_rate)

        baseline_hash = _sha256_file_fingerprint(oracle_path)
        candidate_hash = "sha256:" + str(candidate_sha).replace("sha256:", "")[:12] if candidate_sha else compute_hash({"fixture_id": req_body.candidate_fixture_id})
        test_data_hash = compute_hash({"suite_id": suite.suite_id, "suite_version": suite.suite_version, "tolerance": tol})

        details = None
        explanation = None
        if include_details_effective:
            explanation = "QQQ oracle comparison" if failed_checks == 0 else "QQQ oracle divergence detected"
            details = {
                "suite_id": suite.suite_id,
                "suite_version": suite.suite_version,
                "tolerance": tol,
                "checks": per_col,
            }

        evidence = EvidenceBlock(
            baseline_hash=baseline_hash,
            candidate_hash=candidate_hash,
            test_data_hash=test_data_hash,
            timestamp=datetime.utcnow().isoformat() + "Z",
            domain="ensemble_gate",
            explanation=explanation if include_details_effective else None,
            details=details if include_details_effective else None,
        )

        safe_config: dict = {
            "mode": "ensemble",
            "suite_id": suite.suite_id,
            "suite_version": suite.suite_version,
            "suite_type": suite.suite_type,
            "oracle": "qqq_strategy_oracle.csv",
            "candidate_fixture_id": str(req_body.candidate_fixture_id),
            "tolerance": tol,
            "include_details": bool(include_details_effective),
            "include_details_requested": bool(include_details_requested),
            "details_enforcement": enforcement_mode,
            "policy_id": (os.getenv("LLMLAB_POLICY_ID") or None),
            "policy_version": (os.getenv("LLMLAB_POLICY_VERSION") or None),
        }
        safe_config = {k: v for k, v in safe_config.items() if v is not None and v != ""}

        evidence_pack = EvidencePack(
            schema_version="1.0",
            generated_at=datetime.utcnow().isoformat() + "Z",
            trace_id=trace_id,
            request_id=request_id,
            domain="ensemble_gate",
            mode="ensemble",
            api_version=req_body.api_version,
            build_commit=os.getenv("BUILD_COMMIT"),
            baseline_hash=baseline_hash,
            candidate_hash=candidate_hash,
            test_data_hash=test_data_hash,
            risk=RiskAssessment(score=risk_score, category=category, confidence=confidence),
            summary=SummaryStats(pass_rate=float(pass_rate), total_checks=int(total_checks), failed_checks=int(failed_checks)),
            recommendation=recommendation,
            config=safe_config,
            tenant_context=tenant_context,
        )

        payload_for_signing = evidence_pack.model_dump(mode="json")
        payload_for_signing.pop("signature", None)
        payload_for_signing.pop("signature_alg", None)
        signed = sign_payload(payload_for_signing)
        if signed:
            alg, sig = signed
            evidence_pack.signature_alg = alg
            evidence_pack.signature = sig

        return ValidateResponse(
            trace_id=trace_id,
            request_id=request_id,
            status="ok",
            risk=RiskAssessment(score=risk_score, category=category, confidence=confidence),
            summary=SummaryStats(pass_rate=float(pass_rate), total_checks=int(total_checks), failed_checks=int(failed_checks)),
            recommendation=recommendation,
            evidence=evidence,
            evidence_pack=evidence_pack,
        )

    if suite.suite_id == "superstore_kpi_total_profit_v1":
        if os.getenv("ALLOW_KPI_CODE_EXECUTION", "false").lower() != "true":
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "EXECUTION_DISABLED",
                    "message": "Server-side KPI execution is disabled on this service.",
                },
            )

        candidate_kpi_path = req_body.candidate_kpi_path
        if not candidate_kpi_path:
            raise HTTPException(status_code=400, detail={"code": "MISSING_CANDIDATE", "message": "candidate_kpi_path is required"})

        fixture_path = repo_root / "domain_kits" / "kpi_analytics" / "fixtures" / "superstore_sales.csv"
        if not fixture_path.exists():
            raise HTTPException(status_code=503, detail={"code": "FIXTURE_NOT_AVAILABLE", "message": "Superstore fixture is not packaged on this service"})

        baseline_path = Path(req_body.baseline_kpi_path) if req_body.baseline_kpi_path else (repo_root / "domain_kits" / "kpi_analytics" / "fixtures" / "kpi_oracle_baseline.py")
        if not baseline_path.exists():
            raise HTTPException(status_code=503, detail={"code": "BASELINE_NOT_AVAILABLE", "message": "Baseline KPI oracle is not packaged on this service"})

        runner = KPIRunner()
        normalizer = KPINormalizer()

        baseline_exec = runner.execute(str(baseline_path), str(fixture_path))
        candidate_exec = runner.execute(str(Path(candidate_kpi_path)), str(fixture_path))

        if baseline_exec.get("status") != "success":
            raise HTTPException(status_code=500, detail={"code": "BASELINE_EXEC_FAILED", "message": "Baseline KPI failed to execute"})
        if candidate_exec.get("status") != "success":
            raise HTTPException(status_code=400, detail={"code": "CANDIDATE_EXEC_FAILED", "message": candidate_exec.get("error") or "Candidate KPI failed"})

        baseline_norm = normalizer.normalize(baseline_exec.get("output"), baseline_exec.get("output_type") or "unknown")
        candidate_norm = normalizer.normalize(candidate_exec.get("output"), candidate_exec.get("output_type") or "unknown")

        tolerances = ComparatorConfig.for_profit_metrics().to_dict()
        comparison = normalizer.compare_normalized(baseline_norm, candidate_norm, tolerances)

        match = bool(comparison.get("match"))
        pass_rate = 1.0 if match else 0.0
        total_checks = 1
        failed_checks = 0 if match else 1

        risk_score, confidence, category, recommendation = _risk_from_pass_rate(pass_rate)

        baseline_hash = compute_hash({"suite": suite.suite_id, "baseline_output": baseline_norm})
        candidate_hash = compute_hash({"suite": suite.suite_id, "candidate_output": candidate_norm})
        test_data_hash = compute_hash({"fixture": str(fixture_path.name), "tolerances": tolerances, "suite_version": suite.suite_version})

        details = None
        explanation = None
        if include_details_effective:
            explanation = "KPI match" if match else "KPI drift exceeded tolerance"
            details = {
                "suite_id": suite.suite_id,
                "suite_version": suite.suite_version,
                "fixture": "superstore_sales.csv",
                "baseline": {"status": baseline_norm.get("status"), "type": baseline_norm.get("type")},
                "candidate": {"status": candidate_norm.get("status"), "type": candidate_norm.get("type")},
                "comparison": {k: v for k, v in comparison.items() if k not in {"baseline_value", "candidate_value"}},
            }

        evidence = EvidenceBlock(
            baseline_hash=baseline_hash,
            candidate_hash=candidate_hash,
            test_data_hash=test_data_hash,
            timestamp=datetime.utcnow().isoformat() + "Z",
            domain="ensemble_gate",
            explanation=explanation if include_details_effective else None,
            details=details if include_details_effective else None,
        )

        safe_config: dict = {
            "mode": "ensemble",
            "suite_id": suite.suite_id,
            "suite_version": suite.suite_version,
            "suite_type": suite.suite_type,
            "fixture": "superstore_sales.csv",
            "baseline_kpi": str(baseline_path.name),
            "candidate_kpi": str(Path(candidate_kpi_path).name),
            "tolerances": tolerances,
            "include_details": bool(include_details_effective),
            "include_details_requested": bool(include_details_requested),
            "details_enforcement": enforcement_mode,
            "policy_id": (os.getenv("LLMLAB_POLICY_ID") or None),
            "policy_version": (os.getenv("LLMLAB_POLICY_VERSION") or None),
        }
        safe_config = {k: v for k, v in safe_config.items() if v is not None and v != ""}

        evidence_pack = EvidencePack(
            schema_version="1.0",
            generated_at=datetime.utcnow().isoformat() + "Z",
            trace_id=trace_id,
            request_id=request_id,
            domain="ensemble_gate",
            mode="ensemble",
            api_version=req_body.api_version,
            build_commit=os.getenv("BUILD_COMMIT"),
            baseline_hash=baseline_hash,
            candidate_hash=candidate_hash,
            test_data_hash=test_data_hash,
            risk=RiskAssessment(score=risk_score, category=category, confidence=confidence),
            summary=SummaryStats(pass_rate=float(pass_rate), total_checks=int(total_checks), failed_checks=int(failed_checks)),
            recommendation=recommendation,
            config=safe_config,
            tenant_context=tenant_context,
        )

        payload_for_signing = evidence_pack.model_dump(mode="json")
        payload_for_signing.pop("signature", None)
        payload_for_signing.pop("signature_alg", None)
        signed = sign_payload(payload_for_signing)
        if signed:
            alg, sig = signed
            evidence_pack.signature_alg = alg
            evidence_pack.signature = sig

        return ValidateResponse(
            trace_id=trace_id,
            request_id=request_id,
            status="ok",
            risk=RiskAssessment(score=risk_score, category=category, confidence=confidence),
            summary=SummaryStats(pass_rate=float(pass_rate), total_checks=int(total_checks), failed_checks=int(failed_checks)),
            recommendation=recommendation,
            evidence=evidence,
            evidence_pack=evidence_pack,
        )

    if suite.suite_id == "superstore_kpi_profit_artifact_v1":
        # Hosted-safe mode: no code execution; compare submitted artifacts.
        if req_body.baseline_output is None or req_body.candidate_output is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "MISSING_ARTIFACTS",
                    "message": "baseline_output and candidate_output are required for this suite",
                },
            )

        normalizer = KPINormalizer()
        tolerances = ComparatorConfig.for_profit_metrics().to_dict()

        baseline_type = _infer_artifact_type(req_body.baseline_output)
        candidate_type = _infer_artifact_type(req_body.candidate_output)

        baseline_norm = normalizer.normalize(req_body.baseline_output, baseline_type)
        candidate_norm = normalizer.normalize(req_body.candidate_output, candidate_type)
        comparison = normalizer.compare_normalized(baseline_norm, candidate_norm, tolerances)

        match = bool(comparison.get("match"))
        pass_rate = 1.0 if match else 0.0
        total_checks = 1
        failed_checks = 0 if match else 1

        risk_score, confidence, category, recommendation = _risk_from_pass_rate(pass_rate)

        baseline_hash = compute_hash({"suite": suite.suite_id, "baseline": baseline_norm})
        candidate_hash = compute_hash({"suite": suite.suite_id, "candidate": candidate_norm})
        test_data_hash = compute_hash({"tolerances": tolerances, "suite_version": suite.suite_version})

        details = None
        explanation = None
        if include_details_effective:
            explanation = "KPI artifact match" if match else "KPI artifact drift exceeded tolerance"
            details = {
                "suite_id": suite.suite_id,
                "suite_version": suite.suite_version,
                "tolerances": tolerances,
                "baseline": {"status": baseline_norm.get("status"), "type": baseline_norm.get("type")},
                "candidate": {"status": candidate_norm.get("status"), "type": candidate_norm.get("type")},
                "comparison": {k: v for k, v in comparison.items() if k not in {"baseline_value", "candidate_value"}},
            }

        evidence = EvidenceBlock(
            baseline_hash=baseline_hash,
            candidate_hash=candidate_hash,
            test_data_hash=test_data_hash,
            timestamp=datetime.utcnow().isoformat() + "Z",
            domain="ensemble_gate",
            explanation=explanation if include_details_effective else None,
            details=details if include_details_effective else None,
        )

        safe_config: dict = {
            "mode": "ensemble",
            "suite_id": suite.suite_id,
            "suite_version": suite.suite_version,
            "suite_type": suite.suite_type,
            "tolerances": tolerances,
            "include_details": bool(include_details_effective),
            "include_details_requested": bool(include_details_requested),
            "details_enforcement": enforcement_mode,
            "policy_id": (os.getenv("LLMLAB_POLICY_ID") or None),
            "policy_version": (os.getenv("LLMLAB_POLICY_VERSION") or None),
        }
        safe_config = {k: v for k, v in safe_config.items() if v is not None and v != ""}

        evidence_pack = EvidencePack(
            schema_version="1.0",
            generated_at=datetime.utcnow().isoformat() + "Z",
            trace_id=trace_id,
            request_id=request_id,
            domain="ensemble_gate",
            mode="ensemble",
            api_version=req_body.api_version,
            build_commit=os.getenv("BUILD_COMMIT"),
            baseline_hash=baseline_hash,
            candidate_hash=candidate_hash,
            test_data_hash=test_data_hash,
            risk=RiskAssessment(score=risk_score, category=category, confidence=confidence),
            summary=SummaryStats(pass_rate=float(pass_rate), total_checks=int(total_checks), failed_checks=int(failed_checks)),
            recommendation=recommendation,
            config=safe_config,
            tenant_context=tenant_context,
        )

        payload_for_signing = evidence_pack.model_dump(mode="json")
        payload_for_signing.pop("signature", None)
        payload_for_signing.pop("signature_alg", None)
        signed = sign_payload(payload_for_signing)
        if signed:
            alg, sig = signed
            evidence_pack.signature_alg = alg
            evidence_pack.signature = sig

        return ValidateResponse(
            trace_id=trace_id,
            request_id=request_id,
            status="ok",
            risk=RiskAssessment(score=risk_score, category=category, confidence=confidence),
            summary=SummaryStats(pass_rate=float(pass_rate), total_checks=int(total_checks), failed_checks=int(failed_checks)),
            recommendation=recommendation,
            evidence=evidence,
            evidence_pack=evidence_pack,
        )

    raise HTTPException(status_code=400, detail={"code": "SUITE_NOT_IMPLEMENTED", "message": "Suite not implemented"})
