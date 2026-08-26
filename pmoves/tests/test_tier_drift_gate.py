"""The tier drift gate must not be able to report clean while drift exists.

It shipped with three independent reasons it could never fail:

  1. `--drift` defaulted to False, and the Makefile target passed no flags, so
     the half that catches "declared in .example, absent from the runtime tier"
     never ran in the pipeline.
  2. Without `--strict`, finding drift left rc at 0.
  3. The summary printed "no drift detected" UNCONDITIONALLY when rc == 0 --
     immediately after listing the drift. A reader believes the last line.

Any one of those makes it decorative; it had all three. Meanwhile 55 keys were
drifted across 5 tiers, which is why Z_AI_API_KEY reached crush as nothing and
SPARK hit the same shape with Hermes.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "pmoves" / "tools" / "check_tier_envs.py"
MAKEFILE = REPO_ROOT / "pmoves" / "Makefile"


def _load():
    spec = importlib.util.spec_from_file_location("check_tier_envs", CHECKER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_tier_envs"] = module
    spec.loader.exec_module(module)
    return module


def test_drift_is_on_by_default():
    """Opt-in was the root cause: the pipeline invoked it with no flags."""
    module = _load()
    parser_args = subprocess.run(
        [sys.executable, str(CHECKER), "--help"], capture_output=True, text=True
    ).stdout
    assert "--no-drift" in parser_args, "no explicit opt-OUT means drift is not default-on"
    assert "default: on" in parser_args.lower() or "--no-drift" in parser_args


def test_summary_cannot_claim_clean_while_drift_was_printed():
    """The exact contradiction that shipped: list drift, then deny it."""
    source = CHECKER.read_text(encoding="utf-8")
    # The clean message must be guarded by a drift-was-empty condition, not by
    # rc alone -- rc stays 0 for non-strict runs that DID find drift.
    assert "drift_found" in source, (
        "no state tracks whether drift was actually found; the clean summary "
        "cannot be honest without it"
    )
    idx = source.find("no drift detected")
    assert idx != -1, "clean-summary anchor missing -- test is stale"
    preceding = source[max(0, idx - 400):idx]
    assert "drift_found" in preceding, (
        "the 'no drift detected' message is not guarded by drift_found, so it "
        "can print immediately after listing drift"
    )


def test_strict_still_fails_hard():
    """The ratchet must remain available for CI once the backlog clears."""
    source = CHECKER.read_text(encoding="utf-8")
    assert "--strict" in source
    assert "rc = 1" in source


def test_makefile_target_passes_drift_explicitly():
    """Defaults can be changed by a future edit; the call site should say it."""
    text = MAKEFILE.read_text(encoding="utf-8")
    idx = text.find("check_tier_envs.py")
    assert idx != -1, "Makefile no longer invokes the checker -- test is stale"
    line_end = text.find("\n", idx)
    assert "--drift" in text[idx:line_end], (
        "the Makefile invokes check_tier_envs.py without --drift; that is the "
        "exact configuration in which the gate never ran"
    )


def test_deprecated_workaround_is_labelled():
    """fix_tier_manifest.py must not look like a mechanism to the next reader."""
    path = REPO_ROOT / "pmoves" / "tools" / "fix_tier_manifest.py"
    if not path.is_file():
        return  # retired, which is the goal
    head = path.read_text(encoding="utf-8")[:2000]
    assert "DEPRECATED" in head, (
        "fix_tier_manifest.py carries a hardcoded TIER_MAPPING that nothing "
        "runs; it must be labelled so it is not extended instead of fixed"
    )
