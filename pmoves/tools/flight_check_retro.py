#!/usr/bin/env python3
"""
Retro-styled readiness check with Rich. Runs HTTP checks in parallel and renders a table
with per-endpoint status. Falls back to plain output if Rich is unavailable.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import os
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parents[1]

def _get_url(
    env_var: str | None,
    default: str,
) -> str:
    """Get service URL with environment variable override.

    Priority:
    1. SERVICE_*_URL environment variable (service discovery override)
    2. Legacy environment variable (backward compatibility)
    3. Default localhost URL

    This supports hybrid operation:
    - Docked mode: Use SERVICE_*_URL overrides from service discovery
    - Standalone mode: Use localhost with port overrides
    """
    if env_var:
        url = os.environ.get(env_var)
        if url:
            return url.rstrip("/")
    return default


def _is_true(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_env_shared(key: str) -> str | None:
    env_path = ROOT / "pmoves" / "env.shared"
    if not env_path.exists():
        return None
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip().strip('"')
    except Exception:
        pass
    return None


def _detect_supabase_runtime() -> str:
    runtime = os.environ.get("SUPABASE_RUNTIME") or _read_env_shared("SUPABASE_RUNTIME")
    if runtime:
        return runtime.strip().lower()
    # Fallback: presence of compose-supabase containers means compose runtime.
    try:
        cp = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if cp.returncode == 0 and "pmoves-supabase-kong-1" in cp.stdout:
            return "compose"
    except Exception:
        pass
    return "cli"


def _build_endpoints() -> list[tuple[str, str]]:
    supabase_runtime = _detect_supabase_runtime()
    if supabase_runtime == "compose":
        supa_rest_port = os.environ.get("SUPABASE_REST_PORT", "3000")
        supa_studio_port = os.environ.get("SUPABASE_STUDIO_PORT", "3001")
    else:
        supa_rest_port = os.environ.get("SUPABASE_REST_PORT", "54321")
        supa_studio_port = os.environ.get("SUPABASE_STUDIO_PORT", "54323")
    yt_base = os.environ.get("PMOVES_YT_BASE_URL", "http://localhost:8077").rstrip("/")

    endpoints: list[tuple[str, str]] = [
        ("Supabase REST", _get_url("SERVICE_POSTGREST_URL", f"http://127.0.0.1:{supa_rest_port}/rest/v1/")),
        ("Supabase Studio", _get_url(None, f"http://127.0.0.1:{supa_studio_port}")),
        ("Hi-RAG v2 CPU", _get_url("SERVICE_HIRAG_V2_URL", f"http://localhost:{os.environ.get('HIRAG_V2_HOST_PORT','8086')}/hirag/admin/stats")),
        ("Hi-RAG v2 GPU", _get_url("SERVICE_HIRAG_V2_GPU_URL", f"http://localhost:{os.environ.get('HIRAG_V2_GPU_HOST_PORT','8087')}/hirag/admin/stats")),
        ("Presign", _get_url("SERVICE_PRESIGN_URL", "http://localhost:8088/healthz")),
        ("Archon API", _get_url("SERVICE_ARCHON_URL", "http://localhost:8091/healthz")),
        ("Archon UI", _get_url(None, "http://localhost:3737")),
        ("Archon MCP", _get_url("SERVICE_ARCHON_URL", "http://localhost:8091/mcp/describe")),
        ("Agent Zero API", _get_url("SERVICE_AGENT_ZERO_URL", "http://localhost:8080/healthz")),
        ("Agent Zero Env", _get_url("SERVICE_AGENT_ZERO_URL", "http://localhost:8080/config/environment")),
        ("Agent Zero MCP", _get_url("SERVICE_AGENT_ZERO_URL", "http://localhost:8080/mcp/commands")),
        ("Agent Zero A2A", _get_url(None, "http://localhost:8080/.well-known/agent-card.json")),
        ("PMOVES.YT", _get_url("SERVICE_PMOVES_YT_URL", "http://localhost:8077/healthz")),
        ("YT docs catalog", f"{yt_base}/yt/docs/catalog"),
        ("Channel Monitor", _get_url("SERVICE_CHANNEL_MONITOR_URL", "http://localhost:8097/healthz")),
        ("Monitor Status", _get_url("SERVICE_CHANNEL_MONITOR_URL", "http://localhost:8097/api/monitor/status")),
        ("TensorZero UI", _get_url(None, "http://localhost:4000")),
        ("TensorZero GW", _get_url("SERVICE_TENSORZERO_URL", "http://localhost:3030/metrics")),
        ("Grafana", _get_url("SERVICE_GRAFANA_URL", "http://localhost:3002")),
        ("Loki /ready", _get_url("SERVICE_LOKI_URL", "http://localhost:3100/ready")),
        ("n8n UI", _get_url(None, "http://localhost:5678")),
        ("Jellyfin", _get_url(None, "http://localhost:8096")),
    ]

    if _is_true(os.environ.get("ENABLE_JELLYFIN_AI")) or _is_true(os.environ.get("PMOVES_RETRO_INCLUDE_JELLYFIN_AI")):
        endpoints.append(("Jellyfin AI", _get_url(None, "http://localhost:9096")))

    if _is_true(os.environ.get("RUN_UI_DEV")) or _is_true(os.environ.get("PMOVES_RETRO_INCLUDE_DEV_UI")):
        endpoints.append(("Console UI", _get_url(None, "http://localhost:3001")))

    return endpoints


ENDPOINTS = _build_endpoints()

# Endpoints whose failure should fail the retro check in strict mode.
CRITICAL_NAMES = {
    "Supabase REST",
    "Archon API",
    "Archon UI",
    "Agent Zero API",
    "Agent Zero Env",
    "Agent Zero MCP",
    "Agent Zero A2A",
    "TensorZero UI",
    "TensorZero GW",
    "PMOVES.YT",
    "Channel Monitor",
    "Monitor Status",
    "Grafana",
    "Loki /ready",
    "n8n UI",
}

TIMEOUT = int(os.environ.get("PMOVES_RETRO_TIMEOUT", "5"))


def check(url: str, timeout: int = TIMEOUT) -> tuple[str, int, str]:
    try:
        with urlopen(url, timeout=timeout) as resp:
            code = getattr(resp, "status", 200)
            return ("ok" if 200 <= code < 400 else "warn"), code, ""
    except HTTPError as e:
        return ("warn" if 400 <= e.code < 500 else "error"), e.code, str(e)
    except URLError as e:
        return "error", 0, str(e)
    except Exception as e:
        return "error", 0, str(e)


def main() -> int:
    parser = argparse.ArgumentParser(description="PMOVES retro readiness check")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any critical endpoint is unhealthy")
    args = parser.parse_args()

    try:
        from rich.console import Console
        from rich.table import Table
        from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
    except Exception:
        Console = None  # type: ignore

    checks = ENDPOINTS
    if Console is None:
        print("Retro check (plain):")
        with cf.ThreadPoolExecutor(max_workers=min(16, len(checks))) as ex:
            futs = {ex.submit(check, url): name for name, url in checks}
            failures = 0
            critical_failures = 0
            for fut in cf.as_completed(futs):
                name = futs[fut]
                status, code, err = fut.result()
                mark = "[OK]" if status == "ok" else ("[WARN]" if status == "warn" else "[ERR]")
                print(f" {mark} {name} -> {code}")
                if status in ("error", "warn"):
                    failures += 1
                    if name in CRITICAL_NAMES:
                        critical_failures += 1
        if args.strict and critical_failures:
            print(f"Strict mode: {critical_failures} critical endpoint(s) unhealthy")
            return 1
        return 0

    console = Console()
    progress = Progress(SpinnerColumn(style="bold green"),
                        "[bold]Checking services... ", TimeElapsedColumn())
    with progress:
        task = progress.add_task("wait", total=len(checks))
        results = []
        with cf.ThreadPoolExecutor(max_workers=min(16, len(checks))) as ex:
            futs = {ex.submit(check, url): (name, url) for name, url in checks}
            for fut in cf.as_completed(futs):
                name, url = futs[fut]
                status, code, err = fut.result()
                results.append((name, url, status, code, err))
                progress.advance(task)
    table = Table(title="PMOVES Retro Readiness", show_lines=False)
    table.add_column("Service", no_wrap=True)
    table.add_column("URL", overflow="fold")
    table.add_column("Status")
    table.add_column("Code")
    failures = 0
    critical_failures = 0
    for name, url, status, code, _ in sorted(results, key=lambda x: x[0].lower()):
        mark = "[green]OK[/]" if status == "ok" else ("[yellow]WARN[/]" if status == "warn" else "[red]ERR[/]")
        table.add_row(name, url, mark + " " + status, str(code))
        if status == "error":
            failures += 1
            if name in CRITICAL_NAMES:
                critical_failures += 1
    console.print(table)
    if args.strict and critical_failures:
        console.print(f"[red]Strict mode: {critical_failures} critical endpoint(s) unhealthy[/]")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
