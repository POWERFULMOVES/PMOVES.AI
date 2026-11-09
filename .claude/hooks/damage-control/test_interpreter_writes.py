"""In-process verification of INTERPRETER_WRITE_PATTERNS / INTERPRETER_DELETE_PATTERNS.

Run: python .claude/hooks/damage-control/test_interpreter_writes.py

Every other pattern in the hook keys on a SHELL verb (>, tee, sed -i, cp, mv).
An interpreter uses none of them, so `python - <<'PY'` + pathlib.write_text()
matched nothing: readOnlyPaths were writable from Bash while Edit/Write were
correctly blocked.

The first attempt at closing that asserted "an interpreter runs" AND "a write
verb appears" independently, then only required the path to occur somewhere.
Review found seven defects. The ALLOW cases below are that review's findings
turned into tests — they are the important half of this file, because the
over-broad version passed every BLOCK case while bricking ordinary commands.
"""
import importlib.util
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "bash-tool-damage-control.py"

spec = importlib.util.spec_from_file_location("dc", TOOL)
dc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dc)

CTX = ".claude/context/"

# (should_block, label, command) against readOnlyPath CTX
READ_ONLY_CASES = [
    # --- writes: must block ------------------------------------------------
    (True, "Path(P).write_text",
     "python - <<'PY'\nimport pathlib\npathlib.Path('.claude/context/mcp-api.md').write_text('x')\nPY"),
    (True, "open(P,'w')",
     "python -c \"open('.claude/context/mcp-api.md','w').write('x')\""),
    (True, "node writeFileSync(P)",
     "node -e \"require('fs').writeFileSync('.claude/context/mcp-api.md','x')\""),
    (True, "shutil.copy(src, P)",
     "python -c \"import shutil; shutil.copy('a','.claude/context/mcp-api.md')\""),
    (True, "os.remove(P)",
     "python -c \"import os; os.remove('.claude/context/mcp-api.md')\""),
    # review finding 5 — the class was NOT closed for these
    (True, "Path(P).unlink()",
     "python -c \"from pathlib import Path; Path('.claude/context/x.md').unlink()\""),
    (True, "shutil.rmtree(P)",
     "python -c \"import shutil; shutil.rmtree('.claude/context')\""),
    (True, "os.truncate(P, 0)",
     "python -c \"import os; os.truncate('.claude/context/x.md', 0)\""),
    # review finding 7 — Windows-primary fleet
    (True, "powershell Set-Content -Path P",
     "powershell -c \"Set-Content -Path '.claude/context/x.md' -Value 'x'\""),

    # --- reads and unrelated: must allow -----------------------------------
    (False, "python read",
     "python -c \"print(open('.claude/context/mcp-api.md').read())\""),
    (False, "cat", "cat .claude/context/mcp-api.md"),
    (False, "grep", "grep -n foo .claude/context/mcp-api.md"),
    (False, "interpreter write to an UNprotected path",
     "python - <<'PY'\nimport pathlib\npathlib.Path('pmoves/docs/x.md').write_text('x')\nPY"),
    (False, "path named with no interpreter", "echo .claude/context/mcp-api.md"),
    # review finding 3 — read protected, write elsewhere. The canonical
    # regenerate-a-doc-from-context script; the over-broad version blocked it.
    (False, "read P, write elsewhere",
     "python - <<'PY'\nfrom pathlib import Path\n"
     "Path('pmoves/docs/out.md').write_text(Path('.claude/context/nats-subjects.md').read_text())\nPY"),
    # review finding 4 — differs from the passing read case only by the sink
    (False, "sys.stdout.write(open(P).read())",
     "python -c \"import sys; sys.stdout.write(open('.claude/context/mcp-api.md').read())\""),
]

# review finding 2 — readOnlyPaths contains these, and they appear as BARE
# command fragments in ordinary commands. Requiring the path to be QUOTED is
# what keeps them out.
INCIDENTAL_PATH_CASES = [
    ("/usr/", "absolute interpreter path",
     "/usr/bin/python3 -c \"from pathlib import Path; Path('a.txt').write_text('x')\""),
    ("/bin/", "venv activate then write",
     "source .venv/bin/activate && python -c \"open('out.txt','w').write('x')\""),
    ("build/", "write then list build dir",
     "node -e \"require('fs').writeFileSync('report.json','x')\" && ls build/"),
]

# review finding 6 — NO_DELETE_BLOCKED was never extended
NO_DELETE_CASES = [
    (True, "os.remove on a noDeletePath", "CLAUDE.md",
     "python -c \"import os; os.remove('CLAUDE.md')\""),
    (True, "shutil.rmtree on a noDeletePath", "pmoves/services/",
     "python -c \"import shutil; shutil.rmtree('pmoves/services/gateway')\""),
    (False, "reading a noDeletePath is fine", "CLAUDE.md",
     "python -c \"print(open('CLAUDE.md').read())\""),
]


