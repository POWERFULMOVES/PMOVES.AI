"""The Neo4j make roads must exist, and must fail closed without a password.

Until 2026-10 seven `neo4j-*` targets called `make -C ../PMOVES-Neo4j ...` and read
../PMOVES-Neo4j/db/{migrations,seeds}. That submodule is the upstream neo4j/neo4j
source fork: no Makefile and no db/ on any branch, so every one of them failed.
`load-consciousness-neo4j` asked for a migration that never existed, and
`chit-mindmap-seed` read NEO4J_AUTH_PASSWORD (set nowhere), fell back to the
vendor default password `neo4j`, and put it on cypher-shell's argv.

These tests run the REAL Makefile against a stub `docker` that only records its
argv (build_stub_env, pmoves/tests/_destructive_docker_guard.py); nothing reaches
a real container. LOAD_ENV_SHARED is overridden to `:` so the developer's env
files are never read; the password is whatever the test puts in the env.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[1]
MAKEFILE = PMOVES / "Makefile"
DOCKER_GUARD_FILE = Path(__file__).with_name("_destructive_docker_guard.py")
DOCKER_GUARD_MODULE = "pmoves_tests_destructive_docker_guard"  # conftest's name
SENTINEL = "s3ntinel-not-a-real-password"

APPLY_TARGETS = ("chit-mindmap-seed", "load-consciousness-neo4j", "neo4j-migrate")


def _docker_guard():
    if DOCKER_GUARD_MODULE in sys.modules:
        return sys.modules[DOCKER_GUARD_MODULE]
    import importlib.util
    spec = importlib.util.spec_from_file_location(DOCKER_GUARD_MODULE, DOCKER_GUARD_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[DOCKER_GUARD_MODULE] = module
    spec.loader.exec_module(module)
    return module


def _make(tmp_path: Path, target: str, password: str | None, *extra: str):
    stub = _docker_guard().build_stub_env(tmp_path / "bin", stub_make=False)
    env = dict(stub)
    for k in ("NEO4J_PASSWORD", "NEO4J_AUTH", "NEO4J_AUTH_PASSWORD"):
        env.pop(k, None)
    if password is not None:
        env["NEO4J_PASSWORD"] = password
    proc = subprocess.run(
        ["make", "-s", "-C", str(PMOVES), target, "LOAD_ENV_SHARED=:", "PYTHON=python3", *extra],
        env=env, capture_output=True, text=True, timeout=120,
    )
    docker = [row[1:] for row in stub.calls() if row[0] == "docker"]
    return proc.returncode, docker, proc.stdout + proc.stderr


def test_no_target_calls_the_source_fork():
    text = MAKEFILE.read_text()
    assert "-C ../PMOVES-Neo4j" not in text
    assert "PMOVES-Neo4j/db/" not in text


def _target_block(text: str, target: str) -> str:
    block = text[text.index(f"\n{target}:") + 1:]
    return block[: block.index("\n\n")]


def test_no_neo4j_default_password_fallback():
    """The roads this file covers. neo4j-backup's `:-changeme` is the backup lane's (runbook item 3)."""
    text = MAKEFILE.read_text()
    assert "NEO4J_AUTH_PASSWORD" not in text
    macro = text[text.index("define neo4j_apply_cypher"): text.index("endef")]
    for block in [macro] + [_target_block(text, t) for t in APPLY_TARGETS]:
        # `${NEO4J_PASSWORD:-}` (empty, for set -u) is fine; a non-empty default is a fallback password
        assert not re.search(r"NEO4J_[A-Z_]*PASSWORD:-[^}]", block), block
        assert "-p " not in block.replace("-pl ", ""), block


def test_consciousness_schema_target_points_at_a_real_file():
    text = MAKEFILE.read_text()
    block = _target_block(text, "load-consciousness-neo4j")
    paths = re.findall(r"\$\(CURDIR\)/(\S+\.cypher)", block)
    assert paths, block
    for p in paths:
        assert (PMOVES / p).is_file(), p


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
@pytest.mark.parametrize("password", [None, ""], ids=["unset", "empty"])
@pytest.mark.parametrize("target", APPLY_TARGETS)
def test_unset_or_empty_password_fails_closed_before_docker(tmp_path, target, password):
    # "" matters: a guard weakened to set-only (${VAR+x}) passes an empty password through.
    rc, docker, out = _make(tmp_path, target, password, "VERSION=001")
    assert rc != 0, out
    assert "NEO4J_PASSWORD is unset or empty" in out, out
    assert docker == [], docker


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
@pytest.mark.parametrize("target", APPLY_TARGETS)
def test_password_goes_by_env_never_argv(tmp_path, target):
    rc, docker, out = _make(tmp_path, target, SENTINEL, "VERSION=001")
    assert rc == 0, out
    execs = [c for c in docker if c and c[0] == "exec"]
    assert len(execs) == 1, docker
    call = execs[0]
    assert "cypher-shell" in call
    pairs = [call[i + 1] for i, tok in enumerate(call[:-1]) if tok == "-e"]
    assert "NEO4J_PASSWORD" in pairs, call
    assert "-p" not in call and "--password" not in call, call
    assert all(SENTINEL not in tok for tok in call), call
    assert "pmoves-neo4j" in call  # the compose-declared name, via scripts/neo4j_container.py


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
def test_migrate_refuses_an_ambiguous_or_missing_version(tmp_path):
    rc, docker, out = _make(tmp_path, "neo4j-migrate", SENTINEL, "VERSION=999")
    assert rc != 0 and "matches 0 files" in out, out
    assert docker == []


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
def test_neo4j_up_never_recreates_before_the_compose_reconciliation(tmp_path):
    """Until PR #3251 lands, main's neo4j still has env_file + 0.0.0.0 ports; a plain
    `up -d` on any config-hash drift would recreate on that config."""
    rc, docker, out = _make(tmp_path, "neo4j-up", SENTINEL)
    assert rc == 0, out
    ups = [c for c in docker if "up" in c]
    assert len(ups) == 1, docker
    up = ups[0]
    assert up[up.index("up"):][-1] == "neo4j", up
    assert "--no-recreate" in up and "--force-recreate" not in up, up


# --- scripts/neo4j_bootstrap.sh (what neo4j-bootstrap runs) -----------------

BOOTSTRAP = PMOVES / "scripts" / "neo4j_bootstrap.sh"
CYPHER_DIR = PMOVES / "neo4j" / "cypher"
SMOKE = CYPHER_DIR / "011_chit_geometry_smoke.cypher"
SMOKE_OK = '"CHIT_SMOKE_OK", 1, 3, 3, 2'
# `ps` reports the container running. `exec -i` drains stdin as cypher-shell does
# (otherwise the alias-CSV pipe dies with EPIPE under pipefail), records it, one
# record per exec separated by \x1e, and answers the smoke file with $STUB_SMOKE_REPLY.
STUB_PS = ('if [ "$1" = "ps" ]; then echo pmoves-neo4j; fi\n'
           'if [ "$1" = "exec" ]; then in=$(cat); printf "%s\\036" "$in" >> "$(dirname "$0")/stdin.log";\n'
           '  case "$in" in *CHIT_SMOKE_OK*) printf "verdict, anchors, points, media_refs, modalities\\n%s\\n" "$STUB_SMOKE_REPLY";; esac; fi\n')


def _bootstrap(tmp_path: Path, password: str | None, smoke_reply: str = SMOKE_OK):
    stub = _docker_guard().build_stub_env(tmp_path / "bin", stub_make=False,
                                          behaviours={"docker": STUB_PS})
    env = dict(stub)
    for k in ("NEO4J_PASSWORD", "NEO4J_AUTH", "NEO4J_USERNAME"):
        env.pop(k, None)
    if password is not None:
        env["NEO4J_PASSWORD"] = password
    env["STUB_SMOKE_REPLY"] = smoke_reply
    proc = subprocess.run(["bash", str(BOOTSTRAP)], env=env, capture_output=True, text=True, timeout=120)
    docker = [row[1:] for row in stub.calls() if row[0] == "docker"]
    return proc.returncode, docker, proc.stdout + proc.stderr


def _piped(tmp_path: Path) -> list[str]:
    log = tmp_path / "bin" / "stdin.log"
    return log.read_text().split("\x1e")[:-1] if log.exists() else []


@pytest.mark.parametrize("password", [None, ""], ids=["unset", "empty"])
def test_bootstrap_fails_closed_before_docker(tmp_path, password):
    rc, docker, out = _bootstrap(tmp_path, password)
    assert rc != 0, out
    assert "NEO4J_PASSWORD is unset or empty" in out, out
    assert docker == [], docker


def test_bootstrap_password_goes_by_env_never_argv(tmp_path):
    rc, docker, out = _bootstrap(tmp_path, SENTINEL)
    assert rc == 0, out
    execs = [c for c in docker if c and c[0] == "exec"]
    # every neo4j/cypher file + the alias CSV + the CHIT fixture and smoke
    assert len(execs) >= 4, docker
    for call in execs:
        assert "pmoves-neo4j" in call, call      # the compose-declared name, not pmoves-neo4j-1
        assert "cypher-shell" in call, call
        assert [call[i + 1] for i, tok in enumerate(call[:-1]) if tok == "-e"] == ["NEO4J_USERNAME", "NEO4J_PASSWORD"], call
        assert "-p" not in call and "--password" not in call, call
        assert all(SENTINEL not in tok for tok in call), call
    assert not any(c[:2] == ["exec", "pmoves-neo4j"] and "printenv" in c for c in docker)


def test_bootstrap_applies_each_cypher_file_once_and_the_smoke_last(tmp_path):
    """010 and 011 used to run twice (the glob, then again by name)."""
    rc, docker, out = _bootstrap(tmp_path, SENTINEL)
    assert rc == 0, out
    piped = _piped(tmp_path)
    files = sorted(CYPHER_DIR.glob("*.cypher"))
    for f in files:
        assert sum(1 for body in piped if body == f.read_text().rstrip("\n")) == 1, (f.name, len(piped))
    assert piped[-1] == SMOKE.read_text().rstrip("\n"), "the smoke must run after the alias seed"
    assert len(piped) == len(files) + 1  # + the alias CSV UNWIND


@pytest.mark.parametrize("reply", ['"CHIT_SMOKE_FAIL", 0, 0, 0, 0', ""], ids=["smoke-fail", "no-output"])
def test_bootstrap_fails_when_the_smoke_does(tmp_path, reply):
    """011 returned ok=false and the script printed it and exited 0."""
    rc, docker, out = _bootstrap(tmp_path, SENTINEL, smoke_reply=reply)
    assert rc != 0, out
    assert "CHIT geometry smoke failed" in out, out
    assert "Neo4j bootstrap complete" not in out, out
