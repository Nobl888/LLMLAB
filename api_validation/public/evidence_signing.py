"""Evidence pack signing/verification.

Hosted-safe posture:
- Uses HMAC (shared secret) keyed by `EVIDENCE_SIGNING_KEY`.
- If the key is not configured, signing is simply skipped.
- Verification endpoint returns only boolean results (no secret material).

Note: HMAC is sufficient for tamper detection for early partners.
If you later want public verifiability without sharing secrets, switch to
asymmetric signatures (e.g., Ed25519) and publish a verification key.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import os
from typing import Any, Dict, Optional, Tuple


def get_evidence_signing_key() -> Optional[bytes]:
    key = os.getenv("EVIDENCE_SIGNING_KEY")
    if not key:
        return None
    key = str(key).strip()
    if not key:
        return None
    return key.encode("utf-8")


def _canonical_json(payload: Dict[str, Any]) -> bytes:
    # Deterministic JSON encoding for signing.
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sign_payload(payload: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """Sign a payload; returns (alg, signature_hex) or None if not configured."""
    key = get_evidence_signing_key()
    if not key:
        return None

    msg = _canonical_json(payload)
    digest = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return ("hmac-sha256", digest)


def verify_signature(payload: Dict[str, Any], signature_alg: Any, signature: Any) -> bool:
    key = get_evidence_signing_key()
    if not key:
        return False

    if not signature_alg or not signature:
        return False

    alg = str(signature_alg).strip().lower()
    if alg != "hmac-sha256":
        return False

    provided = str(signature).strip().lower()
    if not provided:
        return False

    msg = _canonical_json(payload)
    expected = hmac.new(key, msg, hashlib.sha256).hexdigest().lower()
    return hmac.compare_digest(expected, provided)
