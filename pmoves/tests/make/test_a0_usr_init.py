"""agent-zero-usr-init: the A0 usr bind mount is handed to uid 65532, by ownership only.

Why: the A0 image runs as 65532 (services/agent-zero/Dockerfile `USER pmoves`,
docker-compose.hardened.yml `user: "65532:65532"`) while the host seeds the
bind-mounted usr tree as uid 1000. Docker does not change a bind mount's
ownership, so every plugin install and settings save failed with EACCES behind a
green healthcheck (Knuckles, 2026-10-01).

PR #3256 answered with `chmod -R a+rwX ... || true` in the up-agents recipe. Its
review (5390245207) found that it turns A0's 0600 OAuth token files 0666, makes
plugin code world-writable, cannot fail, and runs on one up path of several. The
`pr3256` implementation below is that recipe verbatim; its cases are strict
xfails, so this file records the failing-before control and would go red if the
old approach ever started passing them.

The behaviour tests run the real script as the current user with A0_USR_UID set
to the caller's own uid, so the ownership change succeeds without root. A
real-container run as root with only CAP_CHOWN + DAC_READ_SEARCH is recorded in
the PR description.
"""
from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

PMOVES = Path(__file__).resolve().parents[2]
SCRIPT = PMOVES / "scripts" / "a0_usr_init.sh"

# The recipe from #3256 (pmoves/Makefile a0-usr-perms), with the hardcoded
# data/agent-zero/usr prefix replaced by the tree under test.
PR3256 = (
    'for d in agents api knowledge plugins; do '
    'dir="$A0_USR_DIR/$d"; '
    'if [ -d "$dir" ]; then chmod -R a+rwX "$dir" || true; fi; '
    'done'
)


def run_init(tree: Path, impl: str, uid: int | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ, A0_USR_DIR=str(tree))
    env["A0_USR_UID"] = str(os.getuid() if uid is None else uid)
    env["A0_USR_GID"] = str(os.getgid())
    cmd = ["sh", str(SCRIPT)] if impl == "init" else ["sh", "-c", PR3256]
    return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)


def seed(tmp_path: Path) -> Path:
    """A usr tree shaped like the live one: plugins with code and a 0600 token."""
    usr = tmp_path / "usr"
    (usr / "plugins" / "_oauth" / "codex").mkdir(parents=True)
    (usr / "plugins" / "pmoves_notes" / "tools").mkdir(parents=True)
    auth = usr / "plugins" / "_oauth" / "codex" / "auth.json"
    auth.write_text("{}\n")
    auth.chmod(0o600)
    code = usr / "plugins" / "pmoves_notes" / "tools" / "notes.py"
    code.write_text("pass\n")
    code.chmod(0o644)
    for d in (usr, usr / "plugins", usr / "plugins" / "pmoves_notes", usr / "plugins" / "pmoves_notes" / "tools"):
        d.chmod(0o755)
    return usr


def modes(tree: Path) -> dict[str, int]:
    return {str(p.relative_to(tree)): stat.S_IMODE(p.lstat().st_mode) for p in [tree, *tree.rglob("*")]}


IMPLS = [
    "init",
    pytest.param("pr3256", marks=pytest.mark.xfail(strict=True, reason="#3256 chmod -R a+rwX widens modes")),
]


@pytest.mark.parametrize("impl", IMPLS)
def test_oauth_token_stays_0600(tmp_path, impl):
    usr = seed(tmp_path)
    r = run_init(usr, impl)
    assert r.returncode == 0, r.stderr
    auth = usr / "plugins" / "_oauth" / "codex" / "auth.json"
    assert stat.S_IMODE(auth.stat().st_mode) == 0o600


@pytest.mark.parametrize("impl", IMPLS)
def test_plugin_code_is_not_world_writable(tmp_path, impl):
    usr = seed(tmp_path)
    run_init(usr, impl)
    writable = [p for p in usr.rglob("*.py") if p.stat().st_mode & stat.S_IWOTH]
    assert writable == []


def test_no_mode_bit_changes_anywhere(tmp_path):
    usr = seed(tmp_path)
    before = modes(usr)
    assert run_init(usr, "init").returncode == 0
    assert modes(usr) == before


