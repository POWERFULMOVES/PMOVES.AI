#!/usr/bin/env python3
"""Topology + CHIT gate for production readiness checks.

Checks:
1) Project topology acknowledgement (all running compose containers):
   - each container has namespaced networks
   - host publish collisions are blocked
   - host-published services are validated for external namespace reachability
   - critical service URLs avoid loopback hardcoding
   - NATS URL auth is checked across the running project

2) Archon topology acknowledgement:
   - archon-ui and archon containers exist/running
   - archon-ui has host port 3737 published
   - archon API has host port 8091 published
   - archon-ui and archon share a docker network
   - archon API (/healthz) and archon-ui (/) are reachable

3) CHIT sync acknowledgement:
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
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


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
NAMESPACE_EXTRA_NETWORKS = {"bridge", "host", "none", "pmoves-net", "cataclysm-net"}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
CRITICAL_URL_KEYS = {
    "NATS_URL",
    "SUPA_REST_URL",
    "SUPA_REST_INTERNAL_URL",
    "SUPABASE_URL",
    "SUPABASE_INTERNAL_URL",
    "AGENT_ZERO_API_BASE",
    "ARCHON_SERVER_URL",
    "ARCHON_URL",
    "HIRAG_URL",
    "HIRAG_GPU_URL",
    "HIRAG_CPU_URL",
    "TENSORZERO_BASE_URL",
    "MEILI_URL",
    "QDRANT_URL",
    "NEO4J_URL",
    "MINIO_ENDPOINT",
    "DATABASE_URL",
    "POSTGRES_URL",
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


def _docker_inspect_many(names: Sequence[str]) -> Dict[str, Mapping[str, object]]:
    if not names:
        return {}
    result = _run(["docker", "inspect", *names])
    if result.returncode != 0:
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, list):
        return {}
    out: Dict[str, Mapping[str, object]] = {}
    for item in data:
        if not isinstance(item, Mapping):
            continue
        raw_name = item.get("Name")
        if not isinstance(raw_name, str):
            continue
        name = raw_name.lstrip("/")
        if name:
            out[name] = item
    return out


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


def _find_container_by_service(
    inspections: Mapping[str, Mapping[str, object]], service: str
) -> tuple[str, Mapping[str, object]] | None:
    for name, info in inspections.items():
        if _compose_service_name(info) == service:
            return name, info
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


def _published_bindings(inspect_data: Mapping[str, object]) -> List[tuple[str, str, str]]:
    net = inspect_data.get("NetworkSettings")
    if not isinstance(net, Mapping):
        return []
    ports = net.get("Ports")
    if not isinstance(ports, Mapping):
        return []
    out: List[tuple[str, str, str]] = []
    for container_port, bindings in ports.items():
        if not isinstance(bindings, list):
            continue
        for binding in bindings:
            if not isinstance(binding, Mapping):
                continue
            host_ip = binding.get("HostIp")
            host_port = binding.get("HostPort")
            if isinstance(host_ip, str) and isinstance(host_port, str):
                out.append((str(container_port), host_ip, host_port))
    return out


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


def _extract_host(value: str) -> str:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return ""
    return (parsed.hostname or "").strip().lower()


def _url_has_auth(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    return bool(parsed.username and parsed.password)


def _is_loopback_exception(service: str | None, key: str, value: str) -> bool:
    # agent-zero self-address (in-container API loopback)
    if service == "agent-zero" and key == "AGENT_ZERO_API_BASE":
        return True
    # archon self-reference for its own API endpoint
    if service == "archon" and key == "ARCHON_SERVER_URL":
        return True
    return False


def _check_manifest_sync() -> tuple[bool, str]:
    result = _run([sys.executable, "tools/chit_manifest_sync.py", "--check"], cwd=PMOVES_ROOT)
    merged = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode == 0, merged


def _check_project_topology(
    project: str,
    inspections: Mapping[str, Mapping[str, object]],
    *,
    warnings: List[str],
    errors: List[str],
) -> None:
    if not inspections:
        errors.append(f"no running containers found for compose project '{project}'")
        return

    namespace_prefix = f"{project}_"
    host_bindings: Dict[str, List[str]] = defaultdict(list)
    non_namespaced_networks: Dict[str, List[str]] = defaultdict(list)
    published_without_external: List[str] = []
    critical_loopback: Dict[tuple[str, str], List[str]] = defaultdict(list)
    unauth_nats: Dict[str, List[str]] = defaultdict(list)

    for container_name, info in sorted(inspections.items()):
        service = _compose_service_name(info)
        networks = _container_networks(info)
        if not networks:
            errors.append(f"{container_name} has no attached docker networks")
            continue

        for network in networks:
            if network.startswith(namespace_prefix):
                continue
            if network in NAMESPACE_EXTRA_NETWORKS:
                continue
            non_namespaced_networks[network].append(container_name)

        bindings = _published_bindings(info)
        if bindings:
            for _, host_ip, host_port in bindings:
                host_bindings[f"{host_ip}:{host_port}"].append(container_name)
            if not any(
                net.endswith("_external") or net in {"pmoves-net", "cataclysm-net"}
                for net in networks
            ):
                published_without_external.append(container_name)

        env = _env_map(info)
        for key in CRITICAL_URL_KEYS:
            value = env.get(key)
            if not value:
                continue
            host = _extract_host(value)
            if host in LOOPBACK_HOSTS and not _is_loopback_exception(service, key, value):
                critical_loopback[(key, value)].append(container_name)

        nats_url = env.get("NATS_URL")
        if nats_url:
            host = _extract_host(nats_url)
            if host in LOOPBACK_HOSTS:
                errors.append(f"{container_name} uses loopback NATS_URL ({nats_url})")
            if not _url_has_auth(nats_url):
                unauth_nats[nats_url].append(container_name)

    for network_name, containers in sorted(non_namespaced_networks.items()):
        unique = sorted(set(containers))
        sample = unique[0]
        warnings.append(
            f"network namespace drift: '{network_name}' used by {len(unique)} containers (example: {sample})"
        )

    for bind, containers in sorted(host_bindings.items()):
        unique = sorted(set(containers))
        if len(unique) > 1:
            joined = ", ".join(unique[:4])
            suffix = " ..." if len(unique) > 4 else ""
            errors.append(f"host publish collision on {bind}: {joined}{suffix}")

    for container_name in sorted(set(published_without_external)):
        warnings.append(
            f"{container_name} publishes host ports without *_external network attachment (verify namespace publish policy)"
        )

    for (key, value), containers in sorted(
        critical_loopback.items(),
        key=lambda item: len(set(item[1])),
        reverse=True,
    ):
        unique = sorted(set(containers))
        sample = ", ".join(unique[:3])
        suffix = " ..." if len(unique) > 3 else ""
        warnings.append(
            f"{key} uses loopback url '{value}' in {len(unique)} containers ({sample}{suffix}); "
            "prefer service DNS/host.docker.internal for dynamic mapping"
        )

    for nats_url, containers in sorted(
        unauth_nats.items(),
        key=lambda item: len(set(item[1])),
        reverse=True,
    ):
        unique = sorted(set(containers))
        sample = ", ".join(unique[:3])
        suffix = " ..." if len(unique) > 3 else ""
        warnings.append(
            f"NATS_URL is unauthenticated ({nats_url}) in {len(unique)} containers ({sample}{suffix}); "
            "use credentialed nats://user:pass@host:4222"
        )


def _check_archon_topology(
    inspections: Mapping[str, Mapping[str, object]], *, warnings: List[str], errors: List[str]
) -> None:
    archon_ui_hit = _find_container_by_service(inspections, "archon-ui")
    archon_hit = _find_container_by_service(inspections, "archon")

    if not archon_ui_hit:
        errors.append("archon-ui container is not running")
        return
    if not archon_hit:
        errors.append("archon container is not running")
        return

    archon_ui, ui_info = archon_ui_hit
    archon, archon_info = archon_hit

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

    # First request can fail while Vite preview initializes.
    ui_code = _http_code("http://localhost:3737/", retries=6, delay_s=2.0)
    if ui_code != 200:
        errors.append(f"archon-ui health check failed: http://localhost:3737/ => {ui_code}")


def _check_chit_sync(
    inspections: Mapping[str, Mapping[str, object]], *, warnings: List[str], errors: List[str]
) -> None:
    sync_ok, sync_message = _check_manifest_sync()
    if not sync_ok:
        errors.append("CHIT manifest v1/v2 sync check failed")
        if sync_message:
            warnings.append(sync_message)

    matched: List[str] = []
    for container_name, info in inspections.items():
        service = _compose_service_name(info) or ""
        for token in CHIT_CONTAINER_TOKENS:
            if token == service or f"-{token}-" in container_name:
                matched.append(container_name)
                break

    if not matched:
        warnings.append("no CHIT-aware containers found for env propagation checks")
        return

    for container_name in sorted(set(matched)):
        info = inspections.get(container_name)
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

    container_names = _docker_ps(args.project)
    inspections = _docker_inspect_many(container_names)

    _check_project_topology(args.project, inspections, warnings=warnings, errors=errors)
    _check_archon_topology(inspections, warnings=warnings, errors=errors)
    _check_chit_sync(inspections, warnings=warnings, errors=errors)

    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARN: {message}")

    print(
        "SUMMARY: "
        f"errors={len(errors)} warnings={len(warnings)} "
        f"containers={len(inspections)} strict={'true' if args.strict else 'false'}"
    )

    if errors:
        return 1
    if args.strict and warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
