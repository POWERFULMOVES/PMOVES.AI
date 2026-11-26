"""`make nats-pub` must deliver a JSON payload byte-for-byte.

The recipe used to paste $(PAYLOAD) into its shell text: `test -n "$(PAYLOAD)"`
let the JSON's own double quotes end the shell word, so any payload with a space
died with `test: ... binary operator expected` / `too many arguments`, and
`'$(PAYLOAD)'` broke on an apostrophe. Reported 2026-11-23 on node 5090 against
the recipe's own usage example shape.

Measured on node 5090 with the real make and a recorder docker, pre-fix recipe
read from git (live worktree untouched):
    {"from":"x","note":"a b"}  -> rc 2, "test: {from:x,note:a: binary operator expected"
    {"note":"it's"}            -> rc 2, "unexpected EOF while looking for matching `''"
Post-fix both arrive intact as the final docker argv element.

Runs under `stub_docker_path`: the real make renders and runs the recipe, docker
resolves to a recorder. NATS_DOCKER_NETWORK also names a network that does not
exist, so even a stub miss could not publish to a live bus.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[1]
SUBJECT = "claw.task.assign.v1"
NO_SUCH_NETWORK = "NATS_DOCKER_NETWORK=pmoves-test-no-such-network"

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")

PAYLOADS = [
    pytest.param(
        '{"from":"pmoves-4090","to":"pmoves-spark","task":"cascade-wave-B"}',
        id="documented-usage",
    ),
    pytest.param(
        '{"from":"x","to":"y","task":"t","note":"it\'s a wave, go"}',
        id="apostrophe-and-spaces",
    ),
    pytest.param(
        '{"from":"x","to":"y","task":"t","note":"cost $5 $(HOME)"}',
        id="literal-dollar",
    ),
]


def _nats_pub(stub_env, *assignments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["make", "-s", "-C", str(PMOVES), "nats-pub", NO_SUCH_NETWORK, *assignments],
        capture_output=True,
        text=True,
        env=stub_env,
        timeout=120,
    )


@pytest.mark.parametrize("payload", PAYLOADS)
def test_payload_reaches_nats_box_verbatim(stub_docker_path, payload):
    proc = _nats_pub(stub_docker_path, f"SUBJECT={SUBJECT}", f"PAYLOAD={payload}")

    assert proc.returncode == 0, proc.stderr
    assert "too many arguments" not in proc.stderr
    assert "binary operator expected" not in proc.stderr
    runs = [c for c in stub_docker_path.calls("docker") if len(c) > 1 and c[1] == "run"]
    assert len(runs) == 1, stub_docker_path.calls()
    assert runs[0][-3:] == ["pub", SUBJECT, payload]
    assert "pmoves-test-no-such-network" in runs[0]


def test_missing_payload_fails_before_docker(stub_docker_path):
    proc = _nats_pub(stub_docker_path, f"SUBJECT={SUBJECT}")

    assert proc.returncode != 0
    assert "PAYLOAD is required" in proc.stdout + proc.stderr
    assert stub_docker_path.calls("docker") == []


def test_missing_subject_fails_before_docker(stub_docker_path):
    proc = _nats_pub(stub_docker_path, 'PAYLOAD={"from":"x","to":"y","task":"t"}')

    assert proc.returncode != 0
    assert "SUBJECT is required" in proc.stdout + proc.stderr
    assert stub_docker_path.calls("docker") == []
