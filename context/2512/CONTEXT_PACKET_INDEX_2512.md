# Context Packet Index (2512 reference)

Date reference: **2512** (created on 2025-12-25)

## Addendum (2026-01-07) — GitHub Actions LIVE ✅

**CI is fully operational on GitHub Actions.**

| Milestone | Status |
|-----------|--------|
| Workflow triggers on push to `main` | ✅ |
| GitHub Secrets configured | ✅ |
| Offline Bayes wind-tunnel gates (HMM, coin, bijection) | ✅ |
| Offline calibration gate (Telco churn) | ✅ |
| Live health check (Render) | ✅ |
| Live smoke gates (contract + ensemble) | ✅ |
| Run #23 passed | ✅ |

**Files added to LLMLAB repo:**
- `tools/wind_tunnel_bayes/` — HMM, coin, bijection gates
- `tools/wind_tunnel_tabular/` — Telco churn gate
- `tools/client/smoke_validate_ensemble.py`
- `README.md` — minimal, IP-safe public README

**Workflow fixes applied:**
- Added `push: branches: [main]` trigger
- Fixed `secrets` in `if:` conditions (use env vars instead)
- Increased health check timeout to 90s for Render cold start
- Fixed telco CSV path (`telco_churn.csv` not `LLMLAB/telco_churn.csv`)

**Secrets set in GitHub:**
- `LLMLAB_API_BASE_URL` = `https://llmlab-t6zg.onrender.com`
- `LLMLAB_API_KEY` = (set)
- `LLMLAB_TENANT_ID` = (set)

---

## Addendum (2025-12-26)

- Live Render deploy is confirmed healthy and serving commit `333837615bd531a9b4605c02aa573e56a5bb950d` via `GET /health`.
- OpenAPI includes the hosted-safe contract + evidence endpoints:
  - `POST /api/contracts/validate`
  - `GET /api/contracts/templates`
  - `POST /api/evidence/verify`
- Local authenticated smoke has been run successfully against Render (`tools/client/smoke_validate_contract.py` returned `status: ok` + `recommendation: APPROVE`).
- Customer onboarding docs now include a privacy-first “minimize + local redaction + dry-run + PII guard” journey:
  - `API_INTEGRATION_GUIDE.md` (Step 1.5)
  - `LOCAL_CLIENT_TEST_RUNBOOK.md` (0d)
- `API_INTEGRATION_GUIDE.md` also now includes:
  - a GitHub Actions quickstart (aligned to `.github/workflows/llmlab_ci_gates.yml`)
  - a “compliance control layer” positioning section (evidence-first, legal-scope clarity)
  - a South Korea AI Basic Act mapping subsection (how contracts + evidence packs support a compliance program)

This is a dated snapshot index you can point new chats at (without moving any files).

## Addendum (2025-12-31)

- Canonical indicators harness (`tools/qqq_canonical_indicators/`) was used to run a strict oracle-vs-candidate validation for `composite_v1` across default + high-temperature candidate batches.
- Latest `composite_v1` status is clean through the guided high-T batch at **T=3.0**:
  - Total: `attempted=348 PASS=348 FAIL=0`
  - T=3.0: `attempted=12 PASS=12`
  - Summaries: `.llmlab_artifacts/qqq_canonical_indicators/composite_v1/summary_by_temperature.csv` and `overall_summary.csv`
- LLM markdown import safety is supported via `tools/qqq_canonical_indicators/import_llm_markdown.py`:
  - Use `--backup-existing` (timestamped under `.llmlab_artifacts/import_llm_markdown_backups/`) when overwriting candidates.

## The short context packet (7 files)

1) [CI_LAUNCH_STARTER.md](../../CI_LAUNCH_STARTER.md) — CI golden path + secrets + what success looks like
2) [HOSTED_SAFE_POSTURE.md](../../HOSTED_SAFE_POSTURE.md) — hosted-safe posture (artifact-first; customer code execution stays on customer infrastructure by default)
3) [API_INTEGRATION_GUIDE.md](../../API_INTEGRATION_GUIDE.md) — integration narrative + request profiles + FAQ
4) [EXEC_BRIEF_BASELINE_ORACLE.md](../../EXEC_BRIEF_BASELINE_ORACLE.md) — executive one-pager (baseline vs oracle; silent wrongness)
5) [API_PRICING_AND_FREEMIUM_STRATEGY.md](../../API_PRICING_AND_FREEMIUM_STRATEGY.md) — outcome-based pricing narrative + “golden-free” differentiator
6) [.github/workflows/llmlab_ci_gates.yml](../../.github/workflows/llmlab_ci_gates.yml) — what CI actually runs (hosted-safe)
7) [RD_LLMLAB.md](../../RD_LLMLAB.md) — R&D applications + “data-minimization” posture + beyond-numeric opportunities

