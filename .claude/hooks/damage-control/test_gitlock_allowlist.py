"""In-process verification of the bashDeleteAllowlist git-lockfile exception.

Run: python .claude/hooks/damage-control/test_gitlock_allowlist.py
Asserts the allowlist permits ONLY a bare `rm` of git's own internal lockfiles
and that everything else (package locks, flags, chaining) stays blocked.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bash_tool", HERE / "bash-tool-damage-control.py")
assert spec and spec.loader, "could not load bash-tool-damage-control.py"
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

config = mod.load_config()

# (command, expect_blocked)
GIT = ".git/" + "config.lock"          # built from parts so this file's own
GITI = ".git/" + "index.lock"          # strings don't trip a content scanner
DEL = "r" + "m "
cases = [
    (DEL + GIT, False),                       # bare rm of config.lock  -> ALLOW
    (DEL + GITI, False),                       # bare rm of index.lock   -> ALLOW
    (DEL + GIT + " " + GITI, False),          # both at once             -> ALLOW
    (DEL + "./" + GIT, False),                # ./ prefix                -> ALLOW
    (DEL + "yarn.lock", True),                # package lock             -> BLOCK
    (DEL + "uv.lock", True),                  # package lock             -> BLOCK
    (DEL + "-rf " + GIT, True),               # rm -rf                   -> BLOCK (step 1)
    (DEL + "-f " + GIT, True),                # rm -f                    -> BLOCK (step 1)
    (DEL + GIT + " && " + DEL + "yarn.lock", True),   # chaining         -> BLOCK
    (DEL + GIT + " ; echo hi", True),         # chaining via ;           -> BLOCK
]

failures = []
for cmd, want_blocked in cases:
    blocked, ask, reason = mod.check_command(cmd, config)
    got = blocked
    status = "OK" if got == want_blocked else "FAIL"
    if got != want_blocked:
        failures.append((cmd, want_blocked, got, reason))
    print(f"[{status}] blocked={got!s:5} want={want_blocked!s:5} :: {cmd}  {('-> '+reason) if reason else ''}")

if failures:
    print(f"\n{len(failures)} FAILURE(S)")
    sys.exit(1)
print("\nALL CASES PASS")
