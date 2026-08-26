"""The MCP roster normalizer must announce what it cannot resolve.

A server whose ``url`` is ``http://${TS_Z890}:8105/mcp/sse`` with TS_Z890 unset
used to sail through the launcher looking perfectly configured. Claude Code's
documented behaviour is to warn and then send the literal ``${TS_Z890}`` as a
hostname, so the connection died somewhere no agent could observe -- one
session lost its entire memory layer and could not distinguish that from
"cipher is down".

These tests pin the two halves of the fix: an unresolvable server is DROPPED
and NAMED, a resolvable one is kept and expanded. They live here rather than in
deploy/provision/tests/ because that directory's one test is wired into no CI
job and no Make target -- and a test nobody runs is the same defect class this
whole change is about.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "pmoves" / "tools" / "mcp_roster_normalize.py"
LAUNCHER = REPO_ROOT / "deploy" / "provision" / "claude-pmoves.sh"
TS_HELPER = REPO_ROOT / "pmoves" / "scripts" / "tailscale-node-ips.sh"
CRUSH_ENV = REPO_ROOT / "pmoves" / "scripts" / "crush-env.sh"

sys.path.insert(0, str(REPO_ROOT / "pmoves" / "tools"))
import mcp_roster_normalize as norm  # noqa: E402


def _roster(**servers):
    return {"mcpServers": dict(servers)}


# --------------------------------------------------------------------------
# P4: the defect this change exists to close
# --------------------------------------------------------------------------


def test_unset_var_in_url_drops_the_server_and_names_the_variable():
    data = _roster(**{"pmoves-cipher": {"type": "sse", "url": "http://${TS_Z890}:8105/mcp/sse"}})
    clean, dropped = norm.normalize(data, "/repo", {})

    assert "pmoves-cipher" not in clean["mcpServers"], "unresolvable server was handed to Claude"
    assert dropped == [("pmoves-cipher", ["TS_Z890"])]


def test_set_var_in_url_keeps_the_server_and_expands_it():
    data = _roster(**{"pmoves-cipher": {"type": "sse", "url": "http://${TS_Z890}:8105/mcp/sse"}})
    clean, dropped = norm.normalize(data, "/repo", {"TS_Z890": "node.example"})

    assert dropped == []
    assert clean["mcpServers"]["pmoves-cipher"]["url"] == "http://node.example:8105/mcp/sse"


def test_every_missing_variable_is_named_not_just_the_first():
    data = _roster(**{
        "agent-zero": {"url": "http://${TS_Z890}:8081/mcp/t-${AGENT_ZERO_MCP_TOKEN}/sse"},
    })
    _clean, dropped = norm.normalize(data, "/repo", {})
    assert dropped == [("agent-zero", ["AGENT_ZERO_MCP_TOKEN", "TS_Z890"])]


def test_headers_and_env_are_scanned_too():
    data = _roster(
        gateway={"url": "http://localhost:8090/sse",
                 "headers": {"Authorization": "Bearer ${MCP_GATEWAY_AUTH_TOKEN}"}},
        nats={"command": "uv", "env": {"NATS_URL": "${NATS_URL}"}},
    )
    _clean, dropped = norm.normalize(data, "/repo", {})
    assert dict(dropped) == {"gateway": ["MCP_GATEWAY_AUTH_TOKEN"], "nats": ["NATS_URL"]}


def test_an_exported_empty_string_counts_as_missing():
    """An empty export satisfies a presence check and yields http://:8105/."""
    data = _roster(cipher={"url": "http://${TS_Z890}:8105/mcp/sse"})
    _clean, dropped = norm.normalize(data, "/repo", {"TS_Z890": ""})
    assert dropped == [("cipher", ["TS_Z890"])]


def test_one_bad_server_does_not_take_the_others_down():
    data = _roster(
        bad={"url": "http://${NOPE}:1/x"},
        good={"url": "https://mcp.cloudflare.com/mcp"},
    )
    clean, dropped = norm.normalize(data, "/repo", {})
    assert list(clean["mcpServers"]) == ["good"]
    assert [n for n, _ in dropped] == ["bad"]


# --------------------------------------------------------------------------
# default forms -- these must NOT be treated as missing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,environ,expected",
    [
        ("Bearer ${CIPHER_API_TOKEN:-}", {}, "Bearer "),
        ("${A:-fallback}", {}, "fallback"),
        ("${A:-fallback}", {"A": "real"}, "real"),
        ("${A:-fallback}", {"A": ""}, "fallback"),
        ("${A-fallback}", {"A": ""}, ""),  # POSIX: set-but-empty is a value
        ("${A:-${B}}", {"B": "nested"}, "nested"),
        ("${A:-${B:-deep}}", {}, "deep"),
        ("${URL:-http://localhost:8000/rest/v1}", {}, "http://localhost:8000/rest/v1"),
        ("no references here", {}, "no references here"),
        ("${UNBALANCED", {}, "${UNBALANCED"),
    ],
)
def test_default_forms_resolve_without_being_flagged(text, environ, expected):
    missing: list[str] = []
    assert norm.expand(text, environ, missing) == expected
    assert missing == []


