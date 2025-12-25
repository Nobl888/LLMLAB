# Context Packet Index (2512 reference)

Date reference: **2512** (created on 2025-12-25)

This is a dated snapshot index you can point new chats at (without moving any files).

## The short context packet (7 files)

1) [CI_LAUNCH_STARTER.md](../../CI_LAUNCH_STARTER.md) — CI golden path + secrets + what success looks like
2) [HOSTED_SAFE_POSTURE.md](../../HOSTED_SAFE_POSTURE.md) — hosted-safe posture (artifact-first; no customer code execution by default)
3) [API_INTEGRATION_GUIDE.md](../../API_INTEGRATION_GUIDE.md) — integration narrative + request profiles + FAQ
4) [EXEC_BRIEF_BASELINE_ORACLE.md](../../EXEC_BRIEF_BASELINE_ORACLE.md) — executive one-pager (baseline vs oracle; silent wrongness)
5) [API_PRICING_AND_FREEMIUM_STRATEGY.md](../../API_PRICING_AND_FREEMIUM_STRATEGY.md) — outcome-based pricing narrative + “no goldens” differentiator
6) [.github/workflows/llmlab_ci_gates.yml](../../.github/workflows/llmlab_ci_gates.yml) — what CI actually runs (hosted-safe)
7) [RD_LLMLAB.md](../../RD_LLMLAB.md) — R&D applications + “no data” posture + beyond-numeric opportunities

## Optional onboarding assets (recommended for new devs)

- [README_PUBLIC.md](../../README_PUBLIC.md) — public-facing overview + 3-command onboarding
- [LOCAL_CLIENT_TEST_RUNBOOK.md](../../LOCAL_CLIENT_TEST_RUNBOOK.md) — step-by-step client testing + smoke-key bootstrap
- [DEVELOPER_NARRATIVE.md](../../DEVELOPER_NARRATIVE.md) — dev-facing positioning: “release gate, not eval dashboard”
- [KIT_CATALOG.md](../../KIT_CATALOG.md) — kit map + what to use when
- [EVIDENCE_ARTIFACT_EXAMPLE.md](../../EVIDENCE_ARTIFACT_EXAMPLE.md) — redacted evidence artifact example
- [templates/client/validate_contract_invoice.json](../../templates/client/validate_contract_invoice.json) — sample contract payload
- [templates/client/validate_contract_events.json](../../templates/client/validate_contract_events.json) — sample contract payload
- [scripts/run_validate_contract.sh](../../scripts/run_validate_contract.sh) — curl-based runner
- [scripts/README.md](../../scripts/README.md) — scripts usage

## Operational status quick check (for a new chat)

- Live deploy identity: `GET /health` (commit should match the Render deploy)
- Database reachability: `GET /health/db`
- Client smoke (hosted-safe contract mode): run `tools/client/smoke_validate_contract.py` or `bash scripts/run_validate_contract.sh ...`
- Admin/bootstrap endpoints are smoke-key gated and stealth 404 without the smoke key (by design)

## Copy/paste prompt for a new chat

Paste this as the first message in a new chat:

"""
We are working on LLMLAB, a CI-native validation service.

Date reference: 2512 (created 2025-12-25).

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
