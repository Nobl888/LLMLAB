# Integration Guide for Early Partners

**For:** Teams shipping analytics, fintech, telecom, and automation pipelines that need a reliable release gate.

---

## What Is This?

A REST API that validates changes against a baseline **or a deterministic contract/policy**, returning:
- a decision (`APPROVE` / `REVIEW` / etc.)
- a risk score + pass-rate summary
- a portable **evidence pack** you can attach to PRs and change tickets

This is built to run in CI: validate → (optionally) verify signature → upload evidence artifact.

### Baseline vs oracle (exec-friendly)

Two concepts matter for “metrics correctness,” and they solve different executive fears:

- **Baseline (regression baseline):** “last known good output.” It answers: *Did this change alter the numbers unexpectedly?*
- **Oracle (ground truth):** “reference answer.” It answers: *Are these numbers correct?*

Translation:
- Baselines prevent **surprise changes**.
- Oracles prevent **silent wrongness** (wrong-but-plausible dashboards).

Most teams start with baselines (easy), then promote the most important metrics to oracle-backed gates over time.

For an exec-friendly one-pager you can forward internally, see [EXEC_BRIEF_BASELINE_ORACLE.md](EXEC_BRIEF_BASELINE_ORACLE.md).

### Two primary offerings (same CI path)

- **Contract Templates (JSON automation):** validate that agent/tool outputs keep a stable schema + safety constraints.
- **Policy Gates (compliance-as-code):** validate that code/config artifacts comply with a deterministic policy (e.g., ban dynamic exec, ban network imports), producing auditable evidence per PR.

### Why it wins
- **Decision artifact beyond logs:** each run emits an evidence pack you can archive and re-verify later.
- **Minimization-first:** evidence packs can be hash-only while staying verifiable.
- **CI-native:** designed for GitHub Actions calling a hosted service (Render).

### Example Use Case

```
You have a KPI calculation function in production (baseline).
You've written a candidate version that's supposed to be faster.

Question: Did you break anything?

Answer: POST one call to /api/validate, get back:
  - risk_score: 8.7 (high confidence it works)
  - pass_rate: 0.83 (83% of test cases matched baseline)
  - recommendation: APPROVE_WITH_MONITORING
  - trace_id: [UUID for audit log]
```

---

## Getting Started (5 Minutes)

### Step 1: Get a tenant + API key

You need two values:
- `tenant_id`
- `api_key`

How you get them depends on rollout mode:
- Early partners: provisioned by the operator (recommended during onboarding)
- Self-serve (optional): available via `POST /api/signup` when enabled on the service

### Step 1.5: Privacy-first onboarding (recommended)

If your inputs may contain sensitive data (PII, customer records, internal identifiers), the safest workflow is:

1) **Run your pipeline locally (or in your own CI)**
- LLMLAB requires zero access to your source system.

2) **Minimize what you send**
- Prefer sending *derived artifacts* (summaries, aggregates, hashes, schema/shape) instead of raw rows.
- If you upload raw CSV contents, you are explicitly sending those rows to the hosted service.

3) **Add a local pre-processor**
- Strip or mask sensitive columns before sending anything.
- Example outputs that are usually safe to send: row/column counts, per-column null rates, type inference, bounded samples, deterministic hashes.

4) **Use a dry-run to prove what will be sent**
- Run your client with a `--dry-run` option that prints the target URL and payload shape and writes the outbound JSON to a local file.
- The goal is “trust but verify”: your engineers can inspect the outbound payload before any network call.

5) **Enforce a PII guard as a contract**
- Use the built-in contract template `no_pii_guard_v1` so the service will fail the request if the JSON artifact appears to contain PII-like patterns.
- This is best-effort (pattern-based), and is most effective when paired with a local redaction step.

#### Copy/paste: minimal customer script skeleton (local preprocess + dry-run)

This example reads a CSV locally, drops likely-sensitive columns, builds a small JSON “profile”, and either:
- writes what it *would* send (`--dry-run`), or
- sends the profile to `/api/contracts/validate`.

