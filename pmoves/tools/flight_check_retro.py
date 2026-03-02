#!/usr/bin/env python3
"""
Retro-styled readiness check with Rich. Runs HTTP checks in parallel and renders a table
with per-endpoint status. Falls back to plain output if Rich is unavailable.
"""
from __future__ import annotations
import concurrent.futures as cf
import os
import sys
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

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


def _build_endpoints() -> list[tuple[str, str]]:
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
        ("Archon MCP", _get_url("SERVICE_ARCHON_URL", "http://localhost:8091/mcp/describe")),
        ("Agent Zero API", _get_url("SERVICE_AGENT_ZERO_URL", "http://localhost:8080/healthz")),
        ("Agent Zero Env", _get_url("SERVICE_AGENT_ZERO_URL", "http://localhost:8080/config/environment")),
        ("Agent Zero MCP", _get_url("SERVICE_AGENT_ZERO_URL", "http://localhost:8080/mcp/commands")),
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
        ("Jellyfin AI", _get_url(None, "http://localhost:9096")),
        ("Firefly", _get_url(None, "http://localhost:8082")),
        ("Wger", _get_url(None, "http://localhost:8000")),
        ("Open Notebook", _get_url(None, "http://localhost:8503")),
    ]

    if _is_true(os.environ.get("RUN_UI_DEV")) or _is_true(os.environ.get("PMOVES_RETRO_INCLUDE_DEV_UI")):
        endpoints.append(("Console UI", _get_url(None, "http://localhost:3001")))

    return endpoints


ENDPOINTS = _build_endpoints()

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
            for fut in cf.as_completed(futs):
                name = futs[fut]
                status, code, err = fut.result()
                mark = "[OK]" if status == "ok" else ("[WARN]" if status == "warn" else "[ERR]")
                print(f" {mark} {name} -> {code}")
                if status == "error":
                    failures += 1
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
    for name, url, status, code, _ in sorted(results, key=lambda x: x[0].lower()):
        mark = "[green]OK[/]" if status == "ok" else ("[yellow]WARN[/]" if status == "warn" else "[red]ERR[/]")
        table.add_row(name, url, mark + " " + status, str(code))
    console.print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
