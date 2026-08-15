"""In-process verification of INTERPRETER_WRITE_PATTERNS.

Run: python .claude/hooks/damage-control/test_interpreter_writes.py

Every pre-existing pattern keys on a SHELL verb (>, tee, sed -i, cp, mv,
truncate). An interpreter uses none of them, so `python - <<'PY'` followed by
pathlib.write_text() matched nothing and readOnlyPaths were writable from Bash
while the Edit/Write tools were correctly blocked.

Two properties are pinned here, and they pull in opposite directions:

  BLOCKS writes  — otherwise the class is unguarded
  ALLOWS reads   — read-only means read-only, not no-access. A guard that blocks
                   `python -c "print(open(P).read())"` on a read-only path is
                   wrong, and the natural over-broad fix (interpreter + path)
                   does exactly that.

It also asserts every pattern COMPILES. check_path_patterns() catches re.error,
prints a warning and continues — so a malformed pattern does not crash, it
silently protects nothing. That failure mode is invisible in normal operation:
the hook still exits 0 and the write still lands. It cost one debugging cycle to
find while writing these very patterns.
"""
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "bash-tool-damage-control.py"

spec = importlib.util.spec_from_file_location("dc", TOOL)
dc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dc)

PROTECTED = ".claude/context/"

# (should_block, label, command)
CASES = [
    # --- writes: must be blocked -------------------------------------------
    (True, "python heredoc write_text",
     "python - <<'PY'\nimport pathlib\npathlib.Path('.claude/context/mcp-api.md').write_text('x')\nPY"),
    (True, "python open(...,'w')",
     "python -c \"open('.claude/context/mcp-api.md','w').write('x')\""),
    (True, "python3.12 write_bytes",
     "python3.12 - <<'P'\nfrom pathlib import Path\nPath('.claude/context/x.md').write_bytes(b'x')\nP"),
    (True, "python shutil.copy onto the path",
     "python -c \"import shutil; shutil.copy('a','.claude/context/mcp-api.md')\""),
    (True, "python os.remove",
     "python -c \"import os; os.remove('.claude/context/mcp-api.md')\""),
    (True, "node writeFileSync",
     "node -e \"require('fs').writeFileSync('.claude/context/mcp-api.md','x')\""),

    # --- reads and unrelated: must be allowed ------------------------------
    (False, "python read",
     "python -c \"print(open('.claude/context/mcp-api.md').read())\""),
    (False, "cat",
     "cat .claude/context/mcp-api.md"),
    (False, "grep",
     "grep -n foo .claude/context/mcp-api.md"),
    (False, "interpreter write to an UNprotected path",
     "python - <<'PY'\nimport pathlib\npathlib.Path('pmoves/docs/x.md').write_text('x')\nPY"),
    (False, "path named with no interpreter",
     "echo .claude/context/mcp-api.md"),
]


def main() -> int:
    failures = 0

    # 1. every pattern must compile. A pattern that raises re.error is caught,
    #    warned about and skipped -- i.e. silently unguarded.
    for template, op in dc.READ_ONLY_BLOCKED:
        probe = template.replace("{path}", re.escape(PROTECTED))
        try:
            re.compile(probe)
        except re.error as e:
            failures += 1
            print(f"  [FAIL] pattern does not compile ({op}): {e}")
    print(f"  [{'PASS' if not failures else 'FAIL'}] all {len(dc.READ_ONLY_BLOCKED)} read-only patterns compile")

    # 2. behaviour
    for should_block, label, command in CASES:
        blocked, _reason = dc.check_path_patterns(
            command, PROTECTED, dc.READ_ONLY_BLOCKED, "read-only path"
        )
        ok = blocked == should_block
        if not ok:
            failures += 1
        verb = "block" if should_block else "allow"
        print(f"  [{'PASS' if ok else 'FAIL'}] {verb:<5} {label}")

    if failures:
        print(f"\nFAIL — {failures} check(s) failed.")
        return 1
    print(f"\nPASS — {len(CASES)} behaviour checks, patterns compile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
