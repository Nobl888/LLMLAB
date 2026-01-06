# LLMLAB

**CI gates for AI-generated code and data artifacts.**

Catch regressions before they ship. Attach evidence to PRs.

---

## What it does

| Problem | LLMLAB answer |
|---------|---------------|
| AI-assisted change broke a number | **FAIL** with diff + trace ID |
| Refactor changed outputs unexpectedly | **FAIL** with baseline vs candidate hash |
| Need proof for reviewers/auditors | Evidence artifact you can attach to any ticket |

---

## Enable GitHub Actions (3 steps)

1. **Set Secrets** (Settings → Secrets and variables → Actions):
   - `LLMLAB_API_BASE_URL`
   - `LLMLAB_API_KEY`
   - `LLMLAB_TENANT_ID`

2. **Enable the workflow**:
   - Go to **Actions** tab → click **"I understand my workflows, go ahead and enable them"**
   - Or rename `.github/workflows/llmlab_ci_gates.yml` if workflows are disabled by default

3. **Push or open a PR** — the gate runs automatically.

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

- Teams shipping **KPI pipelines, reports, ETL, automation**
- Anyone who needs **deterministic correctness** (not vibes)
- Reviewers who want **attachable evidence** (not re-running everything)

---

## Links

- [CI_LAUNCH_STARTER.md](CI_LAUNCH_STARTER.md) — golden-path setup
- [SECURITY.md](SECURITY.md) — secrets handling
