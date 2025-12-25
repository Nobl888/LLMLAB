"""Client-style smoke test for hosted-safe contract validation.

- Uses stdlib-only HTTP client in tools/ci/llmlab_http.py
- Exercises: Authorization + X-Tenant-ID + /api/contracts/validate + evidence_pack + evidence hashes

Env vars:
- LLMLAB_API_BASE_URL (preferred) or LLMLAB_API_BASE
- LLMLAB_API_KEY
- LLMLAB_TENANT_ID

Exit codes:
- 0: request succeeded (status=ok)
- 1: error
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from tools.ci.llmlab_http import post_json


def main() -> int:
    payload = {
        "template_id": "json_output_basic_v1",
        "baseline_output": {"meta": {"run_id": "run_123abc"}},
        "candidate_output": {"meta": {"run_id": "run_123abc"}},
        "test_data": {"suite": "smoke_contract_templates"},
        "include_details": False,
        "api_version": "1.0",
    }

    resp = post_json("/api/contracts/validate", payload)

    status = str(resp.get("status") or "")
    trace_id = resp.get("trace_id")
    rec = resp.get("recommendation")
    evidence = resp.get("evidence") or {}
    evidence_pack = resp.get("evidence_pack") or {}

    required = [
        ("trace_id", trace_id),
        ("evidence.baseline_hash", evidence.get("baseline_hash")),
        ("evidence.candidate_hash", evidence.get("candidate_hash")),
        ("evidence.test_data_hash", evidence.get("test_data_hash")),
        ("evidence_pack.schema_version", evidence_pack.get("schema_version")),
        ("evidence_pack.domain", evidence_pack.get("domain")),
    ]
    missing = [name for name, val in required if not val]

    print(json.dumps({"status": status, "trace_id": trace_id, "recommendation": rec}, indent=2))

    if status != "ok":
        print("ERROR: status != ok", file=sys.stderr)
        return 1
    if missing:
        print(f"ERROR: missing required fields: {missing}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
