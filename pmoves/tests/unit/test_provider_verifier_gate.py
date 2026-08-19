"""
Hand-written pytest suite for pmoves.tools.provider_verifier_gate.

Tests cover all 6 static checks + the aggregate result + the CLI entry
point. Tests use a tmp_path fixture with a copy of the real verifier
submodule so a real-key leak in the operator's working tree doesn't
trigger a test failure (the real example is fine; we just want to
test the check logic, not re-test the submodule).

Coverage target: >= 80% line coverage.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Iterator

import pytest


# Repo root for the live submodule copy.
REPO_ROOT = Path(__file__).resolve().parents[3]
VERIFIER_SUBMODULE = REPO_ROOT / "Pmoves-MiniMax-Provider-Verifier"

# Path to the helper under test. Importing the module (rather than
# subprocess'ing the CLI) lets us call the individual check functions
# directly and pass in a custom verifier_submodule path.
sys.path.insert(0, str(REPO_ROOT / "pmoves"))
from tools import provider_verifier_gate as gate  # noqa: E402


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def fixture_verifier_dir(tmp_path: Path) -> Path:
    """A temp verifier directory with a valid provider.json + sample.jsonl + verify.py.

    The verify.py is a tiny stub (parseable, not the real one) so the
    test doesn't depend on the submodule's heavy deps. The point of
    the test is the gate's check logic, not the verifier's internals.
    """
    d = tmp_path / "verifier"
    d.mkdir()

    # Valid provider.json
    (d / "provider.json.example").write_text(
        json.dumps(
            [
                {
                    "name": "provider1",
                    "model": "model-name",
                    "base_url": "https://api.example.com/v1",
                    "api_key": "your-api-key-here",
                },
                {
                    "name": "openrouter-minimax",
                    "model": "minimax/minimax-m2",
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key": "your-api-key-here",
                    "extra_body": {"provider": {"only": ["minimax"]}},
                },
            ]
        ),
        encoding="utf-8",
    )

    # Non-empty sample.jsonl
    (d / "sample.jsonl").write_text(
        '{"messages":[{"role":"user","content":"hi"}]}\n'
        '{"messages":[{"role":"user","content":"hello"}]}\n',
        encoding="utf-8",
    )

    # Tiny parseable verify.py stub
    (d / "verify.py").write_text(
        '"""Stub verify.py for testing the static gate."""\n'
        "import argparse\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    return parser\n",
        encoding="utf-8",
    )

    return d


def write_provider_config(d: Path, entries: list) -> None:
    """Helper: rewrite provider.json.example with the given entries."""
    (d / "provider.json.example").write_text(
        json.dumps(entries), encoding="utf-8"
    )


# ============================================================================
# check_verifier_submodule_present
# ============================================================================


def test_check_verifier_submodule_present_pass(fixture_verifier_dir: Path) -> None:
    """Submodule directory exists: check passes."""
    result = gate.check_verifier_submodule_present(fixture_verifier_dir)
    assert result.passed, result.detail
    assert result.name == "verifier_submodule_present"


def test_check_verifier_submodule_present_missing(tmp_path: Path) -> None:
    """Submodule directory does NOT exist: check fails with actionable detail."""
    result = gate.check_verifier_submodule_present(tmp_path / "does-not-exist")
    assert not result.passed
    assert "git submodule update" in result.detail


# ============================================================================
# check_provider_config_well_formed
# ============================================================================


def test_check_provider_config_well_formed_pass(fixture_verifier_dir: Path) -> None:
    """provider.json parses as a JSON array: check passes."""
    result = gate.check_provider_config_well_formed(fixture_verifier_dir)
    assert result.passed, result.detail
    assert "2 provider entries" in result.detail


def test_check_provider_config_well_formed_missing(fixture_verifier_dir: Path) -> None:
    """provider.json missing: check fails."""
    (fixture_verifier_dir / "provider.json.example").unlink()
    result = gate.check_provider_config_well_formed(fixture_verifier_dir)
    assert not result.passed
    assert "not found" in result.detail


def test_check_provider_config_well_formed_invalid_json(fixture_verifier_dir: Path) -> None:
    """provider.json is not valid JSON: check fails with decode error."""
    (fixture_verifier_dir / "provider.json.example").write_text(
        "{ this is not json", encoding="utf-8"
    )
    result = gate.check_provider_config_well_formed(fixture_verifier_dir)
    assert not result.passed
    assert "JSON decode error" in result.detail


def test_check_provider_config_well_formed_wrong_type(fixture_verifier_dir: Path) -> None:
    """provider.json is a dict, not a list: check fails."""
    (fixture_verifier_dir / "provider.json.example").write_text(
        '{"name": "single-provider-not-list"}', encoding="utf-8"
    )
    result = gate.check_provider_config_well_formed(fixture_verifier_dir)
    assert not result.passed
    assert "must be a JSON array" in result.detail


# ============================================================================
# check_provider_entries_have_required_fields
# ============================================================================


def test_check_provider_entries_have_required_fields_pass(fixture_verifier_dir: Path) -> None:
    """All entries have the 4 required fields: check passes."""
    result = gate.check_provider_entries_have_required_fields(fixture_verifier_dir)
    assert result.passed, result.detail


def test_check_provider_entries_missing_field(fixture_verifier_dir: Path) -> None:
    """An entry missing the 'model' field: check fails with the missing field named."""
    write_provider_config(
        fixture_verifier_dir,
        [
            {
                "name": "provider1",
                "base_url": "https://api.example.com/v1",
                "api_key": "your-api-key-here",
                # missing "model"
            }
        ],
    )
    result = gate.check_provider_entries_have_required_fields(fixture_verifier_dir)
    assert not result.passed
    assert "model" in result.detail
    assert "provider1" in result.detail


def test_check_provider_entries_not_a_dict(fixture_verifier_dir: Path) -> None:
    """An entry that's a string, not a dict: check fails."""
    write_provider_config(
        fixture_verifier_dir,
        ["not-a-dict"],
    )
    result = gate.check_provider_entries_have_required_fields(fixture_verifier_dir)
    assert not result.passed
    assert "not a dict" in result.detail


