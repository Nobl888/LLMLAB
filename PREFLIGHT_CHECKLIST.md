# LLMLAB Preflight Checklist (Deploy + CI + Quotas)

Last updated: 2026-01-02

This checklist is the minimal “ship it safely” preflight for LLMLAB.
It is designed to be:
- **Hosted-safe** (no customer code execution required)
- **Deterministic** for CI (offline gates)
- **Deploy-verifiable** (Render commit identity via `GET /health`)

---

## 1) Repo + deploy alignment (prevents "works locally, fails on Render")

### A) Working tree is clean

```bash
git status --porcelain
```
Expected: no output.

### B) No untracked Python modules (common Render boot failure)

```bash
git ls-files --others --exclude-standard | grep -E '\.py$' || true
```
Expected: empty. If you see any `.py` files, they will **not** deploy to Render until committed.

### C) No tracked bytecode / caches

```bash
git ls-files | grep -E '(__pycache__/|\.pyc$|\.pyo$)' || true
```
Expected: empty.

---

## 2) Offline CI gates (run locally or trust GitHub Actions)

These commands mirror [.github/workflows/llmlab_ci_gates.yml](../.github/workflows/llmlab_ci_gates.yml).

### A) Syntax + import gates

```bash
python -m compileall -q api_validation tools domain_kits
python -c "import api_validation.public.routes.health"
python -c "import api_validation.public.routes.validate"
python -c "import api_validation.public.routes.contracts"
python -c "import api_validation.public.routes.evidence"
python -c "import domain_kits.contract_invariants.engine"
```

### B) Offline oracle gate (QQQ quant kit)

```bash
python tools/qqq_canonical_indicators/build_oracles.py --input qqq_clean.csv --indicator composite_v1
python tools/qqq_canonical_indicators/runner.py --indicator composite_v1 --candidates-dir tasks/qqq_canonical_indicators/example_candidates --tolerance 1e-12
```

### C) Bayes wind-tunnel gates

```bash
python tools/wind_tunnel_bayes/ci_gate_hmm.py
python tools/wind_tunnel_bayes/ci_gate_hmm_ood_shift.py
python tools/wind_tunnel_bayes/ci_gate_coin.py
python tools/wind_tunnel_bayes/ci_gate_bijection.py
```

### D) Tabular calibration gate (Telco churn)

```bash
python tools/wind_tunnel_tabular/ci_gate_telco_churn.py
```

---

## 3) Render preflight (post-deploy verification)

### A) Confirm deployed commit identity

```bash
curl -sS "$LLMLAB_API_BASE_URL/health"
```
Expected: JSON with `status: ok` and a `commit` matching the Render deploy SHA.

### B) Confirm DB reachability (if required)

```bash
curl -sS "$LLMLAB_API_BASE_URL/health/db"
```
Expected: JSON with `ok: true`.

Notes:
- CI can enforce this with `LLMLAB_REQUIRE_DB_HEALTH=true`.
- Render must have Postgres attached and `DATABASE_URL` set.

---

## 4) Authenticated API smoke (hosted-safe)

Prereqs (local env):
- `LLMLAB_API_BASE_URL`
- `LLMLAB_API_KEY`
- `LLMLAB_TENANT_ID`

### A) Contract validate (curl)

```bash
curl -i -sS -X POST "$LLMLAB_API_BASE_URL/api/contracts/validate" \
  -H "Authorization: Bearer $LLMLAB_API_KEY" \
  -H "X-Tenant-ID: $LLMLAB_TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{"template_id":"json_output_basic_v1","baseline_output":{"meta":{"run_id":"run_123abc"}},"candidate_output":{"meta":{"run_id":"run_123abc"}},"test_data":{"suite":"preflight"},"include_details":false,"api_version":"1.0"}'
```
Expected:
- `200 OK`
- `x-ratelimit-*` headers
- (if monthly quotas enabled) `x-monthlyquota-*` headers

### B) Contract validate (python smoke)

```bash
python tools/client/smoke_validate_contract.py
```
Expected: `status: ok` and a recommendation.

### C) Ensemble validate (python smoke)

```bash
python tools/client/smoke_validate_ensemble.py
```
Expected: `status: ok`.

---

## 5) Monthly quota verification (Render)

### A) Confirm quota headers are emitted

On any successful request, expect headers similar to:
- `x-monthlyquota-limit`
- `x-monthlyquota-used`
- `x-monthlyquota-remaining`
- `x-monthlyquota-reset`

### B) Confirm config knobs (Render env vars)

Monthly quotas are controlled by:
- `ENABLE_MONTHLY_QUOTAS=true|false`
- `MONTHLY_QUOTA_DEFAULT` (default: 200)
- `MONTHLY_QUOTA_FREE` (default: 200)
- `MONTHLY_QUOTA_STARTER` (default: 10000)
- `MONTHLY_QUOTA_PRO` (default: 50000)

You only need to change these on Render if you want different plan caps.

---

## 6) CI “secrets not set” is expected

In GitHub Actions, live smoke gates intentionally **skip** when secrets aren’t present (fork PR safety). Offline gates still run.

---

## What was completed in this rollout (reference)

- Tracked bytecode removed + `.gitignore` updated to prevent `__pycache__`/`.pyc` from deploying.
- Render boot failure fixed by committing a missing (previously untracked) route module.
- `.envrc` updated to export canonical `LLMLAB_API_BASE_URL`, `LLMLAB_API_KEY`, `LLMLAB_TENANT_ID` for smoother local testing.
- Monthly quota headers made visible on successful responses to simplify verification.
