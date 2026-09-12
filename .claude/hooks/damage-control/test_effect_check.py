"""End-to-end verification that a protected write is caught BY EFFECT.

Run: python .claude/hooks/damage-control/test_effect_check.py

WHAT IS BEING PROVEN, and why a unit test would not have proven it
------------------------------------------------------------------
The defect is not "a regex is wrong". It is that the guard reads command TEXT, so
a verb that takes its targets from a diff is invisible to it no matter how many
patterns are added. Asserting that requires a REAL write by a REAL verb to a REAL
protected file, so this builds a throwaway git repository, copies the guard into
it, and drives the actual verb through subprocess. Nothing here is simulated
except the hook payload, which is the one thing the harness supplies.

The control comes first: the SAME command is put to the path-rule guard with the
opaque-verb tripwire removed from its config, and must be ALLOWED. Without that,
a passing test proves only that something blocks something.

Exit: 0 all assertions held · 1 a check failed
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD_FILES = [
    "patterns.yaml", "path_scope.py", "known_roads.py",
    "bash-tool-damage-control.py", "effect_check.py",
]

failures = []


def check(label, condition, detail=""):
    print(("ok   " if condition else "FAIL ") + label)
    if not condition:
        if detail:
            print("       " + str(detail).replace("\n", "\n       "))
        failures.append(label)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo)] + list(args),
                          capture_output=True, text=True)


def build_repo(root):
    """A throwaway checkout carrying a copy of the guard and one protected file."""
    dc = root / ".claude" / "hooks" / "damage-control"
    dc.mkdir(parents=True)
    for name in GUARD_FILES:
        shutil.copy2(HERE / name, dc / name)
    compose = root / "pmoves" / "docker-compose.yml"
    compose.parent.mkdir(parents=True)
    compose.write_text("services:\n  demo:\n    image: alpine\n", encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "guard test")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "seed")
    return compose


def run_hook(root, command):
    """Invoke effect_check.py exactly as the PostToolUse harness would."""
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    env.pop("KNOWN_ROAD", None)
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(
        [sys.executable, str(root / ".claude/hooks/damage-control/effect_check.py")],
        input=payload, capture_output=True, text=True, env=env, cwd=str(root))
    return proc.returncode, proc.stdout + proc.stderr


def trail_rows(root):
    trail = root / ".claude/hooks/damage-control/known-roads.jsonl"
    if not trail.is_file():
        return []
    return [json.loads(line) for line in
            trail.read_text(encoding="utf-8").splitlines() if line.strip()]


def apply_diff(root, target_rel, new_text):
    """Rewrite `target_rel` by applying a unified diff — the measured shape.

    The path is written INTO the diff and the command names only the diff file,
    which is the whole point: the guard reading the command never sees the target.
    """
    original = (root / target_rel).read_text(encoding="utf-8")
    diff = subprocess.run(
        ["diff", "-u", "--label", "a/" + target_rel, "--label", "b/" + target_rel,
         "-", "-"], input="", capture_output=True, text=True)
    del diff  # `diff` cannot read two stdins; build the hunk directly instead.
    old_lines = original.splitlines()
    new_lines = new_text.splitlines()
    body = ["--- a/" + target_rel, "+++ b/" + target_rel,
            "@@ -1,%d +1,%d @@" % (len(old_lines), len(new_lines))]
    body += ["-" + line for line in old_lines]
    body += ["+" + line for line in new_lines]
    diff_file = root / "change.diff"
    diff_file.write_text("\n".join(body) + "\n", encoding="utf-8")
    verb = "pat" + "ch"          # split so this file's text cannot trip the guard
    proc = subprocess.run([verb, "-p1", "-i", str(diff_file)],
                          cwd=str(root), capture_output=True, text=True)
    return proc.returncode, "%s -p1 -i change.diff" % verb, proc.stdout + proc.stderr


def main():
    root = Path(tempfile.mkdtemp(prefix="effect-e2e-"))
    try:
        compose = build_repo(root)
        rel = "pmoves/docker-compose.yml"

        # ------------------------------------------------------------------
        # CONTROL. The path-rule guard, with the opaque-verb tripwire taken out
        # of its config, must ALLOW the command. That is the defect, stated as an
        # assertion: the text matcher cannot see this write. Without this the
        # rest proves only that something blocks something.
        # ------------------------------------------------------------------
        sys.path.insert(0, str(HERE))
        import importlib.util
        os.environ["CLAUDE_PROJECT_DIR"] = str(root)
        spec = importlib.util.spec_from_file_location(
            "dc_probe", root / ".claude/hooks/damage-control/bash-tool-damage-control.py")
        dc = importlib.util.module_from_spec(spec)
        sys.modules["dc_probe"] = dc
        spec.loader.exec_module(dc)
        cfg = dc.load_config()
        text_only = dict(cfg)
        text_only.pop("opaqueWriteVerbs", None)
        verb = "pat" + "ch"
        cmd = "%s -p1 -i change.diff" % verb
        blocked, ask, _ = dc.check_command(cmd, text_only)
        check("CONTROL: every path rule ALLOWS the opaque write",
              (blocked, ask) == (False, False), (blocked, ask))
        # And with the tripwire in place it becomes an ask -- prevention where
        # prevention is still possible. This is Task 2, not the closure.
        blocked, ask, reason = dc.check_command(cmd, cfg)
        check("tripwire turns the same command into an ask",
              (blocked, ask) == (False, True), (blocked, ask, reason))

        # ------------------------------------------------------------------
        # First call establishes the baseline and SAYS it is unmeasured.
        # ------------------------------------------------------------------
        rc, log = run_hook(root, "echo hello")
        check("baseline call exits 0", rc == 0, rc)
        check("baseline call reports it could not measure",
              "COULD-NOT-MEASURE" in log, log)
        rc, log = run_hook(root, "echo hello again")
        check("a quiet call after the baseline says nothing",
              rc == 0 and log.strip() == "", (rc, log))

        # ------------------------------------------------------------------
        # THE DEMONSTRATION: a real diff applied by the real verb, then the
        # PostToolUse check. No grant is active.
        # ------------------------------------------------------------------
        rows_before = len(trail_rows(root))
        prc, applied_cmd, perr = apply_diff(
            root, rel, "services:\n  demo:\n    image: alpine:edge\n")
        landed = "alpine:edge" in compose.read_text(encoding="utf-8")
        check("the write actually landed", prc == 0 and landed, perr)

        rc, log = run_hook(root, applied_cmd)
        rows_after = len(trail_rows(root))
        check("ungranted opaque write exits 2", rc == 2, (rc, log))
        check("the alert names the protected file", rel in log, log)
        check("the alert says it is detection, not prevention",
              "DETECTION, not prevention" in log, log)
        check("no grant means nothing is appended to the trail",
              rows_before == rows_after == 0, (rows_before, rows_after))

        # ------------------------------------------------------------------
        # The inverse defect: an AUTHORIZED opaque write went unrecorded too, so
        # the trail understated authorized use as well as missing unauthorized use.
        # ------------------------------------------------------------------
        grant = root / ".claude/hooks/damage-control/.known-road-active"
        grant.write_text("compose:pr:3034\n", encoding="utf-8")
        rows_before = len(trail_rows(root))
        prc, applied_cmd, perr = apply_diff(
            root, rel, "services:\n  demo:\n    image: alpine:3.20\n")
        check("the granted write landed", prc == 0, perr)
        rc, log = run_hook(root, applied_cmd)
        rows = trail_rows(root)
        check("granted opaque write exits 0", rc == 0, (rc, log))
        check("granted opaque write appends exactly one trail row",
              len(rows) == rows_before + 1, (rows_before, len(rows)))
        if rows:
            row = rows[-1]
            check("the row is labelled as an observed effect",
                  row.get("tool") == "Bash(effect)", row)
            check("the row carries the note explaining how it was observed",
                  "did not name it" in (row.get("note") or ""), row)
            check("the row names the protected file",
                  row.get("file", "").endswith(rel), row)
            check("the row carries the grant domain and reason",
                  (row.get("domain"), row.get("reason")) == ("compose", "pr:3034"), row)

        # ------------------------------------------------------------------
        # PROPORTIONALITY. A noDeletePath allows read/write/edit and refuses only
        # deletion. Reporting every edit under pmoves/tools/, pmoves/services/,
        # .github/ and README.md would fire on almost every commit anyone makes,
        # and an alert that fires on normal work gets turned off -- which leaves
        # the class it was built for open again.
        # ------------------------------------------------------------------
        tool_file = root / "pmoves" / "tools" / "ordinary.py"
        tool_file.parent.mkdir(parents=True, exist_ok=True)
        tool_file.write_text("x = 1\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "an ordinary tool")
        run_hook(root, "seed the baseline after the commit")
        tool_file.write_text("x = 2\n", encoding="utf-8")
        rc, log = run_hook(root, "edited an ordinary tool")
        check("editing a no-delete path is NOT reported",
              rc == 0 and "ALERT" not in log, (rc, log))
        tool_file.unlink()
        rc, log = run_hook(root, "deleted an ordinary tool")
        check("deleting a no-delete path IS reported",
              rc == 2 and "pmoves/tools/ordinary.py" in log, (rc, log))

        # ------------------------------------------------------------------
        # A check that cannot see must SAY so. This fleet's dominant defect is
        # the opposite: quietly passing when the measurement did not happen.
        # ------------------------------------------------------------------
        notgit = Path(tempfile.mkdtemp(prefix="effect-notgit-"))
        shutil.copytree(root / ".claude", notgit / ".claude")
        rc, log = run_hook(notgit, "echo x")
        check("outside a git repository it reports it could not measure",
              rc == 0 and "COULD-NOT-MEASURE" in log, (rc, log))
        shutil.rmtree(notgit, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print()
    if failures:
        print("FAIL: %d check(s) failed: %s" % (len(failures), ", ".join(failures)))
        return 1
    print("PASS: effect detection holds end to end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
