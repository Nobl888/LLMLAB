"""Topological / diversity indicators (safe, coarse).

This module intentionally exposes only coarse, non-reversible signals suitable for
enterprise governance and audit artifacts.

Do NOT add algorithm-family identifiers, raw entropy values, or per-temperature
breakdowns here. Those belong in private scoring infrastructure.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


_ALLOWED_BUCKETS = {"LOW", "MEDIUM", "HIGH"}


def get_topology_indicator() -> Optional[Dict[str, Any]]:
    """Return a coarse topology indicator for evidence packs.

    This is designed to be populated by the operator / private scoring layer via
    environment variables. The public wrapper only passes through the coarse value.

    Env:
      - LLMLAB_TOPOLOGY_BUCKET: LOW|MEDIUM|HIGH
      - LLMLAB_TOPOLOGY_VERSION: optional string for internal change control
    """

    bucket = (os.getenv("LLMLAB_TOPOLOGY_BUCKET") or "").strip().upper()
    if not bucket:
        return None

    if bucket not in _ALLOWED_BUCKETS:
        # Fail-safe: if misconfigured, do not emit potentially confusing data.
        return None

    version = (os.getenv("LLMLAB_TOPOLOGY_VERSION") or "").strip() or None

    out: Dict[str, Any] = {
        "diversity_bucket": bucket,
    }
    if version:
        out["version"] = version

    return out
