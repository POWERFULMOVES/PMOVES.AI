#!/usr/bin/env python3
"""Manage local-certification GitHub runners via Docker containers.

This keeps the local-cert lanes (`ai-lab`, `vps`, and `hotfix`) reproducible
across Windows/WSL/Linux without manual shell sequences.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


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
    RunnerLane(
        lane="hotfix",
        container_name="gha-runner-hotfix",
        runner_name="pmoves-hotfix-runner",
        labels="self-hosted,hotfix,Linux,X64",
    ),
)


def run_cmd(
    args: list[str],
    check: bool = True,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command with timeout handling.

    TimeoutExpired is re-raised when check=True but returns a synthetic
    CompletedProcess(returncode=-1) when check=False so callers like
    docker_rm and _runner_log_args degrade gracefully.
    """
    try:
        return subprocess.run(
            args,
            check=check,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        if check:
            raise
        return subprocess.CompletedProcess(
            args, returncode=-1, stdout="", stderr="timed out",
        )


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"required tool not found in PATH: {name}")


def registration_token(repo: str, lane: str) -> str:
    """Fetch a short-lived GitHub runner registration token (~1h validity)."""
    require_tool("gh")
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


def access_token(repo: str, lane: str) -> tuple[str, bool, str]:
    """Get auth credentials for persistent runner registration.

    Priority:
      0. GitHub App (APP_ID + APP_PRIVATE_KEY) — auto-renewing, no PAT needed
      1. Lane-specific PAT (RUNNER_PAT_{LANE})
      2. Shared PAT (RUNNER_PAT / GH_TOKEN / GITHUB_TOKEN)
      3. Short-lived registration token (~1h, deprecated)

    Returns (token_or_app_id, is_persistent, auth_mode) where:
      auth_mode = "app" | "pat" | "registration"
    For "app" mode, token_or_app_id is the APP_ID (APP_PRIVATE_KEY read separately).
    """
    # Priority 0: GitHub App credentials — the myoung34/github-runner image
    # natively supports APP_ID + APP_PRIVATE_KEY and mints its own tokens.
    app_id = os.getenv("GH_APP_ID")
    app_key = os.getenv("GH_APP_SEC")
    if app_id and app_key:
        return app_id, True, "app"

    # Priority 1-2: PAT cascade
    env_name = f"RUNNER_PAT_{lane.replace('-', '_').upper()}"
    lane_pat = os.getenv(env_name)
    if lane_pat:
        return lane_pat, True, "pat"
    shared_pat = (
        os.getenv("RUNNER_PAT")
        or os.getenv("GH_TOKEN")
        or os.getenv("GITHUB_TOKEN")
    )
    if shared_pat:
        return shared_pat, True, "pat"
    # Priority 3: short-lived registration token (expires in ~1h)
    print(
        f"WARNING: No App credentials or PAT found. "
        f"Using short-lived registration token for lane '{lane}' — "
        f"container will fail to re-register after ~1 hour.",
        file=sys.stderr,
    )
    return registration_token(repo, lane), False, "registration"


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
    "hotfix": {
        "cpus": os.getenv("RUNNER_HOTFIX_CPUS", "2"),
        "memory": os.getenv("RUNNER_HOTFIX_MEMORY", "4g"),
        "gpus": "",
    },
}


def _docker_socket_mount() -> str:
    """Return the correct Docker socket bind-mount for the current platform.

    On Windows (Docker Desktop via WSL), the socket path needs a leading
    double-slash. On Linux/macOS it's the standard /var/run path.
    """
    if platform.system() == "Windows":
        return "//var/run/docker.sock:/var/run/docker.sock"
    return "/var/run/docker.sock:/var/run/docker.sock"


def _secrets_volume_mount() -> str:
    """Return host↔container bind-mount for persisting synced secrets.

    Uses canonical path from _secrets_common.host_config_dir() to avoid
    duplication of the APPDATA/XDG resolution logic.
    """
    from pmoves.tools._secrets_common import host_config_dir

    host_dir = str(host_config_dir())
    os.makedirs(host_dir, exist_ok=True)
    return f"{host_dir}:/root/.config/pmoves"


def docker_run(
    repo: str, image: str, lane: RunnerLane, token: str,
    *, is_pat: bool = True, auth_mode: str = "pat",
) -> None:
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
    # GPU passthrough for ai-lab lane only (Linux with nvidia-container-toolkit)
    gpus = resources.get("gpus", "")
    if gpus and platform.system() != "Windows":
        cmd.extend(["--gpus", gpus])
        cmd.extend(["-e", "NVIDIA_VISIBLE_DEVICES=all"])
        cmd.extend(["-e", "NVIDIA_DRIVER_CAPABILITIES=compute,utility"])

    # Security: pass secrets via bare -e KEY (inherits from parent env)
    # instead of -e KEY=VALUE which leaks into /proc/<pid>/cmdline.
    env = os.environ.copy()
    token_env_flags: list[str] = []

    if auth_mode == "app":
        # GitHub App: myoung34/github-runner natively supports APP_ID +
        # APP_PRIVATE_KEY and mints installation tokens internally.
        env["APP_ID"] = token  # token is actually app_id in this mode
        env["APP_PRIVATE_KEY"] = os.getenv("GH_APP_SEC", "")
        token_env_flags = ["APP_ID", "APP_PRIVATE_KEY"]
    elif is_pat:
        env["ACCESS_TOKEN"] = token
        token_env_flags = ["ACCESS_TOKEN"]
    else:
        env["RUNNER_TOKEN"] = token
        token_env_flags = ["RUNNER_TOKEN"]

    env["REPO_URL"] = f"https://github.com/{repo}"
    env["RUNNER_NAME"] = lane.runner_name
    env["LABELS"] = lane.labels
    env["RUNNER_WORKDIR"] = "/tmp/runner/_work"

    cmd.extend([
        "-e", "REPO_URL",
        "-e", "RUNNER_NAME",
        "-e", "LABELS",
        "-e", "RUNNER_WORKDIR",
    ])
    for flag in token_env_flags:
        cmd.extend(["-e", flag])
    cmd.extend([
        "-v", _docker_socket_mount(),
        "-v", _secrets_volume_mount(),
        image,
    ])
    run_cmd(cmd, env=env)

def _runner_log_args(lane: RunnerLane) -> list[str]:
    info = run_cmd(
        ["docker", "info", "--format", "{{json .Plugins.Log}}"],
        check=False,
        timeout=15,
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
    for lane in lanes:
        token, is_pat, auth_mode = access_token(repo, lane.lane)
        docker_rm(lane.container_name)
        docker_run(repo, image, lane, token, is_pat=is_pat, auth_mode=auth_mode)
        mode_labels = {
            "app": "APP_ID + APP_PRIVATE_KEY (GitHub App)",
            "pat": "ACCESS_TOKEN (PAT)",
            "registration": "RUNNER_TOKEN (short-lived)",
        }
        print(f"started {lane.container_name} ({lane.runner_name}) [{mode_labels.get(auth_mode, auth_mode)}]")
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
        default=os.getenv("RUNNER_IMAGE", "ghcr.io/powerfulmoves/github-runner-pmoves:latest"),
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
