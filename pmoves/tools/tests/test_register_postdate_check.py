"""Tests for register_postdate_check.

WRITTEN AGAINST A REAL COMMIT GRAPH, not against a mocked one. The whole check
is a comparison between a row's own text and a commit's author time, so a test
that fakes the commit tests nothing that could break.

Each test builds a throwaway repo and commits with an explicit
GIT_AUTHOR_DATE, which is the only way to construct the postdated case
deliberately -- the tool is otherwise correct on every row it can normally see.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "register_postdate_check.py"
REGISTER_REL = "pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md"


def _load():
    spec = importlib.util.spec_from_file_location("register_postdate_check", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "scratch"
    (root / "pmoves" / "docs" / "AGENTS").mkdir(parents=True)
    (root / REGISTER_REL).write_text("# register\n", encoding="utf-8")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, env={**env, "PATH": "/usr/bin:/bin"})
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "seed"],
                   check=True, env={**env, "PATH": "/usr/bin:/bin"})
    return root


def _commit_row(repo: Path, row: str, author_date: str) -> None:
    with (repo / REGISTER_REL).open("a", encoding="utf-8") as fh:
        fh.write(row + "\n")
    env = {"PATH": "/usr/bin:/bin",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e",
           "GIT_AUTHOR_DATE": author_date, "GIT_COMMITTER_DATE": author_date}
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "row"],
                   check=True, env=env)


ROW = "- `{ts}` CLAIM `B850-CLAUDE (Knuckles)` branch: `fix/x` · scope: demo."


def _run(mod, repo: Path) -> tuple[list, list]:
    mod.set_repo(repo)
    revs = mod._git("rev-list", "--reverse", "HEAD~1..HEAD").split()
    return mod.check(revs)


def test_row_before_its_commit_is_clean(repo: Path) -> None:
    mod = _load()
    _commit_row(repo, ROW.format(ts="2026-09-02T11:00:00Z"),
                "2026-09-02T11:05:00+00:00")
    findings, unmeasured = _run(mod, repo)
    assert findings == []
    assert unmeasured == []


def test_row_equal_to_its_commit_is_clean(repo: Path) -> None:
    """The invariant is `<=`, not `<`. A row filed in the same second as the
    commit is the BEST case, and a strict `<` would fail exactly the rows the
    sanctioned tool produces when a commit follows immediately."""
    mod = _load()
    _commit_row(repo, ROW.format(ts="2026-09-02T11:00:00Z"),
                "2026-09-02T11:00:00+00:00")
    findings, _ = _run(mod, repo)
    assert findings == []


def test_postdated_row_is_a_finding(repo: Path) -> None:
    mod = _load()
    _commit_row(repo, ROW.format(ts="2026-09-02T16:05:00Z"),
                "2026-09-02T11:00:00+00:00")
    findings, _ = _run(mod, repo)
    assert len(findings) == 1
    assert "POSTDATED by 5h05m" in findings[0]
    assert "B850-CLAUDE (Knuckles)" in findings[0]


def test_offset_timestamps_compare_in_utc(repo: Path) -> None:
    """`2026-09-02T07:10:26-04:00` is 11:10:26Z. Comparing the wall-clock text
    instead of the instant would call this postdated by four hours."""
    mod = _load()
    _commit_row(repo, ROW.format(ts="2026-09-02T07:10:26-04:00"),
                "2026-09-02T11:10:46+00:00")
    findings, unmeasured = _run(mod, repo)
    assert findings == [] and unmeasured == []


def test_non_claim_kinds_are_checked_too(repo: Path) -> None:
    """A postdated RELEASE is exactly as wrong as a postdated CLAIM, and
    lateness is computed from both."""
    mod = _load()
    _commit_row(
        repo,
        "- `2026-09-02T20:00:00Z` RELEASE `4090-CLAUDE` scope: done.",
        "2026-09-02T11:00:00+00:00",
    )
    findings, _ = _run(mod, repo)
    assert len(findings) == 1 and "RELEASE" in findings[0]


def test_unparseable_timestamp_is_unmeasured_not_clean(repo: Path) -> None:
    """Could not measure is NOT a pass. A row whose stamp cannot be read must
    not be reported as satisfying the invariant."""
    mod = _load()
    _commit_row(repo, "- `2026-13-45T99:99:99Z` CLAIM `X` scope: bad stamp.",
                "2026-09-02T11:00:00+00:00")
    findings, unmeasured = _run(mod, repo)
    assert findings == []
    assert len(unmeasured) == 1 and "not parseable" in unmeasured[0]


def test_prose_lines_are_not_rows(repo: Path) -> None:
    """Ordinary markdown added alongside a row must not be judged."""
    mod = _load()
    _commit_row(repo, "- just a bullet about `2026-09-02T20:00:00Z` in prose",
                "2026-09-02T11:00:00+00:00")
    findings, unmeasured = _run(mod, repo)
    assert findings == [] and unmeasured == []


def test_cli_exit_codes(repo: Path, tmp_path: Path) -> None:
    """0 clean / 1 findings -- observed as exit codes, not as return values."""
    mod = _load()
    _commit_row(repo, ROW.format(ts="2026-09-02T10:00:00Z"),
                "2026-09-02T11:00:00+00:00")
    assert mod.main(["--repo", str(repo), "--base", "HEAD~1", "--head", "HEAD"]) == 0
    _commit_row(repo, ROW.format(ts="2026-09-03T11:00:00Z"),
                "2026-09-02T12:00:00+00:00")
    assert mod.main(["--repo", str(repo), "--base", "HEAD~1", "--head", "HEAD"]) == 1


# --- the amend case: %cI, not %aI -------------------------------------------

def _amend_row(repo: Path, row: str, committer_date: str) -> None:
    """Fold a row into the PREVIOUS commit, as `git commit --amend` really does.

    No GIT_AUTHOR_DATE: git preserves the amended commit's original author date,
    which is the whole point. Only the committer date moves.
    """
    with (repo / REGISTER_REL).open("a", encoding="utf-8") as fh:
        fh.write(row + "\n")
    env = {"PATH": "/usr/bin:/bin",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e",
           "GIT_COMMITTER_DATE": committer_date}
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "--amend", "--no-edit"],
                   check=True, env=env)


def test_a_row_folded_in_with_commit_amend_is_not_postdated(repo: Path) -> None:
    """The false-failure mode the first cut claimed it did not have.

    An honest sequence: a commit is authored at 10:00, work continues, a row is
    filed at 11:30 by the clock-reading sanctioned path, and the author folds it
    into the commit they were already building. `--amend` keeps the 10:00 author
    date and sets the committer date to 11:35.

    Against `%aI` this reported POSTDATED by 1h30m and exited 1 -- a required
    gate manufacturing the exact defect it exists to detect, against a filer who
    used the sanctioned path precisely so this could not happen. Against `%cI`
    it is clean, because 11:30 is genuinely before the commit object existed.
    """
    mod = _load()
    _commit_row(repo, ROW.format(ts="2026-09-02T09:55:00Z"),
                "2026-09-02T10:00:00+00:00")
    _amend_row(repo, ROW.format(ts="2026-09-02T11:30:00Z"),
               "2026-09-02T11:35:00+00:00")
    mod.set_repo(repo)
    findings, unmeasured = mod.check(mod._git("rev-list", "-1", "HEAD").split())
    assert findings == [], (
        "an amended commit's author date is not when the row was written:\n"
        + "\n".join(findings)
    )
    assert unmeasured == []


def test_a_future_author_date_cannot_launder_a_postdated_row(repo: Path) -> None:
    """Why `%cI` alone, and not `row <= max(%aI, %cI)`.

    An author date is settable to anything (`git commit --date=...`). Under
    max() a row could be postdated to a future author date and read clean --
    postdating laundered through a flag, which is this check's entire subject.
    The row here is 3 hours ahead of when the commit object was made and must
    still be a finding.

    It fails at the previous head too, and for a reason worth stating: against
    `%aI` the row and the author date agree exactly, so a row asserting a
    moment three hours after the commit was made read CLEAN. `%cI` catches it.
    So the switch is not purely a loosening -- it closes a hole in the same
    move, and `max(%aI, %cI)` would leave that hole open.
    """
    mod = _load()
    with (repo / REGISTER_REL).open("a", encoding="utf-8") as fh:
        fh.write(ROW.format(ts="2026-09-02T13:00:00Z") + "\n")
    env = {"PATH": "/usr/bin:/bin",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e",
           "GIT_AUTHOR_DATE": "2026-09-02T13:00:00+00:00",
           "GIT_COMMITTER_DATE": "2026-09-02T10:00:00+00:00"}
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "row"],
                   check=True, env=env)
    mod.set_repo(repo)
    findings, _ = mod.check(mod._git("rev-list", "-1", "HEAD").split())
    assert len(findings) == 1, f"a future author date must not clear a row: {findings}"
    assert "POSTDATED by 3h00m" in findings[0], findings[0]
