"""runbook_drift's file-existence probe must look names up, not grep for mentions.

The v3 probe answered "does this referenced file exist?" with a CONTENT grep:
`git grep -l --fixed-strings <basename> origin/main --` returns every file whose
TEXT mentions the name, and the probe then reported the first hit as
"basename found on origin/main at: <that file>". That is a lie: the file it
named was a document that merely mentioned the tool, not the tool. Measured on
a fresh run, 47 of 57 UNDECIDED file_path claims had a file with that EXACT
NAME sitting in the tree, and in every one of those 47 the cited "evidence" was
a file that only mentioned the string.

These tests are hermetic: a throwaway git repo under tmp_path, one local git
process, no network, no NATS, no docker, no gh.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "runbook_drift.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True,
                   text=True, timeout=60)


def _fixture(tmp_path: Path) -> Path:
    """A repo where the tool exists and a doc merely talks about the tool."""
    repo = tmp_path / "repo"
    (repo / "some" / "dir").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "some" / "dir" / "tool.py").write_text("def main():\n    return 0\n")
    (repo / "docs" / "notes.md").write_text("Run `tool.py` before the show.\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "probe@example.invalid")
    _git(repo, "config", "user.name", "probe")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fixture")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


def _fixture_multi(tmp_path: Path) -> Path:
    """A repo where TWO different files carry the same name."""
    repo = tmp_path / "repo"
    (repo / "alpha").mkdir(parents=True)
    (repo / "beta").mkdir()
    (repo / "alpha" / "tool.py").write_text("alpha\n")
    (repo / "beta" / "tool.py").write_text("beta\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "probe@example.invalid")
    _git(repo, "config", "user.name", "probe")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fixture")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


def _load(monkeypatch, root: Path):
    monkeypatch.setenv("RUNBOOK_DRIFT_ROOT", str(root))
    spec = importlib.util.spec_from_file_location("runbook_drift_probe_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cited(evidence: str) -> list[str]:
    """The file paths the evidence claims to have found."""
    assert evidence.startswith("exists as "), evidence
    body = evidence[len("exists as "):].split(" (", 1)[0]
    return [c.strip() for c in body.split(",") if c.strip()]


def test_a_file_found_by_name_is_verified_and_named_in_the_evidence(monkeypatch, tmp_path):
    repo = _fixture(tmp_path)
    m = _load(monkeypatch, repo)
    verdict, evidence = m.probe_file("tool.py")
    assert verdict == "VERIFIED", evidence
    assert "some/dir/tool.py" in evidence
    assert "notes.md" not in evidence


def test_the_evidence_cites_a_file_named_after_the_claim_not_a_file_that_mentions_it(
        monkeypatch, tmp_path):
    """Regression ratchet: the content grep cited a file that merely mentioned
    the name. Every cited path must be a real file whose NAME is the claim."""
    repo = _fixture(tmp_path)
    m = _load(monkeypatch, repo)
    _verdict, evidence = m.probe_file("tool.py")
    cited = _cited(evidence)
    assert cited, evidence
    for path in cited:
        assert Path(path).name.casefold() == "tool.py", evidence
        assert (repo / path).is_file(), evidence
    assert "notes.md" not in evidence, evidence


def test_a_claim_that_names_nothing_is_drifted(monkeypatch, tmp_path):
    repo = _fixture(tmp_path)
    m = _load(monkeypatch, repo)
    verdict, _evidence = m.probe_file("nope.py")
    assert verdict == "DRIFTED"


def test_an_exact_path_present_locally_is_verified(monkeypatch, tmp_path):
    repo = _fixture(tmp_path)
    m = _load(monkeypatch, repo)
    verdict, evidence = m.probe_file("some/dir/tool.py")
    assert verdict == "VERIFIED", evidence
    assert evidence.startswith("exists: ")


def test_an_exact_path_only_on_origin_main_is_undecided_as_a_stale_checkout(
        monkeypatch, tmp_path):
    repo = _fixture(tmp_path)
    later = repo / "later" / "added.py"
    later.parent.mkdir()
    later.write_text("added later\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "later")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    later.unlink()
    m = _load(monkeypatch, repo)
    verdict, evidence = m.probe_file("later/added.py")
    assert verdict == "UNDECIDED", evidence
    assert "stale local checkout" in evidence


def test_several_files_sharing_the_name_are_all_named_in_the_evidence(monkeypatch, tmp_path):
    repo = _fixture_multi(tmp_path)
    m = _load(monkeypatch, repo)
    verdict, evidence = m.probe_file("tool.py")
    assert verdict == "VERIFIED", evidence
    assert "alpha/tool.py" in evidence
    assert "beta/tool.py" in evidence


def test_the_probe_never_answers_a_path_question_with_a_content_grep(monkeypatch, tmp_path):
    """Regression ratchet: `git grep -l <name>` searches file CONTENT.

    Any command that greps the tree for the basename is a content query, so the
    probe cannot be answering "does a file with this NAME exist?" with it. This
    assertion holds on every platform, including ones where the grep branch
    fails loudly instead of lying.
    """
    repo = _fixture(tmp_path)
    m = _load(monkeypatch, repo)
    commands: list[str] = []
    real_sh = m.sh

    def recording_sh(cmd, timeout=20, cwd=None):
        commands.append(cmd)
        return real_sh(cmd, timeout=timeout, cwd=cwd)

    monkeypatch.setattr(m, "sh", recording_sh)
    m.probe_file("tool.py")
    assert commands, "the probe ran no commands at all"
    for cmd in commands:
        assert "git grep" not in cmd, f"content grep in probe command: {cmd}"


def test_the_evidence_names_the_file_relative_to_the_probed_root(monkeypatch, tmp_path):
    """The evidence path must be relative to the audited root, so it can be
    opened from there -- the same frame the claim was written in."""
    repo = _fixture(tmp_path)
    m = _load(monkeypatch, repo)
    _verdict, evidence = m.probe_file("tool.py")
    for path in _cited(evidence):
        assert not Path(path).is_absolute(), evidence
        assert (repo / path).is_file(), evidence


def test_a_claim_with_a_directory_cites_the_file_whose_path_ends_that_way(
        monkeypatch, tmp_path):
    """`dir/tool.py` should cite `some/dir/tool.py`, not an unrelated tool.py."""
    repo = _fixture(tmp_path)
    (repo / "other").mkdir()
    (repo / "other" / "tool.py").write_text("other\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "other")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    m = _load(monkeypatch, repo)
    verdict, evidence = m.probe_file("dir/tool.py")
    assert verdict == "VERIFIED", evidence
    cited = _cited(evidence)
    assert cited, evidence
    assert cited[0] == "some/dir/tool.py", evidence


def test_a_name_match_respects_path_boundaries(monkeypatch, tmp_path):
    """`tool.py` must not be satisfied by a file named `mytool.py`, and the
    suffix preference must not treat `mytool.py` as ending with `tool.py`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "mytool.py").write_text("decoy\n")
    m = _load(monkeypatch, repo)
    assert m._paths_named(["mytool.py", "some/tool.py"], "tool.py") == ["some/tool.py"]


