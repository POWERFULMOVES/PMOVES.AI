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


# ---------------------------------------------------------------------------
# http probe: SSRF guard and fail-closed behaviour
#
# The first version of _http_host_allowed blocked only the dotted-quad spelling
# of the cloud metadata address. Every alternate encoding of the same address
# walked straight through to it. These tests enumerate the spellings so the hole
# cannot silently reopen — the original guard passed its own suite precisely
# because that suite only ever tried the one literal.
#
# Non-loopback examples use RFC 5737 documentation space (203.0.113.0/24), never
# real fleet addressing: committed files must not carry LAN topology.
# ---------------------------------------------------------------------------

import pytest

from pmoves.tools.tac_runner import _http_host_allowed


@pytest.mark.parametrize(
    "host",
    [
        "169.254.169.254",            # canonical instance-metadata endpoint
        "2852039166",                 # same address, decimal (glibc resolves it)
        "0xa9fea9fe",                 # same address, hex
        "::ffff:169.254.169.254",     # IPv4-mapped IPv6 — is_link_local is False on v6
        "[::ffff:169.254.169.254]",   # ...and bracketed, as a URL would carry it
        "169.254.1.1",                # link-local generally, not just metadata
        "fe80::1",                    # IPv6 link-local
    ],
)
def test_link_local_blocked_in_every_spelling(host):
    """Every encoding of a link-local address must be refused."""
    assert _http_host_allowed(host) is False


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "127.0.0.1",
        "7860.localhost",       # loopback subdomain used by real nodes
        "headscale.pmoves.ai",  # public DNS, our own infrastructure
        "pmoves-z890",          # tailnet hostname
        "203.0.113.10",         # RFC 5737 documentation address
    ],
)
def test_legitimate_fleet_targets_still_allowed(host):
    """The guard must not regress the 38 real http nodes it exists to enable."""
    assert _http_host_allowed(host) is True


def test_empty_host_refused():
    assert _http_host_allowed("") is False


@pytest.mark.parametrize(
    "extra",
    [
        {"method": "POST"},                             # pinokio-p8 shape
        {"body": "{}"},
        {"headers": {"Authorization": "Bearer x"}},     # public-tunnel shape
        {"json": {"text": "hi"}},                       # voice-agents shape
        {"expect_json": {"cycles": []}},                # content predicate
        {"expect_contains": "reconciled_at"},
    ],
)
def test_unsupported_http_fields_fail_closed(extra):
    """A node the probe cannot honour must FAIL, never PASS on status alone.

    The probe sends an unauthenticated GET and reads only the status code. A
    node declaring a different request, or asserting on a body that is never
    read, would otherwise be evaluated against a request it did not describe —
    green on an assertion nobody checked.
    """
    action = {"type": "http", "url": "http://127.0.0.1:9/x"}
    action.update(extra)
    result = evaluate_node(_node(action))
    assert result["status"] == "fail"
    assert "cannot honour" in result["detail"]


def test_prose_expect_does_not_fail_closed():
    """`expect` is human prose on all 38 existing nodes — it must still probe.

    Treating it as a machine-readable predicate would fail-close every node this
    change set out to wire up. Connection-refused here is the correct, truthful
    FAIL: the node was evaluated, the service is down.
    """
    result = evaluate_node(
        _node({"type": "http", "url": "http://127.0.0.1:9/healthz", "expect": "200 OK"})
    )
    assert result["status"] == "fail"
    assert "cannot honour" not in result["detail"]
