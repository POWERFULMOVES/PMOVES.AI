#!/usr/bin/env python3
"""Hydrate runtime-emitted secrets into env files after services start."""

from __future__ import annotations

import argparse
import logging
import os
import secrets
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Sequence
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / "env.shared"
DEFAULT_STATUS_FILE = PROJECT_ROOT / ".supabase.status.env"
LOG = logging.getLogger("runtime_secrets_hydrate")


def _parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip()
    return values


def _write_env_file(path: Path, updates: Mapping[str, str]) -> None:
    if not updates:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines() if path.exists() else []

    index: Dict[str, int] = {}
    for idx, raw in enumerate(lines):
        if not raw or raw.lstrip().startswith("#") or "=" not in raw:
            continue
        key, _ = raw.split("=", 1)
        index[key.strip()] = idx

    for key, value in updates.items():
        entry = f"{key}={value}"
        if key in index:
            lines[index[key]] = entry
        else:
            lines.append(entry)

    text = "\n".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        delete=False,
        newline="",
    ) as handle:
        handle.write(text)
        tmp_name = handle.name
    os.replace(tmp_name, path)


def _run(cmd: Sequence[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _docker_list_containers() -> List[str]:
    output = _run(["docker", "ps", "--format", "{{.Names}}"])
    if not output:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _docker_env(container: str) -> Dict[str, str]:
    output = _run(
        ["docker", "inspect", "--format", "{{range .Config.Env}}{{println .}}{{end}}", container]
    )
    envs: Dict[str, str] = {}
    if not output:
        return envs
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        envs[key] = value
    return envs


def _find_container_env_value(
    containers: Sequence[str],
    *,
    name_tokens: Sequence[str],
    keys: Sequence[str],
) -> str:
    lower_tokens = tuple(token.lower() for token in name_tokens)
    for container in containers:
        container_l = container.lower()
        if not any(token in container_l for token in lower_tokens):
            continue
        envs = _docker_env(container)
        for key in keys:
            value = envs.get(key, "").strip()
            if value:
                return value
    return ""


def _masked(value: str) -> str:
    if len(value) < 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _looks_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    if "@" in lowered:
        domain = lowered.split("@", 1)[1]
        if domain == "example.com" or domain.endswith(".example.com"):
            return True

    parsed = urlparse(lowered if "://" in lowered else f"https://{lowered}")
    host = (parsed.hostname or "").strip().lower()

    return (
        lowered.startswith("placeholder_")
        or lowered.startswith("your_")
        or lowered in {"changeme", "change_me", "none", "null"}
        or host == "example.com"
        or host.endswith(".example.com")
    )


def _sanitize_secret_candidate(value: str | None) -> str:
    candidate = (value or "").strip()
    if not candidate or _looks_placeholder(candidate):
        return ""
    return candidate


def _resolve_secret_candidate(*values: str, generator_len: int) -> tuple[str, bool]:
    for value in values:
        candidate = _sanitize_secret_candidate(value)
        if candidate:
            return candidate, False
    return secrets.token_urlsafe(generator_len), True


def hydrate_runtime_labels(
    env_values: Dict[str, str],
    *,
    status_values: Mapping[str, str],
    containers: Sequence[str],
) -> Dict[str, str]:
    updates: Dict[str, str] = {}

    def set_if_missing(key: str, value: str) -> None:
        if not value:
            return
        current = env_values.get(key, "").strip()
        if current and not _looks_placeholder(current):
            return
        env_values[key] = value
        updates[key] = value

    # Supabase runtime aliases from status and existing env aliases.
    set_if_missing(
        "SUPABASE_SERVICE_KEY",
        status_values.get("SERVICE_ROLE_KEY", "").strip()
        or env_values.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or env_values.get("SERVICE_ROLE_KEY", "").strip(),
    )
    set_if_missing(
        "SUPABASE_REALTIME_KEY",
        status_values.get("ANON_KEY", "").strip()
        or env_values.get("SUPABASE_ANON_KEY", "").strip()
        or env_values.get("ANON_KEY", "").strip(),
    )
    set_if_missing(
        "SUPABASE_REALTIME_SECRET",
        status_values.get("JWT_SECRET", "").strip()
        or env_values.get("SUPABASE_JWT_SECRET", "").strip()
        or env_values.get("JWT_SECRET", "").strip(),
    )

    # Pull runtime-emitted labels from running containers when available.
    meili_value, meili_generated = _resolve_secret_candidate(
        _find_container_env_value(containers, name_tokens=("meili",), keys=("MEILI_MASTER_KEY", "MEILI_ENV")),
        env_values.get("MEILI_MASTER_KEY", ""),
        generator_len=24,
    )
    if meili_generated:
        LOG.warning(
            "[AUTO-GENERATED-PLACEHOLDER] generated placeholder for %s",
            "MEILI_MASTER_KEY",
        )
    set_if_missing("MEILI_MASTER_KEY", meili_value)
    firefly_value, firefly_generated = _resolve_secret_candidate(
        _find_container_env_value(
            containers, name_tokens=("firefly", "wealth"), keys=("FIREFLY_APP_KEY", "APP_KEY")
        ),
        env_values.get("FIREFLY_APP_KEY", ""),
        env_values.get("FIREFLY_ACCESS_TOKEN", ""),
        generator_len=24,
    )
    if firefly_generated:
        LOG.warning(
            "[AUTO-GENERATED-PLACEHOLDER] generated placeholder for %s",
            "FIREFLY_APP_KEY",
        )
    set_if_missing("FIREFLY_APP_KEY", firefly_value)
    agent_value, agent_generated = _resolve_secret_candidate(
        _find_container_env_value(
            containers, name_tokens=("agent-zero", "agent0"), keys=("AGENT_ZERO_EVENTS_TOKEN",)
        ),
        env_values.get("AGENT_ZERO_EVENTS_TOKEN", ""),
        generator_len=32,
    )
    if agent_generated:
        LOG.warning(
            "[AUTO-GENERATED-PLACEHOLDER] generated placeholder for %s",
            "AGENT_ZERO_EVENTS_TOKEN",
        )
    set_if_missing("AGENT_ZERO_EVENTS_TOKEN", agent_value)

    return updates


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE, help="env file to update")
    parser.add_argument(
        "--status-file",
        type=Path,
        default=DEFAULT_STATUS_FILE,
        help="Supabase status env snapshot (from make supa-status)",
    )
    args = parser.parse_args(argv)

    env_file = args.env_file.expanduser().resolve()
    status_file = args.status_file.expanduser().resolve()

    env_values = _parse_env_file(env_file)
    status_values = _parse_env_file(status_file)
    containers = _docker_list_containers()

    updates = hydrate_runtime_labels(env_values, status_values=status_values, containers=containers)
    if not updates:
        print("No runtime labels needed hydration.")
        return 0

    _write_env_file(env_file, updates)
    print(f"Hydrated {len(updates)} runtime labels into {env_file}:")
    for key in sorted(updates):
        print(f"  - {key}={_masked(updates[key])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
