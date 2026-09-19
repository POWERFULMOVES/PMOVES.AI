"""A command substitution is a command, and the register hook must judge it as one.

Measured 2026-09-15, before the fix:

    env cp /tmp/x <register>        BLOCK   "cp writes the register as its DESTINATION"
    N=$(env cp /tmp/x <register>)   ALLOW   <- the same write, permitted

`shlex` yields `['N=$(env', 'cp', '/tmp/x', '<register>)']`. `ASSIGNMENT_RE`
matched the `N=` prefix of token 0, so the whole token was consumed as an
assignment and `env` never reached `_strip_prefixes`' wrapper list. The
destination then arrived as `<register>)` — paren attached — so `_is_register()`
(a path test) said no, and the copy-verb guard never fired.

Wrapping a blocked register write in `$( )` plus one leading word turned BLOCK
into ALLOW. The hook's own header records six shapes that bypassed the previous
design; this was a seventh, inside the allowlist that replaced it.

The same fault refused reads the hook intends to permit:

    N=$(git show origin/main:<register>)   "`show` is not a command ..."

though `show` is in `_GIT_READ_SUBCOMMANDS`. `git` was eaten with the `N=`, so
the SUBCOMMAND was judged as the command. `git diff` survived only because
`diff` ALSO exists as a top-level read-only command — the documented read path
worked for the wrong reason.

These tests pin both directions. The write cases matter more, so they carry the
negative controls.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / ".claude" / "hooks" / "governance" / "claim-collision-pre.py"

# Assembled, not written literally: a test file that contains the register's own
# name in a command string is itself the literal-match hazard the hook's
# `_segments` docstring describes.
REG = "pmoves/docs/AGENTS/" + "AGNOTE4482PHI" + ".t1.md"

ALLOW, BLOCK = "ALLOW", "BLOCK"


def _verdict(cmd: str) -> tuple:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    proc = subprocess.run(
        [sys.executable, str(HOOK)], input=payload,
        capture_output=True, text=True, timeout=120,
    )
    text = (proc.stdout + proc.stderr).strip()
    return (ALLOW if proc.returncode == 0 else BLOCK), text


@pytest.fixture(autouse=True)
def _require_hook():
    if not HOOK.is_file():
        pytest.skip("claim-collision-pre.py not present")


# --- the fail-open, and its controls -----------------------------------------

@pytest.mark.parametrize("cmd", [
    f"N=$(env cp /tmp/x {REG})",
    f"N=$(sudo cp /tmp/x {REG})",
    f"N=`env cp /tmp/x {REG}`",
    f"echo $(env cp /tmp/x {REG})",
])
def test_a_write_wrapped_in_a_substitution_is_still_a_write(cmd):
    verdict, why = _verdict(cmd)
    assert verdict == BLOCK, (
        f"{cmd!r} was ALLOWED. A command substitution is a command; wrapping a "
        f"register overwrite in one must not launder it.\n{why[:400]}"
    )


@pytest.mark.parametrize("cmd", [
    f"cp /tmp/x {REG}",
    f"env cp /tmp/x {REG}",
])
def test_control_the_same_write_unwrapped_is_blocked(cmd):
    """NEGATIVE CONTROL: proves the test above measures the WRAPPER.

    If these were allowed too, the parametrised test would be asserting that the
    hook blocks `cp` at all — not that the substitution stopped laundering it.
    """
    verdict, _ = _verdict(cmd)
    assert verdict == BLOCK


def test_control_a_substitution_that_writes_nothing_is_not_blocked_wholesale():
    """NEGATIVE CONTROL in the other direction.

    The cheap "fix" is to refuse every `$( )` touching the register. That would
    pass every test above and break the read path the hook documents, which is
    how this defect was found in the first place.
    """
    verdict, why = _verdict(f"N=$(wc -l < {REG})")
    assert verdict == ALLOW, f"a pure read inside a substitution was refused:\n{why[:400]}"


# --- the false refusals -------------------------------------------------------

@pytest.mark.parametrize("cmd", [
    f"git show origin/main:{REG}",
    f"N=$(git show origin/main:{REG})",
    f"N=$(git show origin/main:{REG} | wc -c)",
    f"N=$(git diff --numstat -- {REG})",
    f"N=$(cat {REG} | wc -c)",
    f"N=$(grep -c CLAIM {REG})",
])
def test_reads_are_allowed_wrapped_or_not(cmd):
    verdict, why = _verdict(cmd)
    assert verdict == ALLOW, (
        f"{cmd!r} was refused. These are read-only forms the hook's own "
        f"allowlist names; refusing them with no alternative is the deadlock the "
        f"sanctioned targets exist to avoid.\n{why[:400]}"
    )


# --- shapes that must keep working -------------------------------------------

def test_arithmetic_expansion_is_not_a_command_substitution():
    """`$((1+1))` has no command in it; judging `1` as one would refuse it."""
    verdict, why = _verdict(f"N=$((1+1)); grep -c CLAIM {REG}")
    assert verdict == ALLOW, why[:400]


def test_unterminated_substitution_does_not_swallow_the_rest():
    """An unbalanced `$(` must leave the write visible, not hide it.

    Fail-closed: the text stays in the segment and faces the allowlist, so the
    verdict can only get stricter.
    """
    verdict, _ = _verdict(f"N=$(echo hi; cp /tmp/x {REG}")
    assert verdict == BLOCK


def test_nested_substitution_is_still_reached():
    verdict, why = _verdict(f"N=$(echo $(env cp /tmp/x {REG}))")
    assert verdict == BLOCK, f"a write nested two substitutions deep was allowed:\n{why[:400]}"


def test_the_sanctioned_write_path_is_untouched():
    """The make targets must keep working, or the fix trades one deadlock for another."""
    verdict, why = _verdict("make -C pmoves register-status")
    assert verdict == ALLOW, why[:400]