## Optional onboarding assets (recommended for new devs)

- [README_PUBLIC.md](../../README_PUBLIC.md) — public-facing overview + 3-command onboarding
- [LOCAL_CLIENT_TEST_RUNBOOK.md](../../LOCAL_CLIENT_TEST_RUNBOOK.md) — step-by-step client testing + smoke-key bootstrap
- [DEVELOPER_NARRATIVE.md](../../DEVELOPER_NARRATIVE.md) — dev-facing positioning: “release gate + evaluation evidence in CI artifacts”
- [KIT_CATALOG.md](../../KIT_CATALOG.md) — kit map + what to use when
- [EVIDENCE_ARTIFACT_EXAMPLE.md](../../EVIDENCE_ARTIFACT_EXAMPLE.md) — redacted evidence artifact example
- [templates/client/validate_contract_invoice.json](../../templates/client/validate_contract_invoice.json) — sample contract payload
- [templates/client/validate_contract_events.json](../../templates/client/validate_contract_events.json) — sample contract payload
- [scripts/run_validate_contract.sh](../../scripts/run_validate_contract.sh) — curl-based runner
- [scripts/README.md](../../scripts/README.md) — scripts usage

## Pre-launch ops (recommended)

- [LLMLAB/ROTATE_SECRETS_BEFORE_LAUNCH_CHECKLIST.md](../../LLMLAB/ROTATE_SECRETS_BEFORE_LAUNCH_CHECKLIST.md) — rotate keys/DB URL before going live

## Operational status quick check (for a new chat)

- Live deploy identity: `GET /health` (commit should match the Render deploy)
- Database reachability: `GET /health/db`
- Client smoke (hosted-safe contract mode): run `tools/client/smoke_validate_contract.py` or `bash scripts/run_validate_contract.sh ...`
- Admin/bootstrap endpoints are smoke-key gated and stealth 404 without the smoke key (by design)

## Preserved early work (separate from production)

- Branch: `review/stash0-main` preserves early/experimental work that stays separate from the deployed `main` branch.
- Contains: draft `evidence_pack`, draft contract/invariants mode inside `/api/validate`, and draft `fixture_id` resolution via a `fixtures` table.

## Copy/paste prompt for a new chat

Paste this as the first message in a new chat:

"""
We are working on LLMLAB, a CI-native validation service.

Date reference: 2512 (created 2025-12-25).

Non-negotiables:
- Hosted-safe by default: customers run code/data locally; service validates structured artifacts; customer code execution stays on customer infrastructure in hosted mode.
- Deliverable is a portable evidence pack per gate/run (hash-first; optionally signed).
- Multi-tenant API key auth; CI workflow exists.

Canonical docs to use as truth:
- CI_LAUNCH_STARTER.md
- HOSTED_SAFE_POSTURE.md
- API_INTEGRATION_GUIDE.md
- EXEC_BRIEF_BASELINE_ORACLE.md
- API_PRICING_AND_FREEMIUM_STRATEGY.md
- .github/workflows/llmlab_ci_gates.yml
- RD_LLMLAB.md

Goal for this chat:
(you fill in: e.g., add compliance gate suite, refine pricing page, implement new contract template, etc.)
"""

## Files created/modified recently (last 7 days)

Use the canonical list in [CONTEXT_PACKET_INDEX.md](../../CONTEXT_PACKET_INDEX.md) to avoid duplicating/rotting this section.

If you need to regenerate the list later:

```bash
find /home/gouldd5 -type f \
  \( -name '*.md' -o -name '*.yml' -o -name '*.yaml' -o -name '*.py' -o -name '*.txt' \) \
  -mtime -7 \
  ! -path '/home/gouldd5/.git/*' \
  ! -path '/home/gouldd5/venv/*' \
  ! -path '/home/gouldd5/.venv/*' \
  ! -path '/home/gouldd5/autogen-env/*' \
  ! -path '/home/gouldd5/.vscode-server/*' \
  | sed 's|^/home/gouldd5/||' | sort
```
