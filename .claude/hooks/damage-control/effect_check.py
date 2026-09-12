# /// script
# requires-python = ">=3.8"
# dependencies = ["pyyaml"]
# ///
"""PostToolUse effect check -- did a protected file ACTUALLY change?

    PostToolUse(Bash) -> uv run .claude/hooks/damage-control/effect_check.py

WHY THIS EXISTS
---------------
Every pattern in bash-tool-damage-control.py matches COMMAND TEXT, and every one
of them interpolates the protected path into the template. The guard can
therefore only see a write that NAMES a protected path in the command it is
reading. Anything that writes a path it does not spell is invisible to it.

Measured on 2026-09-12: applying a diff from a file wrote two protected compose
files, and the audit trail read 250 rows before and 250 rows after. The verb that
did it appears zero times in the guard. Neither do archive extraction, file
mirroring, block copy, an executed shell script, an executed python script, or a
build-tool target.

That is not a missing pattern. It is the shape of text matching: a text matcher
cannot see effects. Enumerating write verbs is whack-a-mole -- it looks finished
while staying open, which is the more dangerous of the two states.

So this runs AFTER the command and asks a different question. Not "does this
command look like a write to a protected path" but "is a protected path different
than it was". Every verb above answers that question the same way, including the
ones nobody has thought of yet.

WHAT IT DOES
------------
  * changed protected path + a valid Known Road grant  -> RECORD it to
    known-roads.jsonl. This closes the inverse defect too: an authorized change
    made through an unnamed verb was never recorded either, so the trail
    UNDERSTATES authorized use exactly as it misses unauthorized use.
  * changed protected path + no grant  -> say so LOUDLY (exit 2; stderr is fed
    back to the model). The write already happened, so this is detection and
    disclosure, not prevention. Prevention is PreToolUse's job, and PreToolUse
    cannot see this class at all.

WHAT IT CANNOT SEE -- stated, not implied away
----------------------------------------------
  1. UNTRACKED and GITIGNORED protected paths. The scan runs with
     --untracked-files=no, so a protected path git does not track is invisible:
     the interpreter-environment, dependency, build and cache directories in
     readOnlyPaths are all in that category, and so is the grant file itself
     (gitignored). Covering them means walking those trees on every Bash call,
     which is the cost this must not pay.
  2. PATHS OUTSIDE THE REPOSITORY. The system directories and the shell-rc files
     in readOnlyPaths are paths git cannot report on. Those keep only their
     PreToolUse text-matching coverage.
  3. A WRITE THAT RESTORES THE ORIGINAL BYTES. The measurement is divergence from
     the index, not "was opened for writing". Write-then-revert reads as no change.
  4. ATTRIBUTION IS TO THE LAST OBSERVED Bash CALL IN THIS REPOSITORY, not
     provably to the command that just ran. The baseline is a file, so two
     concurrent sessions in one checkout can cross-attribute. The DETECTION still
     fires; only the "which command" is approximate, and the alert says so.
  5. ONE TREE: whichever CLAUDE_PROJECT_DIR names. A command that writes inside a
     different worktree is not measured here. A worktree is not a checkout.

Exit codes:
  0  no unauthorized change detected (or the change was granted and recorded)
  2  a protected path changed with no valid grant -- stderr goes back to the model
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import path_scope  # noqa: E402
import known_roads  # noqa: E402

# Cost, measured on this checkout (80 submodules, 6552 tracked files, 3 runs
# each): with submodule scanning ON, 0.25-0.31 s; with --ignore-submodules=dirty,
# 0.00-0.01 s. `dirty` and not `all`, because `dirty` still reports a submodule
# GITLINK move while skipping the recursive walk that costs the 300 ms.
GIT_ARGS = [
    "status", "--porcelain=v1", "-z",
    "--untracked-files=no",
    "--ignore-submodules=dirty",
    "--no-renames",          # keeps every -z record a single "XY path" field
]
GIT_TIMEOUT = 10

# Re-emitting the same COULD-NOT-MEASURE on every Bash call would train the reader
# to skip it, which is how a broken check becomes a silent one.
NOTICE_REPEAT_SECONDS = 900

STATE_VERSION = 1


def state_path(repo: Path) -> Path:
    return repo / ".claude" / "hooks" / "damage-control" / ".effect-state.json"


# ---------------------------------------------------------------------------
# scanning
# ---------------------------------------------------------------------------

def protected_entries(config: Dict) -> List[Tuple[str, str]]:
    """[(entry, kind)] for every protected path git could possibly report on.

    Absolute and tilde entries are dropped: git cannot report on a path outside
    the working tree, so keeping them would only cost matching time and imply a
    coverage this cannot deliver (limitation 2 in the module docstring).
    """
    out: List[Tuple[str, str]] = []
    for kind, key in (("read-only path", "readOnlyPaths"),
                      ("no-delete path", "noDeletePaths")):
        for entry in config.get(key) or ():
            if entry.startswith("/") or entry.startswith("~"):
                continue
            out.append((entry, kind))
    return out


def git_status(repo: Path) -> Tuple[Optional[Dict[str, str]], str]:
    """({path: XY}, "") or (None, why-not). None means COULD-NOT-MEASURE."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo)] + GIT_ARGS,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=GIT_TIMEOUT,
        )
    except FileNotFoundError:
        return None, "git is not on PATH"
    except subprocess.TimeoutExpired:
        return None, "git status did not return within %ds" % GIT_TIMEOUT
    except OSError as exc:
        return None, "git status could not run: %s" % exc

    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        return None, ("git status exited %d" % proc.returncode
                      + (": %s" % detail[0] if detail else ""))

    rows: Dict[str, str] = {}
    for record in proc.stdout.decode("utf-8", "replace").split("\0"):
        if len(record) < 4:
            continue
        rows[record[3:]] = record[:2]
    return rows, ""


