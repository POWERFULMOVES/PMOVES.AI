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