```python
#!/usr/bin/env python3
"""privacy_first_csv_gate.py

Local-only preprocessing: produces a small JSON profile and optionally sends it.

Usage:
  python privacy_first_csv_gate.py --csv ./data.csv --dry-run
  python privacy_first_csv_gate.py --csv ./data.csv

Required env:
  LLMLAB_API_BASE_URL
  LLMLAB_API_KEY
  LLMLAB_TENANT_ID
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.request


DROP_COLUMNS = {
  "name",
  "first_name",
  "last_name",
  "email",
  "phone",
  "ssn",
  "address",
}


def require_env(name: str) -> str:
  v = os.getenv(name)
  if v is None or v == "":
    raise SystemExit(f"Missing env var: {name}")
  return v


def build_profile(csv_path: str) -> dict:
  with open(csv_path, "r", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    if reader.fieldnames is None or len(reader.fieldnames) == 0:
      raise SystemExit("CSV has no header row")

    kept: list[str] = []
    for c in reader.fieldnames:
      if c in DROP_COLUMNS:
        continue
      kept.append(c)
    nulls = {c: 0 for c in kept}
    rows = 0
    for row in reader:
      rows += 1
      for c in kept:
        v = (row.get(c) or "").strip()
        if v == "":
          nulls[c] += 1

  return {
    "schema_version": "1.0",
    "source": {"filename": os.path.basename(csv_path)},
    "shape": {"rows": rows, "cols": len(kept), "columns": kept},
    "nulls": {"by_column": nulls},
    "note": "This is a minimized CSV profile (no raw rows).",
  }


def post_contract_validate(payload: dict) -> dict:
  base = require_env("LLMLAB_API_BASE_URL").rstrip("/")
  api_key = require_env("LLMLAB_API_KEY")
  tenant_id = require_env("LLMLAB_TENANT_ID")

  url = base + "/api/contracts/validate"
  body = json.dumps(
    {
      "template_id": "no_pii_guard_v1",
      "baseline_output": {},
      "candidate_output": payload,
      "include_details": False,
      "api_version": "1.0",
      "test_data": {"suite": "privacy_first_csv_profile"},
    }
  ).encode("utf-8")

  req = urllib.request.Request(
    url=url,
    method="POST",
    data=body,
    headers={
      "Content-Type": "application/json",
      "Authorization": f"Bearer {api_key}",
      "X-Tenant-ID": tenant_id,
    },
  )
  with urllib.request.urlopen(req, timeout=30) as resp:
    raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def main(argv: list[str]) -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--csv", required=True, help="Path to local CSV")
  ap.add_argument("--dry-run", action="store_true", help="Dry-run: print outbound payload")
  args = ap.parse_args(argv)

  profile = build_profile(args.csv)

  if args.dry_run:
    out = {
      "would_post": "/api/contracts/validate",
      "template_id": "no_pii_guard_v1",
      "candidate_output": profile,
      "note": "Inspect this payload; it should contain no PII or raw rows.",
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0

  resp = post_contract_validate(profile)
  print(json.dumps(resp, indent=2))
  return 0


if __name__ == "__main__":
  raise SystemExit(main(sys.argv[1:]))
```

### Step 2: Make Your First Request

**Using Python:**

```python
import requests

api_key = "<your_api_key>"
tenant_id = "<your_tenant_id>"
api_url = "<YOUR_API_BASE>/api/validate"

response = requests.post(
    api_url,
  headers={
    "Authorization": f"Bearer {api_key}",
    "X-Tenant-ID": tenant_id,
  },
    json={
        "baseline_output": {
            "kpi_value": 0.847,
            "num_transactions": 5234
        },
        "candidate_output": {
            "kpi_value": 0.849,
            "num_transactions": 5234
        },
        "test_data": {
            "num_tests": 100,
            "date_range": "2025-01-01 to 2025-01-31"
        }
    }
)

result = response.json()
print(f"Risk Score: {result['risk']['score']}")
print(f"Recommendation: {result['recommendation']}")
print(f"Trace ID: {result['trace_id']}")  # Save this for your audit log
```

**Using cURL:**

```bash
curl -X POST <YOUR_API_BASE>/api/validate \
  -H "Authorization: Bearer <your_api_key>" \
  -H "X-Tenant-ID: <your_tenant_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "baseline_output": {"kpi_value": 0.847},
    "candidate_output": {"kpi_value": 0.849},
    "test_data": {"num_tests": 100}
  }'

> Note: `X-Tenant-ID` is required and must match the API key tenant.
```

### Step 3: Read the Response