# ============================================================================
# check_example_keys_are_placeholders
# ============================================================================


def test_check_example_keys_are_placeholders_pass(fixture_verifier_dir: Path) -> None:
    """Both entries use the placeholder: check passes."""
    result = gate.check_example_keys_are_placeholders(fixture_verifier_dir)
    assert result.passed, result.detail


def test_check_example_keys_real_key_detected(fixture_verifier_dir: Path) -> None:
    """An entry with a real-looking key: check fails with a clear leak signal."""
    write_provider_config(
        fixture_verifier_dir,
        [
            {
                "name": "leaky",
                "model": "m",
                "base_url": "https://api.example.com/v1",
                "api_key": "sk-1234567890abcdefghijklmnop",  # looks like a real key
            }
        ],
    )
    result = gate.check_example_keys_are_placeholders(fixture_verifier_dir)
    assert not result.passed
    assert "Real API key" in result.detail
    assert "leaky" in result.detail


def test_check_example_keys_empty_key_detected(fixture_verifier_dir: Path) -> None:
    """An entry with an empty api_key: check fails (codex review catch).

    Earlier formulation `if key and key != PLACEHOLDER` was
    truthiness-guarded, which let `""` silently pass: `if ""` is
    False, so the check never compared the value. The fix is to
    always compare against PLACEHOLDER_API_KEY regardless of
    truthiness. Empty, None, and any other non-placeholder value
    all fail this comparison.
    """
    write_provider_config(
        fixture_verifier_dir,
        [
            {
                "name": "emptykey",
                "model": "m",
                "base_url": "https://api.example.com/v1",
                "api_key": "",
            }
        ],
    )
    result = gate.check_example_keys_are_placeholders(fixture_verifier_dir)
    assert not result.passed, (
        "empty api_key must be flagged as non-placeholder; the "
        "example file is a template and empty is a sentinel for "
        "'the operator forgot to fill in the placeholder'"
    )
    assert "emptykey" in result.detail
    assert "not the placeholder" in result.detail


def test_check_example_keys_none_key_detected(fixture_verifier_dir: Path) -> None:
    """An entry with api_key: null: check fails (None != placeholder)."""
    write_provider_config(
        fixture_verifier_dir,
        [
            {
                "name": "nullkey",
                "model": "m",
                "base_url": "https://api.example.com/v1",
                "api_key": None,
            }
        ],
    )
    result = gate.check_example_keys_are_placeholders(fixture_verifier_dir)
    assert not result.passed
    assert "nullkey" in result.detail


