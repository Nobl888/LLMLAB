# Local Client Test Runbook (step-by-step)

Goal: test the service like a real customer *before* GitHub Actions is enabled.

This runbook assumes you have a deployed base URL, tenant id, and API key.

## 0) Set env vars (your client config)

```bash
export LLMLAB_API_BASE_URL="https://<your-service>"   # or http://localhost:8000
export LLMLAB_TENANT_ID="<tenant-uuid>"
export LLMLAB_API_KEY="llm_<...>"
```

## 0.1) Render deployment sanity (what must be enabled)

If you’re deploying on Render, these settings determine whether the key bootstrap and ensemble endpoints exist.
  -d '{
    "suite_id": "superstore_kpi_profit_artifact_v1",
    "baseline_output": {"total_profit": 123.45},
    "candidate_output": {"total_profit": 123.45},
    "include_details": false,
    "api_version": "1.0"
  }' | cat
  - Set `ENABLE_ENSEMBLE_API=true` and redeploy to expose ensemble endpoints.
- `LLMLAB_TOPOLOGY_BUCKET` (optional; coarse governance signal)
  - If set to `LOW|MEDIUM|HIGH`, the service will include `evidence_pack.topology.diversity_bucket` in responses.
  - This is intentionally coarse (safe to expose). Do not set algorithm-family identifiers here.
- `LLMLAB_TOPOLOGY_VERSION` (optional)
  - Free-form version string for change control (e.g., `2025-12-27`).
  - Included in `evidence_pack.topology.version` when present.
- `DATABASE_URL`
  - Only required if your deployment mode uses a DB for persistence/audit.
  - Confirm it exists, points to the intended Render Postgres instance, and that it’s marked **Secret** in Render.
  - For first boot (or migrations), set `DB_INIT_ON_STARTUP=1` so the service can initialize required tables.
- Python version
  - Render’s Python runtime is determined by the service runtime and/or a `PYTHON_VERSION` env var (if your build uses it).
  - Verify the effective version in **Deploy → Build Logs** (look for the Python version line) and ensure it matches what your repo expects.

After changing env vars in Render:

1) Click **Manual Deploy** (or restart) so the new env is applied.
2) Re-run the checks in sections 0b / 1 / 0.2 below.

## 0.2) Post-deploy route availability checks

These checks confirm that your deployed service actually mounted the expected routes.

### 0.2a) OpenAPI has expected paths

```bash
curl -sS "$LLMLAB_API_BASE_URL/openapi.json" | python - <<'PY'
import json, sys
spec = json.load(sys.stdin)
paths = sorted((spec.get('paths') or {}).keys())
print("total_paths:", len(paths))
for p in paths:
  if p.startswith("/api/ensemble"):
    print("ensemble_path:", p)
PY
```

Expected:
- If `ENABLE_ENSEMBLE_API=true`, you should see at least one `ensemble_path: /api/ensemble/...` line.
- If you see none, the env var is not applied (or the build doesn’t include the routes).

### 0.2b) Smoke route is gated (expected behavior)

Without a smoke key, `/_smoke` should be hidden.

```bash
curl -sS -i "$LLMLAB_API_BASE_URL/_smoke" | head -n 20
```

Expected: `404` (stealth hide) or an auth-style failure depending on configuration.

## 0d) Privacy-first onboarding (plain terms)

If your source data may contain sensitive information (PII/customer records), the recommended workflow is:

1) **Run your code locally (or in your own CI)**
- LLMLAB is a validation gate: it requires zero access to your source systems.

2) **Pre-process locally to minimize data**
- Strip/mask sensitive columns.
- Prefer sending **summaries/hashes** or a “profile JSON” instead of raw rows.

3) **Dry-run to verify what would be sent**
- Before you enable CI, ensure your client can print the target URL and payload shape and (optionally) save the outbound JSON to disk without making a network call.

4) **Enforce a PII guard contract**
- Use template `no_pii_guard_v1` so the service best-effort rejects artifacts that look like they contain PII patterns.
- This is pattern-based and should be paired with local redaction.

### 0e) Copy/paste skeleton: local preprocess + dry-run (local-only)

This is a minimal pattern you can adapt in your own repo. It reads a CSV locally, drops likely-sensitive columns, and prints a small JSON profile.

```bash
python - <<'PY'
import csv, json

CSV_PATH = "./your.csv"  # change me
DROP = {"name","first_name","last_name","email","phone","ssn","address"}

with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
  reader = csv.DictReader(f)
  cols = []
  for c in (reader.fieldnames or []):
    if c in DROP:
      continue
    cols.append(c)
  nulls = {c: 0 for c in cols}
  rows = 0
  for row in reader:
    rows += 1
    for c in cols:
      v = (row.get(c) or "").strip()
      if v == "":
        nulls[c] += 1

profile = {
  "schema_version": "1.0",
  "shape": {"rows": rows, "cols": len(cols), "columns": cols},
  "nulls": {"by_column": nulls},
  "note": "Minimized profile only (raw rows remain local).",
}

print(json.dumps(profile, indent=2, sort_keys=True))
PY
```

If you need a tenant id + API key, use the smoke-key gated bootstrap flow:

### 0a) Load Smoke Key into your terminal (hidden input)

Copy `SMOKE_KEY` from your Render Environment and run:

```bash
stty -echo; printf "SMOKE_KEY: "; IFS= read -r SMOKE_KEY; stty echo; printf "\n"; export SMOKE_KEY
```

### 0b) Confirm Smoke Key works

