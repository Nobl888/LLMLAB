from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import re


@dataclass(frozen=True)
class CheckResult:
    rule_id: str
    ok: bool
    message: str
    path: Optional[str] = None


def _split_path(path: str) -> List[str]:
    return [p for p in (path or "").split(".") if p]


def _get_path_value(obj: Any, path: str) -> Tuple[bool, Any]:
    """Return (found, value) for dotted dict paths.

    Supported: dict traversal only (no array indexing) to keep this safe and simple.
    """
    cur = obj
    for key in _split_path(path):
        if not isinstance(cur, dict):
            return False, None
        if key not in cur:
            return False, None
        cur = cur[key]
    return True, cur


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def _iter_strings(obj: Any) -> List[str]:
    """Collect strings from a JSON-like structure.

    Returns actual strings in-memory but callers must never return them.
    """
    out: List[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_iter_strings(item))
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_iter_strings(v))
    return out


def _safe_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def evaluate_contract(
    *,
    baseline: Dict[str, Any],
    candidate: Dict[str, Any],
    contract: Dict[str, Any],
) -> Dict[str, Any]:
    """Evaluate candidate (and optionally baseline) against a contract.

    Contract format (minimal, stable):

    {
      "schema_version": "1.0",
      "rules": [
        {"id": "r1", "type": "exists", "path": "metrics.revenue"},
        {"id": "r2", "type": "type_is", "path": "metrics.revenue", "expected": "number"},
        {"id": "r3", "type": "approx", "path": "metrics.revenue", "baseline_path": "metrics.revenue", "abs_tol": 0.01},
        {"id": "r4", "type": "range", "path": "metrics.margin", "min": 0, "max": 1},
        {"id": "r5", "type": "regex", "path": "meta.run_id", "pattern": "^[a-z0-9_-]{6,64}$"},
        {"id": "r6", "type": "no_pii", "paths": ["*"], "patterns": ["email", "phone"]}
      ]
    }

    Safety: details returned are rule ids + paths + messages, never raw values.
    """

    rules = contract.get("rules") or []
    if not isinstance(rules, list):
        rules = []

    check_results: List[CheckResult] = []

    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            check_results.append(
                CheckResult(rule_id=f"rule_{idx}", ok=False, message="Invalid rule (not an object)")
            )
            continue

        rule_id = str(rule.get("id") or f"rule_{idx}")
        rule_type = str(rule.get("type") or "").strip().lower()

        try:
            if rule_type == "exists":
                path = str(rule.get("path") or "")
                found, _ = _get_path_value(candidate, path)
                check_results.append(CheckResult(rule_id=rule_id, ok=bool(found), path=path, message="exists" if found else "missing"))

            elif rule_type == "type_is":
                path = str(rule.get("path") or "")
                expected = str(rule.get("expected") or "")
                found, value = _get_path_value(candidate, path)
                if not found:
                    check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="missing"))
                else:
                    actual = _type_name(value)
                    ok = actual == expected
                    check_results.append(
                        CheckResult(
                            rule_id=rule_id,
                            ok=ok,
                            path=path,
                            message=(
                                f"type={actual}" if ok else f"type_mismatch expected={expected} got={actual}"
                            ),
                        )
                    )

            elif rule_type == "eq":
                path = str(rule.get("path") or "")
                baseline_path = rule.get("baseline_path")
                has_value = "value" in rule

                found_c, cand_val = _get_path_value(candidate, path)
                if not found_c:
                    check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="missing"))
                    continue

                if baseline_path is not None:
                    found_b, base_val = _get_path_value(baseline, str(baseline_path))
                    if not found_b:
                        check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="baseline_missing"))
                        continue
                    ok = cand_val == base_val
                    check_results.append(CheckResult(rule_id=rule_id, ok=ok, path=path, message="eq_baseline" if ok else "neq_baseline"))
                elif has_value:
                    ok = cand_val == rule.get("value")
                    check_results.append(CheckResult(rule_id=rule_id, ok=ok, path=path, message="eq_value" if ok else "neq_value"))
                else:
                    check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="eq_missing_comparator"))

            elif rule_type == "approx":
                path = str(rule.get("path") or "")
                baseline_path = rule.get("baseline_path")
                abs_tol = float(rule.get("abs_tol") or 0.0)
                rel_tol = float(rule.get("rel_tol") or 0.0)

                found_c, cand_val = _get_path_value(candidate, path)
                if not found_c:
                    check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="missing"))
                    continue

                cand_f = _safe_float(cand_val)
                if cand_f is None:
                    check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="not_numeric"))
                    continue

                if baseline_path is not None:
                    found_b, base_val = _get_path_value(baseline, str(baseline_path))
                    if not found_b:
                        check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="baseline_missing"))
                        continue
                    base_f = _safe_float(base_val)
                    if base_f is None:
                        check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="baseline_not_numeric"))
                        continue
                    diff = abs(cand_f - base_f)
                    denom = max(abs(base_f), 1e-12)
                    ok = (diff <= abs_tol) or ((diff / denom) <= rel_tol)
                    check_results.append(CheckResult(rule_id=rule_id, ok=ok, path=path, message="approx_baseline" if ok else "drift_exceeded"))
                elif "value" in rule:
                    target_f = _safe_float(rule.get("value"))
                    if target_f is None:
                        check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="target_not_numeric"))
                        continue
                    diff = abs(cand_f - target_f)
                    denom = max(abs(target_f), 1e-12)
                    ok = (diff <= abs_tol) or ((diff / denom) <= rel_tol)
                    check_results.append(CheckResult(rule_id=rule_id, ok=ok, path=path, message="approx_value" if ok else "drift_exceeded"))
                else:
                    check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="approx_missing_comparator"))

            elif rule_type == "range":
                path = str(rule.get("path") or "")
                min_v = rule.get("min")
                max_v = rule.get("max")
                found, value = _get_path_value(candidate, path)
                if not found:
                    check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="missing"))
                    continue
                value_f = _safe_float(value)
                if value_f is None:
                    check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="not_numeric"))
                    continue
                ok = True
                if min_v is not None:
                    ok = ok and (value_f >= float(min_v))
                if max_v is not None:
                    ok = ok and (value_f <= float(max_v))
                check_results.append(CheckResult(rule_id=rule_id, ok=ok, path=path, message="in_range" if ok else "out_of_range"))

            elif rule_type == "regex":
                path = str(rule.get("path") or "")
                pattern = str(rule.get("pattern") or "")
                found, value = _get_path_value(candidate, path)
                if not found:
                    check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="missing"))
                    continue
                if not isinstance(value, str):
                    check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="not_string"))
                    continue
                ok = bool(re.match(pattern, value))
                check_results.append(CheckResult(rule_id=rule_id, ok=ok, path=path, message="regex_match" if ok else "regex_mismatch"))

            elif rule_type == "in":
                path = str(rule.get("path") or "")
                allowed = rule.get("allowed")
                if not isinstance(allowed, list):
                    allowed = []
                found, value = _get_path_value(candidate, path)
                if not found:
                    check_results.append(CheckResult(rule_id=rule_id, ok=False, path=path, message="missing"))
                    continue
                ok = value in allowed
                check_results.append(CheckResult(rule_id=rule_id, ok=ok, path=path, message="allowed" if ok else "not_allowed"))

            elif rule_type == "no_pii":
                paths = rule.get("paths")
                if not isinstance(paths, list) or not paths:
                    paths = ["*"]

                patterns = rule.get("patterns")
                if not isinstance(patterns, list) or not patterns:
                    patterns = ["email", "phone"]

                compiled: List[re.Pattern[str]] = []
                for p in patterns:
                    if p == "email":
                        compiled.append(re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE))
                    elif p == "phone":
                        compiled.append(re.compile(r"\+?\d[\d\s().-]{7,}\d"))
                    else:
                        compiled.append(re.compile(str(p)))

                values_to_scan: List[str] = []
                for pth in paths:
                    if pth == "*":
                        values_to_scan.extend(_iter_strings(candidate))
                        continue
                    found, value = _get_path_value(candidate, str(pth))
                    if found:
                        values_to_scan.extend(_iter_strings(value))

                detected = False
                for s in values_to_scan:
                    for rx in compiled:
                        if rx.search(s):
                            detected = True
                            break
                    if detected:
                        break

                check_results.append(
                    CheckResult(
                        rule_id=rule_id,
                        ok=not detected,
                        path=None,
                        message="no_pii" if not detected else "pii_detected",
                    )
                )

            else:
                check_results.append(CheckResult(rule_id=rule_id, ok=False, path=None, message=f"unknown_rule_type:{rule_type}"))

        except Exception:
            check_results.append(CheckResult(rule_id=rule_id, ok=False, path=rule.get("path"), message="rule_error"))

    total = len(check_results)
    failed = [r for r in check_results if not r.ok]

    return {
        "total_checks": total,
        "failed_checks": len(failed),
        "pass_rate": (0.0 if total == 0 else (total - len(failed)) / total),
        "checks": [
            {"id": r.rule_id, "ok": r.ok, "path": r.path, "message": r.message} for r in check_results
        ],
    }
