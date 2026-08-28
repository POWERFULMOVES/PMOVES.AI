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
import re
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

# ``${VAR:-default}`` is the REMEDY the roster's own note prescribes, not the
# disease: an unset var expands to the default, so nothing is ever sent as a
# placeholder. ``.claude/mcp.json`` uses exactly this for the cipher bearer
# today. A gate that refuses here refuses the fix.
ROSTER_ONLY_DEFAULTED = {
    "mcpServers": {
        "defaulted": {
            "type": "sse",
            "url": "http://127.0.0.1:8105/mcp/sse",
            "headers": {"Authorization": "Bearer ${PM_TEST_ABSENT_TOKEN:-}"},
        }
    }
}

# ``${...}`` inside a ``_``-prefixed metadata key is prose ABOUT placeholders,
# not a placeholder. Not hypothetical: ``.claude/mcp.json`` carries the literal
# text "uses the unexpanded ${VAR} text as-is" inside a ``_note``, so a node
# that had expanded every real reference still could not pass a whole-file
# match.
ROSTER_PLACEHOLDER_ONLY_IN_PROSE = {
    "_pinned_versions_note": "the docs say the unexpanded ${VAR} text is used as-is",
    "mcpServers": {
        "plain": {
            "_note": "the remedy for ${PM_TEST_ABSENT_TOKEN} is the ':-' fallback",
            "type": "sse",
            "url": "http://127.0.0.1:8105/mcp/sse",
            "headers": {"Authorization": "Bearer literal-value"},
        }
    }
}

