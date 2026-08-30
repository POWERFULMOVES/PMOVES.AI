"""Tests for pmoves/tools/secrets_untrack.py — the leaked-env-file untrack Known Road.

Safety-critical: the tool must only ever untrack a *gitignored generated-secret*
path, never an arbitrary source file or a .example template.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

secrets_untrack = pytest.importorskip("secrets_untrack")


@pytest.mark.parametrize(
    "rel,expected",
    [
        ("pmoves/env.shared", True),
        ("pmoves/env.shared.pre-funnel", True),
        ("pmoves/env.shared.generated", True),
        ("pmoves/env.tier-media", True),
        ("pmoves/env.tier-agent", True),
        ("pmoves/.env.generated", True),
        # Templates are never eligible.
        ("pmoves/env.shared.example", False),
        ("pmoves/env.tier-media.example", False),
        # Arbitrary / source files are never eligible.
        ("pmoves/tools/secrets_untrack.py", False),
        ("pmoves/examples/distributed/tailscale/botz.env", False),  # nested → not top-level
        ("README.md", False),
        ("", False),
    ],
)
def test_is_allowed(rel: str, expected: bool) -> None:
    assert secrets_untrack.is_allowed(rel) is expected


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture()
def temp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "t@t")
    _run_git(repo, "config", "user.name", "t")
    (repo / "pmoves").mkdir()
    monkeypatch.setattr(secrets_untrack, "REPO_ROOT", repo)
    return repo


def test_refuses_non_gitignored(temp_repo: Path) -> None:
    # A tracked env.shared that is NOT gitignored must be refused (could be a real file).
    f = temp_repo / "pmoves" / "env.shared"
    f.write_text("SECRET=x\n", encoding="utf-8")
    _run_git(temp_repo, "add", "pmoves/env.shared")
    _run_git(temp_repo, "commit", "-qm", "add")
    assert secrets_untrack.main(["--file", "pmoves/env.shared"]) == 2
    # still tracked
    assert secrets_untrack.is_tracked("pmoves/env.shared")


def test_untracks_gitignored_secret(temp_repo: Path) -> None:
    (temp_repo / ".gitignore").write_text("pmoves/env.shared\n", encoding="utf-8")
    f = temp_repo / "pmoves" / "env.shared"
    f.write_text("SECRET=x\n", encoding="utf-8")
    # Force-add past the ignore rule to simulate the historical leak.
    _run_git(temp_repo, "add", "-f", "pmoves/env.shared", ".gitignore")
    _run_git(temp_repo, "commit", "-qm", "leak")
    assert secrets_untrack.is_tracked("pmoves/env.shared")

    assert secrets_untrack.main(["--file", "pmoves/env.shared"]) == 0
    assert not secrets_untrack.is_tracked("pmoves/env.shared")  # untracked
    assert f.exists()  # but still on disk


def test_noop_when_untracked(temp_repo: Path) -> None:
    assert secrets_untrack.main(["--file", "pmoves/env.tier-media"]) == 0


def test_refuses_arbitrary_path(temp_repo: Path) -> None:
    assert secrets_untrack.main(["--file", "pmoves/tools/secrets_untrack.py"]) == 2
