# Evidence artifact example (redacted)

This is what “attachable evidence” looks like for a typical CI gate run.

Why this format works in real reviews:

- Traceable: `trace_id` lets you find logs without sharing payloads.
- Portable: hashes can be stored in PR comments/tickets and compared later.
- Data-minimized: evidence can be hash-first by default.

## Example: `/api/validate` response (contract mode)

```json
{
  "trace_id": "943098ab-660d-405f-b458-0fd2c758825d",
  "request_id": "82f80bac-aaa2-400b-af23-3a9d79fdaf34",
  "status": "ok",
  "risk": {"score": 8.7, "category": "low", "confidence": 94.0},
  "recommendation": "APPROVE_WITH_MONITORING",
  "evidence": {
    "baseline_hash": "sha256:38f907cff725",
    "candidate_hash": "sha256:38f907cff725",
    "test_data_hash": "sha256:855fffdc41c4",
    "timestamp": "2025-12-25T20:30:59.215656Z",
    "domain": "analytics_kpi"
  }
}
```

## What to attach to a PR (minimum)

- The JSON response (above)
- A deployment identity check (so reviewers can confirm what code ran): `GET /health`

## How teams use this

- Paste the `trace_id` into a PR comment or ticket.
- Store the JSON as a CI artifact (so reviewers can reproduce the exact decision inputs by hash).
- Keep `include_details=false` in CI for safety; enable details only for private debugging.
