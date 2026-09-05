#!/usr/bin/env python3
"""Hydrate runtime-emitted secrets into env files after services start."""

from __future__ import annotations

import argparse
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pmoves.tools._secrets_common import (
    PROJECT_ROOT,
    is_placeholder as _looks_placeholder,
    parse_env_file as _parse_env_file,
)

DEFAULT_ENV_FILE = PROJECT_ROOT / "env.shared"
DEFAULT_STATUS_FILE = PROJECT_ROOT / ".supabase.status.env"


def _write_env_file(path: Path, updates: Mapping[str, str]) -> None:
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
    path.write_text(text, encoding="utf-8")


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
            if value and not _looks_placeholder(value):
                return value
    return ""


def _masked(value: str) -> str:
    if len(value) < 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"



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
    set_if_missing(
        "MEILI_MASTER_KEY",
        _find_container_env_value(
            containers, name_tokens=("meili",), keys=("MEILI_MASTER_KEY", "MEILI_ENV")
        )
        or env_values.get("MEILI_MASTER_KEY", "").strip()
        or secrets.token_urlsafe(24),
    )
    set_if_missing(
        "FIREFLY_APP_KEY",
        _find_container_env_value(
            containers, name_tokens=("firefly", "wealth"), keys=("FIREFLY_APP_KEY", "APP_KEY")
        )
        or env_values.get("FIREFLY_ACCESS_TOKEN", "").strip()
        or secrets.token_urlsafe(24),
    )
    set_if_missing(
        "AGENT_ZERO_EVENTS_TOKEN",
        _find_container_env_value(
            containers, name_tokens=("agent-zero", "agent0"), keys=("AGENT_ZERO_EVENTS_TOKEN",)
        )
        or secrets.token_urlsafe(32),
    )

    # Core credentials that the running containers already hold. These are the
    # values a recreate MUST reproduce, so there is deliberately NO random
    # fallback here: a minted value would not match the live Postgres / MinIO /
    # Neo4j / ClickHouse and would turn a placeholder into a wrong password.
    # Container-only; if no container carries the key, the placeholder stays and
    # auth-alignment keeps flagging it. Recovery Known Road for the 2026-09-05
    # incident where the shared env file carried template placeholders for all
    # of these while the fleet ran on real values baked at container creation.
    def _container_only(name_tokens: Sequence[str], keys: Sequence[str]) -> str:
        return _find_container_env_value(containers, name_tokens=name_tokens, keys=keys)

    pg_password = _container_only(("supabase-db", "supabase_db"), ("POSTGRES_PASSWORD", "PGPASSWORD"))
    for key in ("POSTGRES_PASSWORD", "SUPABASE_DB_PASSWORD", "SERVICE_PASSWORD_POSTGRES"):
        set_if_missing(key, pg_password)

    minio_user = _container_only(("minio",), ("MINIO_ROOT_USER", "MINIO_ACCESS_KEY"))
    minio_password = _container_only(("minio",), ("MINIO_ROOT_PASSWORD", "MINIO_SECRET_KEY"))
    for key in ("MINIO_ROOT_USER", "MINIO_USER", "MINIO_ACCESS_KEY"):
        set_if_missing(key, minio_user)
    for key in ("MINIO_ROOT_PASSWORD", "MINIO_PASSWORD", "MINIO_SECRET_KEY"):
        set_if_missing(key, minio_password)

    neo4j_auth = _container_only(("neo4j",), ("NEO4J_AUTH",))
    if neo4j_auth and "/" in neo4j_auth:
        set_if_missing("NEO4J_AUTH", neo4j_auth)
        set_if_missing("NEO4J_PASSWORD", neo4j_auth.split("/", 1)[1])
    else:
        set_if_missing("NEO4J_PASSWORD", _container_only(("neo4j",), ("NEO4J_PASSWORD",)))

    set_if_missing(
        "TENSORZERO_CLICKHOUSE_USER",
        _container_only(("tensorzero-clickhouse", "clickhouse"), ("CLICKHOUSE_USER",)),
    )
    set_if_missing(
        "TENSORZERO_CLICKHOUSE_PASSWORD",
        _container_only(("tensorzero-clickhouse", "clickhouse"), ("CLICKHOUSE_PASSWORD",)),
    )
    set_if_missing("PG_META_CRYPTO_KEY", _container_only(("supabase-meta", "meta"), ("CRYPTO_KEY", "PG_META_CRYPTO_KEY")))
    set_if_missing(
        "LOGFLARE_PRIVATE_ACCESS_TOKEN",
        _container_only(("supabase-analytics", "logflare"), ("LOGFLARE_PRIVATE_ACCESS_TOKEN", "LOGFLARE_API_KEY")),
    )
    set_if_missing(
        "LOGFLARE_PUBLIC_ACCESS_TOKEN",
        _container_only(("supabase-analytics", "logflare"), ("LOGFLARE_PUBLIC_ACCESS_TOKEN",)),
    )

    # Invidious companion key: must be exactly 16 alphanumeric characters.
    # The Invidious companion rejects keys that are not 16 hex chars.
    set_if_missing(
        "INVIDIOUS_COMPANION_KEY",
        _find_container_env_value(
            containers, name_tokens=("invidious",), keys=("INVIDIOUS_COMPANION_KEY", "SERVER_SECRET_KEY")
        )
        or secrets.token_hex(8),  # 8 bytes = 16 hex chars
    )

    return updates


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE, help="env file to update")
    parser.add_argument(
        "--status-file",
        type=Path,
        default=DEFAULT_STATUS_FILE,
        help="Supabase status env snapshot (from make supa-status)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the masked hydration plan without writing the env file",
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

    if args.dry_run:
        print(f"DRY RUN: {len(updates)} runtime label(s) would be hydrated into {env_file.name}:")
        for key in sorted(updates):
            print(f"  - {key}={_masked(updates[key])}")
        return 0

    _write_env_file(env_file, updates)
    print(f"Hydrated {len(updates)} runtime labels into {env_file}:")
    for key in sorted(updates):
        print(f"  - {key}={_masked(updates[key])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
