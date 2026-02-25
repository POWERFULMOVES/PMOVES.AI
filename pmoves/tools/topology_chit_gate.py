#!/usr/bin/env python3
"""Topology + CHIT gate for production readiness checks.

Checks:
1) Archon topology acknowledgement:
   - archon-ui and archon containers exist/running
   - archon-ui has host port 3737 published
   - archon API has host port 8091 published
   - archon-ui and archon share a docker network
   - archon API (/healthz) and archon-ui (/) are reachable

2) CHIT sync acknowledgement:
   - v1 CHIT manifest is in sync with v2 source
   - key CHIT-aware running containers expose required CHIT env keys
   - CHIT passphrase is not empty/placeholder on those containers
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES_ROOT = Path(__file__).resolve().parents[1]

CHIT_REQUIRED_KEYS = ("CHIT_REQUIRE_SIGNATURE", "CHIT_DECRYPT_ANCHORS", "CHIT_PASSPHRASE")
CHIT_CONTAINER_TOKENS = (
    "agent-zero",
    "hi-rag-gateway-v2-gpu",
    "hi-rag-gateway-v2",
    "hi-rag-gateway",
    "gateway",
    "flute-gateway",
    "evo-controller",
)
PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "change-me",
    "placeholder",
    "your_auth_token_here",
    "your_client_secret_here",
    "placeholder_db_password_here_generate_with_generate-keys.sh",
}


def _run(cmd: Sequence[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="ignore",
    )


def _docker_ps(project: str) -> List[str]:
    result = _run(
        [
            "docker",
            "ps",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--format",
            "{{.Names}}",
        ]
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _docker_inspect(name: str) -> Mapping[str, object] | None:
    result = _run(["docker", "inspect", name])
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list) or not data:
        return None
    item = data[0]
    return item if isinstance(item, Mapping) else None


def _compose_service_name(inspect_data: Mapping[str, object]) -> str | None:
    config = inspect_data.get("Config")
    if not isinstance(config, Mapping):
        return None
    labels = config.get("Labels")
    if not isinstance(labels, Mapping):
        return None
    value = labels.get("com.docker.compose.service")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _find_container_by_service(containers: Sequence[str], service: str) -> str | None:
    for name in containers:
        info = _docker_inspect(name)
        if info is None:
            continue
        if _compose_service_name(info) == service:
            return name
    return None


def _ports_published(inspect_data: Mapping[str, object], container_port: int) -> bool:
    net = inspect_data.get("NetworkSettings")
    if not isinstance(net, Mapping):
        return False
    ports = net.get("Ports")
    if not isinstance(ports, Mapping):
        return False
    value = ports.get(f"{container_port}/tcp")
    return isinstance(value, list) and len(value) > 0


def _container_networks(inspect_data: Mapping[str, object]) -> List[str]:
    net = inspect_data.get("NetworkSettings")
    if not isinstance(net, Mapping):
        return []
    networks = net.get("Networks")
    if not isinstance(networks, Mapping):
        return []
    return [str(name) for name in networks.keys()]


def _http_code(url: str, *, retries: int = 1, delay_s: float = 0.0) -> int:
    for attempt in range(retries):
        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=5) as resp:
                return int(getattr(resp, "status", 200))
        except HTTPError as exc:
            return int(exc.code)
        except URLError:
            if attempt < retries - 1 and delay_s > 0:
                time.sleep(delay_s)
                continue
            return 0
        except TimeoutError:
            if attempt < retries - 1 and delay_s > 0:
                time.sleep(delay_s)
                continue
            return 0
    return 0


def _env_map(inspect_data: Mapping[str, object]) -> Dict[str, str]:
    config = inspect_data.get("Config")
    if not isinstance(config, Mapping):
        return {}
    env = config.get("Env")
    if not isinstance(env, list):
        return {}
    out: Dict[str, str] = {}
    for item in env:
        if not isinstance(item, str) or "=" not in item:
            continue
        key, value = item.split("=", 1)
        out[key] = value
    return out


def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_placeholder(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    return normalized in PLACEHOLDER_VALUES


def _check_manifest_sync() -> tuple[bool, str]:
    result = _run([sys.executable, "tools/chit_manifest_sync.py", "--check"], cwd=PMOVES_ROOT)
    merged = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode == 0, merged


def _check_topology(project: str, *, warnings: List[str], errors: List[str]) -> None:
    containers = _docker_ps(project)
    archon_ui = _find_container_by_service(containers, "archon-ui")
    archon = _find_container_by_service(containers, "archon")

    if not archon_ui:
        errors.append("archon-ui container is not running")
        return
    if not archon:
        errors.append("archon container is not running")
        return

    ui_info = _docker_inspect(archon_ui)
    archon_info = _docker_inspect(archon)
    if ui_info is None:
        errors.append(f"unable to inspect container: {archon_ui}")
        return
    if archon_info is None:
        errors.append(f"unable to inspect container: {archon}")
        return

    if not _ports_published(ui_info, 3737):
        errors.append(f"{archon_ui} is missing host publish for 3737/tcp")
    if not _ports_published(archon_info, 8091):
        errors.append(f"{archon} is missing host publish for 8091/tcp")

    ui_nets = set(_container_networks(ui_info))
    archon_nets = set(_container_networks(archon_info))
    if not (ui_nets & archon_nets):
        errors.append("archon-ui and archon do not share any docker network")

    if "pmoves_external" not in ui_nets:
        warnings.append(
            "archon-ui is not attached to pmoves_external; host reachability may break on internal api networks"
        )

    archon_code = _http_code("http://localhost:8091/healthz", retries=2, delay_s=1.0)
    if archon_code != 200:
        errors.append(f"archon API health check failed: http://localhost:8091/healthz => {archon_code}")

    # First request can fail while vite preview initializes.
    ui_code = _http_code("http://localhost:3737/", retries=6, delay_s=2.0)
    if ui_code != 200:
        errors.append(f"archon-ui health check failed: http://localhost:3737/ => {ui_code}")


def _check_chit_sync(project: str, *, warnings: List[str], errors: List[str]) -> None:
    sync_ok, sync_message = _check_manifest_sync()
    if not sync_ok:
        errors.append("CHIT manifest v1/v2 sync check failed")
        if sync_message:
            warnings.append(sync_message)

    containers = _docker_ps(project)
    matched: List[str] = []
    for token in CHIT_CONTAINER_TOKENS:
        for name in containers:
            if f"-{token}-" in name and name not in matched:
                matched.append(name)

    if not matched:
        warnings.append("no CHIT-aware containers found for env propagation checks")
        return

    for container_name in matched:
        info = _docker_inspect(container_name)
        if info is None:
            warnings.append(f"unable to inspect CHIT-aware container: {container_name}")
            continue
        env = _env_map(info)

        missing = [key for key in CHIT_REQUIRED_KEYS if key not in env]
        if missing:
            errors.append(f"{container_name} missing CHIT env keys: {', '.join(missing)}")
            continue

        passphrase = env.get("CHIT_PASSPHRASE")
        if _is_placeholder(passphrase):
            warnings.append(f"{container_name} has empty/placeholder CHIT_PASSPHRASE")

        if not _is_true(env.get("CHIT_REQUIRE_SIGNATURE")):
            warnings.append(f"{container_name} has CHIT_REQUIRE_SIGNATURE disabled")

        if not _is_true(env.get("CHIT_DECRYPT_ANCHORS")):
            warnings.append(f"{container_name} has CHIT_DECRYPT_ANCHORS disabled")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="pmoves", help="docker compose project name (default: pmoves)")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as failures (recommended for production gates)",
    )
    args = parser.parse_args(argv)

    warnings: List[str] = []
    errors: List[str] = []

    _check_topology(args.project, warnings=warnings, errors=errors)
    _check_chit_sync(args.project, warnings=warnings, errors=errors)

    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARN: {message}")

    print(
        "SUMMARY: "
        f"errors={len(errors)} warnings={len(warnings)} "
        f"strict={'true' if args.strict else 'false'}"
    )

    if errors:
        return 1
    if args.strict and warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
