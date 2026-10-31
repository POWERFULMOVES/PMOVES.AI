"""Raw-compose deploy paths run the Invidious key preflight before compose.

deploy/scripts/deploy-vps.sh runs ``docker compose ... --env-file <vps env>``
over SSH; deploy/scripts/deploy-compose.sh runs compose locally. Neither goes
through make, so neither got the make-goal preflight. Without it, the next
deploy after #3431 merges fails EVERY service on ${INVIDIOUS_*_KEY:?}.

These tests execute the exact remote command string deploy-vps.sh builds, with
stub ``docker`` and a stub preflight, and assert the exit semantics: preflight
1 stops before compose with the fix command; 0 and 3 continue to compose.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from pmoves.tools.bash_resolver import resolve_bash  # never System32's WSL stub

REPO = Path(__file__).resolve().parents[2]
VPS = REPO / "deploy" / "scripts" / "deploy-vps.sh"
LOCAL = REPO / "deploy" / "scripts" / "deploy-compose.sh"


def _vps_vars() -> dict:
    """Evaluate deploy-vps.sh's own definitions (no SSH, no main)."""
    lines = VPS.read_text(encoding="utf-8").splitlines()
    keep = [l for l in lines if l.startswith(("COMPOSE_CMD=", "WORK_DIR="))]
    a = next(i for i, l in enumerate(lines) if l.startswith("VPS_ENV_FILE="))
    b = next(i for i, l in enumerate(lines) if l.startswith("KEYS_PREFLIGHT_GATE="))
    script = "\n".join(keep + lines[a:b + 1])
    script += '\nprintf "%s\\0" "$COMPOSE_CMD" "$WORK_DIR" "$VPS_ENV_FILE" "$KEYS_PREFLIGHT_MINT" "$KEYS_PREFLIGHT_GATE"\n'
    out = subprocess.run([resolve_bash(), "-c", script], capture_output=True, text=True, check=True).stdout
    keys = ("COMPOSE_CMD", "WORK_DIR", "VPS_ENV_FILE", "MINT", "GATE")
    return dict(zip(keys, out.split("\0")))


