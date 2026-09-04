"""Tests for tools/chit_provenance_check.py.

The check exists because the two EXISTING warnings are rotate-triggered, so the
thing most worth pinning is that this one answers without a rotate, without a
network, and without printing a secret value.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load():
    path = _ROOT / "pmoves" / "tools" / "chit_provenance_check.py"
    spec = importlib.util.spec_from_file_location("chit_provenance_check", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cpc = _load()


def _bundle(tmp_path: Path, labels=("A_KEY", "B_KEY"), values=("s3cr3t", "hunter2")):
    p = tmp_path / "env.cgp.json"
    p.write_text(
        json.dumps(
            {
                "version": "cgp-1",
                "namespace": "pmoves",
                "points": [
                    {"label": lbl, "value": val, "anchor": 0, "encoding": "hex"}
                    for lbl, val in zip(labels, values)
                ],
            }
        ),
        encoding="utf-8",
    )
    return p


# --------------------------------------------------------------------------
# Where the bundle lives
# --------------------------------------------------------------------------


def test_an_explicit_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("CHIT_EXPORT_PATH", str(tmp_path / "elsewhere.json"))
    assert cpc.default_bundle() == tmp_path / "elsewhere.json"


def test_the_default_path_mirrors_the_makefile(monkeypatch):
    """codex.mk:4-6 puts it under APPDATA on Windows and XDG_CONFIG_HOME
    otherwise. Duplicated in the tool on purpose -- asking a Makefile where its
    own secrets live is a dependency on the thing being diagnosed -- so the
    duplication needs a test holding the two together."""
    monkeypatch.delenv("CHIT_EXPORT_PATH", raising=False)
    got = cpc.default_bundle()
    assert got.name == "env.cgp.json"
    assert got.parent.name == "chit"
    assert got.parent.parent.name == "pmoves"


# --------------------------------------------------------------------------
# The three states
# --------------------------------------------------------------------------


def test_a_missing_bundle_is_reported_and_gated(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["x", "--bundle", str(tmp_path / "nope.json"), "--offline", "--strict"],
    )
    assert cpc.main() == 1
    assert "ABSENT" in capsys.readouterr().out


def test_a_ci_pulled_bundle_passes_even_under_strict(tmp_path, monkeypatch, capsys):
    """The marker is the whole signal: with it, the prod-only keys are present
    and there is nothing to warn about."""
    b = _bundle(tmp_path)
    Path(str(b) + ".provenance").write_text("run=123\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["x", "--bundle", str(b), "--offline", "--strict"])
    assert cpc.main() == 0
    out = capsys.readouterr().out
    assert "CI-pulled" in out
    assert "LOCAL EXPORT" not in out


def test_a_local_export_is_advisory_by_default_and_gated_under_strict(
    tmp_path, monkeypatch, capsys
):
    """Advisory by default because env-check calls it, and a fleet's routine
    environment validation must not fail on a node that simply has not pulled."""
    b = _bundle(tmp_path)
    monkeypatch.setattr("sys.argv", ["x", "--bundle", str(b), "--offline"])
    assert cpc.main() == 0
    assert "LOCAL EXPORT" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["x", "--bundle", str(b), "--offline", "--strict"])
    assert cpc.main() == 1


# --------------------------------------------------------------------------
# Safe to run in a transcript
# --------------------------------------------------------------------------


def test_it_never_prints_a_value_from_the_bundle(tmp_path, monkeypatch, capsys):
    """It reads a file full of secrets. Printing NAMES is the point; printing
    values would make the diagnostic unusable in the place the fault appears."""
    b = _bundle(tmp_path, labels=("TOKEN_A",), values=("SUPERSECRETVALUE",))
    monkeypatch.setattr("sys.argv", ["x", "--bundle", str(b), "--offline"])
    cpc.main()
    assert "SUPERSECRETVALUE" not in capsys.readouterr().out


def test_offline_makes_no_subprocess_call_for_the_artifact(monkeypatch):
    called = []
    monkeypatch.setattr(cpc.subprocess, "run", lambda *a, **k: called.append(a))
    assert "not checked" in cpc.recovery_window("z890", offline=True)
    assert called == [], "--offline still reached for the network"


# --------------------------------------------------------------------------
# Reporting a failure usefully
# --------------------------------------------------------------------------


def test_a_projection_failure_names_the_cause_not_the_traceback_header(
    tmp_path, monkeypatch
):
    """A python traceback's FIRST line is 'Traceback (most recent call last):'
    -- true of every failure and therefore useless. The cause is on the last
    line. Measured: through `make`, CODEX_PY has no PyYAML, and the first
    version of this reported the header, which named nothing actionable."""

    class _R:
        returncode = 1
        stdout = ""
        stderr = (
            "Traceback (most recent call last):\n"
            '  File "secrets_sync.py", line 12, in <module>\n'
            "    import yaml\n"
            "ModuleNotFoundError: No module named 'yaml'\n"
        )

    monkeypatch.setattr(cpc.subprocess, "run", lambda *a, **k: _R())
    n, names, err = cpc.audit_missing(tmp_path / "b.json")
    assert n == -1 and names == []
    assert "ModuleNotFoundError" in err
    assert "Traceback" not in err


def test_the_missing_list_is_parsed_from_the_existing_projection(tmp_path, monkeypatch):
    """It must NOT re-derive which keys matter -- that projection already exists
    as `make manifest-audit`, and a second implementation would drift."""

    class _R:
        returncode = 0
        stdout = "WARNING: Missing secrets (non-fatal): A_KEY, B_KEY, C_KEY\n"
        stderr = ""

    monkeypatch.setattr(cpc.subprocess, "run", lambda *a, **k: _R())
    n, names, err = cpc.audit_missing(tmp_path / "b.json")
    assert err == ""
    assert n == 3
    assert names == ["A_KEY", "B_KEY", "C_KEY"]


@pytest.mark.parametrize(
    "window,expect_producer",
    [
        ("EXPIRED -- newest run 1 has no unexpired chit-bundle-* (1-day retention)", True),
        ("NO successful producer run found at all", True),
        ("OK -- an unexpired artifact for 'z890' exists (run 1)", False),
        # ANOTHER NODE'S bundle is recoverable: pull_chit_bundle.sh falls back
        # to any unexpired chit-bundle-*. An earlier version treated this as
        # unrecoverable and sent the operator to dispatch a workflow that was
        # not needed -- a false alarm costing a CI run, on an advisory whose
        # only real currency is being believed.
        ("OK -- no artifact for 'z890', but 2 other unexpired bundle(s) exist "
         "and the puller falls back to them (run 1)", False),
        ("not checked (--offline)", False),
        ("not checked (gh unavailable or unauthenticated)", False),
    ],
)
def test_the_producer_command_appears_only_when_pulling_cannot_work(
    tmp_path, monkeypatch, capsys, window, expect_producer
):
    """The 24-hour shelf life is the finding. When the artifact is gone,
    `secrets-pull` alone is the WRONG instruction -- it will fail, and an
    operator hits that at the worst moment. When it is still alive, printing
    the workflow-dispatch line would be noise."""
    b = _bundle(tmp_path)
    monkeypatch.setattr(cpc, "recovery_window", lambda node, offline: window)
    monkeypatch.setattr(cpc, "audit_missing", lambda bundle: (0, [], ""))
    monkeypatch.setattr("sys.argv", ["x", "--bundle", str(b), "--node", "z890"])
    cpc.main()
    out = capsys.readouterr().out
    assert ("secrets-sync-trigger" in out) is expect_producer
    assert "secrets-pull" in out, "the restore road is always worth naming"


def test_the_dispatch_target_is_the_producer_not_this_node(tmp_path, monkeypatch, capsys):
    """Pattern-B nodes are CONSUMERS with no self-hosted runner, and
    sync-secrets-local.yml schedules on one -- so `-f targets=z890` names a job
    nothing can pick up. pull_chit_bundle.sh:27 already draws the distinction as
    PMOVES_BUNDLE_PRODUCER (default b850); the same default is used here so the
    two roads cannot disagree about who can produce."""
    b = _bundle(tmp_path)
    monkeypatch.setattr(
        cpc, "recovery_window",
        lambda node, offline: "EXPIRED -- newest run 1 has no unexpired chit-bundle-*",
    )
    monkeypatch.setattr(cpc, "audit_missing", lambda bundle: (0, [], ""))
    monkeypatch.setattr("sys.argv", ["x", "--bundle", str(b), "--node", "z890"])
    cpc.main()
    out = capsys.readouterr().out
    assert "TARGETS=b850" in out
    assert "TARGETS=z890" not in out, "dispatched at a node with no runner"


def test_an_absent_bundle_still_reports_recoverability(tmp_path, monkeypatch, capsys):
    """The one case where the operator has NO bundle is the worst place to be
    told to run a command that will fail. An earlier version returned before
    checking, so `secrets-pull` was the only instruction offered even when the
    artifact behind it had expired."""
    monkeypatch.setattr(
        cpc, "recovery_window",
        lambda node, offline: "EXPIRED -- newest run 1 has no unexpired chit-bundle-*",
    )
    monkeypatch.setattr(
        "sys.argv", ["x", "--bundle", str(tmp_path / "gone.json"), "--node", "z890"]
    )
    cpc.main()
    out = capsys.readouterr().out
    assert "recovery" in out
    assert "will fail as things stand" in out
    assert "TARGETS=b850" in out


def test_an_absent_bundle_does_not_cry_wolf_when_a_pull_would_work(
    tmp_path, monkeypatch, capsys
):
    """Bound on the test above."""
    monkeypatch.setattr(
        cpc, "recovery_window",
        lambda node, offline: "OK -- an unexpired artifact for 'z890' exists (run 1)",
    )
    monkeypatch.setattr(
        "sys.argv", ["x", "--bundle", str(tmp_path / "gone.json"), "--node", "z890"]
    )
    cpc.main()
    out = capsys.readouterr().out
    assert "secrets-pull" in out
    assert "secrets-sync-trigger" not in out


def test_it_honours_the_repo_override_the_puller_honours(monkeypatch):
    """pull_chit_bundle.sh:21 reads PMOVES_REPO. Hard-coding it here meant a node
    with the override set would have its artifact checked against upstream while
    `secrets-pull` queried the fork -- reporting a live artifact the pull could
    not find, or demanding a producer run the overridden repo already had."""
    monkeypatch.setenv("PMOVES_REPO", "SOMEONE/ELSE")
    assert _load().REPO == "SOMEONE/ELSE"
    monkeypatch.delenv("PMOVES_REPO", raising=False)
    assert _load().REPO == "POWERFULMOVES/PMOVES.AI"


def test_the_override_reaches_the_actual_query(monkeypatch):
    """The constant is not the contract -- the query is."""
    monkeypatch.setenv("PMOVES_REPO", "SOMEONE/ELSE")
    mod = _load()
    seen = []

    class _R:
        returncode = 1
        stdout = ""
        stderr = ""

    monkeypatch.setattr(mod.subprocess, "run", lambda cmd, *a, **k: (seen.append(cmd), _R())[1])
    mod.recovery_window("z890", offline=False)
    assert any("SOMEONE/ELSE" in " ".join(c) for c in seen), seen


def test_the_dispatch_is_a_known_road_not_a_raw_gh_call(tmp_path, monkeypatch, capsys):
    """Routed through `make secrets-sync-trigger` (infra.mk:314) rather than a
    raw `gh workflow run`.

    NOTE the reviewer's stated reason -- that damage-control intercepts raw
    dispatches -- did NOT reproduce: the hook returns 0 for that command on this
    node. The recommendation still stands on the better ground that the make
    target is the Known Road and does more than the raw call, waiting for the
    run to start and reporting it."""
    b = _bundle(tmp_path)
    monkeypatch.setattr(
        cpc, "recovery_window",
        lambda node, offline: "EXPIRED -- newest run 1 has no unexpired chit-bundle-*",
    )
    monkeypatch.setattr(cpc, "audit_missing", lambda bundle: (0, [], ""))
    monkeypatch.setattr("sys.argv", ["x", "--bundle", str(b), "--node", "z890"])
    cpc.main()
    printed = capsys.readouterr().out
    assert "make -C pmoves secrets-sync-trigger" in printed
    assert "gh workflow run" not in printed
