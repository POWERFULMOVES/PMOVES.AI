"""In-process verification that the Bash guard consults Known Roads.

Run: python .claude/hooks/damage-control/test_bash_known_roads.py

BEFORE: the Edit and Write guards each carried four references to known_roads.py;
the Bash guard carried zero. Edit and Write blocked and then GUIDED. Bash blocked
and then abandoned, so the protected set was discoverable only by tripping it and
the sanctioned route was never named. A road that the tool naming it cannot take
is not guidance.

This suite asserts BOTH halves:
  * the refusal now names the road (advisory, opens nothing);
  * a valid grant is honored, and an invalid one is refused WITH ITS REASON --
    the same provability gate known_roads.py already applies to Edit and Write.

And the containment, which matters more than either: a grant cannot reach the
zero-access class, and cannot reach a destructive command shape, because both of
those gates run EARLIER in check_command and return before Known Roads is
consulted.

Fixtures are assembled from split parts at runtime so this file's own source text
cannot trip the guard reading it.
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("CLAUDE_PROJECT_DIR") or HERE.parents[2])
os.environ["CLAUDE_PROJECT_DIR"] = str(REPO)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


dc = _load("dc", HERE / "bash-tool-damage-control.py")
kr = _load("known_roads_t", HERE / "known_roads.py")
cfg = dc.load_config()

# The guard imported its OWN known_roads instance; redirect that one.
KR = sys.modules.get("known_roads") or kr

# Never append to the real audit log from a test, and never inherit a grant that
# happens to be open on this node -- both would make the result depend on state
# outside this file.
_TRAIL = Path(tempfile.mkdtemp(prefix="kr-trail-")) / "known-roads.jsonl"
_NO_FILE_GRANT = Path(tempfile.mkdtemp(prefix="kr-none-")) / ".known-road-active"
KR._trail_path = lambda: _TRAIL
KR._grant_file = lambda: _NO_FILE_GRANT

V_SED = "s" + "ed"
V_RM = "r" + "m"
COMPOSE = "pmoves/docker-" + "compose.yml"
SCHEMA = "pmoves/contra" + "cts/schemas/z.schema.json"
LOCKFILE = "poetry" + ".lock"
ZERO_ACCESS_PATH = "~/.s" + "sh"


def _set_road_reason(value):
    if value is None:
        os.environ.pop("KNOWN_ROAD", None)
    else:
        os.environ["KNOWN_ROAD"] = value


def main() -> int:
    failures = 0

    def check(label, road_reason, command, want_blocked, want_in_reason=None,
              want_not_in_reason=None):
        nonlocal failures
        _set_road_reason(road_reason)
        blocked, _ask, reason = dc.check_command(command, cfg)
        ok = blocked == want_blocked
        if ok and want_in_reason is not None:
            ok = want_in_reason in reason
        if ok and want_not_in_reason is not None:
            ok = want_not_in_reason not in reason
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            print(f"          road_reason={road_reason!r} cmd={command}")
            print(f"          blocked={blocked} (want {want_blocked})")
            print(f"          reason={reason!r}")

    # ---- 1. the refusal now NAMES the road ---------------------------------
    check("a block on a compose file names the compose road",
          None, V_SED + " -i s/a/b/ " + COMPOSE, True,
          want_in_reason="KNOWN_ROAD=compose:")
    check("the hint names the provable reason forms",
          None, V_SED + " -i s/a/b/ " + COMPOSE, True,
          want_in_reason="handoff:")
    check("a block on a contract schema names the schema road",
          None, V_SED + " -i s/a/b/ " + SCHEMA, True,
          want_in_reason="KNOWN_ROAD=schema:")

    # ---- 2. a path with NO road must not be given false guidance -----------
    check("a block with no road available offers none",
          None, V_SED + " -i s/a/b/ " + LOCKFILE, True,
          want_not_in_reason="KNOWN_ROAD=")

    # ---- 3. a valid grant is honored ---------------------------------------
    check("a provable pr: grant opens its own domain",
          "compose:pr:2656", V_SED + " -i s/a/b/ " + COMPOSE, False)
    check("a provable issue: grant opens its own domain",
          "compose:issue:42", V_SED + " -i s/a/b/ " + COMPOSE, False)

    # ---- 4. an invalid grant is refused, WITH ITS REASON -------------------
    check("a malformed reason is refused and says why",
          "compose:because-i-said-so", V_SED + " -i s/a/b/ " + COMPOSE, True,
          want_in_reason="not provable")
    check("a handoff reason with no brief on disk is refused",
          "compose:handoff:does-not-exist-9f2c.md", V_SED + " -i s/a/b/ " + COMPOSE, True,
          want_in_reason="handoff brief not found")

    # ---- 5. a grant does not leak across domains ---------------------------
    check("a compose grant does not open a contract schema",
          "compose:pr:2656", V_SED + " -i s/a/b/ " + SCHEMA, True)
    check("a schema grant does not open a compose file",
          "schema:pr:2656", V_SED + " -i s/a/b/ " + COMPOSE, True)
    check("an unknown domain opens nothing",
          "everything:pr:2656", V_SED + " -i s/a/b/ " + COMPOSE, True)

    # ---- 6. CONTAINMENT: the earlier gates are unreachable from a grant ----
    check("a grant cannot reach the zero-access class",
          "compose:pr:2656", V_SED + " -i s/a/b/ " + ZERO_ACCESS_PATH + "/id_ed25519", True)
    check("a grant cannot reach a destructive command shape",
          "compose:pr:2656", V_RM + " -rf " + COMPOSE, True)

    # ---- 7. the grant was RECORDED, and to the test trail only ------------
    _set_road_reason("compose:pr:2656")
    dc.check_command(V_SED + " -i s/a/b/ " + COMPOSE, cfg)
    recorded = _TRAIL.is_file() and "compose" in _TRAIL.read_text(encoding="utf-8")
    failures += 0 if recorded else 1
    print(f"  [{'PASS' if recorded else 'FAIL'}] every honored grant is recorded to the trail")

    real_trail = HERE / "known-roads.jsonl"
    before = real_trail.stat().st_mtime if real_trail.is_file() else None
    dc.check_command(V_SED + " -i s/a/b/ " + COMPOSE, cfg)
    after = real_trail.stat().st_mtime if real_trail.is_file() else None
    clean = before == after
    failures += 0 if clean else 1
    print(f"  [{'PASS' if clean else 'FAIL'}] the real audit log was not touched by this suite")

    _set_road_reason(None)

    if failures:
        print(f"\nFAIL — {failures} check(s) failed.")
        return 1
    print("\nPASS — all checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
