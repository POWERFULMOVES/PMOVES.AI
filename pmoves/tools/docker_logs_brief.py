#!/usr/bin/env python3
"""Brief Docker runtime log summary for PMOVES operators/audits."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


DEFAULT_PREFIXES = ("pmoves-", "supabase-")
DEFAULT_PATTERN = r"(error|fatal|traceback|exception|warn|timeout|failed)"


def run_cmd(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    out = proc.stdout or ""
    err = proc.stderr or ""
    merged = out if not err else (out + ("\n" if out and not out.endswith("\n") else "") + err)
    return proc.returncode, merged


def list_containers(prefixes: tuple[str, ...]) -> list[str]:
    rc, out = run_cmd(["docker", "ps", "--format", "{{.Names}}"])
    if rc != 0:
        return []
    names = [line.strip() for line in out.splitlines() if line.strip()]
    return [name for name in names if any(name.startswith(prefix) for prefix in prefixes)]


def inspect_state(container: str) -> tuple[str, str]:
    rc, out = run_cmd(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
            container,
        ]
    )
    if rc != 0:
        return "unknown", "unknown"
    parts = (out.strip() or "unknown|unknown").split("|", maxsplit=1)
    if len(parts) != 2:
        return "unknown", "unknown"
    return parts[0], parts[1]


def collect_logs(container: str, tail: int) -> list[str]:
    _, out = run_cmd(["docker", "logs", "--tail", str(tail), container])
    return out.splitlines()


def summarize_chit_events(chit_path: Path) -> list[str]:
    if not chit_path.exists():
        return ["CHIT: not found"]
    try:
        payload = json.loads(chit_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"CHIT: unreadable ({exc})"]

    events: list[object]
    if isinstance(payload, dict):
        for key in ("events", "event_log", "timeline", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                events = value
                break
        else:
            return ["CHIT: loaded, but no recognizable event list key (events/event_log/timeline/records)."]
    elif isinstance(payload, list):
        events = payload
    else:
        return ["CHIT: loaded, unsupported root format."]

    types: list[str] = []
    for item in events[-20:]:
        if isinstance(item, dict):
            event_type = (
                str(item.get("event") or item.get("type") or item.get("topic") or item.get("name") or "unknown")
            )
        else:
            event_type = str(item)
        types.append(event_type)

    lines = [f"CHIT: events={len(events)} tail_sample={len(types)}"]
    if types:
        lines.append("CHIT tail: " + ", ".join(types[-10:]))
    return lines


def build_report(
    containers: list[str],
    tail: int,
    matcher: re.Pattern[str],
    show_all: bool,
    chit_path: Path | None,
) -> str:
    lines: list[str] = []
    lines.append("# PMOVES Docker Log Brief")
    lines.append(f"containers={len(containers)} tail={tail} pattern={matcher.pattern}")
    if chit_path:
        lines.extend(summarize_chit_events(chit_path))
    lines.append("")

    for container in containers:
        status, health = inspect_state(container)
        log_lines = collect_logs(container, tail=tail)
        matched = [line for line in log_lines if matcher.search(line)]
        lines.append(f"## {container}")
        lines.append(f"status={status} health={health} matched={len(matched)}")
        if matched:
            lines.extend(matched[-40:])
        elif show_all:
            lines.extend(log_lines[-40:])
        else:
            lines.append("(no matching lines)")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tail", type=int, default=120, help="Tail line count per container.")
    parser.add_argument(
        "--prefix",
        action="append",
        default=list(DEFAULT_PREFIXES),
        help="Container name prefix filter (repeatable).",
    )
    parser.add_argument("--pattern", default=DEFAULT_PATTERN, help="Regex for lines to surface.")
    parser.add_argument("--show-all-if-no-match", action="store_true", help="Show last lines when no matches found.")
    parser.add_argument("--save", default="", help="Optional file path to save report.")
    parser.add_argument(
        "--chit-path",
        default="data/chit/env.cgp.json",
        help="Optional CHIT event bundle path to summarize (set empty string to disable).",
    )
    args = parser.parse_args()

    matcher = re.compile(args.pattern, flags=re.IGNORECASE)
    containers = list_containers(tuple(args.prefix))
    chit_path = Path(args.chit_path) if args.chit_path else None
    report = build_report(
        containers=containers,
        tail=args.tail,
        matcher=matcher,
        show_all=args.show_all_if_no_match,
        chit_path=chit_path,
    )
    print(report, end="")

    if args.save:
        save_path = Path(args.save)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(report, encoding="utf-8")
        print(f"Saved: {save_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
