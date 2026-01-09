# LLMLAB

[![llmlab-ci-gates](https://github.com/Nobl888/LLMLAB/actions/workflows/llmlab_ci_gates.yml/badge.svg)](https://github.com/Nobl888/LLMLAB/actions/workflows/llmlab_ci_gates.yml)

**CI gates for AI-generated code and data artifacts.**

LLM evaluation gates, portable evidence artifacts, and MLOps guardrails wired straight into GitHub Actions.

Catch regressions before they ship. Attach evidence to PRs.

---

## What it does

| Problem | LLMLAB answer |
|---------|---------------|
| AI-assisted change broke a number | **FAIL** with diff + trace ID |
| Refactor changed outputs unexpectedly | **FAIL** with baseline vs candidate hash |
| Need proof for reviewers/auditors | Evidence artifact you can attach to any ticket |

Under the hood this behaves like a lightweight **LLM eval harness** for:
- JSON contracts / invariants (agents, extractors, config generators)
- KPI regression (analytics/BI, backtests, financial reports)
- Quant-style CSV oracles (e.g., QQQ SMA crossover strategy comparisons)

---

## Quickstart: GitHub Actions CI gates

1. **Fork and enable Actions**
   - Fork this repo (Use this template or Fork in GitHub).
   - In your fork, go to **Actions** → enable workflows if prompted.

2. **Set LLMLAB secrets** (Settings → Secrets and variables → Actions → New repository secret):
   - `LLMLAB_API_BASE_URL` – your hosted validation API base URL (for example, `https://llmlab-t6zg.onrender.com`).
   - `LLMLAB_API_KEY` – API key issued by the LLMLAB backend.
   - `LLMLAB_TENANT_ID` – tenant UUID/slug for this repo.

3. **Push or open a PR**
   - On every push/PR, `.github/workflows/llmlab_ci_gates.yml` runs:
     - Offline: compiles and imports `api_validation`, `domain_kits`, and `tools`.
     - Online: calls `/api/contracts/validate` and `/api/ensemble/validate` via the smoke clients.
     - Uploads `.llmlab_artifacts/**` as a `llmlab-evidence` GitHub Actions artifact.
   - If you haven't set LLMLAB secrets yet, the workflow still runs offline checks but **skips API calls** and stays non-blocking for forks.

4. **Inspect the evidence pack**
   - Open the workflow run → **Artifacts** → download `llmlab-evidence`.
   - Inside you’ll find JSON evidence packs (`evidence_pack`) with hashes, risk/summary, and recommendations you can paste into PRs or tickets.
   - For a deeper API walkthrough (OpenAPI, QQQ oracle, Superstore KPI suites) see `API_VALIDATION_ONBOARDING_RECAP.md` in this repo.

---

## What you get per PR

```
✓ PASS / ✗ FAIL
trace_id: 943098ab-...
baseline_hash: sha256:38f907c...
candidate_hash: sha256:38f907c...
recommendation: APPROVE / REVIEW / REJECT
```

Attach this to your PR comment or ticket. Done.

---

## Who it's for

- MLOps and platform teams shipping **KPI pipelines, reports, ETL, automation**
- Quants and data scientists running **backtests and trading strategy analytics** (QQQ-style CSV oracles)
- Engineering teams who need **deterministic correctness** (not vibes) for LLM-assisted workflows
- Reviewers and risk/compliance who want **attachable evidence** (EU AI Act-style technical files, audits) without re-running everything

## Why not just guardrails or eval dashboards?

- Guardrails help block obviously bad text at runtime; LLMLAB ensures **structured outputs and KPIs don’t silently drift** before deploy.
- Eval dashboards show aggregate model quality; LLMLAB gives you **per-PR, attachable evidence packs** you can paste into tickets.
- Both coexist: LLMLAB plugs into the GitHub Actions surface you already use.

Keywords: LLM evaluation, GitHub Actions, CI gates, MLOps, quantitative finance, algo trading, KPI drift, JSON contracts, evidence artifacts.
