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


def _archon_build_targets(text: str) -> set[str]:
    """Targets whose recipe BUILDS archon through $(DC)."""
    import re
    found, target = set(), None
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+):(?!=)", line)
        if m:
            target = m.group(1)
        elif line.startswith("\t") and target and "$(DC)" in line and "archon" in line \
                and re.search(r"(--build\b|\sbuild\s)", line):
            found.add(target)
    return found


def _exported_build_targets(text: str) -> set[str]:
    import re
    m = re.search(r"^ARCHON_BUILD_TARGETS\s*:=\s*(.+)$", text, re.M)
    ok = re.search(r"^\$\(ARCHON_BUILD_TARGETS\):\s*export override ARCHON_IMAGE = \$\(ARCHON_LOCAL_BUILD_IMAGE\)$", text, re.M)
    return set(m.group(1).split()) if (m and ok) else set()


def test_every_target_that_builds_archon_exports_the_local_build_tag():
    text = MAKEFILE.read_text()
    builds = _archon_build_targets(text)
    assert {"up-agents-stack", "archon-rebuild", "build-agents-integrations"} <= builds, builds
    assert builds <= _exported_build_targets(text), builds - _exported_build_targets(text)


def test_recipe_lines_carry_no_image_prefix_in_front_of_dc():
    # The cipher-token guard pins the rendered $(DC) shape; the image must come
    # from a target-specific export, never a line prefix.
    for l in _recipe_lines():
        if "$(DC)" in l:
            assert "ARCHON_IMAGE=" not in l.split("$(DC)")[0], l


PROBE = ["--eval", 'zz-probe: ; +@echo "AI=[$$ARCHON_IMAGE]"']


def _probe(env, target, *extra):
    env = dict(env)
    for k in ("CIPHER_API_TOKEN", "ARCHON_IMAGE", "SERVICES", "DRY_RUN"):
        env.pop(k, None)
    r = subprocess.run(["make", "-k", "-n", "-s", "--no-print-directory", "-C", str(PMOVES), *PROBE,
                        "--eval", f"{target}: zz-probe", target, *extra],
                       env=env, capture_output=True, text=True, timeout=120)
    return sorted({l for l in r.stdout.splitlines() if l.startswith("AI=")})


@pytest.mark.parametrize("target", ["up-agents-stack", "archon-rebuild", "build-agents-integrations"])
def test_build_targets_run_with_the_local_build_image(stub_docker_path, target):
    assert _probe(stub_docker_path, target) == ["AI=[pmoves-archon:local-build]"]


def test_command_line_current_cannot_reach_a_build(stub_docker_path):
    got = _probe(stub_docker_path, "archon-rebuild", "ARCHON_IMAGE=ghcr.io/powerfulmoves/pmoves-archon:current")
    assert got == ["AI=[pmoves-archon:local-build]"]


@pytest.mark.parametrize("target", ["up-a0-archon-scoped", "archon-follow", "cipher-build-pin-check", "qdrant-provision-cipher"])
def test_the_export_does_not_leak_into_non_build_paths(stub_docker_path, target):
    assert _probe(stub_docker_path, target) == ["AI=[]"]


def test_build_recipes_render_no_channel_tag(stub_docker_path):
    env = dict(stub_docker_path)
    for k in ("CIPHER_API_TOKEN", "ARCHON_IMAGE"):
        env.pop(k, None)
    for target in ("archon-rebuild", "build-agents-integrations"):
        r = subprocess.run(["make", "-n", "--no-print-directory", "-C", str(PMOVES), target],
                           env=env, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr
        assert ":current" not in r.stdout