```json
{
  "trace_id": "9f4a5c3e-2b61-4c2b-a8c0-9e6a1b2c7d11",
  "status": "ok",
  "risk": {
    "score": 8.7,
    "category": "low",
    "confidence": 94.0
  },
  "summary": {
    "pass_rate": 0.83,
    "total_checks": 24,
    "failed_checks": 4
  },
  "recommendation": "APPROVE_WITH_MONITORING",
  "evidence": {
    "baseline_hash": "sha256:abcd1234...",
    "candidate_hash": "sha256:efef5678...",
    "test_data_hash": "sha256:9900aa11...",
    "timestamp": "2025-12-13T20:10:15Z",
    "domain": "analytics_kpi"
  }
}
```

**What this means:**
- `risk.score: 8.7` = High confidence (score 0–10, higher = safer)
- `risk.category: "low"` = Low risk
- `confidence: 94%` = We're 94% sure about this assessment
- `pass_rate: 0.83` = 83% of test cases matched baseline
- `recommendation: APPROVE_WITH_MONITORING` = You can deploy, but keep an eye on it

---

## GitHub Actions quickstart (copy/paste)

This is the fastest path for early engineers: wire the hosted-safe gate into PRs with one workflow.

### What you add

1) **Enable the workflow**
- This repo ships a ready workflow: `.github/workflows/llmlab_ci_gates.yml`.
- It always runs offline gates (syntax/import). It runs a live API smoke only when secrets exist.

2) **Add 3 repository secrets (for live smoke)**
- `LLMLAB_API_BASE_URL` (example: `https://llmlab-t6zg.onrender.com`)
- `LLMLAB_API_KEY` (starts with `llm_...`)
- `LLMLAB_TENANT_ID` (UUID)

Notes:
- If secrets are unset (forks/PRs), the workflow will skip the live smoke gate and remain non-blocking by design.
- The live smoke calls `POST /api/contracts/validate` using a hosted-safe payload.

### What “success” looks like

- PR check `llmlab-ci-gates` is green.
- Evidence artifacts (if any) are uploaded as a build artifact under `llmlab-evidence`.

---

## Compliance control layer (positioning without over-claiming)

Teams in regulated environments often need a repeatable control that answers:
- *What changed?*
- *What checks ran?*
- *Who/what approved it?*
- *Can we prove integrity after the fact?*

LLMLAB is designed to support that workflow by producing **deterministic evidence** per gate:

- **Minimization-first inputs:** you can submit JSON artifacts/summaries/hashes instead of raw datasets.
- **Deterministic decision + summary:** `pass_rate`, `failed_checks`, `recommendation`.
- **Evidence pack:** a portable record you can attach to PRs/change tickets.
- **Optional tamper detection:** if evidence signing is configured (`EVIDENCE_SIGNING_KEY`), signatures can be verified later.

If you are evaluating governance requirements (including upcoming AI governance regimes), treat this as a **technical control primitive** you can map to your internal policies (change control, testing evidence, traceability). For legal interpretation and formal certifications, coordinate with your counsel and assurance teams; LLMLAB provides the technical evidence layer.

### South Korea: AI Basic Act (effective Jan 2026) — how LLMLAB fits

Based on public summaries (and your internal onboarding needs), the AI Basic Act emphasizes risk-based oversight for “high-impact” systems, transparency for generative AI, and documentation/controls.

LLMLAB fits as a **control layer** for engineering teams because it can help you operationalize parts of that program in CI:

- **Documentation + retention-ready artifacts:** each gate run returns an `evidence_pack` you can archive with the PR/change ticket (hash-first, portable).
- **Traceability (“what ran, when, on what inputs”):** evidence includes stable fingerprints of baseline/candidate/test inputs plus deterministic summaries.
- **Transparency/labeling enforcement for GenAI outputs:** you can treat “labels required” as a contract requirement.
  - Example: enforce that responses include fields like `ai_generated: true`, `content_label`, `model_id`, `generated_at`, `disclosure_version`.
  - Watermark generation is handled by your pipeline; LLMLAB validates the presence of required labeling/disclosure metadata.
- **Risk check evidence (high-impact workflows):** you can require a structured “risk check result” JSON artifact (e.g., `risk_assessment.status`, `hazards_checked`, `mitigations_applied`) and gate changes on that shape.

