#!/usr/bin/env python3
"""The gh trust check MEASURES writability on Windows (issue #3362).

The defect
----------
`_untrusted_reason` decided whether the trusted `gh` directory was writable with
`os.access(path, os.W_OK)`. On Windows that call reads only the read-only file
attribute and ignores ACLs, so `C:\\Program Files\\GitHub CLI` (Users: RX) was
reported writable on every node, `_trusted_gh()` raised, and every `pr:`/`issue:`
grant fell back to `!offline` -- the one form that skips the referent check the
trust test exists to protect. Measured on z890 and 5090, 2026-10-11/12.

What is asserted
----------------
On Windows:
1. A directory this user can write to (a fresh temp dir) is reported writable.
2. A file this user can write to is reported writable.
3. A missing path is "cannot stat", never trusted.
4. If `%ProgramFiles%\\GitHub CLI` exists, it is trusted ("" reason) and no probe
   file is left behind. If the suite runs elevated, the directory IS writable and
   the check must say so -- an elevated agent could replace gh.
5. `_untrusted_reason` never raises for any of the above.

On POSIX the Windows branch is unreachable; the suite records that it ran and
passes, so the discovered/executed counts in run_guard_tests.sh stay honest.

Exit: 0 all checks held · 1 a check failed
"""
import ctypes
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]
os.environ["CLAUDE_PROJECT_DIR"] = str(TREE)
os.environ.pop("KNOWN_ROAD", None)
sys.path.insert(0, str(HERE))

import known_roads as KR  # noqa: E402  -- the SAME instance the hooks import

FAILS = []
CHECKS = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    """`detail` is kept for a debugger, never printed: the reasons carry absolute
    paths from the trust probe, and CodeQL (py/clear-text-logging-sensitive-data)
    treats them as a secret sink. Re-run the probed call to see the value."""
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


def main() -> int:
    print("== gh trust check measures writability on Windows (#3362) ==")
    if os.name != "nt":
        print("  skip  not Windows: the os.access branch under test is unreachable here")
        print("PASS: 0 checks (POSIX branch is covered by test_grant_expiry.py)")
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="kr-ghtrust-"))
    print("-- user-writable targets are reported writable --")
    why = KR._untrusted_reason(str(tmp))
    check("a fresh temp directory is writable", why.endswith("is writable (probe file created)"), why)
    check("... and the probe file was removed", not any(p.name.startswith(".known-roads-probe") for p in tmp.iterdir()))
    f = tmp / "f.txt"
    f.write_text("x", encoding="utf-8")
    why = KR._untrusted_reason(str(f))
    check("a user-owned file is writable", why.endswith("is writable (opened for write)"), why)
    check("... and opening it for write did not truncate it", f.read_text(encoding="utf-8") == "x")
    why = KR._untrusted_reason(str(tmp / "nope"))
    check("a missing path is 'cannot stat', not trusted", why.startswith("cannot stat"), why)

    print("-- the real trusted location --")
    pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "GitHub CLI"
    if not pf.is_dir():
        print(f"  skip  {pf} is absent on this node; the positive case needs the winget install")
    else:
        why = KR._untrusted_reason(str(pf))
        if _elevated():
            check("ELEVATED session: Program Files is writable and the check says so",
                  why.endswith("is writable (probe file created)"), why)
        else:
            check("non-elevated: Program Files\\GitHub CLI is trusted (ACCESS_DENIED measured)", why == "", why)
            gh = pf / "gh.exe"
            if gh.is_file():
                why = KR._untrusted_reason(str(gh))
                check("non-elevated: gh.exe itself is trusted", why == "", why)
                try:
                    got = KR._trusted_gh()
                    check("_trusted_gh() resolves to the Program Files gh", Path(got) == gh.resolve(), got)
                except KR.GrantUnverifiable as exc:  # pragma: no cover - the bug
                    check("_trusted_gh() resolves to the Program Files gh", False, str(exc))
        check("no probe file left in Program Files",
              not any(p.name.startswith(".known-roads-probe") for p in pf.iterdir()))

    if FAILS:
        print(f"FAIL: {len(FAILS)} of {CHECKS} checks failed.")
        for name, _detail in FAILS:
            print(f"  - {name}")
        return 1
    print(f"PASS: {CHECKS} checks held.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