```bash
curl -sS "$LLMLAB_API_BASE_URL/_smoke" \
  -H "X-Smoke-Key: $SMOKE_KEY" | cat
```

Expected: JSON with `status: ok`.

### 0c) Bootstrap tenant + API key (admin-only, smoke-key gated)

```bash
curl -sS -X POST "$LLMLAB_API_BASE_URL/admin/keys/bootstrap" \
  -H "X-Smoke-Key: $SMOKE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tenant_name":"local-test","scopes":""}' | cat
```

Copy values from the response:

```bash
export LLMLAB_TENANT_ID="<tenant_id-from-response>"
stty -echo; printf "LLMLAB_API_KEY: "; IFS= read -r LLMLAB_API_KEY; stty echo; printf "\n"; export LLMLAB_API_KEY
```

## 1) Health check

```bash
curl -sS "$LLMLAB_API_BASE_URL/health" | cat
```

Expected: JSON with `status`/service metadata.

If Postgres is enabled in your deployment:

```bash
curl -sS "$LLMLAB_API_BASE_URL/health/db" | cat
```

Expected: JSON with `status: ok`.

CI note: you can require DB health in GitHub Actions by setting repo variable `LLMLAB_REQUIRE_DB_HEALTH=true`.

## 2) Happy-path validate (hosted-safe contract templates)

Customer code executes on customer infrastructure; the service validates structured artifacts.

```bash
curl -sS -X POST "$LLMLAB_API_BASE_URL/api/contracts/validate" \
  -H "Authorization: Bearer $LLMLAB_API_KEY" \
  -H "X-Tenant-ID: $LLMLAB_TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "no_pii_guard_v1",
    "baseline_output": {"invoice_id":"INV-1","total":123.45,"currency":"EUR"},
    "candidate_output": {"invoice_id":"INV-1","total":123.45,"currency":"EUR"},
    "test_data": {"suite":"smoke_contract_templates"},
    "include_details": false,
    "api_version": "1.0"
  }' | cat
```

Expected:
- `status: ok`
- `trace_id` present
- `evidence.baseline_hash` / `evidence.candidate_hash` / `evidence.test_data_hash` present
- `recommendation` is one of APPROVE/REVIEW/REJECT

## 2b) Ensemble gate (suite-based regression)

This requires `ENABLE_ENSEMBLE_API=true` on the deployed service.

### 2b.1) List available suites

Note: this endpoint is tenant-authenticated, so missing/invalid auth may return a stealth `Not found`.

```bash
curl -sS "$LLMLAB_API_BASE_URL/api/ensemble/suites" \
  -H "Authorization: Bearer $LLMLAB_API_KEY" \
  -H "X-Tenant-ID: $LLMLAB_TENANT_ID" | cat
```

### 2b.2) Run a hosted-safe ensemble validation

Use the artifact-only suite (no code execution): `superstore_kpi_profit_artifact_v1`.

```bash
curl -sS -X POST "$LLMLAB_API_BASE_URL/api/ensemble/validate" \
  -H "Authorization: Bearer $LLMLAB_API_KEY" \
  -H "X-Tenant-ID: $LLMLAB_TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "suite_id": "superstore_kpi_profit_artifact_v1",
    "baseline_output": {"total_profit": 123.45},
    "candidate_output": {"total_profit": 123.45},
    "include_details": false,
    "api_version": "1.0"
  }' | cat
```

Tip: you can also run a saved payload file via:

```bash
bash scripts/run_validate_contract.sh templates/client/validate_contract_invoice.json
```

### 3b) Wrong tenant id

```bash
curl -sS -X POST "$LLMLAB_API_BASE_URL/api/contracts/validate" \
  -H "Authorization: Bearer $LLMLAB_API_KEY" \
  -H "X-Tenant-ID: 00000000-0000-0000-0000-000000000000" \
  -H "Content-Type: application/json" \
  -d '{"template_id":"no_pii_guard_v1","baseline_output":{},"candidate_output":{},"api_version":"1.0"}' | cat
```

Expected: `TENANT_MISMATCH` (403).

### 3c) Missing/invalid API key

```bash
curl -sS -X POST "$LLMLAB_API_BASE_URL/api/contracts/validate" \
  -H "X-Tenant-ID: $LLMLAB_TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{"template_id":"no_pii_guard_v1","baseline_output":{},"candidate_output":{},"api_version":"1.0"}' | cat
```

Expected: stealth 404 (route hidden).

## 4) Optional: verify evidence pack signatures

Only works if the service sets `EVIDENCE_SIGNING_KEY`.

1) Run a validate call and capture `evidence_pack` from the response.
2) Post it to `/api/evidence/verify`:

```bash
curl -sS -X POST "$LLMLAB_API_BASE_URL/api/evidence/verify" \
  -H "Authorization: Bearer $LLMLAB_API_KEY" \
  -H "X-Tenant-ID: $LLMLAB_TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{"evidence_pack": {"schema_version":"1.0","generated_at":"...","trace_id":"...","signature_alg":"hmac-sha256","signature":"..."}}' | cat
```

Expected:
- `verified: true` when configured and untampered.

## 5) Tiny automation option

Run the included smoke client:

```bash
python tools/client/smoke_validate_contract.py
python tools/client/smoke_validate_ensemble.py
```

Optionally require that the server emits a coarse topology indicator:

```bash
export LLMLAB_REQUIRE_TOPOLOGY=true
python tools/client/smoke_validate_contract.py
python tools/client/smoke_validate_ensemble.py
```
