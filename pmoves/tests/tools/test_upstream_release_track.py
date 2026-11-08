"""upstream_release_track: containment decides the exit code; bad data is could-not-measure."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "tools" / "upstream_release_track.py"
_spec = importlib.util.spec_from_file_location("upstream_release_track", _PATH)
urt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(urt)

TAG_SHA = "a" * 40
FORK_SHA = "b" * 40


def _fake_gh(tag="v0.11.1", compare="ahead", fork_sha=FORK_SHA):
    def gh(path, jq):
        if path.endswith("/releases/latest"):
            return tag
        if "/commits/" in path:
            return TAG_SHA
        if "/git/ref/heads/" in path:
            return fork_sha
        if "/compare/" in path:
            return compare
        raise AssertionError(path)
    return gh


def _run(monkeypatch, capsys, **kw):
    monkeypatch.setattr(urt, "gh", _fake_gh(**kw))
    monkeypatch.setattr(urt.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setattr(sys, "argv", ["x", "archon"])
    rc = urt.main()
    return rc, capsys.readouterr()


@pytest.mark.parametrize("compare,rc,contains", [
    ("ahead", 0, "yes"), ("identical", 0, "yes"),
    ("diverged", 1, "no"), ("behind", 1, "no"),
])
def test_containment_drives_exit_code(monkeypatch, capsys, compare, rc, contains):
    got, out = _run(monkeypatch, capsys, compare=compare)
    assert got == rc
    assert f"CONTAINS_RELEASE={contains}" in out.out
    assert "RELEASE_VERSION=0.11.1" in out.out


def test_unsafe_tag_is_could_not_measure(monkeypatch, capsys):
    got, out = _run(monkeypatch, capsys, tag="v1;rm -x")
    assert got == 3
    assert "COULD-NOT-MEASURE" in out.err
    assert out.out == ""


def test_malformed_sha_is_could_not_measure(monkeypatch, capsys):
    got, _ = _run(monkeypatch, capsys, fork_sha="not-a-sha")
    assert got == 3


def test_missing_gh_is_could_not_measure(monkeypatch, capsys):
    monkeypatch.setattr(urt.shutil, "which", lambda _: None)
    monkeypatch.setattr(sys, "argv", ["x", "agent-zero"])
    assert urt.main() == 3


@pytest.mark.parametrize("tag", ["-v1", "v1..2", "v1/../x", "v1\n"])
def test_tag_rejects_leading_dash_dotdot_slash_newline(monkeypatch, capsys, tag):
    got, out = _run(monkeypatch, capsys, tag=tag)
    assert got == 3 and out.out == ""
