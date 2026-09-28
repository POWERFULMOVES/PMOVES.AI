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
    hits = [l for l in lines if l.rstrip().rstrip(";\\ ").endswith(f" {service}")]
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


def test_archon_recreate_is_preceded_by_the_gated_label_preflight(stub_docker_path):
    r, _ = plan(stub_docker_path, "SERVICES=archon")
    out = r.stdout
    assert "config --images archon" in out
    pre = out.index("archon_release_channel.sh verify-current")
    assert pre < out.index("--renew-anon-volumes archon")


def test_archon_follow_pulls_the_channel_then_verifies_then_recreates(stub_docker_path):
    env = dict(stub_docker_path)
    env.pop("CIPHER_API_TOKEN", None)
    r = subprocess.run(["make", "-n", "--no-print-directory", "-C", str(PMOVES), "archon-follow"],
                       env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    i_pull = out.index('docker pull "$img"')
    i_verify = out.index('verify-current "$img"')
    i_up = out.index("--renew-anon-volumes archon")
    assert i_pull < i_verify < i_up
    assert "--pull never" in out  # the recreate itself stays offline; the pull is explicit


# ---- ungated builds never wear the :current channel tag --------------------

MAKEFILE = PMOVES / "Makefile"


def _recipe_lines():
    return [l for l in MAKEFILE.read_text().splitlines() if l.startswith("\t")]


def test_every_recipe_that_builds_archon_uses_the_local_build_tag():
    import re
    builds = [
        l for l in _recipe_lines()
        if "$(DC)" in l and "archon" in l and re.search(r"(--build\b|\sbuild\s)", l)
    ]
    assert len(builds) >= 3, builds  # up-agents-stack, archon-rebuild, build-agents-integrations
    for l in builds:
        assert "$(ARCHON_UNGATED)" in l, l


@pytest.mark.parametrize("target", ["archon-rebuild", "build-agents-integrations"])
def test_build_recipes_render_a_non_channel_tag(stub_docker_path, target):
    env = dict(stub_docker_path)
    env.pop("CIPHER_API_TOKEN", None)
    env.pop("ARCHON_IMAGE", None)
    r = subprocess.run(["make", "-n", "--no-print-directory", "-C", str(PMOVES), target],
                       env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    build = [l for l in r.stdout.splitlines() if " build " in l]
    assert build and all("ARCHON_IMAGE=pmoves-archon:local-build" in l for l in build)
    assert ":current" not in r.stdout
