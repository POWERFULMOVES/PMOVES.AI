#!/usr/bin/env python3
"""Monitoring smoke test with production/runtime guards.

This replaces jq-heavy shell parsing with Python so it runs consistently across
Windows/WSL/Linux while keeping the existing environment variable interface.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_float(name: str, default: float) -> float:
    raw = _env(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = _env(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _csv(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _http_code(url: str, timeout: int = 5) -> str:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return str(resp.getcode())
    except urllib.error.HTTPError as err:
        return str(err.code)
    except Exception:
        return "000"


def _http_json(url: str, timeout: int = 5, auth: tuple[str, str] | None = None):
    req = urllib.request.Request(url, method="GET")
    if auth is not None:
        import base64

        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _docker_ps_names() -> List[str]:
    try:
        cp = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []
    if cp.returncode != 0:
        return []
    return [line.strip() for line in cp.stdout.splitlines() if line.strip()]


def _docker_logs(container: str, tail: int) -> str:
    cp = subprocess.run(
        ["docker", "logs", "--tail", str(tail), container],
        check=False,
        capture_output=True,
        text=True,
    )
    # Docker writes logs to stderr by default.
    return (cp.stdout or "") + (cp.stderr or "")


def _detect_supabase_runtime(names: Sequence[str]) -> str:
    has_cli = any(name.startswith("supabase_") for name in names)
    has_compose = any("supabase-" in name for name in names)
    if has_cli and has_compose:
        return "mixed"
    if has_cli:
        return "cli"
    if has_compose:
        return "compose"
    return "none"


def _runtime_matches(detected: str, expected: Sequence[str]) -> bool:
    want = {item.lower() for item in expected}
    if not want or "any" in want or "*" in want:
        return True
    if detected == "compose":
        return bool({"compose", "kong", "non-cli"} & want)
    if detected == "cli":
        return "cli" in want
    if detected == "mixed":
        return "mixed" in want or ("cli" in want and bool({"compose", "kong"} & want))
    if detected == "none":
        return "none" in want
    return False


def _strip_yaml_scalar(raw: str) -> str:
    value = raw.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    return value.strip()


def _provisioned_datasource_names(repo_root: Path) -> set[str]:
    datasource_file = repo_root / "monitoring" / "grafana" / "datasources" / "datasource.yml"
    if not datasource_file.exists():
        return set()
    names: set[str] = set()
    try:
        for line in datasource_file.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^\s*-\s*name:\s*(.+?)\s*$", line)
            if not match:
                continue
            name = _strip_yaml_scalar(match.group(1))
            if name:
                names.add(name.lower())
    except Exception:
        return set()
    return names


def _provisioned_dashboard_count(repo_root: Path) -> int:
    dashboard_dir = repo_root / "monitoring" / "grafana" / "dashboards"
    if not dashboard_dir.exists() or not dashboard_dir.is_dir():
        return 0
    try:
        return sum(1 for item in dashboard_dir.glob("*.json") if item.is_file())
    except Exception:
        return 0


@dataclass
class FailureState:
    failures: List[str]
    warnings: List[str]

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def _check(condition: bool, msg: str, state: FailureState) -> None:
    if not condition:
        state.fail(msg)


def _safe_get(obj, path: Iterable[str], default=None):
    cur = obj
    for key in path:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return default
    return cur


def _prom_query_result_count(prom: str, query: str) -> int:
    encoded = urllib.parse.quote(query, safe="")
    payload = _http_json(f"{prom}/api/v1/query?query={encoded}")
    result = _safe_get(payload, ["data", "result"], [])
    if isinstance(result, list):
        return len(result)
    return 0


def main() -> int:
    prom = f"http://localhost:{_env('PROMETHEUS_HOST_PORT', '9090')}"
    loki = f"http://localhost:{_env('LOKI_HOST_PORT', '3100')}"
    grafana = f"http://localhost:{_env('GRAFANA_HOST_PORT', '3002')}"
    guser = _env("GRAFANA_ADMIN_USER", "admin")
    gpass = _env("GRAFANA_ADMIN_PASSWORD", "admin")
    warmup = _env_int("MONITORING_SMOKE_WARMUP_SECONDS", 30)
    required_jobs = _csv(_env("MONITORING_SMOKE_REQUIRED_JOBS", ""))
    require_job_up = _env("MONITORING_SMOKE_REQUIRE_JOB_UP", "0") == "1"
    min_healthy_ratio = _env_float("MONITORING_SMOKE_MIN_HEALTHY_RATIO", 0.0)
    expected_runtime = _csv(_env("MONITORING_SMOKE_EXPECT_SUPABASE_RUNTIME", ""))
    realtime_dev_policy = _env("MONITORING_SMOKE_REALTIME_DEV_POLICY", "allow").strip().lower()
    realtime_log_tail = _env_int("MONITORING_SMOKE_REALTIME_LOG_TAIL", 250)

    print("Probing Prometheus/Loki/Grafana + dashboard provisioning...")
    deadline = time.time() + max(0, warmup)
    prom_code = loki_code = "000"
    gdb = ""
    while True:
        prom_code = _http_code(f"{prom}/-/ready")
        loki_code = _http_code(f"{loki}/ready")
        try:
            health = _http_json(f"{grafana}/api/health", auth=(guser, gpass))
            gdb = str(health.get("database", "")).lower()
        except Exception:
            gdb = ""

        if prom_code == "200" and loki_code == "200" and gdb == "ok":
            break
        if time.time() >= deadline:
            break
        time.sleep(2)

    state = FailureState(failures=[], warnings=[])
    repo_root = Path(__file__).resolve().parents[1]

    try:
        targets_payload = _http_json(f"{prom}/api/v1/targets")
    except Exception as exc:
        state.fail(f"Unable to fetch Prometheus targets: {exc}")
        targets_payload = {"data": {"activeTargets": []}}

    active_targets = _safe_get(targets_payload, ["data", "activeTargets"], [])
    targets = len(active_targets) if isinstance(active_targets, list) else 0
    healthy = sum(1 for t in active_targets if isinstance(t, dict) and t.get("health") == "up")

    try:
        blackbox_samples = _prom_query_result_count(prom, "probe_success")
    except Exception as exc:
        state.fail(f"Unable to query probe_success from Prometheus: {exc}")
        blackbox_samples = 0

    try:
        ds_payload = _http_json(f"{grafana}/api/datasources", auth=(guser, gpass))
        datasource_names = {str(item.get("name", "")).lower() for item in ds_payload if isinstance(item, dict)}
    except urllib.error.HTTPError as exc:
        datasource_names = set()
        state.fail(f"Grafana datasource API returned HTTP {exc.code}; verify Grafana auth/provisioning")
    except urllib.error.URLError as exc:
        datasource_names = set()
        fallback_names = _provisioned_datasource_names(repo_root)
        if fallback_names:
            datasource_names = fallback_names
            state.warn(f"Grafana datasource API unavailable; used provisioning fallback ({exc})")
    has_prom = "prometheus" in datasource_names
    has_loki = "loki" in datasource_names

    try:
        dash_payload = _http_json(f"{grafana}/api/search?type=dash-db", auth=(guser, gpass))
        dash_count = len(dash_payload) if isinstance(dash_payload, list) else 0
    except Exception as exc:
        dash_count = 0
        fallback_dash_count = _provisioned_dashboard_count(repo_root)
        if fallback_dash_count > 0:
            dash_count = fallback_dash_count
            state.warn(f"Grafana dashboard API unavailable; used provisioning fallback ({exc})")

    print("Monitoring Smoke Report")
    print(f"- prom.ready: {prom_code}")
    print(f"- loki.ready: {loki_code}")
    print(f"- grafana.database: {gdb or 'unknown'}")
    print(f"- prom.targets: active={targets} healthy={healthy}")
    print(f"- prom.blackbox.samples: {blackbox_samples}")
    print(f"- grafana.datasources: prometheus={str(has_prom).lower()} loki={str(has_loki).lower()}")
    print(f"- grafana.dashboards: {dash_count}")

    # Runtime guard: production smoke should reject CLI runtime by default.
    names = _docker_ps_names()
    runtime = _detect_supabase_runtime(names)
    if expected_runtime:
        expected_display = ",".join(expected_runtime)
        print(f"- supabase.runtime: detected={runtime} expected={expected_display}")
        _check(
            _runtime_matches(runtime, expected_runtime),
            f"Supabase runtime mismatch: detected={runtime}, expected one of {expected_display}",
            state,
        )
    else:
        print(f"- supabase.runtime: detected={runtime}")

    if required_jobs:
        print(f"- required.jobs: {','.join(required_jobs)}")
        for job in required_jobs:
            total = 0
            up = 0
            for target in active_targets:
                labels = target.get("labels", {}) if isinstance(target, dict) else {}
                if labels.get("job") == job:
                    total += 1
                    if target.get("health") == "up":
                        up += 1
            print(f"  - job.{job}: total={total} up={up}")
            _check(total > 0, f"Required Prometheus job '{job}' not discovered", state)
            if require_job_up:
                _check(up > 0, f"Required Prometheus job '{job}' has no healthy targets", state)

    _check(prom_code == "200", "Prometheus /-/ready is not HTTP 200", state)
    _check(loki_code == "200", "Loki /ready is not HTTP 200", state)
    _check(gdb == "ok", "Grafana database status is not ok", state)
    _check(targets > 0, "Prometheus active target count is zero", state)
    _check(healthy > 0, "Prometheus healthy target count is zero", state)

    if min_healthy_ratio > 0:
        ratio = float(healthy) / float(targets) if targets else 0.0
        print(f"- prom.healthy_ratio: {ratio:.3f} (min {min_healthy_ratio:.3f})")
        _check(
            ratio >= min_healthy_ratio,
            f"Healthy target ratio below threshold: got {ratio:.3f}, need >= {min_healthy_ratio:.3f}",
            state,
        )

    _check(blackbox_samples > 0, "probe_success query returned zero samples", state)
    _check(has_prom, "Grafana 'Prometheus' datasource missing", state)
    _check(has_loki, "Grafana 'Loki' datasource missing", state)
    _check(dash_count > 0, "Grafana has no dashboards", state)

    # Optional production hygiene: fail/warn if Realtime still logs realtime-dev tenant identity.
    if realtime_dev_policy not in {"allow", "warn", "forbid"}:
        state.warn(
            "Invalid MONITORING_SMOKE_REALTIME_DEV_POLICY value; expected allow|warn|forbid. "
            f"Got '{realtime_dev_policy}', defaulting to allow."
        )
        realtime_dev_policy = "allow"

    if realtime_dev_policy != "allow":
        realtime_names = [
            name for name in names if "supabase" in name.lower() and "realtime" in name.lower()
        ]
        if not realtime_names:
            state.warn("No Supabase realtime container found while checking realtime-dev policy")
        else:
            logs = _docker_logs(realtime_names[0], max(1, realtime_log_tail))
            found_dev = bool(re.search(r"(project|external_id)=realtime-dev", logs))
            msg = (
                "Supabase Realtime still reports realtime-dev tenant labels in logs. "
                "Set production tenant/external_id before audit."
            )
            print(
                "- realtime.dev_labels:"
                f" {'detected' if found_dev else 'not_detected'} (policy={realtime_dev_policy})"
            )
            if found_dev and realtime_dev_policy == "warn":
                state.warn(msg)
            elif found_dev and realtime_dev_policy == "forbid":
                state.fail(msg)

    if state.warnings:
        for warning in state.warnings:
            print(f"WARN: {warning}")

    if state.failures:
        for failure in state.failures:
            print(f"FAIL: {failure}")
        return 1

    print("OK: Monitoring smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