Scope clarity (keeps positioning precise):
- High-impact classification and legal obligations are determined by regulators and your compliance program.
- LLMLAB provides deterministic validation + evidence artifacts you can map to those controls.

## Two hosted-safe request profiles (recommended)

These profiles preserve the hosted-safe posture: customers run code/data locally and submit only structured artifacts.

**Important:** the `/api/validate` request schema supports multiple modes via *which fields you include*:

- **Hosted artifact mode (recommended for hosted):** send `baseline_output`, `candidate_output`, optional `test_data`.
  - No server-side customer code execution.
- **Contract template mode (recommended for hosted):** use `POST /api/contracts/validate` with a `template_id`.
  - This is the currently supported “contract/invariants” gate in the deployed `main` branch.
- **KPI kit execution mode (self-hosted / private only):** send `baseline_kpi_path`, `candidate_kpi_path`, and `fixture_id`/`fixture_path`.
  - This requires server-side code execution to be explicitly enabled (see `ALLOW_KPI_CODE_EXECUTION`).

Note: a draft “contract/invariants inside `/api/validate` + `evidence_pack` response bundle” exists as preserved early work on branch `review/stash0-main`, and it stays separate from the deployed `main`.
Note: a draft “contract/invariants inside `/api/validate` + `evidence_pack` response bundle” exists as preserved early work on branch `review/stash0-main`, and remains outside the deployed `main` branch.

### Profile A: Extraction JSON gate (schema + invariants + optional drift)

Use this when you have an extractor or agent/tool output that must keep a stable JSON shape.

```json
{
  "baseline_output": {"invoice_id":"INV-1","total":123.45,"currency":"EUR","line_items":[{"sku":"A","qty":1}]},
  "candidate_output": {"invoice_id":"INV-1","total":123.45,"currency":"EUR","line_items":[]},
  "contract": {
    "schema_version": "1.0",
    "rules": [
      {"id": "inv.invoice_id.exists", "type": "exists", "path": "invoice_id"},
      {"id": "inv.total.type", "type": "type_is", "path": "total", "expected": "number"},
      {"id": "inv.total.nonneg", "type": "range", "path": "total", "min": 0},
      {"id": "inv.currency.allowed", "type": "in", "path": "currency", "allowed": ["USD","EUR","GBP"]}
    ]
  },
  "test_data": {"suite": "invoice-extract", "suite_version": "1.0.0"},
  "include_details": false
}
```

Practical goal:
- Stop “output shape drift broke downstream” *before merge*, with an evidence pack attached to the PR.

### Profile B: KPI artifact gate (tolerance drift + optional categorization)

Use this when the output is a KPI result you can express as a small artifact (no database access required).

```json
{
  "baseline_output": {"metrics": {"profit_2017_USA": 11980.55}, "unit": "USD"},
  "candidate_output": {"metrics": {"profit_2017_USA": 12001.12}, "unit": "USD"},
  "contract": {
    "schema_version": "1.0",
    "rules": [
      {"id": "kpi.profit.exists", "type": "exists", "path": "metrics.profit_2017_USA"},
      {"id": "kpi.profit.type", "type": "type_is", "path": "metrics.profit_2017_USA", "expected": "number"},
      {"id": "kpi.profit.drift", "type": "approx", "path": "metrics.profit_2017_USA", "baseline_path": "metrics.profit_2017_USA", "abs_tol": 50.0, "rel_tol": 0.01}
    ]
  },
  "test_data": {"suite": "kpi-profit", "suite_version": "1.0.0"},
  "include_details": false
}
```

Practical goal:
- Stop wrong-but-plausible KPI drift (join/filter/group-by mistakes) from shipping.

Notes:
- You can start as **baseline regression** (no oracle yet), then promote critical KPIs to an oracle-backed fixture.
- These are intentionally small payloads that work well with the hosted-safe posture.

## Field Reference

### Request Fields

| Field | Type | Required | Example |
|---|---|---|---|
| `baseline_output` | dict | Optional | `{"kpi": 0.847}` |
| `candidate_output` | dict | Optional | `{"kpi": 0.849}` |
| `test_data` | dict | Optional | `{"num_tests": 100}` |
| `contract` | dict | Optional | `{ "schema_version": "1.0", "rules": [...] }` |
| `include_details` | bool | Optional | `false` |
| `api_version` | string | Optional | `"1.0"` |

