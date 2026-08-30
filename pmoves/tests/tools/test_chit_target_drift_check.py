"""Tests for the github_secret target-drift check.

The bug that motivated it: `minimax_token_plan_api_key` declares
`github_secret: MINIMAX_API_KEY` -- routing the token-plan credential to the
pay-as-you-go secret name. That is issue #2748's defect reproduced in the
manifest, and nothing surfaced it.

The tests that matter are the two that keep the check honest in opposite
directions: an undeclared divergence must FAIL (or the misroute stays
invisible), and a declared one must PASS (or the tool rewrites a deliberate
alias, which is what a naive `target == label` rule would have done to
`service_password_postgres`).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "tools" / "chit_target_drift_check.py"

spec = importlib.util.spec_from_file_location("chit_target_drift_check", MODULE)
assert spec and spec.loader
drift = importlib.util.module_from_spec(spec)
sys.modules["chit_target_drift_check"] = drift
spec.loader.exec_module(drift)


def _manifest(tmp_path: Path, entries) -> Path:
    path = tmp_path / "m.yaml"
    path.write_text(yaml.safe_dump({"secrets": entries}), encoding="utf-8")
    return path


def _entry(eid: str, label: str, github_secret: str | None):
    targets = [{"file": ".env.generated", "key": label}]
    if github_secret:
        targets.append({"github_secret": github_secret})
    return {"id": eid, "source": {"label": label}, "targets": targets}


def _accepted(tmp_path: Path, rows) -> Path:
    path = tmp_path / "a.yaml"
    path.write_text(yaml.safe_dump({"accepted": rows}), encoding="utf-8")
    return path


def _run(tmp_path, entries, accepted_rows=None, argv=()):
    m = _manifest(tmp_path, entries)
    a = _accepted(tmp_path, accepted_rows or [])
    return drift.main(["--manifest", str(m), "--accepted", str(a), *argv])


def test_matching_targets_pass(tmp_path):
    assert _run(tmp_path, [_entry("a", "A_KEY", "A_KEY")]) == 0


def test_an_entry_with_no_github_target_is_not_drift(tmp_path):
    """52 entries carry no github_secret at all. Absence is not divergence."""
    assert _run(tmp_path, [_entry("a", "A_KEY", None)]) == 0


def test_an_undeclared_divergence_fails(tmp_path, capsys):
    """The MiniMax case. Without this the misroute stays invisible."""
    assert _run(tmp_path, [_entry("minimax_token_plan_api_key",
                                  "MINIMAX_TOKEN_PLAN_API_KEY", "MINIMAX_API_KEY")]) == 1
    err = capsys.readouterr().err
    assert "UNDECLARED" in err
    assert "MINIMAX_TOKEN_PLAN_API_KEY" in err and "MINIMAX_API_KEY" in err


def test_a_declared_divergence_passes(tmp_path, capsys):
    """The alias case. A naive `target == label` rule would have rewritten
    service_password_postgres and broken an existing secret."""
    rc = _run(
        tmp_path,
        [_entry("service_password_postgres", "SUPABASE_DB_PASSWORD", "SERVICE_PASSWORD_POSTGRES")],
        [{"entry": "service_password_postgres",
          "github_secret": "SERVICE_PASSWORD_POSTGRES",
          "reason": "stored under the owning service's name"}],
    )
    assert rc == 0
    assert "accepted" in capsys.readouterr().out


def test_an_acceptance_is_scoped_to_its_own_target(tmp_path):
    """Negative control. Accepting one divergence must not excuse another --
    otherwise a single recorded alias would blanket-approve every misroute."""
    rc = _run(
        tmp_path,
        [_entry("other", "OTHER_KEY", "WRONG_KEY")],
        [{"entry": "service_password_postgres",
          "github_secret": "SERVICE_PASSWORD_POSTGRES", "reason": "unrelated"}],
    )
    assert rc == 1


def test_an_acceptance_naming_a_different_secret_does_not_apply(tmp_path):
    """Same entry, different target name: still undeclared. The key is the
    PAIR, so re-pointing a target does not inherit the old approval."""
    rc = _run(
        tmp_path,
        [_entry("e", "LABEL_A", "TARGET_NOW")],
        [{"entry": "e", "github_secret": "TARGET_BEFORE", "reason": "stale"}],
    )
    assert rc == 1


def test_an_unreadable_manifest_is_unmeasured(tmp_path):
    assert drift.main(["--manifest", str(tmp_path / "absent.yaml")]) == 3


def test_a_manifest_with_no_entries_is_unmeasured(tmp_path):
    """Reporting "no drift" because nothing parsed is worse than no check."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"version": 1}), encoding="utf-8")
    assert drift.main(["--manifest", str(bad)]) == 3


def test_a_missing_accepted_file_is_not_an_error(tmp_path):
    """No acceptances recorded yet is a valid state -- it just means every
    divergence must be declared before it can pass."""
    m = _manifest(tmp_path, [_entry("a", "A_KEY", "A_KEY")])
    assert drift.main(["--manifest", str(m), "--accepted", str(tmp_path / "none.yaml")]) == 0


def test_json_mode_separates_declared_from_undeclared(tmp_path, capsys):
    _run(
        tmp_path,
        [_entry("ok", "K", "K"),
         _entry("alias", "L", "L_ALIAS"),
         _entry("bad", "M", "N")],
        [{"entry": "alias", "github_secret": "L_ALIAS", "reason": "deliberate"}],
        argv=["--json"],
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["with_github_target"] == 3
    assert [r["entry"] for r in payload["undeclared"]] == ["bad"]
    assert [r["entry"] for r in payload["declared"]] == ["alias"]


def test_the_real_manifest_has_exactly_the_two_known_divergences():
    """Anchored to the live tree, so a NEW drift shows up here as a failure
    rather than being absorbed into a count nobody reads."""
    entries = drift.load_entries()
    found = {(eid, secret) for eid, _label, secret in drift.find_divergence(entries)}
    assert found == {
        ("minimax_token_plan_api_key", "MINIMAX_API_KEY"),
        ("service_password_postgres", "SERVICE_PASSWORD_POSTGRES"),
    }, f"github_secret drift changed: {found}"
