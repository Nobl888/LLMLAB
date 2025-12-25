# LLMLAB for Developers: make AI changes boringly safe

You don’t need another “eval dashboard.” You need a release gate.

LLMLAB treats AI-generated code and AI-generated outputs as **stochastic candidates**. Instead of debating intent, it validates **deterministic consequences**.

## The problem (what devs actually live)

- A small refactor ships and a KPI shifts. No one notices for days.
- An agent outputs JSON that “looks right” until a downstream system breaks.
- Reviewers ask for proof, but reproducing the exact state takes hours.

The hidden cost isn’t the bug — it’s the debugging loop, re-runs, and review churn.

## The idea (how it works)

- You already have a baseline (known-good output) and a candidate (new output).
- LLMLAB compares them using:
  - **contracts / invariants** (schema, types, ranges, allowed values)
  - **domain rules** (KPI tolerances, drift checks)
- It returns a CI-friendly result:
  - pass/fail recommendation
  - trace ID
  - **evidence hashes** so results are reproducible and attachable

## What makes it feel “enterprise”

- **Hosted-safe by default:** contract mode does not execute customer code.
- **Stealth auth:** invalid keys look like 404 (reduces probing surface).
- **Tenant isolation:** strict `X-Tenant-ID` match.
- **Evidence-first:** outputs are designed to be attached to PRs/tickets.

## The fastest first win (5 minutes)

1) Pick one deterministic workflow.
2) Capture one baseline JSON output.
3) Define 3–6 invariants (types, ranges, allowed values).
4) Run `POST /api/validate` and attach the response evidence to your PR.

If it fails, you catch the drift before production. If it passes, you ship with confidence.

## Copy/paste templates

- Use the starter payloads in templates/client:
  - `validate_contract_invoice.json`
  - `validate_contract_events.json`

Run them with the script:

```bash
bash scripts/run_validate_contract.sh templates/client/validate_contract_invoice.json
```
