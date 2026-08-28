"""What deploy/provision/claude-pmoves.sh does when the roster cannot be normalized.

The path used to end in one line:

    WARN: could not normalize roster (python3 missing?); using raw <roster>

Two things were wrong with it. It GUESSED the cause -- four distinct failures
(normalizer absent, no interpreter, normalizer exited non-zero, normalizer
printed nothing) collapsed into a question mark about python3, so the operator
was pointed at the wrong fix. And it understated the outcome: the raw roster's
credentials are still literal ``${VAR}`` text, and Claude Code's documented
behaviour for an unresolvable reference is to warn once and then send that text
as the value. The session came up with MCP servers that looked configured and
could not authenticate -- indistinguishable, from inside, from "the service is
down".

These tests drive the real launcher end to end in a sandbox repo, with a fake
``claude`` on PATH so the exec is observable. That is deliberately not a
grep-the-source test: the thing under test is which of exec/exit happens and
what the operator is told, and only running it can answer that.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER_REL = "deploy/provision/claude-pmoves.sh"
LAUNCHER = REPO_ROOT / LAUNCHER_REL
NORMALIZER_REL = "pmoves/tools/mcp_roster_normalize.py"
PM_PYTHON_REL = "pmoves/scripts/pm-python.sh"

BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="needs bash")

# A roster with an unresolvable reference in a *credential*, which is the case
# that costs authentication, plus one in a url, which costs the endpoint.
ROSTER_WITH_PLACEHOLDERS = {
    "mcpServers": {
        "needs-a-token": {
            "type": "sse",
            "url": "http://127.0.0.1:8105/mcp/sse",
            "headers": {"Authorization": "Bearer ${PM_TEST_ABSENT_TOKEN}"},
        }
    }
}

# Same shape with nothing left to expand: the raw file is credential-equivalent
# to the normalized one.
ROSTER_WITHOUT_PLACEHOLDERS = {
    "mcpServers": {
        "plain": {
            "type": "sse",
            "url": "http://127.0.0.1:8105/mcp/sse",
            "headers": {"Authorization": "Bearer literal-value"},
        }
    }
}


class Launch:
    def __init__(self, proc: subprocess.CompletedProcess, argv_log: Path) -> None:
        self.rc = proc.returncode
        self.stdout = proc.stdout
        self.stderr = proc.stderr
        self.claude_argv = (
            argv_log.read_text(encoding="utf-8").splitlines()
            if argv_log.exists()
            else []
        )

    @property
    def claude_ran(self) -> bool:
        return bool(self.claude_argv)

    @property
    def mcp_config(self) -> str | None:
        for a in self.claude_argv:
            if a.startswith("--mcp-config="):
                return a.split("=", 1)[1]
        return None

    def __repr__(self) -> str:  # pragma: no cover - only rendered on failure
        return (
            f"Launch(rc={self.rc}, claude_argv={self.claude_argv!r}, "
            f"stderr={self.stderr!r})"
        )


class FakeRepo:
    """A repo-shaped tree the real launcher can resolve itself inside."""

    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "pmoves" / "scripts").mkdir(parents=True)
        (root / "pmoves" / "tools").mkdir(parents=True)
        (root / "deploy" / "provision").mkdir(parents=True)
        (root / ".claude").mkdir(parents=True)
        self.bin = root / "bin"
        self.bin.mkdir()

        # The marker the launcher validates its derived ROOT against.
        (root / "pmoves" / "Makefile").write_text("# marker\n", encoding="utf-8")
        (root / "pmoves" / "env.shared").write_text(
            "PM_TEST_PRESENT=present\n", encoding="utf-8"
        )

        self.launcher = root / LAUNCHER_REL
        shutil.copy2(LAUNCHER, self.launcher)
        self.launcher.chmod(0o755)
        shutil.copy2(REPO_ROOT / PM_PYTHON_REL, root / PM_PYTHON_REL)

        self.normalizer = root / NORMALIZER_REL
        shutil.copy2(REPO_ROOT / NORMALIZER_REL, self.normalizer)

        self.roster = root / ".claude" / "mcp.json"
        self.set_roster(ROSTER_WITH_PLACEHOLDERS)

        # A fake `claude` makes the exec observable. Nothing else on PATH is
        # replaced: the launcher legitimately uses mktemp/tr/grep.
        self.argv_log = root / "claude-argv.txt"
        claude = self.bin / "claude"
        claude.write_text(
            "#!/bin/sh\n"
            'for a in "$@"; do printf "%s\\n" "$a" >> "$PM_TEST_ARGV_LOG"; done\n'
            "exit 0\n",
            encoding="utf-8",
        )
        claude.chmod(claude.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    def set_roster(self, data: dict) -> None:
        self.roster.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def break_normalizer(self, body: str) -> None:
        self.normalizer.write_text(body, encoding="utf-8")

    def remove_normalizer(self) -> None:
        self.normalizer.unlink()

    def launch(self, **overrides: str) -> Launch:
        environ = {
            "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HOME": str(self.root),
            "PM_TEST_ARGV_LOG": str(self.argv_log),
            # Pin the interpreter so discovery is not the variable under test.
            "PMOVES_PYTHON": sys.executable,
        }
        environ.update(overrides)
        proc = subprocess.run(
            [BASH, str(self.launcher), "--some-arg"],
            cwd=self.root,
            env=environ,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return Launch(proc, self.argv_log)


@pytest.fixture()
def repo(tmp_path: Path) -> FakeRepo:
    return FakeRepo(tmp_path / "repo")


# --------------------------------------------------------------------------
# The happy path still works.
# --------------------------------------------------------------------------


def test_a_working_normalizer_launches_with_the_normalized_roster(repo: FakeRepo):
    r = repo.launch()
    assert r.rc == 0, r
    assert r.claude_ran, r
    assert r.mcp_config != str(repo.roster), (
        f"launched with the raw roster despite a working normalizer: {r!r}"
    )
    assert "ERROR" not in r.stderr, r
    assert "--some-arg" in r.claude_argv, (
        f"the caller's own arguments were dropped: {r!r}"
    )


# --------------------------------------------------------------------------
# Fail closed: placeholders left in the roster mean unauthenticated servers.
# --------------------------------------------------------------------------


def test_it_refuses_when_the_raw_roster_still_holds_placeholders(repo: FakeRepo):
    """The decision this change makes, stated as a test.

    Continuing here starts a session whose MCP credentials are the strings
    ``${...}``. Nothing in the session can see that; the operator finds out by
    noticing tools they expected are absent, and every later session on the node
    repeats it. Refusing costs one command, and the command is printed.
    """
    r = repo.launch(PMOVES_PYTHON=" ")
    assert r.rc != 0, f"launched anyway with placeholder credentials: {r!r}"
    assert not r.claude_ran, f"claude was exec'd despite the refusal: {r!r}"


def test_the_refusal_says_what_is_lost_not_just_that_something_failed(
    repo: FakeRepo,
):
    r = repo.launch(PMOVES_PYTHON=" ")
    err = r.stderr.lower()
    assert "bearer" in err, f"never names the credential consequence: {r!r}"
    assert "authenticate" in err, f"never says the servers will not connect: {r!r}"
    assert "${" in r.stderr, f"never names the literal placeholder text: {r!r}"


def test_the_refusal_prints_the_way_out(repo: FakeRepo):
    """A gate with no exit is a lockout; this one names its own override."""
    r = repo.launch(PMOVES_PYTHON=" ")
    assert "PMOVES_ALLOW_RAW_ROSTER" in r.stderr, r


def test_the_override_is_honoured_and_uses_the_raw_roster(repo: FakeRepo):
    r = repo.launch(PMOVES_PYTHON=" ", PMOVES_ALLOW_RAW_ROSTER="1")
    assert r.rc == 0, r
    assert r.claude_ran, f"the override did not launch anything: {r!r}"
    assert r.mcp_config == str(repo.roster), r


def test_a_roster_with_nothing_left_to_expand_warns_and_launches(repo: FakeRepo):
    """Proportionate, not absolute.

    With no ``${...}`` remaining, the raw roster authenticates exactly as the
    normalized one would. Refusing there would be a lock with nothing behind it,
    so it warns about what it actually loses and starts.
    """
    repo.set_roster(ROSTER_WITHOUT_PLACEHOLDERS)
    r = repo.launch(PMOVES_PYTHON=" ")
    assert r.rc == 0, r
    assert r.claude_ran, r
    assert r.mcp_config == str(repo.roster), r
    assert "WARN" in r.stderr, r


# --------------------------------------------------------------------------
# Each cause is named. The operator's next command differs for each.
# --------------------------------------------------------------------------


def test_a_whitespace_pin_is_reported_as_no_interpreter_not_as_a_python3_guess(
    repo: FakeRepo,
):
    """The original defect, end to end.

    ``PMOVES_PYTHON=" "`` used to satisfy ``pm_pick_python`` with an EMPTY
    PM_PY, so the launcher ran the normalizer's .py file as the command and
    then blamed a missing python3.
    """
    r = repo.launch(PMOVES_PYTHON=" ")
    assert "no usable python interpreter" in r.stderr, r
    assert "python3 missing?" not in r.stderr, (
        f"still guessing at the cause: {r!r}"
    )
    assert "PMOVES_PYTHON" in r.stderr, (
        f"does not mention the variable that actually caused it: {r!r}"
    )


def test_a_missing_normalizer_is_named_as_such(repo: FakeRepo):
    repo.remove_normalizer()
    r = repo.launch()
    assert "normalizer is missing" in r.stderr, r
    assert str(repo.normalizer) in r.stderr, (
        f"does not say which file is missing: {r!r}"
    )


def test_a_normalizer_that_exits_non_zero_reports_its_exit_code(repo: FakeRepo):
    repo.break_normalizer("import sys\nsys.exit(3)\n")
    r = repo.launch()
    assert "exited 3" in r.stderr, r


def test_a_normalizer_that_prints_nothing_is_distinguished_from_one_that_fails(
    repo: FakeRepo,
):
    """Exit 0 with no stdout wrote no file. Silent success is its own cause."""
    repo.break_normalizer("import sys\nsys.exit(0)\n")
    r = repo.launch()
    assert "printed no roster path" in r.stderr, r
    assert "exited 3" not in r.stderr, r


def test_the_pinned_interpreter_is_shown_when_the_normalizer_itself_fails(
    repo: FakeRepo,
):
    repo.break_normalizer("import sys\nsys.exit(4)\n")
    r = repo.launch()
    assert sys.executable in r.stderr, (
        f"does not say which interpreter ran it: {r!r}"
    )


# --------------------------------------------------------------------------
# The Windows twin. There is no pwsh in CI, so this cannot be executed here --
# but the drift it guards is documented in that file's own header: the POSIX
# launcher grew ${VAR} resolution and the PowerShell one did not, and the blind
# launcher was the one running on the machine the url named. A policy that
# exists on one platform only is how that happened.
# --------------------------------------------------------------------------

PS1 = REPO_ROOT / "deploy" / "provision" / "claude-pmoves.ps1"


def test_the_powershell_twin_carries_the_same_gate():
    src = PS1.read_text(encoding="utf-8")
    assert "PMOVES_ALLOW_RAW_ROSTER" in src, (
        "the Windows launcher still fails open with no override -- the two "
        "twins have drifted on the policy again"
    )
    assert "exit 1" in src, "the Windows launcher never refuses"


def test_the_powershell_twin_also_stopped_guessing_the_cause():
    src = PS1.read_text(encoding="utf-8")
    assert "the normalizer is missing" in src, src[:0] or "cause not distinguished"
    assert "no usable python interpreter" in src
    assert "printed no roster path" in src


def test_the_powershell_twin_no_longer_emits_the_one_size_guess():
    """Scoped to lines it PRINTS.

    The POSIX side is asserted at runtime instead (see the whitespace-pin test);
    both files still quote the old message in comments, and a check that cannot
    tell a comment from an emitted string would fail on the record of the fix.
    """
    emitted = [
        line
        for line in PS1.read_text(encoding="utf-8").splitlines()
        if "Write-Warning" in line and not line.lstrip().startswith("#")
    ]
    assert emitted, "no Write-Warning lines found — did the file move?"
    offenders = [line for line in emitted if "python3 missing?" in line]
    assert not offenders, (
        f"the Windows launcher still reports one guess for four causes: {offenders}"
    )
