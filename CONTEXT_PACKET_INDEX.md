# Context Packet Index (for new chats)

This file is a “carry-forward” index to avoid losing critical context when you start a new chat.

## Dated snapshot index

- [context/2512/CONTEXT_PACKET_INDEX_2512.md](context/2512/CONTEXT_PACKET_INDEX_2512.md) — dated reference snapshot (created 2025-12-25)

## The short context packet (7 files)

1) [CI_LAUNCH_STARTER.md](CI_LAUNCH_STARTER.md) — CI golden path + secrets + what success looks like
2) [HOSTED_SAFE_POSTURE.md](HOSTED_SAFE_POSTURE.md) — hosted-safe posture (artifact-first; no customer code execution by default)
3) [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md) — integration narrative + request profiles + FAQ
4) [EXEC_BRIEF_BASELINE_ORACLE.md](EXEC_BRIEF_BASELINE_ORACLE.md) — executive one-pager (baseline vs oracle; silent wrongness)
5) [API_PRICING_AND_FREEMIUM_STRATEGY.md](API_PRICING_AND_FREEMIUM_STRATEGY.md) — outcome-based pricing narrative + “no goldens” differentiator
6) [.github/workflows/llmlab_ci_gates.yml](.github/workflows/llmlab_ci_gates.yml) — what CI actually runs (hosted-safe)
7) [RD_LLMLAB.md](RD_LLMLAB.md) — R&D applications + “no data” posture + beyond-numeric opportunities

## Optional onboarding assets (useful context)

- [README_PUBLIC.md](README_PUBLIC.md) — public-facing overview + 3-command onboarding
- [LOCAL_CLIENT_TEST_RUNBOOK.md](LOCAL_CLIENT_TEST_RUNBOOK.md) — step-by-step client testing + smoke-key bootstrap
- [DEVELOPER_NARRATIVE.md](DEVELOPER_NARRATIVE.md) — dev-facing positioning
- [KIT_CATALOG.md](KIT_CATALOG.md) — kit map + what to use when
- [EVIDENCE_ARTIFACT_EXAMPLE.md](EVIDENCE_ARTIFACT_EXAMPLE.md) — redacted evidence artifact example
- [templates/client/validate_contract_invoice.json](templates/client/validate_contract_invoice.json)
- [templates/client/validate_contract_events.json](templates/client/validate_contract_events.json)
- [scripts/run_validate_contract.sh](scripts/run_validate_contract.sh)
- [scripts/README.md](scripts/README.md)

## Operational status quick check

- Live deploy identity: `GET /health` (commit should match the Render deploy)
- Database reachability: `GET /health/db`
- Client smoke (hosted-safe contract mode): run `tools/client/smoke_validate_contract.py` or `bash scripts/run_validate_contract.sh ...`

## Preserved early work (not deployed)

- Branch: `review/stash0-main` (pushed to GitHub) preserves early/experimental work without changing Render’s deploy branch (`main`).
- Contains: draft `evidence_pack` response bundle, draft contract/invariants mode inside `/api/validate`, draft `fixture_id` resolution via a `fixtures` table, and a `python-multipart` dependency.
- Important: `main` is the deploy branch; treat `review/stash0-main` as a source of context/ideas to selectively merge later.

## Copy/paste prompt for a new chat

Paste this as the first message in a new chat:

"""
We are working on LLMLAB, a CI-native validation service.

Non-negotiables:
- Hosted-safe by default: customers run code/data locally; service validates structured artifacts; do not execute customer code on the service in hosted mode.
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

This list is timestamp-based (filesystem mtime) and excludes virtualenvs and VS Code server folders:

- .github/workflows/llmlab_ci_gates.yml
- API_INTEGRATION_GUIDE.md
- API_PRICING_AND_FREEMIUM_STRATEGY.md
- API_READY_TO_LAUNCH_SUMMARY.md
- CI_LAUNCH_STARTER.md
- COMPETITIVE_MATRIX_EVIDENCE_GATE.md
- DATA_RETENTION_POLICY.md
- DEPLOY_NOW_COPY_PASTE.md
- EXAMPLE_RUN_LINKS_AND_VALUE.md
- EXEC_BRIEF_BASELINE_ORACLE.md
- EXPORT_CHECKLIST_PUBLIC_REPO.md
- EXPORT_SAFE_INTERNAL_RECAP_DEC2025.md
- FINGERPRINT_REPORT_ONE_PAGER.md
- FOUNDING_LAB_RUN_NOTES.md
- GO_TO_MARKET_NEXT_STEPS.md
- HOSTED_SAFE_POSTURE.md
- ICP_FOCUS_AND_3MONTH_SALES_CYCLE.md
- LAB_CLI_GUIDE.md
- LAB_PATTERN_REPORT_DRAFT.md
- LICENSING_AND_PARTNERSHIP_PATH.md
- LLMlab_Two_Pager_Final.md
- OUTREACH_EMAIL_TEMPLATES_BY_ICP.md
- QUICKSTART.md
- RD_LLMLAB.md
- README_COMPLETE_WORKFLOW.txt
- README_ECOMMERCE_WORKFLOW.md
- README_KPI_KIT_WORKFLOW.md
- README_PUBLIC.md
- scripts/README.md
- scripts/run_validate_contract.sh
- SALES_ASSETS_PACK.md
- SECURITY.md
- SECURITY_QUESTIONNAIRE_SHORT.md
- SUPPORT_POLICY.md
- TEMPLATE_GOVERNANCE.md
- templates/client/validate_contract_events.json
- templates/client/validate_contract_invoice.json
- VENDOR_READINESS_PACK_INDEX.md
- WEEK_2_PLAYBOOK_AUTHENTICATION_AND_OUTREACH.md
- api_validation/API_ONBOARDING.md
- api_validation/docs/contract-invariants-kit.md
- api_validation/docs/first-clients-targets-and-pilot-plans.md
- api_validation/docs/poc-pilot-technical-steps.md
- api_validation/docs/poc-real-life-playbook.md
- api_validation/public/db_init.py
- api_validation/public/key_admin.py
- api_validation/public/main.py
- api_validation/public/requirements.txt
- api_validation/public/routes/auth.py
- api_validation/public/routes/contracts.py
- api_validation/public/routes/ensemble.py
- api_validation/public/routes/evidence.py
- api_validation/public/routes/fixtures.py
- api_validation/public/routes/signup.py
- api_validation/public/routes/validate.py
- api_validation/public/schemas.py
- demos/client_pilot/README.md
- demos/json_automation/README.md
- demos/json_automation/demo_full_local_runbook.md
- demos/policy_gate/README.md
- domain_kits/contract_invariants/__init__.py
- domain_kits/contract_invariants/engine.py
- domain_kits/kpi_analytics/normalizer.py
- experiment_runner.py
- personalmemo.md
- run_pilot_kpi.py
- tools/__init__.py
- tools/ci/__init__.py
- tools/ci/llmlab_http.py
- tools/ci/run_duckdb_json_contract_gate.py
- tools/ci/run_superstore_artifact_gate.py
- tools/csv_profile_to_json.py
- tools/evidence_pack_to_markdown.py

- DEVELOPER_NARRATIVE.md
- EVIDENCE_ARTIFACT_EXAMPLE.md
- KIT_CATALOG.md

If you need to regenerate this list later:

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
