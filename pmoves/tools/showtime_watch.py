#!/usr/bin/env python3
"""Live readiness watcher for bringup-showtime.

Monitors key PMOVES endpoints and updates a live table so operators can see
services transition from pending to ready during bring-up.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import signal
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

# Import sibling module directly so execution is stable from `pmoves/` Make targets.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flight_check_retro import ENDPOINTS  # type: ignore


STOP = False


def _on_signal(_sig: int, _frame: object) -> None:
    global STOP
    STOP = True


def probe(url: str, timeout: float = 2.5) -> tuple[bool, int]:
    try:
        with urlopen(url, timeout=timeout) as resp:
            code = getattr(resp, "status", 200)
            return (200 <= code < 400), code
    except HTTPError as exc:
        return False, exc.code
    except (TimeoutError, URLError):
        return False, 0
    except Exception:
        return False, 0


def render_plain(cycle: int, started: float, rows: list[tuple[str, bool, int]]) -> None:
    ready = sum(1 for _, ok, _ in rows if ok)
    total = len(rows)
    elapsed = int(time.time() - started)
    print(f"[showtime] t+{elapsed:>3}s cycle={cycle} ready={ready}/{total}")
    for name, ok, code in rows:
        mark = "[ok]" if ok else "[--]"
        print(f"  {mark} {name:<24} {code}")
    print("")


def run(interval: float, max_seconds: int) -> int:
    try:
        from rich.live import Live
        from rich.table import Table
        from rich.text import Text
    except Exception:
        Live = None  # type: ignore

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    started = time.time()
    cycle = 0

    def collect() -> list[tuple[str, bool, int]]:
        with cf.ThreadPoolExecutor(max_workers=min(24, len(ENDPOINTS))) as ex:
            futs = {ex.submit(probe, url): name for name, url in ENDPOINTS}
            rows: list[tuple[str, bool, int]] = []
            for fut in cf.as_completed(futs):
                name = futs[fut]
                ok, code = fut.result()
                rows.append((name, ok, code))
        rows.sort(key=lambda r: r[0].lower())
        return rows

    if Live is None:
        while not STOP and int(time.time() - started) <= max_seconds:
            cycle += 1
            rows = collect()
            render_plain(cycle, started, rows)
            if rows and all(ok for _, ok, _ in rows):
                return 0
            time.sleep(interval)
        return 0

    table = Table(title="PMOVES Showtime Bring-Up", show_lines=False)
    table.add_column("Service", no_wrap=True)
    table.add_column("Status")
    table.add_column("Code")

    with Live(table, refresh_per_second=5, transient=True) as live:
        while not STOP and int(time.time() - started) <= max_seconds:
            cycle += 1
            rows = collect()
            ready = sum(1 for _, ok, _ in rows if ok)
            total = len(rows)
            elapsed = int(time.time() - started)

            table = Table(
                title=f"PMOVES Showtime Bring-Up  •  t+{elapsed}s  •  ready {ready}/{total}",
                show_lines=False,
            )
            table.add_column("Service", no_wrap=True)
            table.add_column("Status")
            table.add_column("Code")
            for name, ok, code in rows:
                if ok:
                    status = Text("READY", style="bold green")
                else:
                    status = Text("PENDING", style="yellow")
                table.add_row(name, status, str(code))
            live.update(table)
            if rows and all(ok for _, ok, _ in rows):
                return 0
            time.sleep(interval)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=1.5, help="Polling interval in seconds")
    parser.add_argument("--max-seconds", type=int, default=900, help="Maximum run duration")
    args = parser.parse_args()
    return run(interval=args.interval, max_seconds=args.max_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