def _stubs(tmp_path: Path, preflight_rc: int) -> dict:
    work = tmp_path / "work"
    (work / "tools").mkdir(parents=True)
    (work / "tools" / "invidious_keys_preflight.py").write_text(
        "import sys\nprint('preflight', ' '.join(sys.argv[1:]))\nsys.exit(%d)\n" % preflight_rc
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    docker = bindir / "docker"
    docker.write_text('#!/bin/sh\necho "docker $*"\n')
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
    return {"work": work, "env": env}


@pytest.mark.parametrize(
    "rc,continues,says",
    [
        (0, True, None),
        (3, True, "could not measure"),
        (1, False, "compose would refuse every service. Fix: cd "),
        (127, True, "did not run (exit 127)"),
    ],
)
def test_vps_deploy_runs_mint_preflight_before_compose(tmp_path, rc, continues, says):
    v = _vps_vars()
    assert v["VPS_ENV_FILE"] and " " not in v["VPS_ENV_FILE"]
    st = _stubs(tmp_path, rc)
    mint = v["MINT"].replace(v["WORK_DIR"], str(st["work"]))
    # The suite's destructive-docker guard (rightly) refuses a mutating compose
    # call unless argv names a throwaway project -- even against the stub docker.
    cmd = f"cd {st['work']} && {mint} && {v['COMPOSE_CMD']} -p pmoves-test-1a2b3c4d pull nginx"
    r = subprocess.run([resolve_bash(), "-c", cmd], capture_output=True, text=True, env=st["env"])
    out = r.stdout + r.stderr
    assert f"preflight --mint --env-file {v['VPS_ENV_FILE']}" in out  # MINT, by path
    assert ("docker compose" in r.stdout) is continues
    if says:
        assert says in r.stderr
    if not continues:
        assert r.returncode == 1


def test_vps_status_uses_read_only_gate(tmp_path):
    v = _vps_vars()
    st = _stubs(tmp_path, 0)
    gate = v["GATE"].replace(v["WORK_DIR"], str(st["work"]))  # status path
    r = subprocess.run(
        [resolve_bash(), "-c", f"cd {st['work']} && {gate} && {v['COMPOSE_CMD']} ps"],
        capture_output=True, text=True, env=st["env"],
    )
    assert "preflight --gate --env-file" in r.stdout + r.stderr
    assert "docker compose" in r.stdout


def test_vps_deploy_and_status_lines_use_the_preflight():
    text = VPS.read_text(encoding="utf-8")
    assert "${KEYS_PREFLIGHT_MINT} && ${COMPOSE_CMD} pull" in text
    assert text.count("${KEYS_PREFLIGHT_GATE} && ${COMPOSE_CMD} ps") == 2


def test_local_deploy_wraps_every_compose_call():
    """deploy-compose.sh: up = MINT, down/logs = GATE, health loop = env-only."""
    text = LOCAL.read_text(encoding="utf-8")
    body = text.split("keys_compose() {", 1)[1].split("\n}\n", 1)[1]
    calls = [l for l in body.splitlines() if '"${DOCKER_COMPOSE_BIN[@]}"' in l]
    # Outside keys_compose (whose exec target and no-python fallback are the only
    # direct uses), no compose call may bypass the preflight.
    assert calls == [], calls
    assert 'keys_compose mint -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" up -d' in text
    for verb in ("down", "logs -f"):
        assert f'keys_compose gate -f "${{COMPOSE_FILE}}" -p "${{PROJECT_NAME}}" {verb}' in text
    assert 'keys_compose env -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" ps --format json' in text


def _keys_compose(tmp_path: Path, env_text, mode: str, *compose_args: str):
    """Run the REAL keys_compose function from deploy-compose.sh with the real
    preflight, a stub docker on PATH and docker pointed at a dead socket."""
    pm = tmp_path / "pmoves"
    (pm / "tools").mkdir(parents=True)
    (pm / "tools" / "invidious_keys_preflight.py").symlink_to(REPO / "pmoves" / "tools" / "invidious_keys_preflight.py")
    if env_text is not None:
        (pm / ("env." + "shared")).write_text(env_text, encoding="utf-8")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "stubdocker"
    # Reports only the SHAPE of what it received -- never a value.
    stub.write_text(
        '#!/bin/sh\n'
        'echo "stub-docker $* companion-len=${#INVIDIOUS_COMPANION_KEY} hmac-len=${#INVIDIOUS_HMAC_KEY}"\n'
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    text = LOCAL.read_text(encoding="utf-8")
    fn = "keys_compose() {" + text.split("keys_compose() {", 1)[1].split("\n}\n", 1)[0] + "\n}\n"
    script = (
        f'set -euo pipefail\nPMOVES_DIR="{pm}"\nDOCKER_COMPOSE_BIN=("{stub}" "compose")\n'
        + fn + 'keys_compose "$@"\n'
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith(("INVIDIOUS_", "DOCKER_"))}
    env["DOCKER_HOST"] = "unix:///nonexistent/pmoves-test-no-docker.sock"
    env["PATH"] = f"{bindir}:{env['PATH']}"
    r = subprocess.run([resolve_bash(), "-c", script, "keys_compose", mode, *compose_args],
                       capture_output=True, text=True, env=env, timeout=120)
    return r, pm / ("env." + "shared")


def test_keys_compose_mint_mints_then_runs_compose_with_the_keys(tmp_path):
    r, env = _keys_compose(tmp_path, "OTHER=keep\n", "mint", "-p", "pmoves-test-1a2b3c4d", "ps")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "stub-docker compose -p pmoves-test-1a2b3c4d ps companion-len=16 hmac-len=64"
    assert "minted" in r.stderr  # preflight talk goes to stderr, compose stdout stays clean
    text = env.read_text(encoding="utf-8")
    assert "INVIDIOUS_COMPANION_KEY=" in text and "OTHER=keep" in text


def test_keys_compose_gate_stops_before_compose_and_never_writes(tmp_path):
    r, env = _keys_compose(tmp_path, "OTHER=keep\n", "gate", "-p", "pmoves-test-1a2b3c4d", "ps")
    assert r.returncode == 1
    assert "stub-docker" not in r.stdout
    assert env.read_text(encoding="utf-8") == "OTHER=keep\n"


def test_keys_compose_mint_never_rotates_an_invalid_key(tmp_path):
    good_hmac = "f" * 40
    r, env = _keys_compose(
        tmp_path, f"INVIDIOUS_HMAC_KEY={good_hmac}\nINVIDIOUS_COMPANION_KEY=ab-def_123456789\n",
        "mint", "-p", "pmoves-test-1a2b3c4d", "ps",
    )
    assert r.returncode == 0, r.stderr
    assert "WARNING" in r.stderr and "ab-def_123456789" not in r.stderr + r.stdout
    assert "INVIDIOUS_COMPANION_KEY=ab-def_123456789" in env.read_text(encoding="utf-8")
