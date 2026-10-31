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

REPO = Path(__file__).resolve().parents[2]
VPS = REPO / "deploy" / "scripts" / "deploy-vps.sh"
LOCAL = REPO / "deploy" / "scripts" / "deploy-compose.sh"


def _vps_vars() -> dict:
    """Evaluate deploy-vps.sh's own variable definitions (no SSH, no main)."""
    wanted = ("COMPOSE_CMD=", "WORK_DIR=", "VPS_ENV_FILE=", "KEYS_PREFLIGHT_FIX=", "KEYS_PREFLIGHT_GATE=")
    lines = [l for l in VPS.read_text(encoding="utf-8").splitlines() if l.startswith(wanted)]
    script = "\n".join(lines) + '\nprintf "%s\\0" "$COMPOSE_CMD" "$WORK_DIR" "$VPS_ENV_FILE" "$KEYS_PREFLIGHT_FIX" "$KEYS_PREFLIGHT_GATE"\n'
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout
    keys = ("COMPOSE_CMD", "WORK_DIR", "VPS_ENV_FILE", "FIX", "GATE")
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


@pytest.mark.parametrize("rc,continues", [(0, True), (3, True), (1, False)])
def test_vps_deploy_runs_fix_preflight_before_compose(tmp_path, rc, continues):
    v = _vps_vars()
    assert v["VPS_ENV_FILE"] and " " not in v["VPS_ENV_FILE"]
    st = _stubs(tmp_path, rc)
    fix = v["FIX"].replace(v["WORK_DIR"], str(st["work"]))
    # The suite's destructive-docker guard (rightly) refuses a mutating compose
    # call unless argv names a throwaway project -- even against the stub docker.
    cmd = f"cd {st['work']} && {fix} && {v['COMPOSE_CMD']} -p pmoves-test-1a2b3c4d pull nginx"
    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, env=st["env"])
    out = r.stdout + r.stderr
    assert f"preflight --env-file {v['VPS_ENV_FILE']}" in out  # FIX mode, by path
    assert ("docker compose" in out) is continues
    if not continues:
        assert r.returncode == 1 and "Fix: cd " in out


def test_vps_status_uses_read_only_gate(tmp_path):
    v = _vps_vars()
    st = _stubs(tmp_path, 0)
    gate = v["GATE"].replace(v["WORK_DIR"], str(st["work"]))
    r = subprocess.run(
        ["bash", "-c", f"cd {st['work']} && {gate} && {v['COMPOSE_CMD']} ps"],
        capture_output=True, text=True, env=st["env"],
    )
    assert "preflight --gate --env-file" in r.stdout + r.stderr
    assert "docker compose" in r.stdout


def test_vps_deploy_and_status_lines_use_the_preflight():
    text = VPS.read_text(encoding="utf-8")
    assert "${KEYS_PREFLIGHT_FIX} && ${COMPOSE_CMD} pull" in text
    assert text.count("${KEYS_PREFLIGHT_GATE} && ${COMPOSE_CMD} ps") == 2


def test_local_deploy_wraps_every_compose_call():
    """deploy-compose.sh: up = FIX, down/logs/health-ps = GATE, all via --exec."""
    text = LOCAL.read_text(encoding="utf-8")
    body = text.split("keys_compose() {", 1)[1].split("\n}\n", 1)[1]
    calls = [l for l in body.splitlines() if '"${DOCKER_COMPOSE_BIN[@]}"' in l]
    # Outside keys_compose (whose exec target and no-python fallback are the only
    # direct uses), no compose call may bypass the preflight.
    assert calls == [], calls
    assert 'keys_compose fix -f "${COMPOSE_FILE}" -p "${PROJECT_NAME}" up -d' in text
    for verb in ("down", "logs -f", "ps --format json"):
        assert f'keys_compose gate -f "${{COMPOSE_FILE}}" -p "${{PROJECT_NAME}}" {verb}' in text
