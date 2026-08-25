"""Fit resolution: the most conservative observation wins, and absence stays absent."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _fittings():
    path = REPO_ROOT / "pmoves" / "tools" / "fittings.py"
    spec = importlib.util.spec_from_file_location("fittings", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fittings"] = module
    spec.loader.exec_module(module)
    return module


def test_no_observations_is_none_not_untested():
    """Absent reads as honestly unknown; `untested` reads as a completed
    observation with a null result and survives for months looking like data."""
    f = _fittings()
    assert f.effective_fit([]) is None


def test_single_observation_is_its_verdict():
    f = _fittings()
    assert f.effective_fit([{"verdict": "full", "by": "x", "method": "hand"}]) == "full"


def test_most_conservative_wins_over_a_permissive_measurement():
    """One credible 'this is worse than it looks' is never averaged away by a
    benchmark that did not exercise the failing path."""
    f = _fittings()
    observations = [
        {"verdict": "full", "by": "provider_verifier", "method": "measured"},
        {"verdict": "limited", "by": "darkxside", "method": "hand",
         "note": "requires adapter layer"},
    ]
    assert f.effective_fit(observations) == "limited"


def test_none_beats_everything():
    f = _fittings()
    observations = [
        {"verdict": "full", "method": "measured"},
        {"verdict": "none", "method": "hand"},
        {"verdict": "limited", "method": "hand"},
    ]
    assert f.effective_fit(observations) == "none"


def test_unknown_verdict_is_rejected_loudly():
    f = _fittings()
    try:
        f.effective_fit([{"verdict": "untested", "method": "hand"}])
    except ValueError as exc:
        assert "untested" in str(exc)
    else:
        raise AssertionError("an unknown verdict must raise, not resolve")