def filter_protected(
    rows: Dict[str, str], entries: List[Tuple[str, str]]
) -> Dict[str, Dict[str, str]]:
    """{path: {"xy":..., "entry":..., "kind":...}} for rows a protected entry covers.

    Matching goes through path_scope.token_matches_entry -- the SAME matcher the
    PreToolUse guard confirms its candidates with -- so the protected set cannot
    drift between the two halves of the mechanism.
    """
    hits: Dict[str, Dict[str, str]] = {}
    for path, xy in rows.items():
        for entry, kind in entries:
            if path_scope.token_matches_entry(path, entry):
                hits[path] = {"xy": xy, "entry": entry, "kind": kind}
                break
    return hits


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------

def load_state(path: Path) -> Dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict) or raw.get("version") != STATE_VERSION:
        return {}
    return raw


def save_state(path: Path, state: Dict) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
        os.replace(str(tmp), str(path))
        return True
    except OSError:
        return False


def diff(before: Dict[str, Dict], after: Dict[str, Dict]) -> List[Dict]:
    """Protected paths whose working-tree status changed since the last scan."""
    changes: List[Dict] = []
    for path in sorted(set(before) | set(after)):
        was = (before.get(path) or {}).get("xy")
        now = (after.get(path) or {}).get("xy")
        if was == now:
            continue
        meta = after.get(path) or before.get(path) or {}
        changes.append({
            "path": path,
            "was": was,
            "now": now,
            "entry": meta.get("entry", "?"),
            "kind": meta.get("kind", "?"),
            # A path that LEAVES the status list matches the index again:
            # something rewrote it back, or checked it out. That is still an
            # effect on a protected path, so it is reported -- labelled, not
            # silently dropped.
            "restored": now is None,
        })
    return changes


# ---------------------------------------------------------------------------
# verdict
# ---------------------------------------------------------------------------

