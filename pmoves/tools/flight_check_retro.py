#!/usr/bin/env python3
"""
Retro-styled readiness check with Rich. Runs HTTP checks in parallel and renders a table
with per-endpoint status. Falls back to plain output if Rich is unavailable.
"""
from __future__ import annotations
import concurrent.futures as cf
import os
import sys
import time
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


ENDPOINTS = [
    ("Supabase REST", _get_url("SERVICE_POSTGREST_URL", f"http://127.0.0.1:{os.environ.get('SUPABASE_REST_PORT','65421')}/rest/v1")),
    ("Hi-RAG v2 CPU", _get_url("SERVICE_HIRAG_V2_URL", f"http://localhost:{os.environ.get('HIRAG_V2_HOST_PORT','8086')}/")),
    ("Hi-RAG v2 GPU", _get_url("SERVICE_HIRAG_V2_GPU_URL", f"http://localhost:{os.environ.get('HIRAG_V2_GPU_HOST_PORT','8087')}/")),
    ("Presign", _get_url("SERVICE_PRESIGN_URL", "http://localhost:8088/healthz")),
    ("Archon API", _get_url("SERVICE_ARCHON_URL", "http://localhost:8091/healthz")),
    ("Archon MCP", _get_url("SERVICE_ARCHON_URL", "http://localhost:8091/mcp/describe")),
    ("Agent Zero API", _get_url("SERVICE_AGENT_ZERO_URL", "http://localhost:8080/healthz")),
    ("Agent Zero Env", _get_url("SERVICE_AGENT_ZERO_URL", "http://localhost:8080/config/environment")),
    ("Agent Zero MCP", _get_url("SERVICE_AGENT_ZERO_URL", "http://localhost:8080/mcp/commands")),
    ("PMOVES.YT", _get_url("SERVICE_PMOVES_YT_URL", "http://localhost:8077/")),
    ("YT docs catalog", _get_url("SERVICE_PMOVES_YT_URL", f"{os.environ.get('PMOVES_YT_BASE_URL','http://localhost:8077')}/yt/docs/catalog")),
    ("Grafana", _get_url("SERVICE_GRAFANA_URL", "http://localhost:3002")),
    ("Loki /ready", _get_url("SERVICE_LOKI_URL", "http://localhost:3100/ready")),
    ("Channel Monitor", _get_url("SERVICE_CHANNEL_MONITOR_URL", "http://localhost:8097/healthz")),
    ("Monitor Status", _get_url("SERVICE_CHANNEL_MONITOR_URL", "http://localhost:8097/api/monitor/status")),
    ("Console UI", _get_url(None, "http://localhost:3001")),
    ("n8n UI", _get_url(None, "http://localhost:5678")),
    ("TensorZero UI", _get_url(None, "http://localhost:4000")),
    ("TensorZero GW", _get_url("SERVICE_TENSORZERO_URL", "http://localhost:3000")),
    ("Jellyfin", _get_url(None, "http://localhost:8096")),
    ("Firefly", _get_url(None, "http://localhost:8082")),
    ("Wger", _get_url(None, "http://localhost:8000")),
    ("Open Notebook", _get_url(None, "http://localhost:8503")),
    ("Supabase Studio", _get_url(None, "http://127.0.0.1:65433")),
]

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
                mark = "✔" if status == "ok" else ("!" if status == "warn" else "✖")
                print(f" {mark} {name} → {code}")
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
        mark = "[green]✔[/]" if status == "ok" else ("[yellow]![/]" if status == "warn" else "[red]✖[/]")
        table.add_row(name, url, mark + " " + status, str(code))
    console.print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
