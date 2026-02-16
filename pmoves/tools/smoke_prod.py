#!/usr/bin/env python3
"""Production-oriented smoke checks for hardened local bring-up."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Iterable


PROJECT = os.environ.get("PROJECT", "pmoves")


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _check_http(url: str, name: str, failures: list[str]) -> None:
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            if not (200 <= resp.status < 300):
                failures.append(f"{name}: HTTP {resp.status} from {url}")
    except urllib.error.URLError as exc:
        failures.append(f"{name}: unreachable {url} ({exc})")


def _normalize_supabase_rest_url(raw_url: str) -> str:
    # Supabase REST root commonly serves 200 at /rest/v1/ while /rest/v1 can return 404.
    url = raw_url.strip()
    if url.endswith("/rest/v1"):
        return f"{url}/"
    return url


def _container_name(service: str) -> str:
    return f"{PROJECT}-{service}-1"


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
    code, out, err = _run(["docker", "exec", source, "python", "-c", py])
    if code != 0:
        details = err or out or "request failed"
        failures.append(f"{name}: {details}")


def _print_checks(title: str, items: Iterable[str]) -> None:
    print(title)
    for item in items:
        print(f"  - {item}")


def main() -> int:
    failures: list[str] = []

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

    supa_rest = _normalize_supabase_rest_url(
        os.environ.get("SUPA_REST_URL", "http://127.0.0.1:65421/rest/v1/")
    )
    _check_http(supa_rest, "supabase_rest", failures)
    _check_http("http://localhost:8086/hirag/admin/stats", "hirag_v2_stats", failures)
    _check_http("http://localhost:8080/healthz", "agent_zero_health", failures)
    _check_internal_http("agent-zero", "http://archon:8091/healthz", "archon_internal_health", failures)

    # Validate internal service mesh reachability from hi-rag-v2.
    _check_internal_http("hi-rag-gateway-v2", "http://qdrant:6333/collections", "qdrant_internal", failures)
    _check_internal_http("hi-rag-gateway-v2", "http://meilisearch:7700/health", "meili_internal", failures)
    _check_internal_http("hi-rag-gateway-v2", "http://neo4j:7474", "neo4j_internal_http", failures)
    _check_internal_http("hi-rag-gateway-v2", "http://presign:8080/healthz", "presign_internal", failures)
    _check_internal_http("hi-rag-gateway-v2", "http://render-webhook:8085/healthz", "render_webhook_internal", failures)

    if failures:
        _print_checks("Production smoke failed:", failures)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
