"""Trail-row actor attribution: which BODY took a Known Road.

Run: python .claude/hooks/damage-control/test_known_roads_attribution.py

BEFORE: every known-roads.jsonl row's `agent` was AGENT_ID, else PMOVES_NODE_ID,
else "unknown", and `session` was "unknown" whenever CLAUDE_SESSION_ID was unset
in the hook env (which it is). A delivery-agent subagent, a reviewer subagent and
the steward that spawned them all recorded as the same node.

AFTER: the hook callers hand their parsed stdin to known_roads.set_hook_input().
A hook `agent_type` that maps onto an agent_registry.yaml key is recorded as the
row's `agent`, the old value moves to `node`, and the hook `agent_id` becomes
`agent_instance`. An unregistered type is kept visible under
`unregistered_agent_type` and never promoted to `agent`.

This is ATTRIBUTION, NOT AUTHENTICATION. `agent_type` is whatever the harness
loaded; nothing here proves who sent it. The suite therefore pins the
fail-toward-under-claiming edges: malformed or injection-shaped names are never
certified, and an unreadable registry certifies nothing.

Isolation: the trail is redirected to a temp file and the registry path is
monkeypatched, so this suite never writes the git-tracked known-roads.jsonl
(run_guard_tests.sh counts that file's rows before and after).
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("CLAUDE_PROJECT_DIR") or HERE.parents[2])
os.environ["CLAUDE_PROJECT_DIR"] = str(REPO)
sys.path.insert(0, str(HERE))

import known_roads as KR  # noqa: E402  -- the SAME instance the hooks import


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_TMP = Path(tempfile.mkdtemp(prefix="kr-attr-"))
_TRAIL = _TMP / "known-roads.jsonl"
# The registry in THIS tree, not whatever CLAUDE_PROJECT_DIR names: that env var is
# inherited from the session and can point at another checkout whose registry
# predates the bodies this tree registers (measured: it named the main checkout).
_REAL_REGISTRY = HERE.parents[2] / "pmoves" / "config" / "agent_registry.yaml"
KR._trail_path = lambda: _TRAIL

# A fixture registry rather than the live one, so the result cannot drift with
# registry edits: one registered body, and `researcher` deliberately absent.
_FIXTURE_REGISTRY = _TMP / "agent_registry.yaml"
_FIXTURE_REGISTRY.write_text(
    "agents:\n"
    "  delivery_agent:\n"
    "    class: delivery\n"
    "  node_steward:\n"
    "    class: control\n",
    encoding="utf-8",
)

# The old row key set, exactly: nothing may add a key when no hook input is set.
# (Rows are written with sort_keys=True, so the set is the whole shape.)
OLD_KEYS = {"ts", "tool", "file", "domain", "reason", "agent", "session"}


def _use_registry(path):
    KR._registry_path = lambda: path
    KR._REGISTRY_KEYS = None  # the module caches; reset per case


def _env(node="test-node", session=None):
    for k in ("AGENT_ID", "PMOVES_NODE_ID", "CLAUDE_SESSION_ID", "SESSION_ID"):
        os.environ.pop(k, None)
    if node is not None:
        os.environ["PMOVES_NODE_ID"] = node
    if session is not None:
        os.environ["CLAUDE_SESSION_ID"] = session


def _row(hook_input):
    """Record one row with `hook_input` set; return it parsed, and the raw line."""
    KR.set_hook_input(hook_input)
    if _TRAIL.exists():
        _TRAIL.unlink()
    ok = KR.record_use("Edit", "pmoves/example.txt", "testdomain", "brief:x.md")
    assert ok, "record_use could not write the redirected trail"
    lines = _TRAIL.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, "expected exactly one JSONL line, got %d" % len(lines)
    return json.loads(lines[0]), lines[0]


def main() -> int:
    failures = 0
    checks = 0

    def check(label, cond, detail=""):
        nonlocal failures, checks
        checks += 1
        if cond:
            print("  ok   %s" % label)
        else:
            failures += 1
            print("  FAIL %s %s" % (label, detail))

    _use_registry(_FIXTURE_REGISTRY)

    # 1. No hook input -> the old row shape, byte-for-byte in keys and values.
    _env()
    for label, hook in (("none", None), ("empty dict", {}), ("list", ["x"]),
                        ("string", "delivery-agent"), ("int", 7)):
        row, _ = _row(hook)
        check("no hook input (%s): old key set" % label, set(row) == OLD_KEYS, sorted(row))
        check("no hook input (%s): agent is node" % label, row["agent"] == "test-node", row)
        check("no hook input (%s): session unknown" % label, row["session"] == "unknown", row)

    _env(node=None)
    row, _ = _row(None)
    check("no env, no hook: agent falls back to 'unknown'", row["agent"] == "unknown", row)
    _env()

    # 2. Registered body -> agent=body, node=old value, agent_instance=hook agent_id.
    row, _ = _row({"agent_type": "delivery-agent", "agent_id": "a1b2c3",
                   "session_id": "sess-123"})
    check("registered: agent is the body", row.get("agent") == "delivery-agent", row)
    check("registered: node keeps the old value", row.get("node") == "test-node", row)
    check("registered: agent_instance from hook agent_id",
          row.get("agent_instance") == "a1b2c3", row)
    check("registered: session falls back to hook session_id",
          row.get("session") == "sess-123", row)
    check("registered: no unregistered_agent_type",
          "unregistered_agent_type" not in row, row)

    # --agent main thread: agent_type without agent_id.
    row, _ = _row({"agent_type": "node-steward", "session_id": "s"})
    check("--agent main thread: certified, no agent_instance",
          row.get("agent") == "node-steward" and "agent_instance" not in row, row)

    # Env session still wins over the hook's session_id.
    _env(session="env-sess")
    row, _ = _row({"agent_type": "delivery-agent", "session_id": "hook-sess"})
    check("CLAUDE_SESSION_ID still takes precedence", row.get("session") == "env-sess", row)
    _env()

    # 3. Unregistered type -> agent stays the node; the type stays visible.
    row, _ = _row({"agent_type": "researcher", "agent_id": "ffff"})
    check("unregistered: agent is the node", row.get("agent") == "test-node", row)
    check("unregistered: no node key", "node" not in row, row)
    check("unregistered: type recorded",
          row.get("unregistered_agent_type") == "researcher", row)
    check("unregistered: agent_instance still recorded",
          row.get("agent_instance") == "ffff", row)

    # 4. Malformed / injection-shaped names are never certified.
    hostile = [
        "delivery_agent",                 # registry KEY spelling, not runtime spelling
        "Delivery-Agent",                 # case
        " delivery-agent",                # leading space
        "delivery-agent ",                # trailing space
        "delivery-agent\n",               # trailing newline (re `$` would accept this)
        "delivery-agent\nnode-steward",   # line injection
        "../delivery-agent",              # path shape
        "delivery-agent\"}",              # JSON break-out shape
        "delivery--agent",                # empty segment
        "-delivery-agent",                # leading dash
        "delivery-agent-",                # trailing dash
        "x" * 500,                        # oversize
    ]
    for name in hostile:
        row, line = _row({"agent_type": name, "agent_id": "i" * 200})
        check("hostile %r: not certified" % name[:30],
              row.get("agent") == "test-node" and "node" not in row, row)
        check("hostile %r: recorded as unregistered, capped" % name[:30],
              row.get("unregistered_agent_type") == name[:128], row)
        check("hostile %r: agent_instance capped at 64" % name[:30],
              row.get("agent_instance") == "i" * 64, row)
        check("hostile %r: row stays one JSONL line" % name[:30], "\n" not in line)

    # Non-string agent_type / agent_id / session_id are ignored, not stringified.
    row, _ = _row({"agent_type": {"x": 1}, "agent_id": 5, "session_id": ["s"]})
    check("non-string fields: old key set", set(row) == OLD_KEYS, sorted(row))

    # 5. Unreadable registry certifies nothing.
    for label, path in (("missing", _TMP / "does-not-exist.yaml"),
                        ("directory", _TMP)):
        _use_registry(path)
        row, _ = _row({"agent_type": "delivery-agent", "agent_id": "a"})
        check("registry %s: not certified" % label,
              row.get("agent") == "test-node" and "node" not in row, row)
        check("registry %s: type still visible" % label,
              row.get("unregistered_agent_type") == "delivery-agent", row)
    for label, text in (("unparseable", "agents: [unclosed\n"),
                        ("agents not a mapping", "agents:\n  - delivery_agent\n"),
                        ("top level not a mapping", "- agents\n")):
        bad = _TMP / ("bad-%d.yaml" % checks)
        bad.write_text(text, encoding="utf-8")
        _use_registry(bad)
        row, _ = _row({"agent_type": "delivery-agent"})
        check("registry %s: not certified" % label,
              row.get("agent") == "test-node" and "node" not in row, row)

    # 6. The live registry certifies the body this lane registered.
    _use_registry(_REAL_REGISTRY)
    row, _ = _row({"agent_type": "delivery-agent"})
    check("live registry: delivery-agent certified", row.get("agent") == "delivery-agent", row)
    _use_registry(_FIXTURE_REGISTRY)

    # 7. Wiring: every hook that can record a trail row hands its stdin over
    #    BEFORE any early exit. A non-matching tool_name takes the earliest exit.
    seen = []

    def spy(data):
        seen.append(data)

    real = KR.set_hook_input
    try:
        for fname, tool in (("bash-tool-damage-control.py", "Read"),
                            ("edit-tool-damage-control.py", "Read"),
                            ("write-tool-damage-control.py", "Read"),
                            ("effect_check.py", "Read")):
            mod = _load("attr_" + fname.replace("-", "_").replace(".py", ""), HERE / fname)
            if hasattr(mod, "set_hook_input"):
                mod.set_hook_input = spy          # `from known_roads import` binding
            KR.set_hook_input = spy               # `known_roads.set_hook_input` binding
            payload = {"tool_name": tool, "tool_input": {}, "agent_type": "delivery-agent"}
            seen.clear()
            old_stdin = sys.stdin
            sys.stdin = io.StringIO(json.dumps(payload))
            try:
                mod.main()
            except SystemExit:
                pass
            finally:
                sys.stdin = old_stdin
            check("wiring: %s passes hook stdin to set_hook_input" % fname,
                  seen == [payload], seen)
    finally:
        KR.set_hook_input = real
        KR.set_hook_input(None)

    print()
    if failures:
        print("FAIL: %d of %d checks failed." % (failures, checks))
        return 1
    print("PASS — all %d checks." % checks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
