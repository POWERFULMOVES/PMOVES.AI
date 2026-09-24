"""No damage-control hook may exit with anything but 0 or 2.

Run: python .claude/hooks/damage-control/test_fail_closed.py

WHY (review of #3174, F1, confirmed): a poisoned grant-state cache made the guard
raise, the hook exited 1, and for PreToolUse any code other than 2 is
NON-BLOCKING -- the protected edit went ahead with no trail row. These checks run
the REAL hook scripts as subprocesses, exactly as the harness does, inside a
throwaway tree that carries a copy of the guard, so every exit code asserted here
is the one Claude Code would see.

No network: every hook runs with KNOWN_ROAD_GH pointing at a path that does not
exist, so any GitHub lookup refuses as unverifiable instead of calling out. No
real grant is read or written: grant files exist only inside the throwaway tree.

Paths are assembled from parts so this file's text cannot trip the guard.

Exit: 0 all checks held · 1 a check failed
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD_FILES = ["patterns.yaml", "path_scope.py", "known_roads.py", "fail_closed.py",
               "bash-tool-damage-control.py", "edit-tool-damage-control.py",
               "write-tool-damage-control.py", "effect_check.py"]
DC_REL = Path(".claude") / "hooks" / ("damage-" + "control")
COMPOSE = "pmoves/docker-" + "compose.yml"
EDIT_CMD = "s" + "ed -i s/a/b/ " + COMPOSE
HOOKS = {"bash": "bash-tool-damage-control.py", "edit": "edit-tool-damage-control.py",
         "write": "write-tool-damage-control.py", "effect": "effect_check.py"}

failures = []
checks = 0


def check(label, cond, detail=""):
    global checks
    checks += 1
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        failures.append(label)
        print("         " + repr(detail)[:500])


def build_tree():
    root = Path(tempfile.mkdtemp(prefix="dc-failclosed-"))
    dc = root / DC_REL
    dc.mkdir(parents=True)
    for name in GUARD_FILES:
        shutil.copy2(HERE / name, dc / name)
    (root / "pmoves").mkdir()
    (root / COMPOSE).write_text("services: {}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def env_for(root, grant=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root),
               KNOWN_ROAD_GH=str(root / "no-such-dir" / "gh"))
    env.pop("KNOWN_ROAD", None)
    if grant:
        env["KNOWN_ROAD"] = grant
    return env


def payload(kind, root):
    if kind == "bash" or kind == "effect":
        return {"tool_name": "Bash", "tool_input": {"command": EDIT_CMD}}
    tool = "Edit" if kind == "edit" else "Write"
    return {"tool_name": tool, "tool_input": {
        "file_path": str(root / COMPOSE), "content": "x",
        "old_string": "services", "new_string": "servicez"}}


def run(root, kind, stdin, env, pre=""):
    """Run hook `kind`; `pre` is Python executed first, in the hook's process."""
    hook = str(root / DC_REL / HOOKS[kind])
    if pre:
        code = ("import sys, runpy; sys.path.insert(0, %r); %s; "
                "sys.argv=[%r]; runpy.run_path(%r, run_name='__main__')"
                % (str(root / DC_REL), pre, hook, hook))
        argv = [sys.executable, "-c", code]
    else:
        argv = [sys.executable, hook]
    p = subprocess.run(argv, input=stdin, capture_output=True, text=True, env=env,
                       cwd=str(root), timeout=60)
    return p.returncode, p.stdout, p.stderr


def main():
    root = build_tree()
    dc = root / DC_REL
    cache = dc / (".grant-state-" + "cache.json")

    print("-- sanity: the wrapper leaves normal verdicts alone --")
    rc, out, err = run(root, "bash", json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}), env_for(root))
    check("a benign command still exits 0", rc == 0, (rc, err))
    rc, out, err = run(root, "bash", json.dumps(payload("bash", root)), env_for(root))
    check("an ungranted protected edit still exits 2 with the guard's own reason",
          rc == 2 and "SECURITY:" in err and "guard error" not in err, (rc, err))

    print("-- F1: poisoned cache, every PreToolUse hook --")
    poisons = {
        "checked: 10**400": ('{"POWERFULMOVES/PMOVES.AI#pr:3101": {"state": "open", '
                             '"checked": 1' + "0" * 400 + '}}').encode(),
        "200k-deep [": b"[" * 200000,
    }
    for label, raw in poisons.items():
        for kind in ("bash", "edit", "write"):
            cache.write_bytes(raw)
            rc, out, err = run(root, kind, json.dumps(payload(kind, root)),
                               env_for(root, "compose:pr:3101"))
            check("%s guard, poisoned cache (%s): exit 2 with a message"
                  % (kind, label), rc == 2 and err.strip() != "", (rc, err[-300:]))
            check("... refused because the grant could not be verified, not a crash",
                  "grant not verifiable" in err and "guard error" not in err, err[-300:])
    if cache.exists():
        cache.unlink()

    print("-- a non-UTF-8 grant file grants nothing, and the edit is blocked --")
    grant = dc / (".known-road-" + "active")
    grant.write_bytes(b"compose:pr:3200\xff\n")
    for kind in ("bash", "edit", "write"):
        rc, out, err = run(root, kind, json.dumps(payload(kind, root)), env_for(root))
        check("%s guard with a non-UTF-8 grant: exit 2 with a message" % kind,
              rc == 2 and err.strip() != "", (rc, err[-300:]))
    grant.unlink()

    print("-- generic: an exception injected inside each hook blocks --")
    # set_hook_input is called unconditionally near the top of every hook's
    # main(); replacing it on the shared module reaches all four.
    boom = ("import known_roads; "
            "known_roads.set_hook_input = (lambda *a, **k: (_ for _ in ()).throw("
            "RuntimeError('injected')))")
    for kind in ("bash", "edit", "write", "effect"):
        rc, out, err = run(root, kind, json.dumps(payload(kind, root)), env_for(root), boom)
        want = "EFFECT-CHECK GUARD ERROR" if kind == "effect" else "guard error, refusing"
        check("%s hook: injected RuntimeError exits 2" % kind, rc == 2, (rc, err[-300:]))
        check("... naming the type, with the event-appropriate message",
              want in err and "RuntimeError" in err, err[-300:])
        check("... and not the exception text (it can carry file contents)",
              "injected" not in err, err[-300:])

    print("-- the pre-existing sys.exit(1) on unreadable input no longer fails open --")
    for kind in ("bash", "edit", "write"):
        rc, out, err = run(root, kind, "{not json", env_for(root))
        check("%s guard with unreadable hook input: exit 2 (was 1)" % kind,
              rc == 2 and "code 1" in err, (rc, err[-300:]))

    print()
    if failures:
        print("FAIL: %d of %d checks failed." % (len(failures), checks))
        return 1
    print("PASS — all %d checks." % checks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
