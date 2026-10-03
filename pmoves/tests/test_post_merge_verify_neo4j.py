"""post-merge-verify's Neo4j auth check must be able to verify, and fail.

Neo4j publishes no host ports since #3251, so the old `port_up 7474` gate made the
check WARN-skip every time and never verify auth enforcement. It now runs
cypher-shell inside the container. These tests run the function against a recording
`docker` stub (pmoves/tests/_destructive_docker_guard.py), so nothing reaches a real
container. The configured password must travel by env and never appear in argv.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
from pmoves.tools.bash_resolver import resolve_bash  # never System32's WSL stub

PMOVES = Path(__file__).resolve().parents[1]
REPO = PMOVES.parent
SCRIPT = REPO / "scripts" / "security" / "post-merge-verify.sh"
DOCKER_GUARD_FILE = Path(__file__).with_name("_destructive_docker_guard.py")
DOCKER_GUARD_MODULE = "pmoves_tests_destructive_docker_guard"
SENTINEL = "s3ntinel-not-a-real-password"


def _docker_guard():
    if DOCKER_GUARD_MODULE in sys.modules:
        return sys.modules[DOCKER_GUARD_MODULE]
    import importlib.util
    spec = importlib.util.spec_from_file_location(DOCKER_GUARD_MODULE, DOCKER_GUARD_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[DOCKER_GUARD_MODULE] = module
    spec.loader.exec_module(module)
    return module


def _function_source() -> str:
    text = SCRIPT.read_text()
    start = text.index("check_neo4j_auth() {\n")
    return text[start: text.index("\n}\n", start) + 3]


def _run(tmp_path: Path, *, running: bool, wrong_pw_rc: int, wrong_pw_out: str, authed_out: str,
         password: str | None):
    # `docker exec` answers by which password it was handed: the wrong-password
    # probe carries it inline (-e NEO4J_PASSWORD=...), the real one by name only.
    behaviour = (
        'if [ "$1" = "ps" ]; then ' + ('echo pmoves-neo4j; ' if running else '') + 'fi\n'
        'if [ "$1" = "exec" ]; then\n'
        '  case "$*" in *NEO4J_PASSWORD=*) printf "%s\\n" "$STUB_WRONG_OUT"; exit "$STUB_WRONG_RC";; esac\n'
        '  printf "%s\\n" "$STUB_AUTHED_OUT"; exit 0\n'
        'fi\n'
    )
    stub = _docker_guard().build_stub_env(tmp_path / "bin", stub_make=False, behaviours={"docker": behaviour})
    env = dict(stub)
    for k in ("NEO4J_PASSWORD", "NEO4J_USER", "NEO4J_USERNAME"):
        env.pop(k, None)
    if password is not None:
        env["NEO4J_PASSWORD"] = password
    env.update(STUB_WRONG_RC=str(wrong_pw_rc), STUB_WRONG_OUT=wrong_pw_out, STUB_AUTHED_OUT=authed_out)
    prelude = (
        "set -euo pipefail\n"
        f"REPO_ROOT={str(REPO)!r}\n"
        "PASS=0; FAIL=0; WARN=0; TOTAL=0\n"
        'pass_check() { PASS=$((PASS+1)); echo "PASS $1"; }\n'
        'fail_check() { FAIL=$((FAIL+1)); echo "FAIL $1"; }\n'
        'warn_check() { WARN=$((WARN+1)); echo "WARN $1"; }\n'
        'section() { :; }\n'
    )
    harness = tmp_path / "harness.sh"
    harness.write_text(prelude + _function_source() + 'check_neo4j_auth\necho "TOTALS $PASS $FAIL $WARN"\n')
    proc = subprocess.run([resolve_bash(), str(harness)], env=env, capture_output=True, text=True, timeout=60)
    docker = [row[1:] for row in stub.calls() if row[0] == "docker"]
    totals = re.search(r"TOTALS (\d+) (\d+) (\d+)", proc.stdout)
    assert totals, proc.stdout + proc.stderr
    return tuple(int(x) for x in totals.groups()), docker, proc.stdout


AUTH_ERR = "The client is unauthorized due to authentication failure."


def test_the_check_no_longer_gates_on_a_host_port():
    code = "\n".join(l for l in _function_source().splitlines() if not l.lstrip().startswith("#"))
    assert "port_up 7474" not in code
    assert "localhost:7474" not in code


def test_auth_enforced_and_password_accepted_is_two_passes(tmp_path):
    (p, f, w), docker, out = _run(tmp_path, running=True, wrong_pw_rc=1, wrong_pw_out=AUTH_ERR,
                                  authed_out="ok\n1", password=SENTINEL)
    assert (p, f, w) == (2, 0, 0), out


def test_auth_not_enforced_fails(tmp_path):
    (p, f, w), _, out = _run(tmp_path, running=True, wrong_pw_rc=0, wrong_pw_out="ok\n1",
                             authed_out="ok\n1", password=SENTINEL)
    assert f >= 1 and "auth not enforced" in out, out


def test_wrong_configured_password_fails(tmp_path):
    (p, f, w), _, out = _run(tmp_path, running=True, wrong_pw_rc=1, wrong_pw_out=AUTH_ERR,
                             authed_out=AUTH_ERR, password=SENTINEL)
    assert (p, f) == (1, 1), out


def test_not_running_warns_and_never_execs(tmp_path):
    (p, f, w), docker, out = _run(tmp_path, running=False, wrong_pw_rc=1, wrong_pw_out=AUTH_ERR,
                                  authed_out="ok\n1", password=SENTINEL)
    assert (p, f, w) == (0, 0, 1), out
    assert not [c for c in docker if c and c[0] == "exec"], docker


def test_configured_password_never_on_argv(tmp_path):
    _, docker, out = _run(tmp_path, running=True, wrong_pw_rc=1, wrong_pw_out=AUTH_ERR,
                          authed_out="ok\n1", password=SENTINEL)
    execs = [c for c in docker if c and c[0] == "exec"]
    assert len(execs) == 2, docker
    assert all(SENTINEL not in tok for c in execs for tok in c), "configured password reached argv"
    assert "pmoves-neo4j" in execs[1]
    assert [execs[1][i + 1] for i, t in enumerate(execs[1][:-1]) if t == "-e"] == ["NEO4J_USERNAME", "NEO4J_PASSWORD"]