**Self-hosted / private execution fields (KPI kit mode only):**

| Field | Type | Required | Example |
|---|---|---|---|
| `baseline_kpi_path` | string | Optional | `"baseline_kpi_v1.py"` |
| `candidate_kpi_path` | string | Optional | `"candidate_kpi_v2.py"` |
| `fixture_id` | string | Optional | `"0f6c..."` |
| `fixture_path` | string | Optional | `"/srv/fixtures/superstore.csv"` |
| `kpi_type` | string | Optional | `"profitmetrics"` |

### Required Headers

| Header | Required | Example |
|---|---:|---|
| `Authorization` | Yes | `Bearer llm_...` |
| `X-Tenant-ID` | Yes | `3b6c2c6c-...` |

---

## Canonical evidence pack fields (v1)

The response always includes an **Evidence Block** (`evidence`) with deterministic hashes:
- `evidence.timestamp`
- `evidence.domain`
- `evidence.baseline_hash`
- `evidence.candidate_hash`
- `evidence.test_data_hash`
- Optional: `evidence.explanation`, `evidence.details` (only when `include_details=true` and your API key scope allows it)

When enabled, the response also includes an **Evidence Pack** (`evidence_pack`) intended for CI artifacts/audit trails:
- `evidence_pack.schema_version`, `evidence_pack.generated_at`
- `evidence_pack.trace_id`, optional `evidence_pack.request_id`
- `evidence_pack.domain`, `evidence_pack.mode`, `evidence_pack.api_version`
- `evidence_pack.baseline_hash`, `evidence_pack.candidate_hash`, `evidence_pack.test_data_hash`
- `evidence_pack.risk`, `evidence_pack.summary`, `evidence_pack.recommendation`
- `evidence_pack.config` (safe snapshot: tolerances, mode, policy_id/version)
- Optional tamper detection: `evidence_pack.signature_alg`, `evidence_pack.signature`

---

## Canonical adoption path (CI-first)

1) Deploy the API (Render + Postgres).
2) Set `LLMLAB_API_BASE_URL` (preferred) **or** `LLMLAB_API_BASE` (legacy) plus `LLMLAB_API_KEY`, `LLMLAB_TENANT_ID` as GitHub Secrets.
3) Enable the canonical workflow that runs validate → (if signed) verify → uploads the evidence artifact.
4) Treat the uploaded evidence pack as the attachable record per PR.

### CI launch (copy/paste)

If you want the lowest-friction “see it working in minutes” path:

- Workflow: `.github/workflows/llmlab_ci_gates.yml` (runs two hosted-safe gates and uploads `.llmlab_artifacts/`)
- Starter note: `CI_LAUNCH_STARTER.md` (secrets, success criteria, next step)
- Reviewer note: `HOSTED_SAFE_POSTURE.md` (export-safe hosted-safe posture summary)

### Response Fields (Always Returned)

| Field | Type | Meaning |
|---|---|---|
| `trace_id` | string (UUID) | Unique ID for this validation. Save it for audits. |
| `status` | string | `"ok"` on success, `"error"` on failure |
| `risk.score` | number (0–10) | Risk assessment. Higher = safer/better. |
| `risk.category` | string | `low` \| `medium` \| `high` \| `critical` |
| `risk.confidence` | number (0–100) | How confident we are in this assessment (%) |
| `summary.pass_rate` | number (0–1) | Fraction of test cases that matched (0–1) |
| `summary.total_checks` | number | How many checks we ran |
| `summary.failed_checks` | number | How many checks differed from baseline |
| `recommendation` | string | `APPROVE` \| `APPROVE_WITH_MONITORING` \| `REVIEW` \| `REJECT` |
| `evidence.baseline_hash` | string | SHA256 hash of your baseline (for audit) |
| `evidence.candidate_hash` | string | SHA256 hash of your candidate code |
| `evidence.test_data_hash` | string | SHA256 hash of test data used |
| `evidence.timestamp` | string (ISO8601) | When this validation ran |
| `evidence.domain` | string | Domain tag (e.g., `analytics_kpi`) |

### Recommendation Guide

| Recommendation | Meaning | Action |
|---|---|---|
| `APPROVE` | Very safe to deploy | Deploy immediately |
| `APPROVE_WITH_MONITORING` | Safe, but watch performance | Deploy, monitor metrics |
| `REVIEW` | Needs review before deploy | Run manual tests, check with team |
| `REJECT` | High risk | Hold deployment; investigate differences and iterate |

