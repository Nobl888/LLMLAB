# Context Packet Index (2727 reference)

Date reference: **2727** (created on 2025-12-27)

This is a dated snapshot index you can point new chats at (without moving any files).

## Addendum (what changed since 2512)

- Coarse topology / diversity indicator is now supported as **metadata-only** in evidence packs (safe buckets only):
  - `evidence_pack.topology.diversity_bucket` is one of `LOW|MEDIUM|HIGH`
  - optional `evidence_pack.topology.version` for internal change control
- Hosted-safe ensemble smoke path exists and can be run from a client/CI:
  - `tools/client/smoke_validate_ensemble.py`
- CI live smokes (when secrets exist) run **both** contract + ensemble and upload `.llmlab_artifacts/**`.
- Enterprise-facing trust layer is present and linked from onboarding:
  - `ACCEPTABLE_USE_POLICY.md`
  - `TERMS.md`
  - `QUICKSTART.md` links “Trust & Terms”

## Addendum (2026-01-01)

- Bayes wind-tunnel CI gates expanded (offline, deterministic artifacts under `.llmlab_artifacts/`):
  - HMM synthetic filtering gate now includes an explicit **OOD-shift / change-point** suite.
  - Coin-flip (Beta-Bernoulli) wind-tunnel gate added.
  - Bijection elimination wind-tunnel gate added (combinatorial posterior tracking; arXiv:2512.22471-aligned).
  - Telco churn calibration gate now includes an explicit **confident-but-wrong** baseline for deterministic separation.

- Internal “canonical indicators” oracle/validator harness exists to support evidence-first evaluation of generated logic (beyond simple request/response CI checks):
  - `tools/qqq_canonical_indicators/` (oracles, runner, summaries)
  - `tasks/qqq_canonical_indicators/README.md` (how to run + interpret attempted vs validated)
- ATR14 experiment hygiene tightened (NaN convention clarified; runtime vs validation failures explicitly tracked); latest ATR14 sweep validates cleanly at `1e-12`.

- Composite indicator high-temperature guided batches are now validated cleanly through **T=3.0**:
  - `composite_v1`: `attempted=348 PASS=348 FAIL=0`, with `max_abs_diff_max=0.0`
  - Per-temp summaries live under `.llmlab_artifacts/qqq_canonical_indicators/composite_v1/`
  - Latest batch: `T=3.0 attempted=12 PASS=12`

- Import workflow for LLM multi-file markdown replies supports safe overwrite with backups:
  - `python tools/qqq_canonical_indicators/import_llm_markdown.py --in <reply.md> --out-dir candidates --overwrite --backup-existing`

- Automation recommendation (prevents silent regression during launch): add a CI step to run the offline oracle validator and upload `.llmlab_artifacts/**`:
  - `python tools/qqq_canonical_indicators/runner.py --indicator composite_v1`

IP / safety note:
- Keep detailed topology artifacts (family names, per-temperature breakdowns, exact entropy) private.
- Only emit the coarse `LOW|MEDIUM|HIGH` bucket from the hosted API.

## The short context packet (7 files)

1) [CI_LAUNCH_STARTER.md](../../CI_LAUNCH_STARTER.md) — CI golden path + secrets + what success looks like
2) [HOSTED_SAFE_POSTURE.md](../../HOSTED_SAFE_POSTURE.md) — hosted-safe posture (artifact-first; customer code execution stays on customer infrastructure by default)
3) [API_INTEGRATION_GUIDE.md](../../API_INTEGRATION_GUIDE.md) — integration narrative + request profiles + FAQ
4) [EXEC_BRIEF_BASELINE_ORACLE.md](../../EXEC_BRIEF_BASELINE_ORACLE.md) — executive one-pager (baseline vs oracle; silent wrongness)
5) [API_PRICING_AND_FREEMIUM_STRATEGY.md](../../API_PRICING_AND_FREEMIUM_STRATEGY.md) — outcome-based pricing narrative + “golden-free” differentiator
6) [.github/workflows/llmlab_ci_gates.yml](../../.github/workflows/llmlab_ci_gates.yml) — what CI actually runs (hosted-safe)
7) [RD_LLMLAB.md](../../RD_LLMLAB.md) — R&D applications + “data-minimization” posture + beyond-numeric opportunities

## Optional onboarding assets (recommended for new devs)

- [QUICKSTART.md](../../QUICKSTART.md) — onboarding entry point (includes “Trust & Terms”)
- [ACCEPTABLE_USE_POLICY.md](../../ACCEPTABLE_USE_POLICY.md)
- [TERMS.md](../../TERMS.md)
- [LOCAL_CLIENT_TEST_RUNBOOK.md](../../LOCAL_CLIENT_TEST_RUNBOOK.md) — step-by-step client testing + smoke-key bootstrap
- [LLMLAB_ONE_PAGER.md](../../LLMLAB_ONE_PAGER.md) — slide-ready overview

## Operational status quick check (for a new chat)

- Live deploy identity: `GET /health` (commit should match the deploy)
- Database reachability (if enabled): `GET /health/db`
- Client smoke (contract): run `python tools/client/smoke_validate_contract.py`
- Client smoke (ensemble): run `python tools/client/smoke_validate_ensemble.py`

CI safety knob:
- Set GitHub repo variable `LLMLAB_REQUIRE_DB_HEALTH=true` to require `GET /health/db` to pass in CI before live smoke gates run.

Topology emission quick check:
- Set (server-side) `LLMLAB_TOPOLOGY_BUCKET=LOW|MEDIUM|HIGH`
- Optional (server-side) `LLMLAB_TOPOLOGY_VERSION=<string>`
- Optionally assert in clients/CI: `LLMLAB_REQUIRE_TOPOLOGY=true`

## Copy/paste prompt for a new chat

Paste this as the first message in a new chat:

"""
We are working on LLMLAB, a CI-native validation service.

Date reference: 2727 (created 2025-12-27).

Non-negotiables:
- Hosted-safe by default: customers run code/data locally; service validates structured artifacts; customer code execution stays on customer infrastructure in hosted mode.
- Deliverable is a portable evidence pack per gate/run (hash-first; optionally signed).
- Multi-tenant API key auth; CI workflow exists.
- IP protection: topology indicators exposed publicly must remain coarse (LOW|MEDIUM|HIGH only).

Canonical docs to use as truth:
- CI_LAUNCH_STARTER.md
- HOSTED_SAFE_POSTURE.md
- API_INTEGRATION_GUIDE.md
- EXEC_BRIEF_BASELINE_ORACLE.md
- API_PRICING_AND_FREEMIUM_STRATEGY.md
- .github/workflows/llmlab_ci_gates.yml
- RD_LLMLAB.md

Goal for this chat:
(you fill in: e.g., add a new hosted-safe suite, tighten evidence pack signing, refine customer onboarding, etc.)
"""

## Files created/modified recently (last 7 days)

Use the canonical list in [CONTEXT_PACKET_INDEX.md](../../CONTEXT_PACKET_INDEX.md) to avoid duplicating/rotting this section.
