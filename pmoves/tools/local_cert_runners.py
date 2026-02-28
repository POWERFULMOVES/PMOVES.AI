#!/usr/bin/env python3
"""Manage local-certification GitHub runners via Docker containers.

This keeps the local-cert lanes (`ai-lab` and `vps`) reproducible across
Windows/WSL/Linux without manual shell sequences.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class RunnerLane:
    lane: str
    container_name: str
    runner_name: str
    labels: str


LANES: tuple[RunnerLane, ...] = (
    RunnerLane(
        lane="ai-lab",
        container_name="gha-runner-ai-lab",
        runner_name="pmoves-ai-lab-runner",
        labels="self-hosted,ai-lab,gpu,Linux,X64",
    ),
    RunnerLane(
        lane="vps",
        container_name="gha-runner-vps",
        runner_name="pmoves-vps-runner",
        labels="self-hosted,vps,Linux,X64",
    ),
)


def run_cmd(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        text=True,
        capture_output=True,
    )


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"required tool not found in PATH: {name}")


def registration_token(repo: str, lane: str) -> str:
    env_name = f"RUNNER_TOKEN_{lane.replace('-', '_').upper()}"
    lane_token = os.getenv(env_name)
    if lane_token:
        return lane_token
    shared_token = os.getenv("RUNNER_TOKEN")
    if shared_token:
        return shared_token

    out = run_cmd(
        [
            "gh",
            "api",
            "--method",
            "POST",
            f"repos/{repo}/actions/runners/registration-token",
            "--jq",
            ".token",
        ]
    )
    token = out.stdout.strip()
    if not token:
        raise RuntimeError(f"failed to retrieve registration token for lane '{lane}'")
    return token


def docker_rm(container_name: str) -> None:
    run_cmd(["docker", "rm", "-f", container_name], check=False)


LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100/loki/api/v1/push")

# Default resource limits per lane (overridable via env)
LANE_RESOURCES: dict[str, dict[str, str]] = {
    "ai-lab": {
        "cpus": os.getenv("RUNNER_AI_LAB_CPUS", "4"),
        "memory": os.getenv("RUNNER_AI_LAB_MEMORY", "8g"),
        "gpus": "all",
    },
    "vps": {
        "cpus": os.getenv("RUNNER_VPS_CPUS", "2"),
        "memory": os.getenv("RUNNER_VPS_MEMORY", "4g"),
        "gpus": "",
    },
}


def docker_run(repo: str, image: str, lane: RunnerLane, token: str) -> None:
    resources = LANE_RESOURCES.get(lane.lane, {"cpus": "4", "memory": "8g"})
    cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        lane.container_name,
        "--restart",
        "unless-stopped",
        "--cpus",
        resources["cpus"],
        "--memory",
        resources["memory"],
    ]
    cmd.extend(_runner_log_args(lane))
    # GPU passthrough for ai-lab lane only
    gpus = resources.get("gpus", "")
    if gpus:
        cmd.extend(["--gpus", gpus])
        cmd.extend(["-e", "NVIDIA_VISIBLE_DEVICES=all"])
        cmd.extend(["-e", "NVIDIA_DRIVER_CAPABILITIES=compute,utility"])
    cmd.extend([
        "-e",
        f"REPO_URL=https://github.com/{repo}",
        "-e",
        f"RUNNER_NAME={lane.runner_name}",
        "-e",
        f"RUNNER_TOKEN={token}",
        "-e",
        f"LABELS={lane.labels}",
        "-e",
        "RUNNER_WORKDIR=/tmp/runner/_work",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        image,
    ])
    run_cmd(cmd)

def _runner_log_args(lane: RunnerLane) -> list[str]:
    info = run_cmd(
        ["docker", "info", "--format", "{{json .Plugins.Log}}"],
        check=False,
    )
    if info.returncode == 0:
        payload = (info.stdout or "").strip()
        if payload:
            try:
                drivers = json.loads(payload)
                if isinstance(drivers, list) and "loki" in drivers:
                    return [
                        "--log-driver",
                        "loki",
                        "--log-opt",
                        f"loki-url={LOKI_URL}",
                        "--log-opt",
                        f"loki-external-labels=job=gha-runner,lane={lane.lane},runner={lane.runner_name}",
                    ]
            except json.JSONDecodeError:
                pass
    return ["--log-driver", "json-file"]
def _selected_lanes(names: list[str] | None) -> tuple[RunnerLane, ...]:
    if not names:
        return LANES
    wanted = {name.strip().lower() for name in names if name.strip()}
    selected = tuple(lane for lane in LANES if lane.lane in wanted)
    missing = sorted(wanted - {lane.lane for lane in selected})
    if missing:
        raise RuntimeError(f"unknown runner lane(s): {', '.join(missing)}")
    return selected


def cmd_up(repo: str, image: str, lanes: tuple[RunnerLane, ...]) -> int:
    require_tool("docker")
    require_tool("gh")
    for lane in lanes:
        token = registration_token(repo, lane.lane)
        docker_rm(lane.container_name)
        docker_run(repo, image, lane, token)
        print(f"started {lane.container_name} ({lane.runner_name})")
    return 0


def cmd_down(lanes: tuple[RunnerLane, ...]) -> int:
    require_tool("docker")
    for lane in lanes:
        docker_rm(lane.container_name)
        print(f"removed {lane.container_name}")
    return 0


def cmd_status(repo: str, lanes: tuple[RunnerLane, ...]) -> int:
    require_tool("docker")
    require_tool("gh")

    ps = run_cmd(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
        check=False,
    )
    print("local containers:")
    names = {line.split("\t", 1)[0]: line for line in ps.stdout.splitlines() if line}
    for lane in lanes:
        line = names.get(lane.container_name)
        if line:
            print(f"  - {line}")
        else:
            print(f"  - {lane.container_name}\tnot-running")

    gh = run_cmd(
        [
            "gh",
            "api",
            f"repos/{repo}/actions/runners",
            "--paginate",
            "--jq",
            ".runners[] | [.name,.status,(.labels|map(.name)|join(\",\"))] | @tsv",
        ],
        check=False,
    )
    print("github runners:")
    rows = [ln for ln in gh.stdout.splitlines() if ln]
    for lane in lanes:
        match = next((r for r in rows if r.startswith(f"{lane.runner_name}\t")), None)
        if match:
            print(f"  - {match}")
        else:
            print(f"  - {lane.runner_name}\tnot-found")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage local-certification runner containers for PMOVES."
    )
    parser.add_argument(
        "action",
        choices=("up", "down", "status"),
        help="Operation to perform.",
    )
    parser.add_argument(
        "--repo",
        default=os.getenv("GITHUB_REPOSITORY", "POWERFULMOVES/PMOVES.AI"),
        help="GitHub repository (owner/name).",
    )
    parser.add_argument(
        "--image",
        default=os.getenv("RUNNER_IMAGE", "myoung34/github-runner:latest"),
        help="Docker image used for runner containers.",
    )
    parser.add_argument(
        "--lane",
        action="append",
        choices=tuple(lane.lane for lane in LANES),
        help="Runner lane to target. Repeat to target multiple lanes. Default: all lanes.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    lanes = _selected_lanes(args.lane)
    try:
        if args.action == "up":
            return cmd_up(args.repo, args.image, lanes)
        if args.action == "down":
            return cmd_down(lanes)
        return cmd_status(args.repo, lanes)
    except Exception as exc:  # pragma: no cover - operator-facing guard
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
