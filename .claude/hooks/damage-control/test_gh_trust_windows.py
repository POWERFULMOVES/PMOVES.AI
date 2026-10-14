#!/usr/bin/env python3
"""The gh trust check MEASURES the ACL on Windows (issue #3362).

The defect
----------
`_untrusted_reason` decided whether the trusted `gh` directory was writable with
`os.access(path, os.W_OK)`. On Windows that call reads only the read-only file
attribute and ignores ACLs, so `C:\\Program Files\\GitHub CLI` (Users: RX) was
reported writable on every Windows node measured, `_trusted_gh()` raised, and
every `pr:`/`issue:` grant fell back to `!offline` -- the one form that skips the
referent check the trust test exists to protect.

What is asserted
----------------
On Windows:
1. A directory this user can write to (a fresh temp dir) is reported writable.
2. A file this user can write to is reported writable.
3. The same file with the read-only ATTRIBUTE set is still reported writable:
   the attribute is not a permission, the user can clear it (the mirror image of
   the os.access bug; a write-open probe would have called this one trusted).
4. A running executable this user owns is reported writable, not "inconclusive":
   the check reads the DACL, it never opens the file for write, so a sharing
   violation cannot occur (a busy gh.exe must not flake a grant closed).
5. A user-owned file whose DACL has been emptied (icacls /inheritance:r) is
   still reported writable through the owner-implied WRITE_DAC right: an
   empty DACL does not hide a file from its owner.
6. A missing path is "cannot stat", never trusted.
7. If `%ProgramFiles%\\GitHub CLI` exists, it is trusted ("" reason). If the suite
   runs elevated, the directory IS writable and the check must say so -- an
   elevated agent could replace gh.
8. `_untrusted_reason` never raises for any of the above.

These checks run only on Windows nodes; the POSIX CI runner records a pass with
zero checks, so the floor in run_guard_tests.sh proves the file ran, not that
the Windows assertions did. The Windows evidence is the guard-suite output a
Windows node posts on the PR.

The environment is scrubbed of KNOWN_ROAD and KNOWN_ROAD_GH so an operator-set
gh override on the host cannot hijack the `_trusted_gh()` resolution check. The
temp dir is removed on exit.

On POSIX the Windows branch is unreachable; the suite records that it ran and
passes, so the discovered/executed counts in run_guard_tests.sh stay honest.

Exit: 0 all checks held · 1 a check failed
"""
import ctypes
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]
os.environ["CLAUDE_PROJECT_DIR"] = str(TREE)
os.environ.pop("KNOWN_ROAD", None)
os.environ.pop("KNOWN_ROAD_GH", None)
sys.path.insert(0, str(HERE))

import known_roads as KR  # noqa: E402  -- the SAME instance the hooks import

FAILS = []
CHECKS = 0
WRITABLE = "is writable by the current user"


def check(label: str, ok: bool, detail: str = "") -> None:
    """`detail` is kept for a debugger, never printed: the reasons carry absolute
    paths from the trust check, and CodeQL (py/clear-text-logging-sensitive-data)
    treats them as a secret sink. Re-run the checked call to see the value."""
    global CHECKS
    CHECKS += 1
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")
    if not ok:
        FAILS.append((label, detail))


def _elevated() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001 - best effort; only steers one expectation
        return False


def _user_targets(tmp: Path) -> None:
    print("-- user-writable targets are reported writable --")
    why = KR._untrusted_reason(str(tmp))
    check("a fresh temp directory is writable", WRITABLE in why, why)
    f = tmp / "f.txt"
    f.write_text("x", encoding="utf-8")
    why = KR._untrusted_reason(str(f))
    check("a user-owned file is writable", WRITABLE in why, why)
    check("... and it was not truncated", f.read_text(encoding="utf-8") == "x")

    os.chmod(f, stat.S_IREAD)  # sets FILE_ATTRIBUTE_READONLY on Windows
    why = KR._untrusted_reason(str(f))
    check("the same file with the read-only ATTRIBUTE set is still writable (attribute != permission)",
          WRITABLE in why, why)
    check("... and the check did not clear the attribute",
          not os.stat(f).st_mode & stat.S_IWRITE)
    os.chmod(f, stat.S_IREAD | stat.S_IWRITE)

    why = KR._untrusted_reason(sys.executable)
    check("a RUNNING executable is measured, never 'inconclusive' (no write-open, no sharing violation)",
          "inconclusive" not in why, why)

    # Owner-implied rights: strip the inherited ACEs so the DACL is EMPTY. The
    # file is still owned by this user, and AccessCheck grants the owner
    # READ_CONTROL | WRITE_DAC implicitly -- enough to re-grant everything.
    g = tmp / "owner-only.txt"
    g.write_text("x", encoding="utf-8")
    stripped = subprocess.run(["icacls", str(g), "/inheritance:r"],
                              capture_output=True, text=True).returncode == 0
    if not stripped:
        print("  skip  icacls could not strip the DACL; owner-implied rights not exercised")
    else:
        try:
            why = KR._untrusted_reason(str(g))
            check("a user-OWNED file with an EMPTY DACL is writable (owner-implied WRITE_DAC)",
                  WRITABLE in why and "write DAC" in why, why)
        finally:
            subprocess.run(["icacls", str(g), "/reset"], capture_output=True)

    why = KR._untrusted_reason(str(tmp / "nope"))
    check("a missing path is 'cannot stat', not trusted", why.startswith("cannot stat"), why)


def _program_files() -> None:
    print("-- the real trusted location --")
    pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "GitHub CLI"
    if not pf.is_dir():
        print("  skip  %ProgramFiles%\\GitHub CLI is absent on this node; the positive case needs the standard install")
        return
    why = KR._untrusted_reason(str(pf))
    if _elevated():
        check("ELEVATED session: Program Files is writable and the check says so", WRITABLE in why, why)
        return
    check("non-elevated: Program Files\\GitHub CLI is trusted (no alter right granted)", why == "", why)
    gh = pf / "gh.exe"
    if not gh.is_file():
        return
    why = KR._untrusted_reason(str(gh))
    check("non-elevated: gh.exe itself is trusted", why == "", why)
    try:
        got = KR._trusted_gh()
        check("_trusted_gh() resolves to the Program Files gh", Path(got) == gh.resolve(), got)
    except KR.GrantUnverifiable as exc:  # pragma: no cover - the bug
        check("_trusted_gh() resolves to the Program Files gh", False, str(exc))


def main() -> int:
    print("== gh trust check measures the ACL on Windows (#3362) ==")
    if os.name != "nt":
        print("  skip  not Windows: the branch under test is unreachable here")
        print("PASS: 0 checks (POSIX branch is covered by test_grant_expiry.py)")
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="kr-ghtrust-"))
    try:
        _user_targets(tmp)
        _program_files()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if FAILS:
        print(f"FAIL: {len(FAILS)} of {CHECKS} checks failed.")
        for name, _detail in FAILS:
            print(f"  - {name}")
        return 1
    print(f"PASS: {CHECKS} checks held.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
