"""pm-python.sh — the one python discovery, finally under test.

#2769 introduced ``pmoves/scripts/pm-python.sh`` as "the ONE python discovery,
sourced by every PMOVES launcher that needs an interpreter" and shipped it with
no tests at all. That is a single point of failure on the startup path of every
session on every node, and it is why a whitespace-only ``PMOVES_PYTHON`` could
survive: ``[ -n " " ]`` is true, the unquoted ``PM_PY=(${PMOVES_PYTHON})``
word-splits it to ZERO elements, and the no-probe form then returned 0 anyway.
``deploy/provision/claude-pmoves.sh`` calls the no-probe form, so it went on to
run ``"${PM_PY[@]}" "$NORMALIZER" ...`` -- i.e. the non-executable ``.py`` file
as the command -- and fell back to the RAW MCP roster, whose bearer tokens are
still literal ``${VAR}`` text.

The contract these tests hold, in one line: **pm_pick_python must never return
0 with a PM_PY the caller cannot run.**

Everything here is hermetic. The sandbox copies pm-python.sh into a throwaway
tree so ``_pm_py_dir`` points at a venv we control, and PATH is replaced with a
stub directory, so the result does not depend on which interpreters this node
happens to have. Only ``bash``, ``sh`` and ``dirname`` are borrowed from the
host -- the launcher's own dependency surface, nothing more. No test here needs
a real CPython, which is the point: a discovery function should be testable
without the matrix it exists to discover.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PM_PYTHON_SH = REPO_ROOT / "pmoves" / "scripts" / "pm-python.sh"

# Absolute paths: the sandbox replaces PATH wholesale, so neither the harness
# nor the stub shebangs may rely on a PATH lookup.
BASH = shutil.which("bash")
SH = shutil.which("sh")

# A shebang needs a POSIX path, and `shutil.which` does not give one on
# Windows: it returns a BACKSLASHED path containing a SPACE
# (C:\Program Files\Git\usr\bin\sh.EXE). A shebang parser splits that at the
# space and tries to exec "C:\Program", so every stub interpreter written with
# it is unrunnable and each discovery test reports COUNT=0. Measured on the
# 4090: 10 tests failed for exactly this, and no error named the shebang.
#
# The register recorded a different cause -- that the skipif below "reads Git
# Bash as a POSIX host". It does, and that is CORRECT: these tests should run
# here. Skipping them would have hidden a portability bug on the one node that
# actually runs Windows.
#
# `/bin/sh` is right everywhere these tests run: POSIX guarantees it, and Git
# Bash provides it inside its own view. The `which` result stays correct for
# `subprocess`, which wants a real Windows path -- only the SHEBANG needs the
# POSIX form.
SHEBANG_SH = "/bin/sh"
DIRNAME = shutil.which("dirname")

pytestmark = pytest.mark.skipif(
    not (BASH and SH and DIRNAME),
    reason="needs bash, sh and dirname (POSIX host)",
)

# pm-python.sh is sourced by launchers that run under `set -u`; the harness does
# the same so an unbound-variable regression surfaces here rather than on a node.
HARNESS = r"""
set -u
# shellcheck source=/dev/null
. "$PM_SCRIPT"
if pm_pick_python "$@"; then rc=0; else rc=$?; fi
echo "RC=$rc"
if declare -p PM_PY >/dev/null 2>&1; then
  echo "DECLARED=1"
  echo "COUNT=${#PM_PY[@]}"
  if [ "${#PM_PY[@]}" -gt 0 ]; then
    printf 'ARGV=%s\n' "${PM_PY[@]}"
  fi
else
  echo "DECLARED=0"
  echo "COUNT=0"
