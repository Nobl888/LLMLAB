# Rotate Secrets Before Launch (Checklist)

Goal: reduce risk of accidental leaks and cut down “unknown exposure” before you ship or start inviting external use.

This is operational hygiene, not legal advice.

## 0) What counts as “launch” here

Any of:
- You start pushing the repo to a remote you don’t fully control.
- You enable GitHub Actions on a shared org repo.
- You deploy a hosted endpoint that anyone outside you can hit.

## 1) Inventory what you actually use (10 minutes)

Write down the **minimum set** of secrets that matter for runtime:

- Render service
  - Database URL / Postgres credentials
  - Any service API keys (e.g., `LLMLAB_API_KEY` if calling upstream, `OPENAI_API_KEY` if used, etc.)
- GitHub Actions
  - `LLMLAB_API_BASE_URL` (or legacy `LLMLAB_API_BASE`)
  - `LLMLAB_API_KEY`
  - `LLMLAB_TENANT_ID`

Rule: if you can’t name it, you can’t secure it.

## 2) Decide rotation scope (simple decision)

Rotate **now** if:
- You pasted secrets into any chat (even “internal”) or copied into docs/runbooks.
- Anyone else has had access to the workstation.
- You’re unsure where the value has been.

Defer rotation if:
- It only ever lived in Render/GitHub Secrets and never in plaintext notes.
- Nothing is live and no one else can access it.

## 3) Rotate Render Postgres (recommended before any public exposure)

Options (pick the simplest you can execute):
- **Best**: create a new DB / new user, update `DATABASE_URL`.
- **Good**: rotate user password and regenerate `DATABASE_URL`.

After updating Render env vars:
- Trigger a redeploy.
- Hit `GET /health/db` to confirm.

## 4) Rotate application/API keys

- Rotate any upstream API keys you rely on.
- Rotate LLMLAB tenant keys if you generated “test keys” and copied them around.

After updating Render env vars:
- Trigger a redeploy.
- Hit `GET /health` and run the local smoke script if applicable.

## 5) Rotate GitHub Actions secrets (if you use live API gates)

In GitHub repo settings:
- Remove old secrets.
- Add new values.

Then:
- Trigger workflow run manually (workflow_dispatch) to confirm.

## 6) Verify nothing is committed (sanity)

- Confirm `.env` and other secret files are not tracked.
- Scan tracked files + git history for key-like patterns.

(We already did a best-effort scan in this workspace and did **not** find key-like patterns in tracked files/history.)

## 7) Post-rotation “done” signals

- Render logs show normal startup (no auth errors)
- `GET /health` returns expected commit
- `GET /health/db` passes
- GitHub Actions runs without failing on secrets

## 8) Keep it from happening again

- Treat anything you paste into chat as potentially persistent.
- Keep secrets only in:
  - Render env vars
  - GitHub Actions secrets
  - local `.env` (never committed)

---

## Reference

Add this checklist to the `2512` reference packet so it’s easy to find in a fresh chat:
- `LLMLAB/context/2512/CONTEXT_PACKET_INDEX_2512.md`