def adjudicate(repo: Path, changes: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Split changes into (granted-and-recorded, ungranted).

    A granted change is APPENDED to known-roads.jsonl. That is the inverse half of
    the same defect: before this, an authorized change made through a verb the
    guard cannot see went unrecorded too, so the trail understated authorized use
    exactly as it missed unauthorized use.
    """
    granted: List[Dict] = []
    ungranted: List[Dict] = []
    for change in changes:
        absolute = os.path.normpath(os.path.join(str(repo), change["path"]))
        absolute = absolute.replace("\\", "/")
        allowed, detail = known_roads.evaluate_known_road(
            "Bash(effect)", absolute, absolute,
            note="observed after the command ran; the command text did not name it",
        )
        if allowed:
            change["grant"] = detail
            granted.append(change)
        else:
            change["grant_error"] = detail
            ungranted.append(change)
    return granted, ungranted


def describe(change: Dict) -> str:
    if change["restored"]:
        what = "restored to the index (was %r)" % (change["was"],)
    elif change["was"] is None:
        what = "now %r" % (change["now"],)
    else:
        what = "%r -> %r" % (change["was"], change["now"])
    return "  %s  [%s %s]  %s" % (
        change["path"], change["kind"], change["entry"], what)


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

def emit(message: str) -> None:
    """Put `message` in front of the model twice over.

    `additionalContext` is the documented PostToolUse channel and reaches the
    model without blocking; stderr reaches the transcript regardless of whether a
    given client honours that field. A disclosure that depends on one optional
    field being supported is not a disclosure.
    """
    print(message, file=sys.stderr)
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": message,
    }}))


def should_notice(state: Dict, reason: str, now: float) -> bool:
    last = state.get("last_notice") or {}
    if last.get("reason") != reason:
        return True
    try:
        return (now - float(last.get("ts", 0))) >= NOTICE_REPEAT_SECONDS
    except (TypeError, ValueError):
        return True


def _notice(state: Dict, spath: Path, now: float, reason: str) -> int:
    """Report a COULD-NOT-MEASURE, at most once per NOTICE_REPEAT_SECONDS.

    Exit 0, not 2: the tool already ran and this says nothing about whether it
    was safe. What it must never do is stay silent -- a check that quietly
    passes when it cannot see is the defect family this whole file exists for.
    """
    if should_notice(state, reason, now):
        emit("EFFECT-CHECK COULD-NOT-MEASURE: %s. Protected-path changes are NOT "
             "being detected by effect while this holds." % reason)
        state = dict(state)
        state["version"] = STATE_VERSION
        state["last_notice"] = {"reason": reason, "ts": now}
        save_state(spath, state)
    return 0


def _load_config() -> Tuple[Optional[Dict], str]:
    """patterns.yaml via the guard's own loader, or (None, why-not).

    The loader exits 2 on a bad config because a PreToolUse hook that cannot read
    its rules must refuse everything. Post-hoc that same failure means "cannot
    measure", not "block" -- the command has already run -- so the exit is caught
    and reported as what it is.
    """
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location(
            "dc_guard_for_effect", HERE / "bash-tool-damage-control.py")
        guard = importlib.util.module_from_spec(spec)
        sys.modules["dc_guard_for_effect"] = guard
        spec.loader.exec_module(guard)
        return guard.load_config(), ""
    except SystemExit as exc:
        return None, "patterns.yaml could not be loaded (guard exit %s)" % exc.code
    except Exception as exc:  # noqa: BLE001 -- reported, never swallowed
        return None, "guard module would not load: %s" % exc


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def run(payload: Dict) -> int:
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")

    repo = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
    spath = state_path(repo)
    state = load_state(spath)
    now = time.time()

    config, why = _load_config()
    if config is None:
        return _notice(state, spath, now, why)

    rows, why = git_status(repo)
    if rows is None:
        return _notice(state, spath, now, why)

    after = filter_protected(rows, protected_entries(config))
    before = state.get("protected")

    if not isinstance(before, dict):
        # No baseline yet. The baseline persists in the checkout, so this is a
        # once-per-checkout gap rather than a once-per-session one -- but the
        # call that establishes it genuinely is not measured, and saying so
        # costs nothing.
        wrote = save_state(spath, {"version": STATE_VERSION, "protected": after})
        emit("EFFECT-CHECK COULD-NOT-MEASURE: no baseline existed for this "
             "checkout, so this Bash call is unmeasured. Baseline of %d "
             "protected path(s) %s" % (
                 len(after),
                 "recorded." if wrote else
                 "COULD NOT be written to %s -- every following call is "
                 "unmeasured too." % spath))
        return 0

    changes = diff(before, after)
    state = {"version": STATE_VERSION, "protected": after,
             "last_notice": state.get("last_notice")}

    if not changes:
        save_state(spath, state)
        return 0

    granted, ungranted = adjudicate(repo, changes)
    if not save_state(spath, state):
        emit("EFFECT-CHECK COULD-NOT-MEASURE: the baseline could not be written "
             "to %s; the change(s) below will be reported again next call."
             % spath)

    if granted:
        print("EFFECT-CHECK: %d protected path(s) changed under the active Known "
              "Road and were recorded to known-roads.jsonl:" % len(granted),
              file=sys.stderr)
        for change in granted:
            print(describe(change), file=sys.stderr)

    if not ungranted:
        return 0

    lines = ["EFFECT-CHECK ALERT: %d protected path(s) changed with no valid "
             "Known Road grant. This is DETECTION, not prevention -- the write "
             "has already happened." % len(ungranted)]
    lines += [describe(c) for c in ungranted]
    lines += ["  grant refused: " + r for r in
              sorted({c["grant_error"] for c in ungranted if c.get("grant_error")})]
    lines += [
        "Command just run: " + command[:300] + ("..." if len(command) > 300 else ""),
        "Attribution note: the baseline is per-checkout, so this is the change "
        "since the last observed Bash call in THIS repository -- a concurrent "
        "session in the same checkout can cross-attribute.",
        "Do not silence this. Disclose it, then revert or justify the change: "
        "see .claude/skills/known-roads/SKILL.md.",
    ]
    emit("\n".join(lines))
    return 2


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError) as exc:
        print("EFFECT-CHECK COULD-NOT-MEASURE: unreadable hook input: %s" % exc,
              file=sys.stderr)
        sys.exit(0)
    sys.exit(run(payload))


if __name__ == "__main__":
    main()
