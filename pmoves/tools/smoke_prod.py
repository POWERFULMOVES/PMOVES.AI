#!/usr/bin/env python3
"""Production-oriented smoke checks for hardened local bring-up."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Iterable


PROJECT = os.environ.get("PROJECT", "pmoves")


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _check_http(url: str, name: str, failures: list[str], retries: int = 5, delay_s: float = 1.5) -> None:
    last_exc: Exception | None = None
    for _ in range(max(retries, 1)):
        try:
            with urllib.request.urlopen(url, timeout=8) as resp:
                if not (200 <= resp.status < 300):
                    failures.append(f"{name}: HTTP {resp.status} from {url}")
                return
        except Exception as exc:
            last_exc = exc
            time.sleep(delay_s)
    failures.append(f"{name}: unreachable {url} ({last_exc})")


def _check_http_warn(url: str, name: str, failures: list[str], warnings: list[str]) -> None:
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            if not (200 <= resp.status < 300):
                warnings.append(f"{name}: HTTP {resp.status} from {url}")
    except Exception as exc:
        warnings.append(f"{name}: unreachable {url} ({exc})")


def _normalize_supabase_rest_url(raw_url: str) -> str:
    # Supabase REST root commonly serves 200 at /rest/v1/ while /rest/v1 can return 404.
    url = raw_url.strip()
    if url.endswith("/rest/v1"):
        return f"{url}/"
    return url


def _container_name(service: str) -> str:
    return f"{PROJECT}-{service}-1"


def _first_running_container(candidates: Iterable[str]) -> str | None:
    for cname in candidates:
        code, out, _ = _run(["docker", "inspect", "--format", "{{.State.Running}}", cname])
        if code == 0 and out.strip().lower() == "true":
            return cname
    return None


def _host_port(container: str, container_port: int) -> int | None:
    code, out, _ = _run(["docker", "port", container, f"{container_port}/tcp"])
    if code != 0 or not out:
        return None
    # Typical output: "0.0.0.0:54321" or ":::54321"
    match = re.search(r":(\d+)\s*$", out.splitlines()[0].strip())
    return int(match.group(1)) if match else None


def _check_container_running(service: str, failures: list[str]) -> None:
    cname = _container_name(service)
    code, out, err = _run(["docker", "inspect", "--format", "{{.State.Running}}", cname])
    if code != 0:
        failures.append(f"{service}: container missing ({cname})")
        return
    if out.strip().lower() != "true":
        failures.append(f"{service}: container not running ({cname})")
        if err:
            failures.append(f"{service}: {err}")


def _check_container_health(service: str, failures: list[str]) -> None:
    cname = _container_name(service)
    code, out, _ = _run(
        [
            "docker",
            "inspect",
            "--format",
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
            cname,
        ]
    )
    if code != 0:
        failures.append(f"{service}: container missing ({cname})")
        return
    status = out.strip().lower()
    if status not in {"healthy", "none"}:
        failures.append(f"{service}: unhealthy ({status})")


def _check_internal_http(
    source_service: str,
    target_url: str,
    name: str,
    failures: list[str],
) -> None:
    source = _container_name(source_service)
    py = (
        "import urllib.request; "
        f"resp=urllib.request.urlopen('{target_url}', timeout=8); "
        "print(resp.status); "
        "raise SystemExit(0 if 200 <= resp.status < 300 else 1)"
    )
    probes = [
        ["docker", "exec", source, "python3", "-c", py],
        ["docker", "exec", source, "python", "-c", py],
        [
            "docker",
            "exec",
            source,
            "sh",
            "-lc",
            f"curl -fsS '{target_url}' >/dev/null || wget -q -O /dev/null '{target_url}'",
        ],
    ]
    details = "request failed"
    for cmd in probes:
        code, out, err = _run(cmd)
        if code == 0:
            return
        details = err or out or details
    failures.append(f"{name}: {details}")


def _inspect_env(container: str) -> dict[str, str]:
    code, out, _ = _run(["docker", "inspect", "--format", "{{range .Config.Env}}{{println .}}{{end}}", container])
    if code != 0:
        return {}
    parsed: dict[str, str] = {}
    for line in out.splitlines():
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        parsed[key] = val
    return parsed


def _is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    raw = value.strip()
    if not raw:
        return True
    lowered = raw.lower()
    return (
        lowered.startswith("placeholder_")
        or lowered in {"changeme", "change_me", "none", "null", "your_value_here"}
    )


def _check_container_env_required(
    container: str,
    required_keys: Iterable[str],
    failures: list[str],
) -> None:
    env = _inspect_env(container)
    for key in required_keys:
        if _is_placeholder(env.get(key)):
            failures.append(f"{container}: {key} is placeholder/empty")


def _check_container_env_equals(container: str, key: str, expected: str, failures: list[str]) -> None:
    env = _inspect_env(container)
    actual = env.get(key, "")
    if actual != expected:
        failures.append(f"{container}: {key}={actual!r} (expected {expected!r})")


def _print_checks(title: str, items: Iterable[str]) -> None:
    print(title)
    for item in items:
        print(f"  - {item}")


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []

    required_running = [
        "qdrant",
        "neo4j",
        "meilisearch",
        "minio",
        "nats",
        "hi-rag-gateway-v2",
        "retrieval-eval",
        "langextract",
        "extract-worker",
        "agent-zero",
        "archon",
        "deepresearch",
        "supaserch",
    ]
    for svc in required_running:
        _check_container_running(svc, failures)

    for svc in ("neo4j", "nats", "agent-zero", "archon"):
        _check_container_health(svc, failures)

    supa_rest = os.environ.get("SUPA_REST_URL", "").strip()
    if not supa_rest:
        kong = _first_running_container(("supabase_kong_pmoves", f"{PROJECT}-supabase-kong-1"))
        kong_port = _host_port(kong, 8000) if kong else None
        if kong_port:
            supa_rest = f"http://127.0.0.1:{kong_port}/rest/v1/"
        else:
            supa_rest = "http://127.0.0.1:54321/rest/v1/"
    supa_rest = _normalize_supabase_rest_url(supa_rest)
    _check_http(supa_rest, "supabase_rest", failures)

    agent_container = _container_name("agent-zero")
    archon_container = _container_name("archon")
    hirag_container = _container_name("hi-rag-gateway-v2")

    # Agent Zero host APIs differ by image builds; use container health + optional UI probe.
    agent_ui_port = _host_port(agent_container, 80)
    if agent_ui_port:
        _check_http_warn(f"http://127.0.0.1:{agent_ui_port}/", "agent_zero_ui_root", failures, warnings)

    hirag_port = _host_port(hirag_container, 8086)
    if hirag_port:
        _check_http(f"http://127.0.0.1:{hirag_port}/hirag/admin/stats", "hirag_v2_stats", failures)
    else:
        _check_internal_http("agent-zero", "http://hi-rag-gateway-v2:8086/hirag/admin/stats", "hirag_v2_internal_stats", failures)

    _check_internal_http("agent-zero", "http://archon:8091/healthz", "archon_internal_health", failures)

    # Validate internal service mesh reachability from hi-rag-v2.
    _check_internal_http("hi-rag-gateway-v2", "http://qdrant:6333/collections", "qdrant_internal", failures)
    _check_internal_http("hi-rag-gateway-v2", "http://meilisearch:7700/health", "meili_internal", failures)
    _check_internal_http("hi-rag-gateway-v2", "http://neo4j:7474", "neo4j_internal_http", failures)
    _check_internal_http("hi-rag-gateway-v2", "http://presign:8080/healthz", "presign_internal", failures)
    _check_internal_http("hi-rag-gateway-v2", "http://render-webhook:8085/healthz", "render_webhook_internal", failures)

    _check_container_env_equals(archon_container, "ENVIRONMENT", "production", failures)
    _check_container_env_equals(archon_container, "ARCHON_ENV", "production", failures)
    _check_container_env_required(
        archon_container,
        ("SUPABASE_SERVICE_ROLE_KEY", "SUPA_REST_URL"),
        failures,
    )
    _check_container_env_required(
        agent_container,
        ("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_ANON_KEY"),
        failures,
    )

    realtime_container = _first_running_container(("supabase_realtime_pmoves", f"{PROJECT}-supabase-realtime-1"))
    if realtime_container:
        # CLI runtime logs include "realtime-dev"; warn only so prod smoke remains compatible with Supabase CLI naming.
        code, out, _ = _run(["docker", "logs", "--tail", "30", realtime_container])
        if code == 0 and "realtime-dev" in out:
            warnings.append(f"{realtime_container}: contains 'realtime-dev' log marker (CLI naming artifact)")
        _check_http_warn("http://127.0.0.1:54321/realtime/v1/api/tenants/realtime-dev/health", "supabase_realtime_health", failures, warnings)

    if failures:
        _print_checks("Production smoke failed:", failures)
        if warnings:
            _print_checks("Production smoke warnings:", warnings)
        return 1

    summary = {
        "project": PROJECT,
        "status": "ok",
        "checks": {
            "containers": len(required_running),
            "internal_http": 6,
            "public_http": 3,
        },
    }
    print(json.dumps(summary, indent=2))
    if warnings:
        _print_checks("Production smoke warnings:", warnings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
