"""Evidence verification endpoints.

Purpose:
- Allow CI systems and compliance tooling to verify that an EvidencePack was
  issued by this service and has not been tampered with.

Security posture:
- Requires tenant auth (Authorization + X-Tenant-ID)
- Does not return signing secrets or computed signatures
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Security

from api_validation.public.evidence_signing import get_evidence_signing_key, verify_signature
from api_validation.public.schemas import EvidenceVerifyRequest, EvidenceVerifyResponse
from api_validation.public.routes.validate import require_tenant_match

router = APIRouter(tags=["evidence"])


@router.post("/api/evidence/verify", response_model=EvidenceVerifyResponse)
def verify_evidence_pack(
    req: EvidenceVerifyRequest,
    request: Request,
    ctx: dict = Security(require_tenant_match),
) -> EvidenceVerifyResponse:
    trace_id = getattr(request.state, "trace_id", None) or "-"

    if not get_evidence_signing_key():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SIGNING_NOT_CONFIGURED",
                "message": "Evidence signing key is not configured on this service.",
            },
        )

    evidence_pack = req.evidence_pack or {}
    signature_alg = evidence_pack.get("signature_alg")
    signature = evidence_pack.get("signature")

    payload_for_verification = dict(evidence_pack)
    payload_for_verification.pop("signature", None)
    payload_for_verification.pop("signature_alg", None)

    ok = verify_signature(
        payload=payload_for_verification,
        signature_alg=signature_alg,
        signature=signature,
    )

    reason = None
    if not signature_alg or not signature:
        reason = "SIGNATURE_MISSING"
    elif str(signature_alg).strip().lower() != "hmac-sha256":
        reason = "UNSUPPORTED_ALGORITHM"
    elif not ok:
        reason = "SIGNATURE_INVALID"

    return EvidenceVerifyResponse(
        trace_id=trace_id,
        verified=bool(ok),
        signature_alg=str(signature_alg) if signature_alg else None,
        reason=reason,
    )
