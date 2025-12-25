"""Minimal HTTP client helpers for LLMLAB CI gates.

- Uses stdlib only (urllib) to avoid extra deps in CI.
- Auth headers:
  - Authorization: Bearer <api-key>
  - X-Tenant-ID: <tenant-uuid>

Environment variables:
- LLMLAB_API_BASE_URL (preferred; default: http://localhost:8000)
- LLMLAB_API_BASE (legacy alias for base URL)
- LLMLAB_API_KEY
- LLMLAB_TENANT_ID
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def require_env(name: str) -> str:
    value = env(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def post_json(path: str, payload: dict[str, Any], *, timeout_s: int = 30) -> dict[str, Any]:
    base_url_raw = os.getenv("LLMLAB_API_BASE_URL") or os.getenv("LLMLAB_API_BASE")
    if os.getenv("GITHUB_ACTIONS", "").lower() == "true" and (base_url_raw is None or base_url_raw.strip() == ""):
        raise RuntimeError(
            "LLMLAB_API_BASE_URL (or legacy LLMLAB_API_BASE) must be set in GitHub Actions to avoid accidentally calling localhost with real secrets."
        )

    base_url = env("LLMLAB_API_BASE_URL") or env("LLMLAB_API_BASE") or "http://localhost:8000"
    api_key = require_env("LLMLAB_API_KEY")
    tenant_id = require_env("LLMLAB_TENANT_ID")

    url = base_url.rstrip("/") + path
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "X-Tenant-ID": tenant_id,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if getattr(e, "fp", None) else ""
        try:
            detail = json.loads(raw) if raw else {"raw": raw}
        except Exception:
            detail = {"raw": raw}
        raise RuntimeError(f"HTTP {e.code} calling {url}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error calling {url}: {e}") from e