# --------------------------------------------------------------------------
# The SHAPE of the claim decides how it may be matched. A bare basename may
# match any file of that name; a PATH claim may only match a path ending that
# way. Matching a path claim on its basename alone let 210 unrelated
# README.md files satisfy `PMOVES-Archon/README.md`.
# --------------------------------------------------------------------------

def test_a_path_claim_is_not_satisfied_by_an_unrelated_file_of_the_same_name(
        monkeypatch, tmp_path):
    """Regression ratchet: a PATH claim must not be resolved by basename.

    The claim names a directory, so the directory is part of the claim. A
    file elsewhere that merely shares the basename is a DIFFERENT artefact.
    """
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "README.md").write_text("unrelated readme\n")
    m = _load(monkeypatch, repo)
    verdict, evidence = m.probe_file("PMOVES-Archon/README.md")
    assert verdict != "VERIFIED", evidence
    assert "docs/README.md" not in evidence, evidence


def test_a_path_claim_that_names_a_real_directory_is_verified(monkeypatch, tmp_path):
    """The positive half: a PATH claim that DOES end that way is VERIFIED and
    cites the file whose path ends that way."""
    repo = tmp_path / "repo"
    (repo / "some" / "dir").mkdir(parents=True)
    (repo / "some" / "dir" / "tool.py").write_text("x\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "probe@example.invalid")
    _git(repo, "config", "user.name", "probe")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fixture")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    m = _load(monkeypatch, repo)
    verdict, evidence = m.probe_file("some/dir/tool.py")
    assert verdict == "VERIFIED", evidence
    assert "some/dir/tool.py" in evidence


def test_a_path_claim_into_a_submodule_is_undecided_not_drifted(monkeypatch, tmp_path):
    """A submodule's files live in ANOTHER repository. The parent tree records
    a gitlink, so their absence proves nothing — the verdict is UNDECIDED."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitmodules").write_text(
        '[submodule "PMOVES-Archon"]\n'
        "\tpath = PMOVES-Archon\n"
        "\turl = https://github.com/POWERFULMOVES/PMOVES-Archon.git\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "README.md").write_text("unrelated\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "probe@example.invalid")
    _git(repo, "config", "user.name", "probe")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fixture")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    m = _load(monkeypatch, repo)
    verdict, evidence = m.probe_file("PMOVES-Archon/README.md")
    assert verdict == "UNDECIDED", evidence
    assert "submodule" in evidence, evidence


def test_a_git_ignored_path_claim_is_undecided_not_drifted(monkeypatch, tmp_path):
    """A git-ignored path is a LOCAL artifact: absent from the tree by design,
    so its absence says nothing about whether the doc is wrong."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text(".kilocode/*\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "probe@example.invalid")
    _git(repo, "config", "user.name", "probe")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fixture")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    m = _load(monkeypatch, repo)
    verdict, evidence = m.probe_file(".kilocode/mcp.json")
    assert verdict == "UNDECIDED", evidence
    assert "git-ignored" in evidence, evidence


def test_a_genuinely_absent_path_claim_is_drifted(monkeypatch, tmp_path):
    """The negative control for the two UNDECIDED branches above: a path that
    is not in a submodule and is not git-ignored, and does not exist, IS drift."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "keep.txt").write_text("x\n")  # git needs something to commit
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "probe@example.invalid")
    _git(repo, "config", "user.name", "probe")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fixture")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    m = _load(monkeypatch, repo)
    verdict, evidence = m.probe_file("pmoves/chit/bundles/nope.signed.json")
    assert verdict == "DRIFTED", evidence
