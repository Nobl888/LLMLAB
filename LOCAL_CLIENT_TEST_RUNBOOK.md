# Local Client Test Runbook (step-by-step)

Goal: test the service like a real customer *before* GitHub Actions is enabled.

This runbook assumes you have a deployed base URL, tenant id, and API key.

## 0) Set env vars (your client config)

```bash
export LLMLAB_API_BASE_URL="https://<your-service>"   # or http://localhost:8000
export LLMLAB_TENANT_ID="<tenant-uuid>"
export LLMLAB_API_KEY="llm_<...>"
```

If you *don't have* a tenant id + API key yet, use the smoke-key gated bootstrap flow:

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

## 2) Happy-path validate (hosted-safe contract mode)

This does **no code execution** on the service.

```bash
curl -sS -X POST "$LLMLAB_API_BASE_URL/api/validate" \
  -H "Authorization: Bearer $LLMLAB_API_KEY" \
  -H "X-Tenant-ID: $LLMLAB_TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "baseline_output": {"invoice_id":"INV-1","total":123.45,"currency":"EUR"},
    "candidate_output": {"invoice_id":"INV-1","total":123.45,"currency":"EUR"},
    "contract": {
      "schema_version": "1.0",
      "rules": [
        {"id":"inv.invoice_id.exists","type":"exists","path":"invoice_id"},
        {"id":"inv.total.type","type":"type_is","path":"total","expected":"number"},
        {"id":"inv.total.nonneg","type":"range","path":"total","min":0}
      ]
    },
    "test_data": {"suite":"smoke_contract"},
    "include_details": false,
    "api_version": "1.0"
  }' | cat
```

Expected:
- `status: ok`
- `trace_id` present
- `evidence.baseline_hash` / `evidence.candidate_hash` / `evidence.test_data_hash` present
- `recommendation` is one of APPROVE/REVIEW/REJECT

## 3) Negative tests (security controls)

### 3a) Missing tenant header

```bash
curl -sS -X POST "$LLMLAB_API_BASE_URL/api/validate" \
  -H "Authorization: Bearer $LLMLAB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"baseline_output":{},"candidate_output":{},"api_version":"1.0"}' | cat
```

Expected: error about missing `X-Tenant-ID`.

### 3b) Wrong tenant id

```bash
curl -sS -X POST "$LLMLAB_API_BASE_URL/api/validate" \
  -H "Authorization: Bearer $LLMLAB_API_KEY" \
  -H "X-Tenant-ID: 00000000-0000-0000-0000-000000000000" \
  -H "Content-Type: application/json" \
  -d '{"baseline_output":{},"candidate_output":{},"api_version":"1.0"}' | cat
```

Expected: `TENANT_MISMATCH` (403).

### 3c) Missing/invalid API key

```bash
curl -sS -X POST "$LLMLAB_API_BASE_URL/api/validate" \
  -H "X-Tenant-ID: $LLMLAB_TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{"baseline_output":{},"candidate_output":{},"api_version":"1.0"}' | cat
```

Expected: stealth 404 (route appears not found).

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
```
