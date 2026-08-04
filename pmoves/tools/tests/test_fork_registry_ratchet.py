# pmoves/tools/tests/test_fork_registry_ratchet.py
"""Tests for the fork-registry ratchet gate.

The ratchet is the operator's "fork coverage" number. It must:
  1. Pass when every fork has sync (bool) + reason (non-empty str).
  2. Fail when any fork is missing the decision.
  3. Fail when any fork uses the deprecated `skip` field.
  4. Treat `_schema`, `_doc`, `_generated`, `_source`, `_excluded`,
     and any future underscore-prefixed meta keys as NOT forks.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

RATCHET = (
    Path(__file__).resolve().parents[1] / "fork_registry_ratchet.py"
)
PYTHON = sys.executable


def _run_on(payload: dict) -> subprocess.CompletedProcess:
    """Run the ratchet on an in-memory registry and return the result."""
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(payload, f)
        path = f.name
    try:
        return subprocess.run(
            [PYTHON, str(RATCHET), "--registry", path, "--json"],
            capture_output=True, text=True,
        )
    finally:
        Path(path).unlink(missing_ok=True)


def _registry(forks: dict, extra: dict | None = None) -> dict:
    return {
        "forks": forks,
        **(extra or {}),
    }


def test_all_decided_passes():
    payload = _registry({
        "F-A": {"upstream": "u/a", "sync": True, "reason": "auto-sync on cron"},
        "F-B": {"upstream": "u/b", "sync": False, "reason": "frozen snapshot"},
    })
    r = _run_on(payload)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["decided"] == 2
    assert out["total"] == 2
    assert out["problems"] == []


def test_missing_sync_fails():
    payload = _registry({
        "F-A": {"upstream": "u/a"},  # no sync
    })
    r = _run_on(payload)
    assert r.returncode == 1, r.stdout
    out = json.loads(r.stdout)
    assert out["decided"] == 0
    assert any("missing 'sync'" in p for p in out["problems"])


def test_missing_reason_fails():
    payload = _registry({
        "F-A": {"upstream": "u/a", "sync": True},  # no reason
    })
    r = _run_on(payload)
    assert r.returncode == 1
    out = json.loads(r.stdout)
    assert any("missing non-empty 'reason'" in p for p in out["problems"])


def test_empty_reason_fails():
    payload = _registry({
        "F-A": {"upstream": "u/a", "sync": True, "reason": "   "},
    })
    r = _run_on(payload)
    assert r.returncode == 1
    out = json.loads(r.stdout)
    assert any("missing non-empty 'reason'" in p for p in out["problems"])


def test_deprecated_skip_field_fails():
    payload = _registry({
        "F-A": {"upstream": "u/a", "skip": "synced"},
    })
    r = _run_on(payload)
    assert r.returncode == 1
    out = json.loads(r.stdout)
    assert any("deprecated 'skip'" in p for p in out["problems"])
    # The deprecated `skip` field does NOT count as decided, even
    # if the value is truthy — operators must explicitly migrate.
    assert out["decided"] == 0


def test_non_bool_sync_fails():
    payload = _registry({
        "F-A": {"upstream": "u/a", "sync": "yes", "reason": "r"},
    })
    r = _run_on(payload)
    assert r.returncode == 1
    out = json.loads(r.stdout)
    assert any("'sync' must be bool" in p for p in out["problems"])


def test_meta_keys_ignored():
    """Underscore-prefixed top-level keys are meta, not forks."""
    payload = _registry(
        {
            "F-A": {"upstream": "u/a", "sync": True, "reason": "r"},
        },
        extra={
            "_doc": "docs",
            "_generated": "2026-08-03",
            "_source": "src",
            "_schema": {"x": "y"},
            "_excluded": {"Pmoves-cipher": "no common ancestor"},
        },
    )
    r = _run_on(payload)
    assert r.returncode == 0, r.stdout
    out = json.loads(r.stdout)
    assert out["total"] == 1, f"meta keys must not be counted as forks: {out}"
    assert out["decided"] == 1


def test_missing_registry_file_returns_2():
    r = subprocess.run(
        [PYTHON, str(RATCHET), "--registry", "/nonexistent/path/registry.json"],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
    assert "not found" in r.stderr.lower()
