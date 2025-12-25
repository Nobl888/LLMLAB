Make AI-generated code boringly reliable in domains where errors are expensive.

Deterministic release gates for error-expensive workflows.

You're starting to use LLMs (and agents / IDE copilots) to speed up code and automation—until you need to be sure the numbers, outputs, and operational decisions are actually correct.

This project is a **deterministic release gate**: treat AI-generated code and AI-generated outputs as *stochastic candidates*, then validate them with **oracles, invariants, and reproducible evidence artifacts**.

It’s not “LLM eval.” It’s **release engineering for deterministic changes** — whether the change came from a human PR, an AI assistant, or an automated agent.

---

## Who it’s for

- **Engineering teams** shipping deterministic outputs (KPI/reporting pipelines, structured JSON outputs, automation)
- **Platform/infra owners** who want a CI-style pass/fail gate before changes ship
- **Reviewers (risk/compliance/ops)** who need repeatable evidence artifacts for change control (not a certification)

---

## What you get

- **A CI-style gate** for deterministic work: pass/fail + drift + recommendation.
- **Portable evidence artifacts**: stable trace IDs + hashes + summary so you can attach results to PRs, tickets, or audits.
- **Framework-agnostic enforcement**: works regardless of which tool generated the change (including no-LLM workflows).

---

## Clear positioning

- **Pre-release validation (CI gate):** gates changes *before* they ship.
- **Deterministic correctness:** checks outputs against a baseline/oracle or explicit invariants.
- **Evidence-first workflow:** produces traceable artifacts reviewers can attach to PRs, tickets, and change-control records.

---

## Time saved (why teams pay)

This is designed to reduce the hidden cost of deterministic changes: long debugging loops, re-runs, and review churn.

- **Earlier failure with a concrete reason:** detect drift or invariant violations before production, not after someone notices a broken number.
- **Smaller search space:** validate one workflow against an agreed fixture/contract, so you’re not debugging the entire system.
- **Less review back-and-forth:** attach a stable evidence artifact (hashes + summary) to a PR/ticket so reviewers don’t need to recreate context.

The goal is to make regressions cheaper to catch and faster to resolve—helping teams spend more time building and less time firefighting.

---

## Two kits (today)

### 1) KPI Regression Kit (tabular → computed metrics)

Use when the question is: *“Did a code change alter computed KPIs?”*

- Runs baseline vs candidate KPI logic against a shared fixture.
- Compares outputs with domain-appropriate tolerance rules.
- Best for analytics/BI/backtests/ETL where correctness is numeric.

### 2) Contract / Invariants Kit (JSON outputs → rules)

Use when the question is: *“Is this output valid, stable, and safe to consume?”*

- Validates baseline vs candidate JSON outputs against explicit rules (existence, types, ranges, formats, allowed values).
- Includes best-effort checks for unsafe leakage patterns (e.g., PII-like strings) without echoing raw values.
- No code execution: it’s deterministic, fast, and broadly applicable.

This kit is “high leverage” because many products (agents, config generators, extractors, pipelines) ultimately emit JSON.

---

## Direct applications

1) **Regression gate for deterministic pipelines**
   - Prove refactors (human or AI-assisted) didn’t change results.

2) **Release gating for agents and automation**
   - Enforce invariants on outputs before they reach production systems.

3) **Objective benchmarking for models/agents**
   - Measure correctness against deterministic checks (no LLM-as-judge).

4) **Audit-friendly validation artifacts**
   - Store an evidence pack alongside builds to support later investigation.

---

## Trust posture (designed for sensitive environments)

- **Data minimization by default**: evidence artifacts contain hashes + summaries, not proprietary implementation details.
- **Value-safe detail mode**: optional details can be enabled for debugging, but should remain safe for sharing.
- **Tenant/key controls exist** to support basic isolation and operational hygiene.

Many teams use this as a **pre-validation layer** in regulated environments: it produces repeatable evidence artifacts and enforces deterministic checks before changes ship.

---

## What evolves post-POC (typical hardening)

- Redis-backed rate limiting for multi-instance deployments.
- External log sinks + retention configuration to match customer requirements.
- Additional kits and rule types driven by early customer workflows.

---

## 1-minute evaluation

If you want to assess fit quickly, pick one workflow and run a tiny, controlled comparison:

- **Contract/Invariants kit (fastest):** provide one known-good JSON output and one candidate output. Define (or auto-generate) a small contract, then validate pass/fail and review the evidence artifact.
- **KPI Regression kit:** provide a small fixture and a baseline vs candidate KPI implementation, then verify drift/tolerances and capture the evidence artifact.

The result should be something you can attach to a PR or ticket: a clear recommendation plus traceable evidence (hashes + summary).

The fastest evaluation is a single workflow:

- KPI kit: one metric + one fixture + baseline vs candidate.
- Contract kit: one known-good JSON output + a contract + a candidate output.

This repo keeps implementation details high-level in public-facing docs; deeper integration details are shared privately.

---

## Developer onboarding (copy/paste)

- Narrative for engineers: [DEVELOPER_NARRATIVE.md](DEVELOPER_NARRATIVE.md)
- Step-by-step client testing: [LOCAL_CLIENT_TEST_RUNBOOK.md](LOCAL_CLIENT_TEST_RUNBOOK.md)
- Copy/paste request payloads: [templates/client](templates/client)
- One-command runner: [scripts/run_validate_contract.sh](scripts/run_validate_contract.sh)
