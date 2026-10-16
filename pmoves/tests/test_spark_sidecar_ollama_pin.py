"""up-spark-sidecar: an Ollama pin must state a reason, or the target refuses.

env.spark-sidecar is a one-time gitignored copy, so nodes bootstrapped before
#3380 carry an unexplained 0.31.2 pin that silently overrides the compose
default Dependabot bumps. The pin check is lifted out of the Makefile recipe
and run against each shape.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[1]


def _run(tmp_path: Path, env_body: str, env: dict) -> subprocess.CompletedProcess:
    text = (PMOVES / "Makefile").read_text(encoding="utf-8")
    a = text.index("\t@# A pin overrides")
    b = text.index('\t@echo "⚡ Starting DGX Spark sidecar')
    (tmp_path / "Makefile").write_text("check:\n" + text[a:b], encoding="utf-8")
    shutil.copy(PMOVES / "docker-compose.spark-sidecar.yml", tmp_path)
    (tmp_path / "env.spark-sidecar").write_text(env_body + "\n", encoding="utf-8")
    return subprocess.run(["make", "-s", "check"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)


@pytest.mark.skipif(shutil.which("make") is None, reason="needs make")
@pytest.mark.parametrize("body,ok,says", [
    ("", True, ""),
    ("# PMOVES_OLLAMA_IMAGE=ollama/ollama:0.31.2", True, ""),
    ("PMOVES_OLLAMA_IMAGE=ollama/ollama:0.31.2", False, "no PMOVES_OLLAMA_PIN_REASON"),
    ('PMOVES_OLLAMA_IMAGE=ollama/ollama:0.31.2\nPMOVES_OLLAMA_PIN_REASON="driver test"', True, "Reason: driver test"),
])
def test_pin_must_state_a_reason(tmp_path, stub_docker_path, body, ok, says):
    # The extracted recipe has no docker calls; the stub PATH is the repo's guard contract.
    r = _run(tmp_path, body, stub_docker_path)
    assert (r.returncode == 0) is ok, r.stdout + r.stderr
    assert says in r.stdout
    if "PMOVES_OLLAMA_IMAGE=" in body and not body.startswith("#"):
        assert "ollama/ollama:0.31.2" in r.stdout  # the pin is shown, not hidden
