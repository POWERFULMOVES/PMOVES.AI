"""up-a0-archon-scoped: archon is always recreated with --force-recreate -V.

Why: on B850 (2026-09-28) recreating the retired Python archon container as the
native image crash-looped, because compose carried the old container's named
volume over the tmpfs docker-compose.yml declares at /home/appuser. Only
`--force-recreate --renew-anon-volumes` restored the tmpfs. That fix must live in
the target, not in whoever remembers the flags.

`make -n` under the stub_docker_path fixture: the recipe has no $(MAKE), so
nothing runs; docker/compose resolve to recorders regardless.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[2]


def plan(env, *args):
    env = dict(env)
    env.pop("CIPHER_API_TOKEN", None)
    env.pop("SERVICES", None)
    env.pop("DRY_RUN", None)
    r = subprocess.run(
        ["make", "-n", "--no-print-directory", "-C", str(PMOVES), "up-a0-archon-scoped", *args],
        env=env, capture_output=True, text=True, timeout=120,
    )
    lines = [l for l in r.stdout.splitlines() if " up -d " in l]
    return r, lines


def line_for(lines, service):
    hits = [l for l in lines if l.rstrip().endswith(f" {service}")]
    assert len(hits) == 1, lines
    return hits[0]


def test_archon_gets_force_recreate_and_renew_anon_volumes(stub_docker_path):
    r, lines = plan(stub_docker_path)
    assert r.returncode == 0, r.stderr
    archon = line_for(lines, "archon")
    assert "--force-recreate" in archon and "--renew-anon-volumes" in archon
    for flag in ("--no-deps", "--no-build", "--pull never", "-p pmoves"):
        assert flag in archon


def test_agent_zero_is_recreated_without_volume_renewal(stub_docker_path):
    r, lines = plan(stub_docker_path)
    a0 = line_for(lines, "agent-zero")
    assert "--renew-anon-volumes" not in a0 and "--force-recreate" not in a0
    assert "--no-deps" in a0 and "--pull never" in a0


def test_narrowing_to_archon_keeps_the_flags(stub_docker_path):
    r, lines = plan(stub_docker_path, "SERVICES=archon")
    assert len(lines) == 1
    assert "--renew-anon-volumes" in line_for(lines, "archon")


@pytest.mark.parametrize("dry,expect", [("1", True), ("0", False), ("false", False)])
def test_dry_run_switch(stub_docker_path, dry, expect):
    r, lines = plan(stub_docker_path, f"DRY_RUN={dry}")
    assert all(("--dry-run" in l) is expect for l in lines) and lines


@pytest.mark.parametrize("bad", ["supabase-db", "archon;id", "archon --pull=always"])
def test_services_outside_the_allowlist_are_refused(stub_docker_path, bad):
    r, lines = plan(stub_docker_path, f"SERVICES={bad}")
    assert r.returncode != 0 and "SERVICES may only name" in r.stderr
    assert lines == []