---

## Common Scenarios

### Scenario 1: KPI Calculation Function

**Your situation:** You have a `calculate_revenue_kpi()` function. You optimized it.

**What to do:**

```python
baseline_output = old_function(test_data)  # Run baseline
candidate_output = new_function(test_data)  # Run optimized version

response = api.validate(
    baseline_output=baseline_output.to_dict(),
    candidate_output=candidate_output.to_dict(),
    test_data={"num_records": len(test_data)}
)

if response['recommendation'] in ['APPROVE', 'APPROVE_WITH_MONITORING']:
    deploy_new_version()
else:
    investigate_differences()
```

### Scenario 2: ML Model Update

**Your situation:** You retrained your fraud detection model.

**What to do:**

```python
# Score test cases with old model
baseline_scores = old_model.predict(test_cases)

# Score test cases with new model
candidate_scores = new_model.predict(test_cases)

response = api.validate(
    baseline_output={"scores": baseline_scores.tolist()},
    candidate_output={"scores": candidate_scores.tolist()},
    test_data={"num_test_cases": len(test_cases)}
)

# If confidence > 90% and pass_rate > 0.8, deploy
if response['risk']['confidence'] > 90 and response['summary']['pass_rate'] > 0.8:
    deploy_model()
```

### Scenario 3: Database Query Refactor

**Your situation:** You rewrote a complex SQL query for performance.

**What to do:**

```python
baseline_result = old_query(start_date, end_date)
candidate_result = new_query(start_date, end_date)

response = api.validate(
    baseline_output={"result": baseline_result},
    candidate_output={"result": candidate_result},
    test_data={"date_range": f"{start_date} to {end_date}"}
)

# Keep old version until you're 95%+ confident
if response['risk']['confidence'] >= 95:
    switch_to_new_query()

---

## JSON Automation (Agents/Tools) — Fastest Onboarding Path

If your output is JSON (agents, tools, workflow steps), use contract templates instead of code execution.

**Compliance-as-code (regulation-safe, compelling):** treat your JSON output shape and safety constraints as versioned policy in CI. Each run yields a portable `evidence_pack` containing *hash-only fingerprints* of baseline/candidate/test inputs plus a deterministic pass/fail summary and safe config metadata. Verbose diagnostics are scope-gated, and regulated tenants can run fail-closed (`DETAILS_ENFORCEMENT=strict`). This gives you clean, consistent change-control evidence (what was checked, when, with which policy) that maps cleanly onto SOC2-style audit workflows.

### What the `evidence_pack` proves (useful for SOC2-style change control)

- **What policy ran:** the evidence pack includes a contract fingerprint (hash) and safe config (e.g., template id), so you can show *which* policy version gated the change.
- **What was compared:** hash-only fingerprints of baseline/candidate/test inputs (no raw values required in the artifact).
- **When and where:** trace id + timestamp + build metadata (e.g., build commit when configured).
- **What happened:** deterministic summary (`pass_rate`, `failed_checks`, recommendation).
- **Integrity after the fact (optional):** if signing is enabled, the signature can be verified later to detect tampering.

### Step 1: List templates

```bash
curl -s https://api.llmlab.com/api/contracts/templates \
  -H "Authorization: Bearer your_api_key_here" \
  -H "X-Tenant-ID: your_tenant_id_here" \
  -H "Content-Type: application/json"
```

### Step 2: Validate using a template in one call

Example using `tool_result_envelope_v1`:

```bash
curl -s https://api.llmlab.com/api/contracts/validate \
  -H "Authorization: Bearer your_api_key_here" \
  -H "X-Tenant-ID: your_tenant_id_here" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "tool_result_envelope_v1",
    "baseline_output": {"status":"ok","tool":"summarizer_v2","run_id":"abc123xyz","result":{"summary":"..."}},
    "candidate_output": {"status":"ok","tool":"summarizer_v2","run_id":"abc123xyz","result":{"summary":"..."}},
    "include_details": false,
    "api_version": "1.0"
  }'
