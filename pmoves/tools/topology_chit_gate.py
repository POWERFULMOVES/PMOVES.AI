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
   - archon container exists/running
   - archon has host port 8091 published
   - archon has host port 3737 published for the consolidated UI
   - archon API (/healthz) and UI (/) are reachable

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
DEFAULT_POLICY_PATH = PMOVES_ROOT / "configs" / "topology_policy_manifest.json"

CHIT_REQUIRED_KEYS = ("CHIT_REQUIRE_SIGNATURE", "CHIT_DECRYPT_ANCHORS", "CHIT_PASSPHRASE")
DEFAULT_CHIT_REQUIRED_SERVICES = (
    "agent-zero",
    "hi-rag-gateway",
    "hi-rag-gateway-gpu",
    "hi-rag-gateway-v2",
    "hi-rag-gateway-v2-gpu",
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
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
DEFAULT_CRITICAL_URL_KEYS = {
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


def _default_policy(project: str) -> Dict[str, object]:
    return {
        "project": project,
        "namespace_prefix": f"{project}_",
        "allowed_extra_networks": ["bridge", "host", "none", "pmoves-net", "cataclysm-net"],
        "external_network_suffixes": ["_external"],
        "external_network_names": [f"{project}_external", "pmoves-net", "cataclysm-net"],
        "published_ports_require_external": True,
        "published_external_exceptions": [],
        "critical_url_keys": sorted(DEFAULT_CRITICAL_URL_KEYS),
        "loopback_exception_keys_by_service": {
            "agent-zero": ["AGENT_ZERO_API_BASE"],
            "archon": ["ARCHON_SERVER_URL"],
        },
        "require_nats_auth": True,
        "nats_auth_exceptions": [],
        "required_networks_by_service": {},
        "required_published_ports_by_service": {},
        "chit_required_services": sorted(DEFAULT_CHIT_REQUIRED_SERVICES),
    }


def _normalize_service_str_map(raw: object) -> Dict[str, List[str]]:
    if not isinstance(raw, Mapping):
        return {}
    out: Dict[str, List[str]] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        if not isinstance(value, list):
            continue
        normalized = [str(item).strip() for item in value if str(item).strip()]
        if normalized:
            out[key.strip()] = normalized
    return out


def _normalize_service_int_map(raw: object) -> Dict[str, List[int]]:
    if not isinstance(raw, Mapping):
        return {}
    out: Dict[str, List[int]] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        if not isinstance(value, list):
            continue
        normalized: List[int] = []
        for item in value:
            try:
                normalized.append(int(item))
            except (TypeError, ValueError):
                continue
        if normalized:
            out[key.strip()] = normalized
    return out


def _load_policy(path: Path, project: str, *, warnings: List[str]) -> Dict[str, object]:
    policy = _default_policy(project)
    if not path.exists():
        warnings.append(f"topology policy manifest not found at {path}; using built-in defaults")
        return policy
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        warnings.append(f"unable to read topology policy manifest {path}: {exc}; using built-in defaults")
        return policy
    except json.JSONDecodeError as exc:
        warnings.append(f"invalid JSON in topology policy manifest {path}: {exc}; using built-in defaults")
        return policy
    if not isinstance(raw, Mapping):
        warnings.append(f"topology policy manifest {path} is not a JSON object; using built-in defaults")
        return policy

    for list_key in (
        "allowed_extra_networks",
        "external_network_suffixes",
        "external_network_names",
        "published_external_exceptions",
        "critical_url_keys",
        "nats_auth_exceptions",
        "chit_required_services",
    ):
        value = raw.get(list_key)
        if isinstance(value, list):
            normalized = [str(item).strip() for item in value if str(item).strip()]
            policy[list_key] = normalized

    for bool_key in ("published_ports_require_external", "require_nats_auth"):
        value = raw.get(bool_key)
        if isinstance(value, bool):
            policy[bool_key] = value

    for str_key in ("project", "namespace_prefix"):
        value = raw.get(str_key)
        if isinstance(value, str) and value.strip():
            policy[str_key] = value.strip()

    policy["loopback_exception_keys_by_service"] = _normalize_service_str_map(
        raw.get("loopback_exception_keys_by_service")
    )
    policy["required_networks_by_service"] = _normalize_service_str_map(raw.get("required_networks_by_service"))
    policy["required_published_ports_by_service"] = _normalize_service_int_map(
        raw.get("required_published_ports_by_service")
    )
    return policy


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


def _published_host_port(inspect_data: Mapping[str, object], container_port: int) -> str | None:
    net = inspect_data.get("NetworkSettings")
    if not isinstance(net, Mapping):
        return None
    ports = net.get("Ports")
    if not isinstance(ports, Mapping):
        return None
    value = ports.get(f"{container_port}/tcp")
    if not isinstance(value, list) or not value:
        return None
    first = value[0]
    if not isinstance(first, Mapping):
        return None
    host_port = first.get("HostPort")
    if not isinstance(host_port, str) or not host_port.strip():
        return None
    return host_port.strip()


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


def _check_manifest_sync() -> tuple[bool, str]:
    result = _run([sys.executable, "tools/chit_manifest_sync.py", "--check"], cwd=PMOVES_ROOT)
    merged = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode == 0, merged


def _check_project_topology(
    project: str,
    inspections: Mapping[str, Mapping[str, object]],
    policy: Mapping[str, object],
    *,
    warnings: List[str],
    errors: List[str],
) -> None:
    if not inspections:
        errors.append(f"no running containers found for compose project '{project}'")
        return

    namespace_prefix = str(policy.get("namespace_prefix") or f"{project}_")
    allowed_extra_networks = {
        str(item).strip()
        for item in (policy.get("allowed_extra_networks") or [])
        if str(item).strip()
    }
    external_network_suffixes = tuple(
        str(item).strip()
        for item in (policy.get("external_network_suffixes") or [])
        if str(item).strip()
    )
    external_network_names = {
        str(item).strip()
        for item in (policy.get("external_network_names") or [])
        if str(item).strip()
    }
    published_requires_external = bool(policy.get("published_ports_require_external", True))
    published_external_exceptions = {
        str(item).strip()
        for item in (policy.get("published_external_exceptions") or [])
        if str(item).strip()
    }
    critical_url_keys = {
        str(item).strip()
        for item in (policy.get("critical_url_keys") or [])
        if str(item).strip()
    }
    loopback_exception_keys_by_service = {
        str(service).strip(): {
            str(key).strip()
            for key in keys
            if str(key).strip()
        }
        for service, keys in _normalize_service_str_map(
            policy.get("loopback_exception_keys_by_service")
        ).items()
    }
    require_nats_auth = bool(policy.get("require_nats_auth", True))
    nats_auth_exceptions = {
        str(item).strip()
        for item in (policy.get("nats_auth_exceptions") or [])
        if str(item).strip()
    }
    required_networks_by_service = _normalize_service_str_map(policy.get("required_networks_by_service"))
    required_published_ports_by_service = _normalize_service_int_map(
        policy.get("required_published_ports_by_service")
    )

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
            if network in allowed_extra_networks:
                continue
            non_namespaced_networks[network].append(container_name)

        bindings = _published_bindings(info)
        if bindings:
            for _, host_ip, host_port in bindings:
                host_bindings[f"{host_ip}:{host_port}"].append(container_name)
            service_for_publish = service or ""
            has_external = any(
                any(net.endswith(suffix) for suffix in external_network_suffixes)
                for net in networks
            ) or any(net in external_network_names for net in networks)
            if (
                published_requires_external
                and service_for_publish not in published_external_exceptions
                and not has_external
            ):
                published_without_external.append(container_name)

        service_name = service or ""
        required_networks = required_networks_by_service.get(service_name, [])
        missing_networks = [network for network in required_networks if network not in networks]
        if missing_networks:
            errors.append(
                f"{container_name} missing required networks from policy: {', '.join(missing_networks)}"
            )

        required_ports = required_published_ports_by_service.get(service_name, [])
        missing_ports = [str(port) for port in required_ports if not _ports_published(info, port)]
        if missing_ports:
            errors.append(
                f"{container_name} missing required published container ports from policy: {', '.join(missing_ports)}"
            )

        env = _env_map(info)
        for key in critical_url_keys:
            value = env.get(key)
            if not value:
                continue
            host = _extract_host(value)
            allowed_keys = loopback_exception_keys_by_service.get(service_name, set())
            if host in LOOPBACK_HOSTS and key not in allowed_keys:
                critical_loopback[(key, value)].append(container_name)

        nats_url = env.get("NATS_URL")
        if nats_url:
            host = _extract_host(nats_url)
            if host in LOOPBACK_HOSTS:
                errors.append(f"{container_name} uses loopback NATS_URL ({nats_url})")
            if require_nats_auth and service_name not in nats_auth_exceptions and not _url_has_auth(nats_url):
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
    archon_hit = _find_container_by_service(inspections, "archon")

    if not archon_hit:
        errors.append("archon container is not running")
        return

    archon, archon_info = archon_hit

    if not _ports_published(archon_info, 8091):
        errors.append(f"{archon} is missing host publish for 8091/tcp")

    # UI port 3737 is host-side; check via _published_host_port (not container port)
    ui_host_port = _published_host_port(archon_info, 3737) or "3737"

    api_host_port = _published_host_port(archon_info, 8091) or "8091"
    api_url = f"http://localhost:{api_host_port}/healthz"
    archon_code = _http_code(api_url, retries=2, delay_s=1.0)
    if archon_code != 200:
        errors.append(f"archon API health check failed: {api_url} => {archon_code}")

    ui_url = f"http://localhost:{ui_host_port}/"
    ui_code = _http_code(ui_url, retries=6, delay_s=2.0)
    if ui_code != 200:
        errors.append(f"archon UI health check failed: {ui_url} => {ui_code}")


def _check_chit_sync(
    inspections: Mapping[str, Mapping[str, object]],
    policy: Mapping[str, object],
    *,
    warnings: List[str],
    errors: List[str],
) -> None:
    sync_ok, sync_message = _check_manifest_sync()
    if not sync_ok:
        errors.append("CHIT manifest v1/v2 sync check failed")
        if sync_message:
            warnings.append(sync_message)

    required_services = {
        str(item).strip()
        for item in (policy.get("chit_required_services") or [])
        if str(item).strip()
    }
    if not required_services:
        warnings.append("no chit_required_services configured in topology policy; skipping CHIT env checks")
        return

    matched: List[str] = []
    for container_name, info in inspections.items():
        service = _compose_service_name(info) or ""
        if service in required_services:
            matched.append(container_name)

    if not matched:
        warnings.append("no CHIT-required containers found for env propagation checks")
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
        "--policy",
        default=str(DEFAULT_POLICY_PATH),
        help=f"topology policy manifest path (default: {DEFAULT_POLICY_PATH.as_posix()})",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as failures (recommended for production gates)",
    )
    args = parser.parse_args(argv)

    warnings: List[str] = []
    errors: List[str] = []
    policy = _load_policy(Path(args.policy), args.project, warnings=warnings)

    container_names = _docker_ps(args.project)
    inspections = _docker_inspect_many(container_names)

    policy_project = str(policy.get("project") or args.project)
    if policy_project != args.project:
        warnings.append(
            f"topology policy project '{policy_project}' differs from '--project {args.project}'"
        )

    _check_project_topology(args.project, inspections, policy, warnings=warnings, errors=errors)
    _check_archon_topology(inspections, warnings=warnings, errors=errors)
    _check_chit_sync(inspections, policy, warnings=warnings, errors=errors)

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
