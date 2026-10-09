"""JuiceFS compose services must not put credentials on the command line.

A DSN or --secret-key in a container's command is visible to every local user
through `ps` on the host (measured on a running juicefs-gateway). JuiceFS reads
META_PASSWORD, ACCESS_KEY and SECRET_KEY from the environment instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PMOVES = Path(__file__).resolve().parents[2]
FILES = ("docker-compose.yml", "docker-compose.juicefs.yml")
SECRET_REFS = ("${SUPABASE_DB_PASSWORD}", "${MINIO_PASSWORD}", "${JUICEFS_S3_PASSWORD")
ARGV_FLAGS = ("--secret-key", "--access-key")


def _services(name: str) -> dict:
    return yaml.safe_load((PMOVES / name).read_text(encoding="utf-8"))["services"]


def _argv(svc: dict) -> str:
    parts = []
    for key in ("entrypoint", "command"):
        v = svc.get(key) or []
        parts.extend(v if isinstance(v, list) else [v])
    return "\n".join(str(p) for p in parts)


def _env(svc: dict) -> dict:
    env = svc.get("environment") or {}
    if isinstance(env, list):
        env = dict(e.split("=", 1) for e in env if "=" in e)
    return env


@pytest.mark.parametrize("name", FILES)
@pytest.mark.parametrize("service", ["juicefs-format", "juicefs-gateway"])
def test_no_credentials_in_argv(name, service):
    argv = _argv(_services(name)[service])
    for ref in SECRET_REFS:
        assert ref not in argv, f"{name}:{service} interpolates {ref} into its command line"
    for flag in ARGV_FLAGS:
        assert flag not in argv, f"{name}:{service} passes {flag} on its command line"


@pytest.mark.parametrize("name", FILES)
@pytest.mark.parametrize("service", ["juicefs-format", "juicefs-gateway"])
def test_metadata_password_comes_from_env(name, service):
    assert "META_PASSWORD" in _env(_services(name)[service])


@pytest.mark.parametrize("name", FILES)
def test_format_object_store_keys_come_from_env(name):
    env = _env(_services(name)["juicefs-format"])
    assert "ACCESS_KEY" in env and "SECRET_KEY" in env
