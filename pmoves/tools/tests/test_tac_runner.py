# pmoves/tools/tests/test_tac_runner.py
"""Tests for tac_runner unknown-action-type surfacing.

Background: prior to the fix, an action.type value that the runner
didn't recognize (e.g. typo, deprecated name, future type) silently
stayed at the default "pending" status with no detail message. That
hidden 141 inert assertions in the same bucket as legitimate
"manual" review items. The fix surfaces them as FAIL with a clear
detail so the operator can correct the YAML or add the new type.
"""
from pmoves.tools.tac_runner import evaluate_node


def _node(action: dict | None, children: list | None = None) -> dict:
    node = {"id": "test", "task": "t", "children": children or []}
    if action is not None:
        node["action"] = action
    return node


def test_unknown_action_type_fails_with_detail():
    """An unrecognized action.type must surface as FAIL, not silently pending."""
    node = _node({"type": "http_get", "target": "https://example.invalid"})
    result = evaluate_node(node)
    assert result["status"] == "fail"
    assert "unknown action.type" in result["detail"]
    assert "'http_get'" in result["detail"]
    # The detail must list the allowed types so the operator can correct quickly.
    for allowed in ("file_exists", "grep", "command", "manual"):
        assert allowed in result["detail"], f"allowed list missing: {allowed}"


def test_known_types_still_work():
    """Regression guard: file_exists / grep / command / manual must be unchanged."""
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        existing = Path(d) / "exists.txt"
        existing.write_text("hello pmoves\n", encoding="utf-8")
        # file_exists: pass
        r = evaluate_node(_node({"type": "file_exists", "target": str(existing)}))
        assert r["status"] == "pass", r
        # file_exists: fail (missing)
        r = evaluate_node(_node({"type": "file_exists", "target": str(Path(d) / "missing.txt")}))
        assert r["status"] == "fail", r
        # grep: pass (substring match)
        r = evaluate_node(_node({"type": "grep", "target": str(existing), "pattern": "pmoves"}))
        assert r["status"] == "pass", r
        # grep: fail (no match)
        r = evaluate_node(_node({"type": "grep", "target": str(existing), "pattern": "absent"}))
        assert r["status"] == "fail", r
        # manual: pending
        r = evaluate_node(_node({"type": "manual"}))
        assert r["status"] == "pending", r
        assert "manual" in r["detail"].lower()


def test_empty_action_dict_falls_through_to_pending():
    """No action.type provided is the same as a missing action — must stay pending."""
    node = _node({})
    result = evaluate_node(node)
    # No action block at all, no children → initial pending.
    assert result["status"] == "pending"


def test_unknown_action_does_not_swallow_children_pass():
    """If a parent has an unknown action.type but all children pass, parent fails.

    A common footgun: write `action: { type: foo }` on a parent with
    children that all pass; the parent would silently appear OK in the
    tree summary. The fix ensures the unknown type is visible.
    """
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "f.txt"
        p.write_text("ok\n", encoding="utf-8")
        children = [_node({"type": "file_exists", "target": str(p)})]
        parent = _node({"type": "http_get", "target": "x"}, children=children)
        result = evaluate_node(parent)
        assert result["status"] == "fail", result
        assert "unknown action.type" in result["detail"]