# ============================================================================
# check_sample_jsonl_present
# ============================================================================


def test_check_sample_jsonl_present_pass(fixture_verifier_dir: Path) -> None:
    """sample.jsonl is non-empty: check passes with a useful detail."""
    result = gate.check_sample_jsonl_present(fixture_verifier_dir)
    assert result.passed, result.detail
    assert "2 non-empty lines" in result.detail


def test_check_sample_jsonl_present_missing(fixture_verifier_dir: Path) -> None:
    """sample.jsonl missing: check fails."""
    (fixture_verifier_dir / "sample.jsonl").unlink()
    result = gate.check_sample_jsonl_present(fixture_verifier_dir)
    assert not result.passed
    assert "not found" in result.detail


def test_check_sample_jsonl_present_empty(fixture_verifier_dir: Path) -> None:
    """sample.jsonl is empty (0 bytes): check fails."""
    (fixture_verifier_dir / "sample.jsonl").write_text("", encoding="utf-8")
    result = gate.check_sample_jsonl_present(fixture_verifier_dir)
    assert not result.passed
    assert "empty" in result.detail


# ============================================================================
# check_verifier_entry_point_importable
# ============================================================================


def test_check_verifier_entry_point_importable_pass(fixture_verifier_dir: Path) -> None:
    """verify.py parses cleanly: check passes."""
    result = gate.check_verifier_entry_point_importable(fixture_verifier_dir)
    assert result.passed, result.detail
    assert "parses cleanly" in result.detail


def test_check_verifier_entry_point_importable_syntax_error(fixture_verifier_dir: Path) -> None:
    """verify.py has a syntax error: check fails with the SyntaxError details."""
    (fixture_verifier_dir / "verify.py").write_text(
        "def broken(:\n    pass\n", encoding="utf-8"
    )
    result = gate.check_verifier_entry_point_importable(fixture_verifier_dir)
    assert not result.passed
    assert "syntax error" in result.detail


def test_check_verifier_entry_point_importable_missing(fixture_verifier_dir: Path) -> None:
    """verify.py missing: check fails with a 'not found' detail."""
    (fixture_verifier_dir / "verify.py").unlink()
    result = gate.check_verifier_entry_point_importable(fixture_verifier_dir)
    assert not result.passed
    assert "not found" in result.detail


# ============================================================================
# run_gate — aggregate
# ============================================================================


def test_run_gate_pass(fixture_verifier_dir: Path) -> None:
    """All 6 checks pass on a valid fixture: verdict is PASS, summary is green."""
    result = gate.run_gate(verifier_submodule=fixture_verifier_dir)
    assert result.verdict == "PASS"
    assert "all 6 static checks passed" in result.summary
    assert len(result.checks) == 6
    assert all(c.passed for c in result.checks)


def test_run_gate_fail(fixture_verifier_dir: Path) -> None:
    """Sample missing: verdict is FAIL, summary names the failed check."""
    (fixture_verifier_dir / "sample.jsonl").unlink()
    result = gate.run_gate(verifier_submodule=fixture_verifier_dir)
    assert result.verdict == "FAIL"
    assert "sample_jsonl_present" in result.summary
    # Only the sample check failed; the other 5 still pass.
    failed = [c for c in result.checks if not c.passed]
    assert len(failed) == 1
    assert failed[0].name == "sample_jsonl_present"


def test_run_gate_to_dict() -> None:
    """The to_dict() output is JSON-serializable (for CI consumption)."""
    import json as _json
    result = gate.GateResult(verdict="PASS", summary="ok", checks=[])
    # Should not raise; the output is plain dict.
    out = result.to_dict()
    _json.dumps(out)  # round-trips cleanly


# ============================================================================
# CLI — main()
# ============================================================================


def test_main_pass_exits_0(fixture_verifier_dir: Path) -> None:
    """The CLI exits 0 when all checks pass."""
    rc = gate.main(
        [
            "--verifier-submodule",
            str(fixture_verifier_dir),
            "--json",
        ]
    )
    assert rc == 0


def test_main_fail_exits_1(fixture_verifier_dir: Path) -> None:
    """The CLI exits 1 when any check fails."""
    (fixture_verifier_dir / "verify.py").unlink()
    rc = gate.main(
        [
            "--verifier-submodule",
            str(fixture_verifier_dir),
        ]
    )
    assert rc == 1
