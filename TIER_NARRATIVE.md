# Tier Narrative (Gold / Silver / Bronze)

This document defines **validation evidence tiers** for LLMLAB artifacts.

These tiers are **not pricing tiers** (e.g., free/pilot/production). They are a neutral way to describe **what validation scope was executed** and what evidence is available for review.

## Design principles

- **Coverage, not judgment:** tiers describe scope completed, not “quality” or “safety.”
- **Audit-first:** every tier maps to concrete evidence artifacts (portfolio JSON + per-gate outputs).
- **No negative language:** avoid “failed build = unsafe.” Use “scope not completed” / “not included in this run.”
- **No over-claims:** avoid “guaranteed,” “certified,” “compliant” unless you run a formal certification program.

## The tiers (neutral wording)

### GOLD — Full Offline Evidence Pack

**Meaning:** The full deterministic offline suite was executed for this build and produced an auditable evidence record.

**Problems solved (what the audience should hear):**
- Reproducible regression prevention without relying on external services.
- Fast, reviewable proof of what was validated for a specific commit.

**Suggested one-liners:**
- "Full offline validation suite completed with an auditable evidence pack for this build."
- "Deterministic validation coverage completed; evidence available for review."

### SILVER — Core Offline Evidence Pack

**Meaning:** Core offline validations were executed and recorded; some optional/extended validations were not included in this run.

**Problems solved:**
- High-signal PR/iteration confidence with traceable evidence.
- Clear, reviewable scope even when time/compute constraints apply.

**Suggested one-liners:**
- "Core offline validations completed; evidence pack available for review."
- "Core coverage completed; extended checks were not included in this run."

### BRONZE — Baseline Integrity Evidence Pack

**Meaning:** Baseline integrity checks were executed and recorded (e.g., import/syntax + minimal invariants).

**Problems solved:**
- Prevents obvious breakage and captures a minimal audit trail.

**Suggested one-liners:**
- "Baseline integrity validations completed; evidence pack available for review."
- "Baseline scope completed to prevent obvious breakage; evidence recorded."

## Audience-aligned framing

### Engineering / CI

- GOLD: merge/release eligible under a "full offline suite" policy.
- SILVER: merge eligible for iteration; schedule GOLD before release.
- BRONZE: useful as a sanity gate; not a release signal.

### Exec / Product

- GOLD: "We can reproduce the validation record for this build on demand."
- SILVER: "We have strong directional confidence with traceability."
- BRONZE: "We eliminate basic regressions and capture a minimal proof trail."

### Customer / Security / Compliance stakeholders

- "Each build produces an evidence pack describing which validations were executed and their results."
- "Tiers indicate evidence coverage level; artifacts are portable and reviewable."

## Evidence mapping (what to show)

At minimum, tiers should map to the portfolio evidence artifact:
- `.llmlab_artifacts/gate_portfolio/offline_gate_portfolio.json`

The portfolio evidence can record both:
- `coverage_tier`: which scope was selected (e.g., `GOLD`/`SILVER`/`BRONZE`)
- `verdict`: whether the selected scope passed as executed

In automation, use the portfolio runner coverage switch to make scope explicit:
- `python tools/gate_portfolio/run_offline_gate_portfolio.py --mode gold`
- `python tools/gate_portfolio/run_offline_gate_portfolio.py --mode silver`
- `python tools/gate_portfolio/run_offline_gate_portfolio.py --mode bronze`

Optionally, tiers may also reference:
- `.llmlab_artifacts/gate_portfolio/portfolio_history.csv` (diff-friendly summary per run)
- Any per-gate artifacts produced under `.llmlab_artifacts/**`

## Recommended terminology (safe)

Prefer:
- "completed" / "included" / "recorded" / "evidence available" / "scope"

Avoid:
- "unsafe" / "non-compliant" / "certified" / "guaranteed"
