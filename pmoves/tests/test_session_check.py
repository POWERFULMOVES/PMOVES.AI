"""Tests for scripts/session_check.py.

Two of these exist specifically because session_check imports from
`mcp_roster_normalize` -- including one private helper. Reuse is the right call
(a second ${VAR} expander would drift from the launcher's, and this tool's only
job is to agree with the launcher), but reuse across a private boundary needs a
test holding it, or a refactor over there silently changes what this reports.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load():
    path = _ROOT / "pmoves" / "scripts" / "session_check.py"
    spec = importlib.util.spec_from_file_location("session_check", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sc = _load()


# --------------------------------------------------------------------------
# The reuse boundary
# --------------------------------------------------------------------------


def test_it_uses_the_launchers_expander_not_its_own():
    """If mcp_roster_normalize.expand ever stops being importable, this tool is
    silently reporting on different semantics than the launcher applies."""
    assert callable(sc.expand)
    assert sc.expand.__module__ == "mcp_roster_normalize"


def test_the_private_brace_matcher_still_behaves():
    """`_match_brace` is private to mcp_roster_normalize. Pinned here because
    session_check imports it; a rename or signature change over there should
    fail loudly instead of degrading reference detection to nothing."""
    assert sc._match_brace("${A}", 1) == 3
    assert sc._match_brace("${A:-${B}}", 1) == 9
    assert sc._match_brace("${A", 1) == -1


# --------------------------------------------------------------------------
# classify() -- the Codex P2 that started this
# --------------------------------------------------------------------------


def test_literal_default_is_not_a_finding():
    """The tracked roster carries
    ${SUPABASE_REST_URL:-http://localhost:8000/rest/v1}, which works with the
    variable unset. The first draft reported it as missing."""
    server = {"url": "${SUPABASE_REST_URL:-http://localhost:8000/rest/v1}"}
    hard, soft = sc.classify(server, {})
    assert hard == []
    assert soft == []


def test_nested_default_resolves_from_the_inner_variable():
    """${A:-${B}} is satisfied when only B is set -- also from the real roster."""
    server = {"headers": {"apikey": "${SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_KEY}}"}}
    hard, soft = sc.classify(server, {"SUPABASE_SERVICE_KEY": "x"})
    assert hard == []
    assert soft == []


def test_nested_default_names_both_when_the_whole_chain_fails():
    server = {"headers": {"apikey": "${SUPABASE_SERVICE_ROLE_KEY:-${SUPABASE_SERVICE_KEY}}"}}
    hard, _ = sc.classify(server, {})
    assert hard == ["SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY"]


def test_empty_default_is_soft_not_hard():
    """${VAR:-} expands successfully to '' -- correct for the launcher, which
    only needs to know whether to drop the server. For a session it means the
    request goes out unauthenticated, which a tokened service answers 401."""
    server = {"headers": {"Authorization": "Bearer ${CIPHER_API_TOKEN:-}"}}
    hard, soft = sc.classify(server, {})
    assert hard == []
    assert soft == ["CIPHER_API_TOKEN"]


def test_bare_reference_is_hard():
    server = {"headers": {"Authorization": "Bearer ${AGENT_ZERO_MCP_TOKEN}"}}
    hard, soft = sc.classify(server, {})
    assert hard == ["AGENT_ZERO_MCP_TOKEN"]
    assert soft == []


def test_a_set_variable_is_neither():
    server = {"url": "http://${TS_Z890}:8105/mcp/sse"}
    hard, soft = sc.classify(server, {"TS_Z890": "host"})
    assert (hard, soft) == ([], [])


def test_an_exported_empty_string_counts_as_unset():
    """Matches expand()'s documented rule: an exported empty string is the
    classic shadow -- it satisfies a presence check and produces http://:8105/."""
    server = {"url": "http://${TS_Z890}:8105/"}
    hard, _ = sc.classify(server, {"TS_Z890": ""})
    assert hard == ["TS_Z890"]


def test_prose_fields_are_not_scanned():
    """`_note` entries in the roster quote ${VAR} spellings as EXAMPLES."""
    server = {"_note": "we send ${NEVER_REAL} here", "command": "echo"}
    hard, soft = sc.classify(server, {})
    assert (hard, soft) == ([], [])


# --------------------------------------------------------------------------
# resolve_roster() -- the other Codex P2
# --------------------------------------------------------------------------


def test_explicit_roster_wins(tmp_path, monkeypatch):
    p = tmp_path / "r.json"
    p.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PMOVES_MCP_ROSTER", str(tmp_path / "other.json"))
    content, display, source = sc.resolve_roster(str(p), _ROOT)
    assert content == b"{}"
    assert "explicit" in source


def test_launcher_marker_beats_discovery(tmp_path, monkeypatch):
    """The launcher knows which roster it actually handed to Claude. Nothing
    this tool can infer beats being told."""
    p = tmp_path / "r.json"
    p.write_text('{"mcpServers":{}}', encoding="utf-8")
    monkeypatch.setenv("PMOVES_MCP_ROSTER", str(p))
    monkeypatch.setenv("PMOVES_MCP_ROSTER_SOURCE", "origin/main")
    content, _, source = sc.resolve_roster(None, _ROOT)
    assert content == b'{"mcpServers":{}}'
    assert "origin/main" in source


def test_from_tree_env_is_honoured(tmp_path, monkeypatch):
    """PMOVES_ROSTER_FROM_TREE is the launcher's documented escape hatch for
    editing the roster itself; this must not silently read origin/main then."""
    monkeypatch.delenv("PMOVES_MCP_ROSTER", raising=False)
    monkeypatch.setenv("PMOVES_ROSTER_FROM_TREE", "1")
    root = tmp_path
    (root / ".claude").mkdir()
    (root / ".claude" / "mcp.json").write_text('{"mcpServers":{}}', encoding="utf-8")
    content, _, source = sc.resolve_roster(None, root)
    assert content == b'{"mcpServers":{}}'
    assert "PMOVES_ROSTER_FROM_TREE" in source


def test_default_prefers_origin_main(monkeypatch):
    """The launcher loads origin/main unless told otherwise (PR #2847). A tool
    reporting on the working tree while Claude loads main's copy is an
    instrument measuring something other than what runs."""
    monkeypatch.delenv("PMOVES_MCP_ROSTER", raising=False)
    monkeypatch.delenv("PMOVES_ROSTER_FROM_TREE", raising=False)
    content, display, source = sc.resolve_roster(None, _ROOT)
    if content is None:  # no origin/main here (shallow clone / detached CI)
        pytest.skip("origin/main:.claude/mcp.json not readable in this checkout")
    assert "origin/main" in source
    json.loads(content.decode("utf-8"))


def test_a_missing_roster_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.delenv("PMOVES_MCP_ROSTER", raising=False)
    monkeypatch.setenv("PMOVES_ROSTER_FROM_TREE", "1")
    content, _, source = sc.resolve_roster(None, tmp_path)
    assert content is None
    assert "unreadable" in source


# --------------------------------------------------------------------------
# Roster-level behaviour
# --------------------------------------------------------------------------


def test_underscore_servers_are_disabled_not_degraded(tmp_path, monkeypatch):
    """A `_`-prefixed key under mcpServers is the roster's convention for a
    disabled entry, and the launcher's normalizer drops exactly these. Counting
    one would send an operator to credential something switched off."""
    roster = tmp_path / "r.json"
    roster.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "live": {"command": "echo"},
                    "_retired": {"headers": {"Authorization": "Bearer ${GONE}"}},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.argv", ["session_check.py", "--roster", str(roster), "--strict"])
    assert sc.main() == 0


def test_strict_exits_nonzero_when_a_server_is_dark(tmp_path, monkeypatch):
    roster = tmp_path / "r.json"
    roster.write_text(
        json.dumps({"mcpServers": {"a": {"headers": {"Authorization": "Bearer ${NOPE}"}}}}),
        encoding="utf-8",
    )
    monkeypatch.delenv("NOPE", raising=False)
    monkeypatch.setattr("sys.argv", ["session_check.py", "--roster", str(roster), "--strict"])
    assert sc.main() == 1


def test_advisory_mode_never_fails(tmp_path, monkeypatch):
    """env-check calls this. It must not be able to fail a fleet's canonical
    environment validation on a host that simply has no roster to authenticate."""
    roster = tmp_path / "r.json"
    roster.write_text(
        json.dumps({"mcpServers": {"a": {"headers": {"Authorization": "Bearer ${NOPE}"}}}}),
        encoding="utf-8",
    )
    monkeypatch.delenv("NOPE", raising=False)
    monkeypatch.setattr("sys.argv", ["session_check.py", "--roster", str(roster)])
    assert sc.main() == 0


# --------------------------------------------------------------------------
# --strict must not pass when it could not look (Codex, second pass)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(None, id="file-missing"),
        pytest.param("{ not json", id="unparseable"),
        pytest.param('{"somethingElse": {}}', id="no-mcpServers"),
    ],
)
def test_strict_fails_when_the_roster_is_indeterminate(tmp_path, monkeypatch, body):
    """A gate that cannot tell "nothing is wrong" from "I could not look" is
    worse than no gate. Every one of these branches used to return 0, so
    --strict could be satisfied by pointing at a path that does not exist."""
    roster = tmp_path / "r.json"
    if body is not None:
        roster.write_text(body, encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["session_check.py", "--roster", str(roster), "--strict"])
    assert sc.main() == 1


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(None, id="file-missing"),
        pytest.param("{ not json", id="unparseable"),
        pytest.param('{"somethingElse": {}}', id="no-mcpServers"),
    ],
)
def test_advisory_still_passes_when_the_roster_is_indeterminate(tmp_path, monkeypatch, body):
    """The other half of the same rule: env-check runs this without --strict on
    CI runners and non-Claude hosts, where having no roster is normal."""
    roster = tmp_path / "r.json"
    if body is not None:
        roster.write_text(body, encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["session_check.py", "--roster", str(roster)])
    assert sc.main() == 0