# The trailing-slash bypass was PRE-EXISTING and affected every pattern class,
# not just the interpreter ones: configured directory paths end with "/" and
# re.escape() kept that slash mandatory, so dropping one character walked past
# the guard. Assembled from fragments so this file contains no literal that the
# hook's own BLOCKED_PATTERNS would trip on.
_DEL = "r" + "m -" + "rf "
DIRECTORY_BYPASS_CASES = [
    (True, "delete protected dir WITH trailing slash", "pmoves/tools/", _DEL + "pmoves/tools/"),
    (True, "delete protected dir WITHOUT slash",       "pmoves/tools/", _DEL + "pmoves/tools"),
    # must not over-block a genuinely different directory that shares a prefix
    (False, "different dir sharing a prefix",          "pmoves/tools/", _DEL + "pmoves/toolsmith"),
    (False, "different dir, hyphen suffix",            "pmoves/tools/", _DEL + "pmoves/tools-old"),
]



# EVERY case above is checked against CTX, a LITERAL readOnlyPath. That is exactly
# why this suite stayed green while the 12 GLOB readOnlyPaths had no interpreter
# protection at all: check_path_patterns takes a different branch for globs, and
# no case here ever exercised it. These carry their own protected path, like
# DIRECTORY_BYPASS_CASES, so both branches are covered.
GLOB_PATH_CASES = [
    (True, "interpreter write to a glob read-only path", 'pmoves/docker-compose*.yml',
     "python -c \"import io; io.open('pmoves/docker-compose.ui.yml','w').write(1)\""),
    (True, "Path(glob path).write_text", 'pmoves/docker-compose*.yml',
     "python -c \"from pathlib import Path; Path('pmoves/docker-compose.ui.yml').write_text('x')\""),
    (True, "interpreter write to a *-suffix glob path", '*.lock',
     "python -c \"import io; io.open('poetry.lock','w').write(1)\""),
    # the shell branch must not regress -- it worked before and must keep working
    (True, "shell edit on a glob path", 'pmoves/docker-compose*.yml',
     "sed -i 's/a/b/' pmoves/docker-compose.ui.yml"),
    # and reads stay allowed: read-only means read-only, not no-access
    (False, "read a glob read-only path", 'pmoves/docker-compose*.yml',
     "python -c \"import io; print(io.open('pmoves/docker-compose.ui.yml').read())\""),
    (False, "write to a path the glob does not cover", 'pmoves/docker-compose*.yml',
     "python -c \"import io; io.open('pmoves/docs/out.md','w').write(1)\""),
]


def main() -> int:
    failures = 0

    for template, op in dc.READ_ONLY_BLOCKED + dc.NO_DELETE_BLOCKED:
        try:
            re.compile(template.replace("{path}", re.escape(CTX)))
        except re.error as e:
            failures += 1
            print(f"  [FAIL] pattern does not compile ({op}): {e}")
    print(f"  [{'PASS' if not failures else 'FAIL'}] all patterns compile")

    for should_block, label, command in READ_ONLY_CASES:
        blocked, _ = dc.check_path_patterns(command, CTX, dc.READ_ONLY_BLOCKED, "read-only path")
        ok = blocked == should_block
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {'block' if should_block else 'allow':<5} {label}")

    for protected, label, command in INCIDENTAL_PATH_CASES:
        blocked, _ = dc.check_path_patterns(command, protected, dc.READ_ONLY_BLOCKED, "read-only path")
        ok = not blocked
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] allow {label} (incidental {protected})")

    for should_block, label, protected, command in NO_DELETE_CASES:
        blocked, _ = dc.check_path_patterns(command, protected, dc.NO_DELETE_BLOCKED, "no-delete path")
        ok = blocked == should_block
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {'block' if should_block else 'allow':<5} {label}")

    for should_block, label, protected, command in DIRECTORY_BYPASS_CASES:
        blocked, _ = dc.check_path_patterns(command, protected, dc.NO_DELETE_BLOCKED, "no-delete path")
        ok = blocked == should_block
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {'block' if should_block else 'allow':<5} {label}")

    for should_block, label, protected, command in GLOB_PATH_CASES:
        blocked, _ = dc.check_path_patterns(command, protected, dc.READ_ONLY_BLOCKED, "read-only path")
        ok = blocked == should_block
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {'block' if should_block else 'allow':<5} {label}")

    # review finding 1 — the over-broad version took 22s on a 5 KB command in a
    # BLOCKING PreToolUse hook. Guard the regression, not just the behaviour.
    big = "echo " + ("a" * 5000)
    t0 = time.perf_counter()
    for template, _op in dc.READ_ONLY_BLOCKED:
        try:
            re.search(template.replace("{path}", re.escape(CTX)), big)
        except re.error:
            pass
    elapsed = time.perf_counter() - t0
    ok = elapsed < 1.0
    failures += 0 if ok else 1
    print(f"  [{'PASS' if ok else 'FAIL'}] 5KB command scans in {elapsed:.3f}s (must be < 1.0s)")

    if failures:
        print(f"\nFAIL — {failures} check(s) failed.")
        return 1
    print("\nPASS — all checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