```

### Step 3 (Optional): Verify the signed evidence pack

If the service is configured with `EVIDENCE_SIGNING_KEY`, each response includes an `evidence_pack.signature`.
You can verify it for tamper detection:

```bash
curl -s https://api.llmlab.com/api/evidence/verify \
  -H "Authorization: Bearer your_api_key_here" \
  -H "X-Tenant-ID: your_tenant_id_here" \
  -H "Content-Type: application/json" \
  -d '{"evidence_pack": {"schema_version":"1.0", "generated_at":"...", "signature_alg":"hmac-sha256", "signature":"...", "trace_id":"..."}}'
```

This is the core CI story:
- deterministic pass/fail signal for automation
- portable evidence artifact you can store as a CI build artifact

---

## Policy Gates (Compliance-as-Code) — CI Evidence for Security/Regulated Teams

Policy Gates use the **same** `/api/contracts/validate` endpoint and evidence pack, but the “contract” represents a deterministic policy.

Start with the built-in template:
- `python_safe_compute_policy_v1` — bans dynamic execution (`eval`/`exec`) and common network/subprocess imports.

Example request (candidate contains Python source in a `code` field):

```bash
curl -s https://api.llmlab.com/api/contracts/validate \
  -H "Authorization: Bearer your_api_key_here" \
  -H "X-Tenant-ID: your_tenant_id_here" \
  -H "Content-Type: application/json" \
  -d ' {
    "template_id": "python_safe_compute_policy_v1",
    "baseline_output": {},
    "candidate_output": {"code": "import requests\nprint(\"hi\")\n"},
    "include_details": false,
    "api_version": "1.0"
  }'
```

Notes:
- Policy Gate diagnostics are scope-gated by `include_details` + key scopes (recommended for internal/security reviewers).
- The evidence pack always includes policy stamping metadata when configured (`LLMLAB_POLICY_ID`, `LLMLAB_POLICY_VERSION`).
```

---

## Pricing & Quotas

| Plan | Calls/Month | Price | Best For |
|---|---|---|---|
| **Free** | 100 | Free | Evaluation, small POCs |
| **Pilot** | 1,000 | $299/mo | Active evaluation + first integration |
| **Production** | 10,000 | $1,499/mo | Enterprise, continuous use |

- Free tier: No credit card, cancel anytime
- Paid tiers: Month-to-month, no long-term contracts
- Overage: If you exceed quota, we notify you before blocking

---

## Support & Questions

**Email:** support@llmlab.com  
**Docs:** https://api.llmlab.com/docs  
**Status:** https://status.llmlab.com

**Response SLA:**
- Free tier: 24–48 hours
- Pilot tier: 12 hours
- Production tier: 4 hours (business hours), 24 hours (critical)

---

## FAQ

### Q: What happens to my code/data?

**A:** In the recommended hosted-safe posture, you run your code and queries in your own environment and submit only structured artifacts (often small JSON summaries). The service returns a decision plus an evidence pack that can be hash-only.

For sensitive datasets:
- Add a local pre-processor that drops/masks PII columns.
- Use a dry-run mode in your client to print/record the outbound payload *before* sending.
- Prefer sending summaries/hashes rather than raw rows.

Contract-template onboarding works with JSON artifacts; raw datasets are optional.

### Q: Can I use this for compliance?

**A:** It’s commonly used to support change-control and audit workflows by producing machine-verifiable evidence per PR/release. Legal compliance determinations and certifications are handled by your governance program and assessors; LLMLAB provides evidence and validation to support that work.

### Q: What if you shut down?

**A:** Your CI artifacts can store the evidence packs returned by the API. If you enable evidence signing, you can verify later whether an evidence pack was modified after it was produced.

### Q: Can I use this for production?

**A:** Yes. Many customers run this as part of their CI/CD pipeline. See the Production tier for high-volume use.

### Q: How fast is the API?

**A:** It’s designed to be CI-friendly and typically fast for artifact/contract validations, but latency depends on payload size, enabled features, and deployment.

---

## Next Steps

1. **Follow the canonical onboarding path:** see `QUICKSTART.md`.
2. **Deploy (Render):** follow `DEPLOY_NOW_COPY_PASTE.md`.
3. **Enable CI gate:** turn on one of the canonical workflows under `.github/workflows/`.
4. **Pick your first template:** start with `tool_result_envelope_v1` (agents/tools) or `python_safe_compute_policy_v1` (policy gates).

We're here to help you validate code with confidence.
