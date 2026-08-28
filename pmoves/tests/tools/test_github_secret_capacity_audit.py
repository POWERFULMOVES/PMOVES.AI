"""Offline tests for the GitHub secret capacity reconciliation.

`gh` is stubbed, so these run with no network and no auth. What is under test is
the verdict logic and — above all — that an unmeasurable scope exits 3 rather
than 0.

Context: GitHub caps secrets at 100 PER SCOPE (repository, and each environment
separately). Nothing compared the CHIT manifest's declarations against that
ceiling, so the funnel could declare more than the platform can store and report
success throughout. Measured 2026-08-28: 158 declared, Prod at 100/100.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "tools" / "github_secret_capacity_audit.py"

spec = importlib.util.spec_from_file_location("github_secret_capacity_audit", MODULE)
assert spec and spec.loader
aud = importlib.util.module_from_spec(spec)
sys.modules["github_secret_capacity_audit"] = aud
spec.loader.exec_module(aud)


def _manifest(tmp_path: Path, names: list[str]) -> Path:
    path = tmp_path / "secrets_manifest_v2.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "secrets": [
                    {"id": n.lower(), "targets": [{"github_secret": n}]} for n in names
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _present(monkeypatch, names: list[str]):
    monkeypatch.setattr(aud, "_gh", lambda *a, **k: "\n".join(names) + "\n")


def test_a_clean_scope_passes(monkeypatch, tmp_path):
    _present(monkeypatch, ["A", "B"])
    assert aud.main(["--manifest", str(_manifest(tmp_path, ["A", "B"]))]) == 0


def test_an_absent_declared_secret_is_a_finding(monkeypatch, tmp_path, capsys):
    _present(monkeypatch, ["A"])
    assert aud.main(["--manifest", str(_manifest(tmp_path, ["A", "B"]))]) == 1
    assert "absent" in capsys.readouterr().err


def test_an_orphan_is_a_finding(monkeypatch, tmp_path, capsys):
    """Present in GitHub, declared nowhere — unmanaged, and free headroom."""
    _present(monkeypatch, ["A", "STRAY"])
    assert aud.main(["--manifest", str(_manifest(tmp_path, ["A"]))]) == 1
    err = capsys.readouterr().err
    assert "orphans" in err and "STRAY" in err


def test_declaring_more_than_the_ceiling_is_reported(monkeypatch, tmp_path, capsys):
    """The finding that motivated this tool.

    101 declared names cannot all exist in a 100-secret scope. Without this the
    funnel pushes until GitHub refuses and the excess is simply never stored.
    """
    names = [f"S{i:03d}" for i in range(aud.SECRET_LIMIT + 1)]
    _present(monkeypatch, names[: aud.SECRET_LIMIT])
    assert aud.main(["--manifest", str(_manifest(tmp_path, names))]) == 1
    assert "OVER CAPACITY by 1" in capsys.readouterr().err


def test_exactly_at_the_ceiling_is_not_over_capacity(monkeypatch, tmp_path):
    """Negative control: 100 declared into a 100 scope is full, not over."""
    names = [f"S{i:03d}" for i in range(aud.SECRET_LIMIT)]
    _present(monkeypatch, names)
    assert aud.main(["--manifest", str(_manifest(tmp_path, names))]) == 0


def test_headroom_is_reported_against_the_limit(monkeypatch, tmp_path, capsys):
    _present(monkeypatch, ["A", "B"])
    aud.main(["--manifest", str(_manifest(tmp_path, ["A", "B"])), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["limit"] == 100
    assert payload["headroom"] == 98


def test_the_environment_scope_is_addressed_separately(monkeypatch, tmp_path):
    """Repository and each environment have their OWN 100. The endpoint differs,
    and auditing the wrong one would report another scope's usage."""
    seen = {}

    def fake(*args, **kwargs):
        seen["endpoint"] = args[2]
        return "A\n"

    monkeypatch.setattr(aud, "_gh", fake)
    aud.main(["--manifest", str(_manifest(tmp_path, ["A"])), "--env", "Prod"])
    assert seen["endpoint"].endswith("/environments/Prod/secrets")


def test_the_listing_is_paginated(monkeypatch, tmp_path):
    """The API pages at 30. A truncated read under-reports usage and
    over-reports absences — which is exactly how a first pass at this
    measurement produced 157 of 158 'missing'."""
    seen = {}

    def fake(*args, **kwargs):
        seen["args"] = args
        return "A\n"

    monkeypatch.setattr(aud, "_gh", fake)
    aud.main(["--manifest", str(_manifest(tmp_path, ["A"]))])
    assert "--paginate" in seen["args"]


def test_no_gh_is_unmeasured_not_a_pass(monkeypatch, tmp_path):
    monkeypatch.setattr(aud.shutil, "which", lambda _: None)
    assert aud.main(["--manifest", str(_manifest(tmp_path, ["A"]))]) == 3


def test_an_unreadable_manifest_is_unmeasured(monkeypatch, tmp_path):
    _present(monkeypatch, ["A"])
    assert aud.main(["--manifest", str(tmp_path / "absent.yaml")]) == 3


def test_a_manifest_with_no_targets_is_unmeasured(monkeypatch, tmp_path):
    """An empty declaration set would make every present secret an 'orphan'.

    Reporting 100 orphans because the manifest failed to parse would be a
    confident wrong answer; refusing to answer is correct.
    """
    _present(monkeypatch, ["A"])
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"version": 1}), encoding="utf-8")
    assert aud.main(["--manifest", str(bad)]) == 3


def test_json_mode_distinguishes_unmeasured_from_clean(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(aud.shutil, "which", lambda _: None)
    aud.main(["--manifest", str(_manifest(tmp_path, ["A"])), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["measured"] is False
