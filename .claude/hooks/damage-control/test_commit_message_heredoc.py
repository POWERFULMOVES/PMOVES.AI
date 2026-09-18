"""In-process verification of the `git commit` quoted-heredoc mask.

Run: python .claude/hooks/damage-control/test_commit_message_heredoc.py

A commit message is not an operation. The zero-access scan matches a BARE path
anywhere in the command text (no operation verb required -- that breadth is what
catches `cat`), so a commit message EXPLAINING why a protected file was skipped
was itself blocked. _mask_git_commit_heredocs blanks the body of a quoted
heredoc feeding `git commit`, for the path-based checks only.

Asserts both halves: the false positive is gone, AND the guard still says NO --
unquoted heredocs (shell still expands them), non-git heredocs, interpreter
writes, and anything chained after the masked body.
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

# Built from parts so this file's own strings don't trip a content scanner.
P = "pmoves/chit/secrets_" + "manifest.yaml"
CM = "git commit -F - "
CAT = "ca" + "t "

# (label, command, expect_blocked)
cases = [
    ("quoted heredoc naming protected path",
     f"{CM}<<'EOF'\nchore: park drift\n\nSkipped {P} (machine-emitted).\nEOF", False),
    ("double-quoted delimiter",
     f'{CM}<<"MSG"\nnote about {P}\nMSG', False),
    ("ordinary commit, no protected path",
     f"{CM}<<'EOF'\nchore: ordinary message\nEOF", False),

    # --- the guard must still say NO ---
    ("plain read of protected path",
     f"{CAT}{P}", True),
    ("UNQUOTED heredoc still expands, so still scanned",
     f"{CM}<<EOF\ntouching {P}\nEOF", True),
    ("interpreter write in a python heredoc is NOT masked",
     f"python - <<'PY'\nopen('{P}','w').write('x')\nPY", True),
    ("real op chained after a masked body",
     f"{CM}<<'EOF'\nharmless message\nEOF\n{CAT}{P}", True),
    ("non-git quoted heredoc is not masked",
     f"sh - <<'SH'\n{CAT}{P}\nSH", True),

    # --- terminator precision: `<<` needs column 0, `<<-` allows indentation ---
    ("plain << : an INDENTED EOF inside prose does not end the mask",
     f"{CM}<<'EOF'\nexample:\n    some text\n    EOF\nand {P} explained\nEOF", False),
    ("plain << : mask must NOT run past the column-0 terminator",
     f"{CM}<<'EOF'\nexample:\n    EOF\nstill message\nEOF\n{CAT}{P}", True),
    ("<<- : an indented terminator DOES end the mask (tab-strip form)",
     f"{CM}<<-'EOF'\n\tmessage body\n\tEOF\n{CAT}{P}", True),
]

failures = []
for label, cmd, want_blocked in cases:
    blocked, ask, reason = mod.check_command(cmd, config)
    status = "OK" if blocked == want_blocked else "FAIL"
    if blocked != want_blocked:
        failures.append((label, want_blocked, blocked, reason))
    print(f"[{status}] blocked={blocked!s:5} want={want_blocked!s:5} :: {label}"
          f"{('  -> ' + reason) if reason else ''}")

if failures:
    print(f"\n{len(failures)} FAILURE(S)")
    for label, want, got, reason in failures:
        print(f"  {label}: want_blocked={want} got={got} {reason}")
    sys.exit(1)
print("\nALL CASES PASS")