@pytest.mark.parametrize("impl", IMPLS)
def test_missing_usr_dir_fails_loudly(tmp_path, impl):
    r = run_init(tmp_path / "absent", impl)
    assert r.returncode != 0
    if impl == "init":
        assert "AGENT_ZERO_USR_DIR" in r.stderr


@pytest.mark.skipif(os.getuid() == 0, reason="root may hand files to any uid")
def test_an_ownership_failure_propagates_nonzero(tmp_path):
    usr = seed(tmp_path)
    r = run_init(usr, "init", uid=os.getuid() + 1)
    assert r.returncode != 0


def test_symlinked_usr_dir_is_refused(tmp_path):
    real = seed(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    r = run_init(link, "init")
    assert r.returncode != 0 and "not a directory" in r.stderr


def test_script_never_changes_modes_and_never_swallows_errors():
    body = [l for l in SCRIPT.read_text().splitlines() if not l.lstrip().startswith("#")]
    assert not any(re.search(r"\bchmod\b", l) for l in body)
    assert not any("|| true" in l for l in body)
    assert "set -eu" in body


# --- every up path invokes the mechanism -----------------------------------

COMPOSE_A0 = {
    "docker-compose.yml": ("agent-zero", "agent-zero-usr-init", "${AGENT_ZERO_USR_DIR:-./data/agent-zero/usr}"),
    "docker-compose.agents.yml": ("agent-zero", "agent-zero-usr-init", "${AGENT_ZERO_USR_DIR:-./data/agent-zero/usr}"),
    "docker-compose.darkxside-sidecar.yml": ("agent-zero-darkxside", "agent-zero-darkxside-usr-init", "${DARKXSIDE_USR_DIR:-./usr}"),
    "docker-compose.spark-sidecar.yml": ("agent-zero-spark", "agent-zero-spark-usr-init", "${SPARK_USR_DIR:-./usr}"),
}


class ComposeLoader(yaml.SafeLoader):
    """SafeLoader that reads compose's merge tags (!override, !reset) as plain nodes."""


def _untagged(loader, suffix, node):
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_scalar(node)


ComposeLoader.add_multi_constructor("!", _untagged)


def compose(path: Path) -> dict:
    return yaml.load(path.read_text(), Loader=ComposeLoader) or {}


def load(name):
    return compose(PMOVES / name)["services"]


def test_every_compose_service_mounting_a0_usr_is_covered():
    """A new A0 service that mounts /a0/usr must join COMPOSE_A0, or this fails."""
    found = set()
    for f in PMOVES.glob("docker-compose*.yml"):
        for name, svc in (compose(f).get("services") or {}).items():
            vols = [v for v in (svc or {}).get("volumes") or [] if isinstance(v, str)]
            if any(v.split(":")[1:2] == ["/a0/usr"] or v.rsplit(":", 1)[-1] == "/a0/usr" for v in vols) and not name.endswith("usr-init"):
                found.add((f.name, name))
    assert found == {(f, svc) for f, (svc, _, _) in COMPOSE_A0.items()}


@pytest.mark.parametrize("fname", sorted(COMPOSE_A0))
def test_a0_depends_on_the_init_and_both_mount_the_same_tree(fname):
    svc, init, usr = COMPOSE_A0[fname]
    services = load(fname)
    assert services[svc]["depends_on"][init]["condition"] == "service_completed_successfully"
    i = services[init]
    assert f"{usr}:/a0/usr" in i["volumes"] and f"{usr}:/a0/usr" in services[svc]["volumes"]
    assert "./scripts/a0_usr_init.sh:/scripts/a0_usr_init.sh:ro" in i["volumes"]
    assert i["entrypoint"] == ["/bin/sh", "/scripts/a0_usr_init.sh"]
    assert i["cap_drop"] == ["ALL"] and sorted(i["cap_add"]) == ["CHOWN", "DAC_READ_SEARCH"]
    assert i["restart"] == "no" and i["network_mode"] == "none" and i["read_only"] is True
    assert "@sha256:" in i["image"]


@pytest.mark.parametrize("overlay", ["docker-compose.hardened.yml", "docker-compose.agents.images.yml", "docker-compose.agents.integrations.yml"])
def test_no_overlay_on_an_up_path_drops_agent_zero_depends_on(overlay):
    raw = (PMOVES / overlay).read_text()
    block = re.search(r"^  agent-zero:\n((?:    .*\n|\n)*)", raw, re.M)
    assert block is None or "depends_on" not in block.group(1)


def recipes():
    out = {}
    for f in [PMOVES / "Makefile", *sorted((PMOVES / "mk").glob("*.mk"))]:
        tgt = None
        for line in f.read_text().splitlines():
            m = re.match(r"^([A-Za-z0-9_.%/-]+)\s*:(?!=)", line)
            if m:
                tgt = (f.name, m.group(1))
                continue
            if tgt and line.startswith("\t") and not line.lstrip("\t@").startswith("#"):
                out.setdefault(tgt, []).append(line)
    return out


def test_every_recipe_that_skips_depends_on_runs_the_init():
    """--no-deps and `start` bypass depends_on; each such road for agent-zero must run A0_USR_INIT."""
    bypass = {}
    for tgt, lines in recipes().items():
        body = "\n".join(lines)
        if not re.search(r"\$\(DC\)", body):
            continue
        if not re.search(r"--no-deps|\$\(A0_ARCHON_UP\)|\$\(DC\) start\b", body):
            continue
        if re.search(r"agent-zero\b(?!-)|\$\(SVC\)", body):
            bypass[tgt] = "A0_USR_INIT" in body
    assert ("Makefile", "up-a0-archon-scoped") in bypass and ("infra.mk", "svc-start") in bypass, bypass
    assert {t for t, ok in bypass.items() if not ok} == set()


def plan(env, target, *args):
    env = dict(env)
    for k in ("CIPHER_API_TOKEN", "SERVICES", "DRY_RUN", "SVC"):
        env.pop(k, None)
    r = subprocess.run(["make", "-n", "--no-print-directory", "-C", str(PMOVES), target, *args],
                       env=env, capture_output=True, text=True, timeout=120)
    return r, r.stdout.splitlines()


def index(lines, pred):
    hits = [i for i, l in enumerate(lines) if pred(l)]
    assert len(hits) == 1, lines
    return hits[0]


@pytest.mark.parametrize("target,args", [
    ("up-a0-archon-scoped", ()),
    ("up-a0-archon-scoped", ("SERVICES=agent-zero",)),
    ("recreate-svc", ("SVC=agent-zero",)),
    ("supa-recreate-svc", ("SVC=agent-zero",)),
    ("svc-start", ("SVC=agent-zero",)),
])
def test_init_runs_before_agent_zero_on_bypass_roads(stub_docker_path, target, args):
    r, lines = plan(stub_docker_path, target, *args)
    assert r.returncode == 0, r.stderr
    init = index(lines, lambda l: l.rstrip().endswith("run --rm --no-deps agent-zero-usr-init"))
    a0 = index(lines, lambda l: re.search(r"( up -d .*| start )agent-zero\b(?!-)", l) is not None)
    assert init < a0


def test_scoped_dry_run_reaches_the_init(stub_docker_path):
    r, lines = plan(stub_docker_path, "up-a0-archon-scoped", "SERVICES=agent-zero", "DRY_RUN=1")
    init = [l for l in lines if l.rstrip().endswith("agent-zero-usr-init")]
    assert len(init) == 1 and "--dry-run run --rm" in init[0]


@pytest.mark.parametrize("target,args", [("up-a0-archon-scoped", ("SERVICES=archon",)), ("recreate-svc", ("SVC=archon",))])
def test_init_is_not_run_for_other_services(stub_docker_path, target, args):
    r, lines = plan(stub_docker_path, target, *args)
    assert not any("agent-zero-usr-init" in l for l in lines)


def test_operator_road_runs_only_the_init(stub_docker_path):
    r, lines = plan(stub_docker_path, "a0-usr-init")
    assert r.returncode == 0, r.stderr
    assert [l for l in lines if "docker compose" in l or "docker-compose" in l] == [lines[index(lines, lambda l: l.rstrip().endswith("run --rm --no-deps agent-zero-usr-init"))]]
