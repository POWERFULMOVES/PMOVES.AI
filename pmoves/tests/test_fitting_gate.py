"""The gate rejects a fitting that names an unregistered harness or unknown role."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "pmoves" / "scripts" / "validate_agent_registry.py"
SUITS_DIR = REPO_ROOT / "pmoves" / "configs" / "model-suits"
VICTIM = SUITS_DIR / "qwen3.6.yaml"


def _run() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
    )


@pytest.fixture
def restore_victim():
    backup = VICTIM.read_text(encoding="utf-8")
    yield
    VICTIM.write_text(backup, encoding="utf-8")


def test_gate_passes_on_the_seeded_data():
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr


def test_gate_rejects_an_unregistered_harness(restore_victim):
    doc = yaml.safe_load(VICTIM.read_text(encoding="utf-8"))
    doc["fit"]["not_a_harness"] = {"*": [
        {"verdict": "full", "by": "t", "method": "hand", "on": "2026-08-25"}
    ]}
    VICTIM.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    assert "not_a_harness" in result.stdout + result.stderr


def test_gate_rejects_an_unknown_role(restore_victim):
    doc = yaml.safe_load(VICTIM.read_text(encoding="utf-8"))
    doc["fit"]["clawz"]["vibes_based_refactor"] = [
        {"verdict": "full", "by": "t", "method": "hand", "on": "2026-08-25"}
    ]
    VICTIM.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    assert "vibes_based_refactor" in result.stdout + result.stderr


def test_gate_rejects_an_unknown_verdict(restore_victim):
    doc = yaml.safe_load(VICTIM.read_text(encoding="utf-8"))
    doc["fit"]["clawz"]["*"] = [
        {"verdict": "untested", "by": "t", "method": "hand", "on": "2026-08-25"}
    ]
    VICTIM.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    assert "untested" in result.stdout + result.stderr
