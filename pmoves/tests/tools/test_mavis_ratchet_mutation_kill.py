"""Mutation-kill harness: the mavis CLI ratchet must reject a broken launcher.

This is the PROVENANCE HARNESS for the two defects found in the
``test_mavis_cli_timeout.py`` ratchet after it shipped in PR #3095.

It is a test (not a scratch script) because a ratchet that nobody re-runs
decays. Run it directly to see the mutation kill in action:

    python -m pytest pmoves/tests/tools/test_mavis_ratchet_mutation_kill.py -v

It works by rewriting the gate inside
``pmoves/tests/test_mavis_cli_timeout.py`` back to its ORIGINAL defective
form, re-running that module, and asserting that the module now FAILS.
If the ratchet ever stops catching the defect, this harness fails.

Two defects are covered:

Defect A -- the version gate accepted stderr as a version string
    Original:  ``version = (proc.stdout or proc.stderr or "").strip()``
                ``assert version``
    A broken launcher (Node's "Cannot find module" banner on stderr, rc=1)
    satisfies that assertion, so the ratchet reported GREEN on a 100%
    broken CLI.

Defect B -- the upstream repo pin pointed at a 404
    ``MiniMaxInc/MiniMax-Code`` does not exist. The real upstream is
    ``MiniMax-AI/minimax-code``. With the wrong pin the fetch returned a
    JSON error object where a list was expected, so the matrix cross-check
    silently degraded to a permanent SKIP.

The harness restores the file in a ``finally`` block, so a failed run
leaves the working tree clean.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TARGET = REPO_ROOT / "pmoves" / "tests" / "test_mavis_cli_timeout.py"

# The FIXED gate, verbatim from the repaired ratchet.
FIXED_GATE = '''    assert proc.returncode == 0, (
        f"mavis --version exited {proc.returncode} (expected 0). The CLI ran "
        f"but failed. stderr={proc.stderr!r} stdout={proc.stdout!r}. "
        f"Investigate the shim / daemon path before merging -- a non-zero "
        f"exit means the launcher is broken even though it did not hang."
    )
    version = (proc.stdout or "").strip()
    assert version, (
        f"mavis --version returned empty stdout (rc={proc.returncode}); CLI "
        f"ran without hanging but did not produce a version string. "
        f"stderr={proc.stderr!r}"
    )
    lowered = version.lower()
    for marker in ("error:", "cannot find module", "traceback", "not found"):
        assert marker not in lowered, (
            f"mavis --version stdout looks like an error banner, not a "
            f"version string: {version!r}. The ratchet must not accept "
            f"error prose as a version."
        )
'''

# The ORIGINAL gate, verbatim from PR #3095 (the defect that shipped).
ORIGINAL_GATE = '''    version = (proc.stdout or proc.stderr or "").strip()
    assert version, (
        f"mavis --version returned empty (rc={proc.returncode}); CLI ran "
        f"without hanging but did not produce a version string."
    )
'''

FIXED_UPSTREAM_PIN = '_UPSTREAM_REPO = "MiniMax-AI/minimax-code"'
ORIGINAL_UPSTREAM_PIN = '_UPSTREAM_REPO = "MiniMaxInc/MiniMax-Code"'


def _run_module() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "pmoves/tests/test_mavis_cli_timeout.py", "-q"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def _mutate_and_run(old: str, new: str) -> tuple[bool, str]:
    """Apply a mutation, run the ratchet module, restore the file.

    Returns (mutation_was_killed, combined_output).
    """
    original = TARGET.read_text(encoding="utf-8")
    assert old in original, "mutation setup failed: anchor not found"
    mutated = original.replace(old, new)
    assert mutated != original, "mutation setup failed: replacement was a no-op"

    TARGET.write_text(mutated, encoding="utf-8")
    try:
        proc = _run_module()
        output = proc.stdout + proc.stderr
        killed = proc.returncode != 0 and "failed" in output
        return killed, output
    finally:
        TARGET.write_text(original, encoding="utf-8")


def test_mutation_original_version_gate_is_killed() -> None:
    """Restoring the original version gate MUST make the ratchet fail."""
    killed, output = _mutate_and_run(FIXED_GATE, ORIGINAL_GATE)
    assert killed, (
        "the ratchet did NOT catch the original stderr-fallback defect -- "
        f"the gate was weakened again.\n{output}"
    )


def test_mutation_original_upstream_pin_is_killed() -> None:
    """Restoring the 404 upstream pin MUST make the ratchet fail."""
    killed, output = _mutate_and_run(FIXED_UPSTREAM_PIN, ORIGINAL_UPSTREAM_PIN)
    assert killed, (
        "the ratchet did NOT catch the wrong upstream repo pin -- the "
        f"cross-check can silently skip again.\n{output}"
    )


def test_ratchet_file_is_left_clean_after_mutations() -> None:
    """The harness must not leave the ratchet file mutated."""
    content = TARGET.read_text(encoding="utf-8")
    assert FIXED_GATE in content, "the ratchet gate is not in its fixed form"
    assert FIXED_UPSTREAM_PIN in content, "the upstream pin is not the fixed one"


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(pytest.main([__file__, "-v"]))
