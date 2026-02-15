#!/usr/bin/env python3
"""Prevent mixed Supabase runtimes (CLI + compose) in the same workspace."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

COMPOSE_PATTERN = re.compile(r"^pmoves-supabase-")
CLI_PATTERN = re.compile(
    r"^supabase_(?:auth|db|rest|realtime|storage|studio|kong|vector|analytics|inbucket|imgproxy|pg_meta|pooler).*"
)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def list_running_names() -> list[str]:
    proc = run(["docker", "ps", "--format", "{{.Names}}"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "docker ps failed")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def classify(names: list[str]) -> tuple[list[str], list[str]]:
    compose = [name for name in names if COMPOSE_PATTERN.search(name)]
    cli = [name for name in names if CLI_PATTERN.search(name)]
    return compose, cli


def stop_containers(names: list[str]) -> None:
    for name in names:
        proc = run(["docker", "stop", name])
        if proc.returncode != 0:
            print(f"WARN: failed to stop {name}: {proc.stderr.strip() or proc.stdout.strip()}", file=sys.stderr)


def stop_cli_stack() -> None:
    proc = run(["supabase", "stop", "--workdir", "."])
    if proc.returncode != 0:
        print(
            f"WARN: supabase stop failed: {proc.stderr.strip() or proc.stdout.strip()}",
            file=sys.stderr,
        )


def render_list(label: str, items: list[str]) -> None:
    print(f"{label}: {len(items)}")
    for item in items:
        print(f"  - {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime",
        choices=["cli", "compose", "kong"],
        required=True,
        help="Desired Supabase runtime for this session.",
    )
    parser.add_argument(
        "--reconcile",
        action="store_true",
        help="Stop the conflicting runtime stack automatically.",
    )
    args = parser.parse_args()

    desired = "compose" if args.runtime == "kong" else args.runtime
    try:
        names = list_running_names()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2

    compose_running, cli_running = classify(names)

    print(f"Supabase runtime guard (desired={desired})")
    render_list("compose running", compose_running)
    render_list("cli running", cli_running)

    if desired == "cli":
        conflict = compose_running
        conflict_label = "compose"
    else:
        conflict = cli_running
        conflict_label = "cli"

    if not conflict:
        print("PASS: no conflicting Supabase runtime detected.")
        return 0

    if args.reconcile:
        print(f"Reconciling: stopping conflicting {conflict_label} runtime...")
        if conflict_label == "cli":
            stop_cli_stack()
            # fallback in case CLI stop misses remaining service containers
            stop_containers(conflict)
        else:
            stop_containers(conflict)
        print("Re-checking runtime state...")
        names = list_running_names()
        compose_running, cli_running = classify(names)
        if desired == "cli" and compose_running:
            render_list("compose still running", compose_running)
            print("FAIL: compose runtime still active after reconcile.")
            return 1
        if desired == "compose" and cli_running:
            render_list("cli still running", cli_running)
            print("FAIL: cli runtime still active after reconcile.")
            return 1
        print("PASS: runtime reconciled.")
        return 0

    print(
        "FAIL: conflicting Supabase runtime detected. "
        "Run `make -C pmoves supa-runtime-reconcile SUPABASE_RUNTIME="
        f"{desired}` or stop the conflicting stack manually."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