fi
"""

# A module name no probe will ever ask for, used to make a stub answer "yes" to
# every import.
_NEVER = "__pm_no_such_module__"


class Result:
    def __init__(self, proc: subprocess.CompletedProcess) -> None:
        self.stdout = proc.stdout
        self.stderr = proc.stderr
        self.rc: int | None = None
        self.count: int | None = None
        self.declared: bool | None = None
        self.argv: list[str] = []
        for line in proc.stdout.splitlines():
            key, _, val = line.partition("=")
            if key == "RC":
                self.rc = int(val)
            elif key == "COUNT":
                self.count = int(val)
            elif key == "DECLARED":
                self.declared = val == "1"
            elif key == "ARGV":
                self.argv.append(val)

    @property
    def ok(self) -> bool:
        return self.rc == 0

    def __repr__(self) -> str:  # pragma: no cover - only rendered on failure
        return (
            f"Result(rc={self.rc}, count={self.count}, argv={self.argv!r}, "
            f"stdout={self.stdout!r}, stderr={self.stderr!r})"
        )


def _fake_interpreter(fails_import: str) -> str:
    """A stub that answers ``-c 'import X'`` the way an interpreter would.

    Deliberately not a real python: the discovery ORDER is under test, not
    CPython, and a stub is the only way to assert "python3 absent, py present"
    on a host that has both.
    """
    return (
        f"#!{SHEBANG_SH}\n"
        'for a in "$@"; do\n'
        f'  case "$a" in "import {fails_import or _NEVER}") exit 1 ;; esac\n'
        "done\n"
        "exit 0\n"
    )


BACKSLASH = chr(92)


def names_path(actual: str, path: Path, root: Path) -> bool:
    """Does the shell-emitted argv element name `path`, whatever FORM it used?

    pm-python.sh runs in a POSIX shell and puts a POSIX path in PM_PY
    (/tmp/pytest-of-.../repo/...). `str(Path)` on Windows gives the
    backslashed Windows form. Both name the same file, and Git Bash /tmp is
    not reachable from pathlib, so an exact comparison can only ever pass on a
    POSIX host -- it tests the operating system, not the discovery ORDER this
    suite exists to pin.

    Compare below the sandbox root: identical in both forms, and it is the
    part that says WHICH interpreter was chosen.
    """
    tail = path.relative_to(root).as_posix()
    return actual.replace(BACKSLASH, "/").endswith(tail)


class Sandbox:
    """A throwaway repo-shaped tree with a fully controlled PATH."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.pmoves = root / "pmoves"
        self.scripts = self.pmoves / "scripts"
        self.bin = root / "bin"
        self.cwd = root / "cwd"
        for d in (self.scripts, self.bin, self.cwd):
            d.mkdir(parents=True, exist_ok=True)
        self.script = self.scripts / "pm-python.sh"
        shutil.copy2(PM_PYTHON_SH, self.script)
        # pm-python.sh calls `dirname` at source time; nothing else external.
        os.symlink(DIRNAME, self.bin / "dirname")

    def stub(self, name: str, *, fails_import: str = "") -> Path:
        """Install a fake interpreter on the sandbox PATH."""
        p = self.bin / name
        p.write_text(_fake_interpreter(fails_import), encoding="utf-8")
        p.chmod(0o755)
        return p

    def venv_python(self, *, fails_import: str = "", subdir: str = "bin") -> Path:
        """Create the canonical venv interpreter pm-python.sh looks for first."""
        d = self.pmoves / ".venv-pmoves" / subdir
        d.mkdir(parents=True, exist_ok=True)
        p = d / ("python.exe" if subdir == "Scripts" else "python")
        p.write_text(_fake_interpreter(fails_import), encoding="utf-8")
        p.chmod(0o755)
        return p

    def process_env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        # PATH is the sandbox bin FIRST, so the stubs win discovery. On
        # Windows it cannot be the sandbox bin ONLY: Git ships coreutils as
        # msys binaries needing `msys-2.0.dll`, which lives beside them in
        # Git's usr/bin. Strip that directory from PATH and every symlinked
        # coreutil fails to START -- `dirname` produced EMPTY output, so
        #     _pm_py_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
        # resolved to "/", the venv was looked for at /.venv-pmoves, and three
        # tests reported COUNT=0 with nothing naming the cause.
        #
        # Appending it is safe for what these tests pin: that directory ships
        # no python, py, or python3, so discovery ORDER is still decided
        # entirely by the sandbox stubs ahead of it. On POSIX the coreutils
        # directory is typically /usr/bin, which DOES carry python3 -- adding it
        # there would defeat the "python3 absent" cases, so this is Windows-only.
        path = str(self.bin)
        if os.name == "nt":
            coreutils = os.path.dirname(shutil.which("dirname") or "")
            if coreutils:
                path = path + os.pathsep + coreutils
        e = {
            "PATH": path,
            "PM_SCRIPT": str(self.script),
            "HOME": str(self.root),
        }
        e.update(extra or {})
        return e

    def run(self, *args: str, pin: dict[str, str] | None = None) -> Result:
        return self.run_harness(HARNESS, *args, pin=pin)

    def run_harness(
        self, harness: str, *args: str, pin: dict[str, str] | None = None
    ) -> Result:
        proc = subprocess.run(
            [BASH, "-c", harness, "harness", *args],
            cwd=self.cwd,
            env=self.process_env(pin),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return Result(proc)


@pytest.fixture()
def sandbox(tmp_path: Path) -> Sandbox:
    return Sandbox(tmp_path)


# --------------------------------------------------------------------------
# 1. The defect: a PMOVES_PYTHON that word-splits to nothing.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("value", [" ", "  ", "\t", " \t "])
def test_whitespace_only_pin_is_rejected_without_a_probe(sandbox: Sandbox, value: str):
    """The headline bug.

    ``[ -n " " ]`` is true so the override branch is taken; the split yields
    zero elements; with no probe the ``[ -z "$probe" ]`` short-circuit returned
    0 anyway, and the caller then ran its own first argument as the command.
    """
    sandbox.stub("python3")
    r = sandbox.run(pin={"PMOVES_PYTHON": value})
    assert not r.ok, (
        f"pm_pick_python returned 0 for PMOVES_PYTHON={value!r} -- the caller "
        f"will run its next argument as the command. {r!r}"
    )
    assert r.count == 0, f"PM_PY left non-empty on a rejected pin: {r!r}"


def test_whitespace_only_pin_is_rejected_with_a_probe(sandbox: Sandbox):
    """The half that already worked -- kept so the fix cannot regress it."""
    sandbox.stub("python3")
    r = sandbox.run("yaml", pin={"PMOVES_PYTHON": " "})
    assert not r.ok, r
    assert r.count == 0, r


@pytest.mark.parametrize(
    "value,probe",
    [
        (" ", ()),
        (" ", ("yaml",)),
        ("*", ()),
        ("*", ("yaml",)),
        ("/nonexistent/python", ()),
        ("", ()),
    ],
)
def test_success_never_yields_an_empty_argv(sandbox: Sandbox, value: str, probe):
    """The invariant, stated once, over every shape of input.

    This is the test meant to outlive the specific bug: whatever the discovery
    does internally, a 0 return must come with something runnable in PM_PY. A
    future branch that forgets to assign fails here.
    """
    sandbox.stub("python3")
    r = sandbox.run(*probe, pin={"PMOVES_PYTHON": value})
    if r.ok:
        assert r.count and r.count >= 1, (
            f"returned 0 with an empty PM_PY for pin={value!r} probe={probe!r} "
            f"-- the caller cannot distinguish this from success. {r!r}"
        )


# --------------------------------------------------------------------------
# 2. The second defect on the same line: filename expansion.
# --------------------------------------------------------------------------


def test_glob_pin_does_not_expand_against_the_callers_cwd(sandbox: Sandbox):
    """``PM_PY=(${PMOVES_PYTHON})`` globs as well as splits (`set -f` is off).

    With ``PMOVES_PYTHON='*'`` the array became the caller's directory listing,
    so pm_pick_python handed back e.g. ``(a.txt b.txt)`` as an interpreter.
    """
    sandbox.stub("python3")
    (sandbox.cwd / "a.txt").write_text("", encoding="utf-8")
    (sandbox.cwd / "b.txt").write_text("", encoding="utf-8")
    r = sandbox.run(pin={"PMOVES_PYTHON": "*"})
    assert "a.txt" not in r.argv and "b.txt" not in r.argv, (
        f"PMOVES_PYTHON='*' expanded against the caller's cwd: {r!r}"
    )
    assert not r.ok, f"a pin that names no interpreter must not succeed: {r!r}"


def test_glob_pin_is_not_satisfied_by_a_file_in_the_callers_cwd(sandbox: Sandbox):
    """The sharp end of the same bug.

    A caller running from a directory that happens to contain a file named
    ``python3`` had its pin silently replaced by that filename, which then
    resolved through PATH to a real interpreter -- so it looked like it worked.
    """
    sandbox.stub("python3")
    (sandbox.cwd / "python3").write_text("", encoding="utf-8")
    r = sandbox.run("yaml", pin={"PMOVES_PYTHON": "*"})
    assert r.argv != ["python3"], (
        f"the glob resolved to a file in cwd named python3 -- a pin must never "
        f"be satisfied by the caller's directory contents: {r!r}"
    )
    assert not r.ok, r


# --------------------------------------------------------------------------
# 3. The behaviour the override branch exists for -- must survive the fix.
# --------------------------------------------------------------------------


def test_multi_word_pin_is_preserved_as_separate_argv_elements(sandbox: Sandbox):
    """``py -3`` is genuinely two words; that is why PM_PY is an array."""
    sandbox.stub("py")
    r = sandbox.run(pin={"PMOVES_PYTHON": "py -3"})
    assert r.ok, r
    assert r.argv == ["py", "-3"], r


def test_multi_word_pin_honours_the_probe(sandbox: Sandbox):
    sandbox.stub("py", fails_import="yaml")
    r = sandbox.run("yaml", pin={"PMOVES_PYTHON": "py -3"})
    assert not r.ok, f"pin failed the probe but was accepted: {r!r}"
    assert r.count == 0, r


def test_a_pinned_interpreter_that_does_not_exist_is_rejected(sandbox: Sandbox):
    """No probe still has to mean "runnable".

    Without this, ``PMOVES_PYTHON=/opt/removed/python`` returns 0 and the caller
    fails on exec having been told discovery succeeded -- the same silence as
    the empty-array bug, one step further along.
    """
    sandbox.stub("python3")
    missing = str(sandbox.root / "no" / "such" / "python")
    r = sandbox.run(pin={"PMOVES_PYTHON": missing})
    assert not r.ok, r
    assert r.count == 0, r


def test_a_valid_pin_is_accepted_without_a_probe(sandbox: Sandbox):
    sandbox.stub("python3")
    r = sandbox.run(pin={"PMOVES_PYTHON": "python3"})
    assert r.ok, r
    assert r.argv == ["python3"], r


def test_pin_wins_over_the_venv(sandbox: Sandbox):
    """Operator pinning is the documented purpose of PMOVES_PYTHON."""
    sandbox.venv_python()
    sandbox.stub("py")
    r = sandbox.run(pin={"PMOVES_PYTHON": "py -3"})
    assert r.ok, r
    assert r.argv == ["py", "-3"], r


def test_empty_pin_falls_through_to_normal_discovery(sandbox: Sandbox):
    """``PMOVES_PYTHON=`` is "unset", not "pinned to nothing" -- `[ -n "" ]`."""
    sandbox.stub("python3")
    r = sandbox.run(pin={"PMOVES_PYTHON": ""})
    assert r.ok, r
    assert r.argv == ["python3"], r


# --------------------------------------------------------------------------
# 4. Discovery order, and the space-safety claim in the file's own header.
# --------------------------------------------------------------------------


def test_venv_wins_and_survives_a_path_containing_spaces(tmp_path: Path):
    """The header claims the venv path is "space-safe as one array element".

    Nothing checked it. A checkout under a directory with a space -- the normal
    case on Windows nodes -- would otherwise split the interpreter path into two
    argv elements and fail on exec.
    """
    sb = Sandbox(tmp_path / "dir with space")
    sb.stub("python3")
    venv = sb.venv_python()
    r = sb.run()
    assert r.ok, r
    assert len(r.argv) == 1 and names_path(r.argv[0], venv, sb.root), (
        f"venv path was split or skipped: {r!r}")
    assert " " in r.argv[0], "test did not actually exercise a spaced path"


def test_a_spaced_venv_path_also_survives_a_probe(tmp_path: Path):
    sb = Sandbox(tmp_path / "dir with space")
    venv = sb.venv_python()
    r = sb.run("yaml")
    assert r.ok, r
    assert len(r.argv) == 1 and names_path(r.argv[0], venv, sb.root), r


def test_venv_failing_the_probe_falls_through_to_python3(tmp_path: Path):
    sb = Sandbox(tmp_path)
    sb.venv_python(fails_import="yaml")
    sb.stub("python3")
    r = sb.run("yaml")
    assert r.ok, r
    assert r.argv == ["python3"], r


def test_windows_venv_layout_is_found(tmp_path: Path):
    """Scripts/python.exe -- the branch a Linux-only CI run would never reach."""
    sb = Sandbox(tmp_path)
    venv = sb.venv_python(subdir="Scripts")
    r = sb.run()
    assert r.ok, r
    assert len(r.argv) == 1 and names_path(r.argv[0], venv, sb.root), r


def test_python3_is_preferred_over_py_and_python(tmp_path: Path):
    sb = Sandbox(tmp_path)
    sb.stub("python3")
    sb.stub("py")
    sb.stub("python")
    r = sb.run()
    assert r.ok, r
    assert r.argv == ["python3"], r


def test_py_dash_three_is_used_when_python3_is_absent(tmp_path: Path):
    sb = Sandbox(tmp_path)
    sb.stub("py")
    r = sb.run()
    assert r.ok, r
    assert r.argv == ["py", "-3"], r


def test_bare_python_is_the_last_resort(tmp_path: Path):
    sb = Sandbox(tmp_path)
    sb.stub("python")
    r = sb.run()
    assert r.ok, r
    assert r.argv == ["python"], r


def test_no_interpreter_anywhere_returns_nonzero_and_leaves_pm_py_empty(
    tmp_path: Path,
):
    sb = Sandbox(tmp_path)
    r = sb.run()
    assert not r.ok, r
    assert r.count == 0, f"PM_PY must not carry a value after a failed pick: {r!r}"


def test_probe_failing_everywhere_returns_nonzero(tmp_path: Path):
    sb = Sandbox(tmp_path)
    sb.venv_python(fails_import="yaml")
    sb.stub("python3", fails_import="yaml")
    sb.stub("py", fails_import="yaml")
    sb.stub("python", fails_import="yaml")
    r = sb.run("yaml")
    assert not r.ok, r
    assert r.count == 0, r


# --------------------------------------------------------------------------
# 5. Cross-call hygiene.
# --------------------------------------------------------------------------


def test_a_failed_pick_does_not_leave_the_previous_result_behind(tmp_path: Path):
    """PM_PY is a global that no caller declares.

    A caller that checks ``${#PM_PY[@]}`` rather than the return code would
    otherwise reuse the interpreter from an earlier call that the later probe
    just rejected -- and ``pmoves/scripts/claude-pmoves.sh`` does exactly that
    shape of check, two lines apart.
    """
    sb = Sandbox(tmp_path)
    sb.stub("python3", fails_import="yaml")
    harness = HARNESS.replace(
        'if pm_pick_python "$@"; then rc=0; else rc=$?; fi',
        "pm_pick_python || true\n"
        'if pm_pick_python yaml; then rc=0; else rc=$?; fi',
    )
    r = sb.run_harness(harness)
    assert not r.ok, r
    assert r.count == 0, (
        f"PM_PY still holds the first call's result after the second failed: {r!r}"
    )