def test_a_server_using_only_defaults_survives_an_empty_environment():
    data = _roster(cipher={
        "url": "http://localhost:8105/mcp/sse",
        "headers": {"Authorization": "Bearer ${CIPHER_API_TOKEN:-}"},
    })
    clean, dropped = norm.normalize(data, "/repo", {})
    assert dropped == []
    assert clean["mcpServers"]["cipher"]["headers"]["Authorization"] == "Bearer "


# --------------------------------------------------------------------------
# P2 / P3 -- preserved from the heredoc this replaced
# --------------------------------------------------------------------------


def test_underscore_prefixed_servers_are_still_dropped():
    data = _roster(**{"_legacy": {"command": "uv"}, "live": {"command": "uv"}})
    clean, _ = norm.normalize(data, "/repo", {})
    assert list(clean["mcpServers"]) == ["live"]


def test_relative_launch_paths_are_still_made_absolute():
    data = _roster(nats={"command": "uv", "args": ["--directory", "./pmoves-nats-mcp", "run"]})
    clean, _ = norm.normalize(data, "/repo", {})
    assert clean["mcpServers"]["nats"]["args"][1] == os.path.join("/repo", "pmoves-nats-mcp")


def test_a_declared_disabled_server_is_left_alone_not_warned_about():
    """It is already off; a WARN about its variables would nag forever."""
    data = _roster(archon={"url": "http://${TS_Z890}:8051", "disabled": True})
    clean, dropped = norm.normalize(data, "/repo", {})
    assert dropped == []
    assert clean["mcpServers"]["archon"]["url"] == "http://${TS_Z890}:8051"


def test_normalize_does_not_mutate_the_tracked_roster():
    data = _roster(cipher={"url": "http://${TS_Z890}:1/x", "args": ["./rel"]})
    norm.normalize(data, "/repo", {"TS_Z890": "node.example"})
    assert data["mcpServers"]["cipher"]["url"] == "http://${TS_Z890}:1/x"
    assert data["mcpServers"]["cipher"]["args"] == ["./rel"]


# --------------------------------------------------------------------------
# CLI contract -- what the launcher actually depends on
# --------------------------------------------------------------------------


def _run_cli(tmp_path, roster, env):
    src = tmp_path / "mcp.json"
    dst = tmp_path / "resolved.json"
    src.write_text(json.dumps(roster))
    proc = subprocess.run(
        [sys.executable, str(TOOL), str(src), str(dst), "--root", "/repo", "--label", "claude-pmoves"],
        capture_output=True, text=True, env={**os.environ, **env},
    )
    return proc, dst


def test_cli_warns_on_stderr_naming_server_and_variable(tmp_path):
    proc, dst = _run_cli(
        tmp_path,
        _roster(**{"pmoves-cipher": {"url": "http://${TS_ZZZ_ABSENT}:8105/mcp/sse"}}),
        {},
    )
    assert proc.returncode == 0
    assert "pmoves-cipher" in proc.stderr
    assert "TS_ZZZ_ABSENT" in proc.stderr
    assert "[claude-pmoves]" in proc.stderr
    assert "pmoves-cipher" not in json.loads(dst.read_text())["mcpServers"]


def test_cli_output_is_owner_only_because_it_now_holds_expanded_secrets(tmp_path):
    _proc, dst = _run_cli(
        tmp_path,
        _roster(gw={"url": "http://x/y", "headers": {"Authorization": "Bearer ${TS_TEST_SECRET}"}}),
        {"TS_TEST_SECRET": "s3cret"},
    )
    body = json.loads(dst.read_text())
    assert body["mcpServers"]["gw"]["headers"]["Authorization"] == "Bearer s3cret"
    assert stat.S_IMODE(dst.stat().st_mode) == 0o600


def test_cli_fails_loudly_on_a_broken_roster_so_the_launcher_can_fall_back(tmp_path):
    src = tmp_path / "mcp.json"
    src.write_text("{ not json")
    proc = subprocess.run(
        [sys.executable, str(TOOL), str(src), str(tmp_path / "out.json"), "--root", "/repo"],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0


# --------------------------------------------------------------------------
# wiring -- the half that made #2764's fix land on a path nobody takes
# --------------------------------------------------------------------------


def test_the_launcher_actually_calls_the_normalizer():
    body = LAUNCHER.read_text()
    assert "pmoves/tools/mcp_roster_normalize.py" in body
    assert "<<'PY'" not in body, "the untestable heredoc came back"


def test_the_launcher_sources_the_shared_tailnet_helper():
    assert "pmoves/scripts/tailscale-node-ips.sh" in LAUNCHER.read_text()


def test_the_tailnet_resolution_has_exactly_one_definition():
    """crush-env.sh must SOURCE the helper, not carry its own copy."""
    body = CRUSH_ENV.read_text()
    assert "tailscale-node-ips.sh" in body
    assert "export TS_Z890=" not in body, "second copy of the resolution reappeared"


def test_the_helper_hardcodes_no_tailnet_address():
    """100.64/10 is CGNAT; a baked address leaks topology and rots."""
    import re

    assert not re.search(r"\b100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.", TS_HELPER.read_text())
