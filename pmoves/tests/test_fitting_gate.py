"""The gate rejects a fitting that names an unregistered harness or unknown role."""
from __future__ import annotations

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
    backup = VICTIM.read_bytes()
    yield
    VICTIM.write_bytes(backup)


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


def test_gate_rejects_an_empty_observation_list(restore_victim):
    """`fit: {clawz: {"*": []}}` is `untested` under another spelling: a
    present-but-empty record that looks like data."""
    doc = yaml.safe_load(VICTIM.read_text(encoding="utf-8"))
    doc["fit"]["clawz"]["*"] = []
    VICTIM.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    assert "observation list is empty" in result.stdout + result.stderr


def test_gate_rejects_an_empty_role_map(restore_victim):
    doc = yaml.safe_load(VICTIM.read_text(encoding="utf-8"))
    doc["fit"]["clawz"] = {}
    VICTIM.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    assert "role map is empty" in result.stdout + result.stderr


def test_gate_rejects_an_empty_harness_map(restore_victim):
    doc = yaml.safe_load(VICTIM.read_text(encoding="utf-8"))
    doc["fit"] = {}
    VICTIM.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    assert "fit: is present but empty" in result.stdout + result.stderr


def test_gate_rejects_an_observation_missing_provenance(restore_victim):
    """`[{verdict: limited}]` must not pass -- evidence, not a permission bit."""
    doc = yaml.safe_load(VICTIM.read_text(encoding="utf-8"))
    doc["fit"]["clawz"]["*"] = [{"verdict": "limited"}]
    VICTIM.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    assert "missing required provenance field" in result.stdout + result.stderr


def test_gate_rejects_an_invalid_method(restore_victim):
    doc = yaml.safe_load(VICTIM.read_text(encoding="utf-8"))
    doc["fit"]["clawz"]["*"] = [
        {"verdict": "limited", "by": "t", "method": "vibes", "on": "2026-08-25"}
    ]
    VICTIM.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    assert "method must be 'hand' or 'measured'" in result.stdout + result.stderr


def test_gate_rejects_the_unquoted_on_boolean_key(restore_victim):
    """Unquoted `on: 2026-06-11` parses under YAML 1.1 as the boolean key
    True, not the string "on" -- the date then silently vanishes rather than
    merely going missing. The gate must name the quoting problem, not just
    report `on` as absent."""
    text = VICTIM.read_text(encoding="utf-8")
    injected = text.replace('"on": 2026-06-11', "on: 2026-06-11")
    assert injected != text, 'fixture no longer has a quoted "on": key to unquote'
    VICTIM.write_text(injected, encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "True" in out and "boolean" in out.lower()


def test_gate_rejects_the_legacy_scalar_fit_shape(restore_victim):
    """`fit: {clawz: full}` is the shape a migrator would naturally write.
    It must become a gate error naming the file, not an uncaught
    AttributeError that aborts the whole validator run."""
    doc = yaml.safe_load(VICTIM.read_text(encoding="utf-8"))
    doc["fit"]["clawz"] = "full"
    VICTIM.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    assert "legacy scalar shape" in result.stdout + result.stderr


def test_gate_rejects_observations_written_as_a_mapping(restore_victim):
    """A role's observations written as a mapping instead of a list must
    become a gate error, not an uncaught AttributeError inside
    effective_fit()."""
    doc = yaml.safe_load(VICTIM.read_text(encoding="utf-8"))
    doc["fit"]["clawz"]["*"] = {
        "verdict": "full", "by": "t", "method": "hand", "on": "2026-08-25",
    }
    VICTIM.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    result = _run()
    assert result.returncode != 0
    assert "expected a list of observations" in result.stdout + result.stderr
