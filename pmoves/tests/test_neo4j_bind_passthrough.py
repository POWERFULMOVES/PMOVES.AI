"""NEO4J_BIND from the node-local env file reaches compose, alone, and never printed.

Measured before this change: under SUPABASE_RUNTIME=compose (the Makefile
default) the node-local file is NOT on COMPOSE_ENV_FILES, and up-data-tier runs
$(DC) directly, so `make env-local-set KEY=NEO4J_BIND` was silently ignored and
Neo4j published on 0.0.0.0. The Makefile now reads ONLY that key (parsed, never
sourced) and exports it into every recipe's environment.

make is spawned only with the guard's own stub dir FIRST on PATH
(build_stub_env from _destructive_docker_guard.py, #3195): docker,
docker-compose and supabase are recorders, and the real make runs its recipes. The real compose render is a separate,
direct, read-only `docker compose config` on a temp file holding the REAL
neo4j `ports` lines. Every address here is FAKE, and NODE_LOCAL_ENV_FILE points
at a pytest temp fixture -- never at the node's real file.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PMOVES = Path(__file__).resolve().parents[1]
REAL_DOCKER = shutil.which("docker")
FAKE_V4 = "10.9.9.9"
FAKE_V4_ENV = "10.8.8.8"
FAKE_V6 = "fd00::1"
FAKE_SUPABASE = "http://fake-supabase.invalid"

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")

DOCKER_GUARD_FILE = Path(__file__).with_name("_destructive_docker_guard.py")
DOCKER_GUARD_MODULE = "pmoves_tests_destructive_docker_guard"  # conftest's name


def _docker_guard():
    """The guard instance conftest registered, or a fresh load of the same file."""
    if DOCKER_GUARD_MODULE in sys.modules:
        return sys.modules[DOCKER_GUARD_MODULE]
    import importlib.util
    spec = importlib.util.spec_from_file_location(DOCKER_GUARD_MODULE, DOCKER_GUARD_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[DOCKER_GUARD_MODULE] = module
    spec.loader.exec_module(module)
    return module


# Runs after the recorder's own argv record (build_stub_env behaviours): what
# ENVIRONMENT a compose call received, which the argv record cannot show.
ENV_BEHAVIOUR = r"""
printf 'NEO4J_BIND=%s SUPABASE_URL=%s\n' "${NEO4J_BIND-<unset>}" "${SUPABASE_URL-<unset>}" >> "$NEO4J_BIND_ENV_LOG"
"""


def _make(tmp_path: Path, env_file_body: str | None, *make_args: str, extra_env: dict | None = None):
    """Run make with the guard's stub dir first; return (rc, stdout+stderr, recorded compose env).

    `recorded` is empty if no docker/docker-compose recorder ran at all.
    """
    node_local = tmp_path / "node_local_fixture.txt"
    if env_file_body is not None:
        node_local.write_text(env_file_body)
    base = {k: v for k, v in os.environ.items() if k not in ("NEO4J_BIND", "SUPABASE_URL")}
    stub = _docker_guard().build_stub_env(
        tmp_path / "bin", stub_make=False, base_env=base,
        behaviours={"docker": ENV_BEHAVIOUR, "docker-compose": ENV_BEHAVIOUR},
    )
    env_log = tmp_path / "compose-env.log"
    env = dict(stub)
    env.update(NEO4J_BIND_ENV_LOG=str(env_log), **(extra_env or {}))
    proc = subprocess.run(
        ["make", "-s", "-C", str(PMOVES), f"NODE_LOCAL_ENV_FILE={node_local}", *make_args],
        capture_output=True, text=True, timeout=120, env=env,
    )
    recorded = env_log.read_text() if env_log.exists() else ""
    ran = [row for row in stub.calls() if row and row[0] in ("docker", "docker-compose")]
    assert bool(ran) == bool(recorded), (ran, recorded)
    return proc.returncode, proc.stdout + proc.stderr, recorded


RENDER = ["--eval", "neo4j-bind-probe: ; @$(DC) config --format json neo4j", "neo4j-bind-probe"]


def _bind_seen(recorded: str) -> str:
    line = recorded.strip().splitlines()[-1]
    return line.split(" ", 1)[0].split("=", 1)[1]


def test_the_file_value_reaches_compose(tmp_path):
    rc, out, rec = _make(tmp_path, f"SUPABASE_URL={FAKE_SUPABASE}\nNEO4J_BIND={FAKE_V4}\n", *RENDER)
    assert rc == 0, out
    assert _bind_seen(rec) == FAKE_V4


def test_other_keys_in_the_file_do_not_reach_compose(tmp_path):
    rc, out, rec = _make(tmp_path, f"SUPABASE_URL={FAKE_SUPABASE}\nNEO4J_BIND={FAKE_V4}\n", *RENDER)
    assert rc == 0, out
    assert FAKE_SUPABASE not in rec
    assert "SUPABASE_URL=<unset>" in rec


def test_absent_key_exports_nothing(tmp_path):
    rc, out, rec = _make(tmp_path, f"SUPABASE_URL={FAKE_SUPABASE}\n", *RENDER)
    assert rc == 0, out
    assert _bind_seen(rec) == "<unset>"


def test_missing_file_exports_nothing(tmp_path):
    rc, out, rec = _make(tmp_path, None, *RENDER)
    assert rc == 0, out
    assert _bind_seen(rec) == "<unset>"


@pytest.mark.parametrize("bad", ["not-an-ip", "10.9.9.9; touch /tmp/x", "$(id)", "999.1.1.1"])
def test_malformed_value_is_refused_without_printing_it(tmp_path, bad):
    rc, out, rec = _make(tmp_path, f"NEO4J_BIND={bad}\n", *RENDER)
    assert rc != 0
    assert "malformed" in out
    assert bad not in out
    assert rec == "", "compose must not run with a refused value"


def test_the_file_is_parsed_not_sourced(tmp_path):
    marker = tmp_path / "sourced"
    rc, out, rec = _make(tmp_path, f"X=$(touch {marker})\nNEO4J_BIND={FAKE_V4}\n", *RENDER)
    assert rc == 0, out
    assert not marker.exists(), "a command substitution in another line ran"


def test_ipv6_is_bracketed_for_compose(tmp_path):
    rc, out, rec = _make(tmp_path, f'NEO4J_BIND="{FAKE_V6}"\n', *RENDER)
    assert rc == 0, out
    assert _bind_seen(rec) == f"[{FAKE_V6}]"


def test_caller_env_wins_over_the_file(tmp_path):
    rc, out, rec = _make(tmp_path, f"NEO4J_BIND={FAKE_V4}\n", *RENDER, extra_env={"NEO4J_BIND": FAKE_V4_ENV})
    assert rc == 0, out
    assert _bind_seen(rec) == FAKE_V4_ENV


def test_command_line_wins_over_env_and_file(tmp_path):
    rc, out, rec = _make(tmp_path, f"NEO4J_BIND={FAKE_V4}\n", f"NEO4J_BIND={FAKE_V6}", *RENDER,
                         extra_env={"NEO4J_BIND": FAKE_V4_ENV})
    assert rc == 0, out
    assert FAKE_V6 in _bind_seen(rec)


def test_malformed_caller_env_is_refused_too(tmp_path):
    rc, out, rec = _make(tmp_path, None, *RENDER, extra_env={"NEO4J_BIND": "garbage"})
    assert rc != 0 and "malformed" in out and "garbage" not in out


def test_printed_recipes_never_contain_the_value(tmp_path):
    """`make -n` prints the recipe lines; the value lives only in the environment."""
    rc, out, rec = _make(tmp_path, f"NEO4J_BIND={FAKE_V4}\n", "-n", "up-bus")
    assert rc == 0, out
    assert "docker compose" in out
    assert FAKE_V4 not in out


# --- the real render: the neo4j ports lines, interpolated by real compose ------

def _neo4j_ports() -> list:
    doc = yaml.safe_load((PMOVES / "docker-compose.yml").read_text())
    return doc["services"]["neo4j"]["ports"]


@pytest.mark.skipif(REAL_DOCKER is None, reason="docker not installed")
@pytest.mark.parametrize("bind,want", [(FAKE_V4, FAKE_V4), (f"[{FAKE_V6}]", FAKE_V6), (None, "0.0.0.0")])
def test_real_compose_binds_7474_and_7687_to_the_value(tmp_path, bind, want):
    f = tmp_path / "compose.yml"
    f.write_text(yaml.safe_dump({"services": {"neo4j": {"image": "busybox", "ports": _neo4j_ports()}}}))
    env = {k: v for k, v in os.environ.items() if not k.startswith("NEO4J_")}
    if bind is not None:
        env["NEO4J_BIND"] = bind
    proc = subprocess.run([REAL_DOCKER, "compose", "-p", "neo4j-bind-test", "-f", str(f),
                           "config", "--format", "json"],
                          capture_output=True, text=True, timeout=60, env=env)
    assert proc.returncode == 0, proc.stderr[-400:]
    ports = json.loads(proc.stdout)["services"]["neo4j"]["ports"]
    got = {str(p["target"]): p.get("host_ip") for p in ports}
    assert got == {"7474": want, "7687": want}, got
