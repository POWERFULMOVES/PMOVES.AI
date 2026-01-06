"""Utility helpers for retrieval evaluation scripts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> str:
    """Return a UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).strftime(ISO_FORMAT)


def compute_sha256(path: Path | str) -> str:
    """Compute the SHA256 hash of a file."""
    h = hashlib.sha256()
    p = Path(path)
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path | str) -> Any:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def artifact_metadata(path: Path | str) -> Dict[str, Any]:
    p = Path(path)
    return {"path": str(p), "sha256": compute_sha256(p)}


def resolve_field(data: Any, path: str) -> Any:
    """Resolve a dotted path within nested dictionaries/lists."""
    current = data
    for part in path.split("."):
        if isinstance(current, Mapping):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                idx = int(part)
            except ValueError:
                return None
            if idx < 0 or idx >= len(current):
                return None
            current = current[idx]
        else:
            return None
    return current


def _normalize_iterable(value: Any) -> Iterable[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return value
    return [value]


def match_filter(context: Mapping[str, Any], flt: Mapping[str, Any]) -> bool:
    field = flt.get("field")
    if not field:
        return True
    value = resolve_field(context, field)

    if "equals" in flt and value != flt["equals"]:
        return False
    if "not_equals" in flt and value == flt["not_equals"]:
        return False

    if "in" in flt:
        allowed = set(_normalize_iterable(flt["in"]))
        if isinstance(value, (list, tuple, set)):
            if not any(v in allowed for v in value):
                return False
        elif value not in allowed:
            return False

    if "not_in" in flt:
        blocked = set(_normalize_iterable(flt["not_in"]))
        if isinstance(value, (list, tuple, set)):
            if any(v in blocked for v in value):
                return False
        elif value in blocked:
            return False

    if "contains_any" in flt:
        if not isinstance(value, (list, tuple, set)):
            return False
        targets = set(_normalize_iterable(flt["contains_any"]))
        if not any(v in targets for v in value):
            return False

    if "exists" in flt:
        exists = flt["exists"]
        if exists and value is None:
            return False
        if not exists and value is not None:
            return False

    return True


def match_filters(context: Mapping[str, Any], filters: Iterable[Mapping[str, Any]]) -> bool:
    return all(match_filter(context, flt) for flt in filters or [])


def evaluate_thresholds(metrics: Mapping[str, float], thresholds: Mapping[str, Mapping[str, float]]):
    """Evaluate metric thresholds, returning pass/fail per metric and overall."""
    evaluations: Dict[str, Any] = {}
    overall_passed = True
    for metric, rules in thresholds.items():
        value = metrics.get(metric)
        metric_passed = True
        rule_min = rules.get("min") if isinstance(rules, Mapping) else None
        rule_max = rules.get("max") if isinstance(rules, Mapping) else None

        if value is None:
            metric_passed = False
        else:
            if rule_min is not None and value < rule_min:
                metric_passed = False
            if rule_max is not None and value > rule_max:
                metric_passed = False
        evaluations[metric] = {
            "value": value,
            "min": rule_min,
            "max": rule_max,
            "passed": metric_passed,
        }
        if not metric_passed:
            overall_passed = False
    return overall_passed, evaluations


def build_suite_context(result: Mapping[str, Any]) -> Dict[str, Any]:
    source = result.get("source", {})
    context = {
        "source": source,
        "result": result,
        "metadata": source.get("metadata", {}),
        "tags": source.get("tags", []),
    }
    context.update(source)
    return context


def evaluate_suites(
    results: Iterable[Mapping[str, Any]],
    suite_config: Optional[Mapping[str, Any]],
    default_metrics: Iterable[str],
) -> List[Dict[str, Any]]:
    if not suite_config:
        return []
    suites = []
    available_metrics = list(default_metrics)
    for suite in suite_config.get("suites", []):
        filters = suite.get("filters", [])
        matched: List[Mapping[str, Any]] = []
        for result in results:
            context = build_suite_context(result)
            if match_filters(context, filters):
                matched.append(result)
        metric_keys = suite.get("metrics") or available_metrics
        metrics_summary = {}
        for key in metric_keys:
            if matched:
                metrics_summary[key] = sum(r.get("metrics", {}).get(key, 0.0) for r in matched) / len(matched)
            else:
                metrics_summary[key] = 0.0
        suite_result: Dict[str, Any] = {
            "name": suite.get("name", "unnamed_suite"),
            "type": suite.get("type", "custom"),
            "description": suite.get("description"),
            "query_count": len(matched),
            "metrics": metrics_summary,
            "filters_applied": filters,
        }
        thresholds = suite.get("thresholds")
        if thresholds:
            passed, evaluations = evaluate_thresholds(metrics_summary, thresholds)
            suite_result["thresholds"] = thresholds
            suite_result["passed"] = passed
            suite_result["threshold_evaluations"] = evaluations
        suites.append(suite_result)
    return suites


def group_suites_by_type(suite_results: Iterable[Mapping[str, Any]]) -> Dict[str, List[Mapping[str, Any]]]:
    grouped: Dict[str, List[Mapping[str, Any]]] = {}
    for suite in suite_results:
        suite_type = suite.get("type", "custom")
        grouped.setdefault(suite_type, []).append(suite)
    return grouped


def ensure_directory(path: Path | str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)