# A bare reference in an ``env`` block rather than a header -- same cost, and
# the narrowing must not lose it.
ROSTER_BARE_PLACEHOLDER_IN_ENV = {
    "mcpServers": {
        "stdio-thing": {
            "command": "uvx",
            "args": ["some-mcp"],
            "env": {"SOME_API_KEY": "${PM_TEST_ABSENT_TOKEN}"},
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
# WHAT COUNTS AS A PLACEHOLDER.
#
# The policy is "refuse when credentials would go out as placeholders". The
# first implementation asked "do the two characters ``${`` appear anywhere in
# this JSON file", which is a different question and answers wrong in both
# directions. These tests pin the policy, not the grep: they drive the real
# launcher with the interpreter deliberately unavailable, so the gate is what
# decides.
# --------------------------------------------------------------------------


def test_a_defaulted_reference_is_not_a_placeholder(repo: FakeRepo):
    """``${TOK:-}`` sends the default, never the literal text.

    Refusing here would refuse the documented remedy -- and it is the remedy
    the tracked roster already uses for the cipher bearer, so this case is
    live, not theoretical.
    """
    repo.set_roster(ROSTER_ONLY_DEFAULTED)
    r = repo.launch(PMOVES_PYTHON=" ")
    assert r.rc == 0, f"refused a roster with no placeholder in it: {r!r}"
    assert r.claude_ran, r
    assert "Refusing" not in r.stderr, (
        f"claimed credentials are placeholders when none are: {r!r}"
    )


def test_a_placeholder_confined_to_metadata_prose_is_not_a_placeholder(
    repo: FakeRepo,
):
    """Claude Code reads ``mcpServers``; ``_``-prefixed keys are documentation.

    A node that has expanded every real reference must be able to launch even
    though the file still *talks about* ``${VAR}``.
    """
    repo.set_roster(ROSTER_PLACEHOLDER_ONLY_IN_PROSE)
    r = repo.launch(PMOVES_PYTHON=" ")
    assert r.rc == 0, f"refused on prose about placeholders: {r!r}"
    assert r.claude_ran, r
    assert "Refusing" not in r.stderr, r


def test_a_bare_reference_in_env_still_refuses(repo: FakeRepo):
    """The narrowing must not become a hole: ``env`` costs the same as a header."""
    repo.set_roster(ROSTER_BARE_PLACEHOLDER_IN_ENV)
    r = repo.launch(PMOVES_PYTHON=" ")
    assert r.rc != 0, f"launched with a literal ${{VAR}} credential in env: {r!r}"
    assert not r.claude_ran, r


def test_the_tracked_roster_itself_still_trips_the_gate(repo: FakeRepo):
    """The anti-over-narrowing control.

    The real ``.claude/mcp.json`` carries bare references in ``url`` and ``env``
    today. If a future narrowing lets THAT through, the gate has been narrowed
    into nothing -- and this test, unlike the constructed ones, moves with the
    file the launcher actually reads.
    """
    tracked = REPO_ROOT / ".claude" / "mcp.json"
    if not tracked.exists():  # pragma: no cover - tracked file is in-repo
        pytest.skip("no tracked roster in this checkout")
    repo.roster.write_text(tracked.read_text(encoding="utf-8"), encoding="utf-8")
    r = repo.launch(PMOVES_PYTHON=" ")
    assert r.rc != 0, f"the real roster no longer trips the gate: {r!r}"
    assert not r.claude_ran, r


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


# --------------------------------------------------------------------------
# The Windows twin, part 2: WHAT FEEDS THE GATE.
#
# The three tests above assert the gate is PRESENT. That is not enough, and the
# gap is not academic -- it is how a half-mirrored twin shipped. The gate was
# copied to the ps1; the interpreter discovery it gates on was not, so the ps1
# tried exactly `Get-Command python` then `Get-Command python3`. On a stock
# Windows 10/11 node `python` resolves to the Microsoft Store stub under
# %LOCALAPPDATA%\Microsoft\WindowsApps, `Get-Command` SUCCEEDS on it, running it
# does not produce an interpreter -- and the node that used to warn and launch
# now cannot start a session at all, via an override the ps1 never read.
#
# So: assert the INPUTS, not just the refusal. These are static assertions
# because `command -v pwsh powershell` exits 1 here; they are the strongest
# check available without a Windows runner, and each one is written to fail
# against the twin as it stood.
# --------------------------------------------------------------------------


def _ps1_src() -> str:
    return PS1.read_text(encoding="utf-8")


def _ps1_emitted() -> list[str]:
    """Lines whose text reaches the operator, excluding comments.

    That is the emit calls plus the ``$why`` assignments, which are printed
    verbatim one line later as ``cause: $why``.

    Comments are excluded deliberately: both files quote the OLD messages as
    the record of the fix, so a check that cannot tell a comment from an
    emitted string fails on the documentation rather than on the behaviour.
    """
    return [
        line
        for line in _ps1_src().splitlines()
        if not line.lstrip().startswith("#")
        and (
            "Write-Warning" in line
            or "Error.WriteLine" in line
            or line.lstrip().startswith("$why")
        )
    ]


def test_the_powershell_twin_searches_the_same_interpreters_as_pm_python():
    """Every rung `pm-python.sh` has, before the ps1 is allowed to refuse.

    Without the venv rung the ps1 cannot see what `make -C pmoves preflight`
    produces; without the PMOVES_PYTHON rung the operator has no override at
    all; without `py -3` a stock Windows node has no real interpreter to find.
    """
    src = _ps1_src()
    missing = []
    if "PMOVES_PYTHON" not in src:
        missing.append("$env:PMOVES_PYTHON (the operator pin -- there is no override without it)")
    if ".venv-pmoves" not in src:
        missing.append(".venv-pmoves (what `make -C pmoves preflight` provisions)")
    if not re.search(r"""['"]py['"]\s*,\s*['"]-3['"]""", src):
        missing.append("py -3 (the real interpreter on a Windows node)")
    if "python3" not in src:
        missing.append("python3")
    if not re.search(r"""['"]python['"]""", src):
        missing.append("python")
    assert not missing, (
        "the Windows launcher refuses on a healthy node because its discovery "
        "ladder is missing: " + "; ".join(missing)
    )


def test_the_powershell_twin_runs_the_candidate_instead_of_trusting_get_command():
    """`Get-Command` succeeding is exactly what makes the Store stub invisible.

    `pm-python.sh` probes with `-c ''` -- a no-op for any real interpreter and
    non-zero for anything that is not one. Presence is not runnability.
    """
    src = _ps1_src()
    assert re.search(r"-c\s+'(pass)?'", src), (
        "the Windows launcher accepts an interpreter it never ran; "
        "Get-Command succeeds on the Microsoft Store stub, so presence proves "
        "nothing (pm-python.sh probes with -c '')"
    )


def test_the_powershell_twin_names_the_store_stub_as_the_thing_it_rejects():
    """The finding must not be silently un-fixed by a later tidy-up.

    A probe with no recorded reason reads like defensive noise and gets removed.
    """
    src = _ps1_src().lower()
    assert "windowsapps" in src or "microsoft store" in src, (
        "nothing in the ps1 records WHY the candidate is probed, so the next "
        "reader cannot tell the probe is load-bearing"
    )


def test_the_powershell_twin_cause_message_names_every_candidate_it_tried():
    """Same contract as the POSIX `why` string.

    The operator's next command depends on knowing what was searched. 'tried
    python, then python3' sends them to install a python the launcher may
    already have had.
    """
    causes = [line for line in _ps1_emitted() if "no usable python interpreter" in line]
    assert causes, "the ps1 no longer reports the no-interpreter cause"
    blob = " ".join(causes)
    for token in ("PMOVES_PYTHON", ".venv-pmoves", "py -3", "python3", "python"):
        assert token in blob, (
            f"the no-interpreter message does not name {token!r}, so it "
            f"under-reports what was searched: {causes}"
        )


def test_the_powershell_twin_only_prints_remedies_it_can_act_on():
    """A printed fix that leaves the operator refused is worse than none.

    `make -C pmoves preflight` provisions `pmoves/.venv-pmoves`. If the ps1
    prints that as the remedy it must also LOOK there, or the operator follows
    the instruction and stays refused.
    """
    src = _ps1_src()
    emitted = _ps1_emitted()

    if any("preflight" in line for line in emitted):
        assert ".venv-pmoves" in src, (
            "the ps1 tells the operator to run `make -C pmoves preflight` but "
            "never looks in pmoves\\.venv-pmoves, which is what preflight "
            "provisions -- following the printed fix leaves them refused"
        )

    pin = [line for line in emitted if "PMOVES_PYTHON" in line]
    assert pin, (
        "the refusal never offers the interpreter pin, so a node whose python "
        "is somewhere the ladder does not look has only "
        "PMOVES_ALLOW_RAW_ROSTER -- i.e. the thing the gate exists to prevent"
    )


def test_the_powershell_twin_uses_the_same_narrowed_placeholder_test():
    """Both twins must agree on what a placeholder IS, not just on refusing.

    A whole-file `${` match fires on `${VAR:-default}` (the remedy) and on
    `${...}` in a `_note` (prose), and both twins carried it.
    """
    src = _ps1_src()
    assert "-SimpleMatch '${'" not in src, (
        "the ps1 still refuses on any occurrence of ${ anywhere in the file, "
        "including the ':-' remedy and `_note` prose"
    )
    assert re.search(r"\\\$\\\{\[A-Za-z_\]", src), (
        "the ps1 has no bare-${IDENT} test -- it cannot tell a placeholder "
        "from a defaulted reference"
    )
    assert re.search(r'"_\[\^"\]\*"', src), (
        "the ps1 does not skip `_`-prefixed metadata keys, so prose about "
        "placeholders still reads as a placeholder"
    )
