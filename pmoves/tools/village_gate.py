#!/usr/bin/env python3
"""Village Gate — automated evaluator gate before Village Rule signoff.

P0 Evaluation Gates (ARCHON_ENHANCEMENT_ROADMAP §2). Runs the declarative
quality-threshold checks in pmoves/configs/village_gate_thresholds.yaml and
produces machine evidence for the AGNOTE4482 signoff checklist:

  * verdict JSON at pmoves/docs/logs/village_gate_latest.json — includes a
    staged ``village.gate.result.v1`` NATS envelope (publish via
    pmoves-nats-mcp when wired; same staged pattern as the mint commands)
  * markdown summary on stdout (and $GITHUB_STEP_SUMMARY when set)
  * Prometheus textfile exposition at --prom-textfile (node-exporter
    textfile-collector convention) — no pushgateway required

Exit codes: 0 = all hard checks pass, 1 = hard failure, 4 = config error.
Advisory checks never affect the exit code.

Threshold rules use the same {metric: {min|max}} shape as
services/retrieval-eval/eval_utils.evaluate_thresholds.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "pmoves" / "configs" / "village_gate_thresholds.yaml"
DEFAULT_VERDICT = REPO_ROOT / "pmoves" / "docs" / "logs" / "village_gate_latest.json"
GATE_SUBJECT = "village.gate.result.v1"


# ---------------------------------------------------------------------------
# Threshold evaluation (mirrors retrieval-eval/eval_utils.evaluate_thresholds)
# ---------------------------------------------------------------------------

def evaluate_thresholds(metrics: Dict[str, float], rules: Dict[str, Dict[str, float]]) -> List[str]:
    """Return a list of human-readable violations; empty list = pass."""
    violations: List[str] = []
    for metric, rule in rules.items():
        if metric not in metrics:
            violations.append(f"{metric}: not produced by check")
            continue
        value = metrics[metric]
        if "min" in rule and value < rule["min"]:
            violations.append(f"{metric}={value} < min {rule['min']}")
        if "max" in rule and value > rule["max"]:
            violations.append(f"{metric}={value} > max {rule['max']}")
    return violations


# ---------------------------------------------------------------------------
# Check adapters — each returns {metric_name: value} or raises ToolMissing
# ---------------------------------------------------------------------------

class ToolMissing(RuntimeError):
    """The external tool a check needs is unavailable on this host."""


class _TagTolerantLoader(yaml.SafeLoader):
    """SafeLoader that accepts application-defined local tags.

    Docker Compose uses tags like ``!override`` / ``!reset``; GitHub Actions
    and other tools define their own. For a *validity* check, an unknown
    local tag is not a syntax error.

    Security: this stays a SafeLoader — the multi-constructor below only
    matches LOCAL tags (``!...``) and constructs plain dict/list/str values.
    Global ``!!python/...`` tags live in the ``tag:yaml.org,2002:python/``
    namespace, which SafeLoader continues to reject (no code execution).
    """


def _ignore_unknown(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_scalar(node)


_TagTolerantLoader.add_multi_constructor("!", _ignore_unknown)


def check_yaml_valid(params: Dict[str, Any]) -> Dict[str, float]:
    invalid = 0
    seen = 0
    for pattern in params.get("globs", []):
        for path in glob.glob(str(REPO_ROOT / pattern)):
            seen += 1
            try:
                with open(path, encoding="utf-8") as fh:
                    yaml.load(fh, Loader=_TagTolerantLoader)
            except yaml.YAMLError:
                invalid += 1
    return {"invalid_count": float(invalid), "files_checked": float(seen)}


def _ruff_argv() -> List[str]:
    if shutil.which("ruff"):
        return ["ruff"]
    if shutil.which("uvx"):
        return ["uvx", "ruff"]
    raise ToolMissing("ruff not found (install ruff, or provide uvx)")


def check_ruff_budget(params: Dict[str, Any]) -> Dict[str, float]:
    paths = [str(REPO_ROOT / p) for p in params.get("paths", [])]
    argv = _ruff_argv() + ["check", *paths, "--output-format", "json", "--exit-zero"]
    # text=True defaults to the platform's encoding (cp1252 on Windows), which
    # chokes on ruff output that contains non-ASCII characters. Pin to UTF-8
    # so the gate returns the real count on every host — without it, a
    # Windows-local run silently reports 0 violations and masks the budget
    # state from the operator.
    proc = subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8",
        cwd=REPO_ROOT, timeout=300,
    )
    # With --exit-zero, a non-zero exit means ruff ITSELF failed (bad config,
    # incompatible version) — that must be a gate error, never "0 violations".
    if proc.returncode != 0:
        raise RuntimeError(
            f"ruff failed to run (exit {proc.returncode}): {proc.stderr.strip()[:300]}"
        )
    try:
        findings = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ruff produced non-JSON output: {exc}") from exc
    return {"violations": float(len(findings))}


def check_dockerfile_user_coverage(params: Dict[str, Any]) -> Dict[str, float]:
    root = REPO_ROOT / params.get("root", "pmoves/services")
    dockerfiles = [
        p for p in root.rglob("Dockerfile*")
        if p.is_file() and "node_modules" not in p.parts
    ]
    if not dockerfiles:
        return {"user_fraction": 1.0, "dockerfiles": 0.0}
    with_user = sum(
        1 for p in dockerfiles
        if re.search(r"^USER ", p.read_text(encoding="utf-8", errors="ignore"), re.MULTILINE)
    )
    return {
        "user_fraction": round(with_user / len(dockerfiles), 4),
        "dockerfiles": float(len(dockerfiles)),
    }


def check_command_exit(params: Dict[str, Any]) -> Dict[str, float]:
    # Pin encoding to UTF-8 for the same reason as check_ruff_budget
    # (the docs-reconcile check can emit non-ASCII characters in
    # commit/drift messages).
    proc = subprocess.run(
        params["command"], capture_output=True, text=True, encoding="utf-8",
        cwd=REPO_ROOT, timeout=600,
    )
    return {"exit_code": float(proc.returncode)}


def check_command_metric(params: Dict[str, Any]) -> Dict[str, float]:
    proc = subprocess.run(
        params["command"], capture_output=True, text=True, encoding="utf-8",
        cwd=REPO_ROOT, timeout=600,
    )
    match = re.search(params["metric_regex"], proc.stdout + proc.stderr)
    if not match:
        raise RuntimeError("metric_regex matched nothing in command output")
    # First metric name in the threshold block names the captured value.
    return {"__captured__": float(match.group(1))}


ADAPTERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, float]]] = {
    "yaml_valid": check_yaml_valid,
    "ruff_budget": check_ruff_budget,
    "dockerfile_user_coverage": check_dockerfile_user_coverage,
    "command_exit": check_command_exit,
    "command_metric": check_command_metric,
}


# ---------------------------------------------------------------------------
# Gate runner
# ---------------------------------------------------------------------------

def run_gate(config: Dict[str, Any], strict_tools: bool = False) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    for check in config.get("checks", []):
        entry: Dict[str, Any] = {
            "id": check["id"],
            "kind": check["kind"],
            "severity": check.get("severity", "hard"),
            "enabled": bool(check.get("enabled", True)),
        }
        if not entry["enabled"]:
            entry["status"] = "disabled"
            results.append(entry)
            continue
        adapter = ADAPTERS.get(check["kind"])
        if adapter is None:
            entry.update(status="error", detail=f"unknown kind '{check['kind']}'")
            results.append(entry)
            continue
        try:
            metrics = adapter(check.get("params", {}))
        except ToolMissing as exc:
            # Local runs may lack CI-only tooling; CI sets strict mode.
            entry.update(
                status="error" if strict_tools else "skipped",
                detail=str(exc),
            )
            results.append(entry)
            continue
        except Exception as exc:  # adapter crashed — always a failure signal
            entry.update(status="error", detail=str(exc))
            results.append(entry)
            continue
        rules = check.get("threshold", {})
        if "__captured__" in metrics and rules:
            metrics = {next(iter(rules)): metrics["__captured__"]}
        violations = evaluate_thresholds(metrics, rules)
        entry.update(
            status="pass" if not violations else "fail",
            metrics=metrics,
            threshold=rules,
            violations=violations,
        )
        results.append(entry)

    hard_failures = [
        r for r in results
        if r["severity"] == "hard" and r.get("status") in ("fail", "error")
    ]
    verdict = {
        "gate": "village-gate",
        "config_version": config.get("version"),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hard_pass": not hard_failures,
        "checks": results,
        # Staged NATS envelope — publish via pmoves-nats-mcp when wired
        # (same staged pattern as the archon mint commands).
        "nats": {
            "subject": GATE_SUBJECT,
            "payload": {
                "gate": "village-gate",
                "hard_pass": not hard_failures,
                "failed_checks": [r["id"] for r in hard_failures],
                "advisory_failures": [
                    r["id"] for r in results
                    if r["severity"] == "advisory" and r.get("status") in ("fail", "error")
                ],
            },
        },
    }
    return verdict


def render_markdown(verdict: Dict[str, Any]) -> str:
    icon = {"pass": "✅", "fail": "❌", "error": "💥", "skipped": "⏭️", "disabled": "▫️"}
    lines = [
        f"## Village Gate — {'PASS' if verdict['hard_pass'] else 'FAIL'}",
        "",
        "| check | severity | status | metrics |",
        "|---|---|---|---|",
    ]
    for r in verdict["checks"]:
        metrics = ", ".join(f"{k}={v}" for k, v in (r.get("metrics") or {}).items()) or "—"
        detail = f" ({r['detail']})" if r.get("detail") else ""
        viol = f" — {'; '.join(r['violations'])}" if r.get("violations") else ""
        lines.append(
            f"| {r['id']} | {r['severity']} | {icon.get(r.get('status'), '?')} "
            f"{r.get('status')}{detail}{viol} | {metrics} |"
        )
    lines.append("")
    lines.append(
        "Machine evidence for AGNOTE4482 Village Rule signoff — verdict JSON "
        "includes a staged `village.gate.result.v1` envelope."
    )
    return "\n".join(lines)


def render_prometheus(verdict: Dict[str, Any]) -> str:
    """Textfile-collector exposition (no pushgateway needed)."""
    out = [
        "# HELP pmoves_village_gate_pass 1 when all hard checks pass",
        "# TYPE pmoves_village_gate_pass gauge",
        f"pmoves_village_gate_pass {1 if verdict['hard_pass'] else 0}",
        "# HELP pmoves_village_gate_check_pass per-check status (1 pass, 0 otherwise)",
        "# TYPE pmoves_village_gate_check_pass gauge",
    ]
    for r in verdict["checks"]:
        if r.get("status") in ("disabled", "skipped"):
            continue
        out.append(
            f'pmoves_village_gate_check_pass{{check="{r["id"]}",severity="{r["severity"]}"}} '
            f'{1 if r.get("status") == "pass" else 0}'
        )
        for name, value in (r.get("metrics") or {}).items():
            out.append(
                f'pmoves_village_gate_metric{{check="{r["id"]}",metric="{name}"}} {value}'
            )
    return "\n".join(out) + "\n"


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--verdict", type=Path, default=DEFAULT_VERDICT)
    parser.add_argument("--prom-textfile", type=Path, default=None,
                        help="write Prometheus textfile exposition here")
    parser.add_argument("--strict-tools", action="store_true",
                        help="missing tools fail hard checks (CI mode)")
    args = parser.parse_args(argv)

    try:
        config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"[error] cannot load config: {exc}", file=sys.stderr)
        return 4
    if not isinstance(config, dict) or not isinstance(config.get("checks"), list):
        print("[error] config has no checks list", file=sys.stderr)
        return 4

    strict = args.strict_tools or os.environ.get("VILLAGE_GATE_STRICT_TOOLS") == "1"
    verdict = run_gate(config, strict_tools=strict)

    args.verdict.parent.mkdir(parents=True, exist_ok=True)
    args.verdict.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    summary = render_markdown(verdict)
    print(summary)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write(summary + "\n")

    if args.prom_textfile:
        args.prom_textfile.parent.mkdir(parents=True, exist_ok=True)
        args.prom_textfile.write_text(render_prometheus(verdict), encoding="utf-8")

    return 0 if verdict["hard_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
