# Kit Catalog (developer-facing)

This is the quick map of what LLMLAB validates today and how to think about it.

## 1) Contract / Invariants Kit (JSON → deterministic rules)

Use when the question is: “Is this JSON output valid, stable, and safe to consume?”

- Input: `baseline_output`, `candidate_output`, optional `contract` rules
- Output: recommendation + trace IDs + evidence hashes
- Hosted-safe: yes (no customer code execution)
- Best for: agents, extractors, config generators, automation outputs, API responses

Starter templates:
- [templates/client/validate_contract_invoice.json](templates/client/validate_contract_invoice.json)
- [templates/client/validate_contract_events.json](templates/client/validate_contract_events.json)

Run:

```bash
bash scripts/run_validate_contract.sh templates/client/validate_contract_invoice.json
```

## 2) KPI Regression Kit (tabular → computed metrics)

Use when the question is: “Did a change alter computed KPIs beyond acceptable tolerance?”

- Input: shared fixture + baseline vs candidate KPI outputs (or kit execution in private/self-hosted mode)
- Output: drift/tolerance summary + recommendation + evidence
- Hosted-safe posture: default hosted mode is artifact-first; KPI code execution can be gated off/on by env
- Best for: analytics, BI, finance reporting, backtests, ETL validation

## Templates (reusable contracts)

If you want standardized “quality gates” per domain, use templates:

- List templates (authenticated): `GET /api/contracts/templates`
- Validate with a template: `POST /api/contracts/validate`

Templates let teams share a stable policy across repos without rewriting rules.

## 3) Ensemble / Suite Gates (multiple checks → one decision)

Use when the question is: “Can I run a small suite of deterministic gates and get one attachable artifact?”

- Input: multiple gate steps (contract checks, artifact comparisons, etc.)
- Output: a single decision + trace IDs + evidence hashes
- Best for: PR gates that need a repeatable bundle (same in local, CI, and change-control)

## How to pick

- If you’re gating structured JSON outputs → start with **Contract / Invariants**.
- If you’re gating numeric dashboards/reports/backtests → use **KPI Regression**.
- If you need “one job runs multiple checks” → use **Ensemble / Suite**.

## Example real-world flows

- **Invoice agent:** contract kit ensures required fields / ranges stay stable as prompts and models evolve.
- **Revenue dashboard:** KPI regression kit alerts when a refactor quietly shifts key metrics.
- **Strategy backtest:** ensemble gate bundles several CSV and KPI comparisons into one attachable decision.

You can start with one small, boring check and grow into richer kits over time without changing your CI wiring.
