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


# ---------------------------------------------------------------------------
# `delegate` must name a destination.
#
# Every other verdict picks a MODEL; delegate picks a SUBSTRATE. The spec says
# so ("the only value that must name a target"), but the loader accepted a
# destination-less delegate, so a router would have received a verdict that
# looked actionable and could not be honoured. Nothing is seeded with it yet,
# which is exactly why the requirement goes in now -- the ambiguity never gets
# into the data.
# ---------------------------------------------------------------------------

import pytest


def test_delegate_without_a_destination_is_rejected():
    f = _fittings()
    with pytest.raises(ValueError, match="must name where the work goes"):
        f.effective_fit([{"verdict": "delegate", "by": "x", "method": "hand"}])


@pytest.mark.parametrize("destination", ["", "   ", None, 42, ["pmoves-surf"]])
def test_delegate_destination_must_be_a_non_empty_string(destination):
    """An empty or wrongly-typed `to:` is the same failure as a missing one --
    it reaches the router as something it cannot dispatch on."""
    f = _fittings()
    with pytest.raises(ValueError, match="must name where the work goes"):
        f.effective_fit(
            [{"verdict": "delegate", "by": "x", "method": "hand", "to": destination}]
        )


def test_delegate_with_a_destination_resolves():
    f = _fittings()
    observations = [{"verdict": "delegate", "by": "x", "method": "hand",
                     "to": "pmoves-surf", "seam": "ctx.tools"}]
    assert f.effective_fit(observations) == "delegate"


def test_the_destination_requirement_does_not_leak_to_other_verdicts():
    """Only delegate routes off-substrate. Requiring `to:` of `full` would make
    every existing fitting invalid for a reason that does not apply to it."""
    f = _fittings()
    for verdict in ("none", "limited", "full"):
        assert f.effective_fit(
            [{"verdict": verdict, "by": "x", "method": "hand"}]
        ) == verdict


# ---------------------------------------------------------------------------
# An erased vocabulary must not read as a satisfied one.
# ---------------------------------------------------------------------------

def test_an_empty_role_vocabulary_is_rejected(tmp_path):
    """`roles: {}` used to load as `{}` and permit everything. Because every
    seeded fitting uses `*`, which resolve_role() honours without consulting the
    mapping, deleting the entire vocabulary left the registry gate exiting 0."""
    f = _fittings()
    path = tmp_path / "model-roles.yaml"
    path.write_text("roles: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="declares no roles"):
        f.load_roles(path)


def test_a_missing_roles_key_is_rejected(tmp_path):
    f = _fittings()
    path = tmp_path / "model-roles.yaml"
    path.write_text("# vocabulary accidentally removed\nother: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="declares no roles"):
        f.load_roles(path)


def test_a_malformed_role_entry_is_rejected(tmp_path):
    f = _fittings()
    path = tmp_path / "model-roles.yaml"
    path.write_text("roles:\n  code_review: 'a description string'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a mapping"):
        f.load_roles(path)


def test_a_non_list_supersedes_is_rejected(tmp_path):
    """A rename that does not parse is a routing outage that reads as a typo."""
    f = _fittings()
    path = tmp_path / "model-roles.yaml"
    path.write_text("roles:\n  code_review:\n    supersedes: debugging\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-list `supersedes`"):
        f.load_roles(path)


def test_the_real_vocabulary_still_loads():
    """The checks must reject erasure without rejecting the file that ships."""
    f = _fittings()
    roles = f.load_roles()
    assert len(roles) >= 8, f"only {len(roles)} roles loaded from the shipped file"
