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
@pytest.mark.parametrize("target", APPLY_TARGETS)
def test_unset_password_fails_closed_before_docker(tmp_path, target):
    rc, docker, out = _make(tmp_path, target, None, "VERSION=001")
    assert rc != 0, out
    assert "NEO4J_PASSWORD is not set" in out, out
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
