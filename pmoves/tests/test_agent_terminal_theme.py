"""Tests for agent_terminal_theme.py — W1 Agent Theming renderer."""
import json
import os
import subprocess
import sys

import pytest

_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "tools", "agent_terminal_theme.py")


def _run(args: list[str], env_override: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run the theme script and return result."""
    env = {**os.environ, "PYTHONUTF8": "1", **(env_override or {})}
    return subprocess.run(
        [sys.executable, _SCRIPT, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=10,
    )


# ---------------------------------------------------------------------------
# Banner output
# ---------------------------------------------------------------------------
class TestBanner:
    def test_known_agent_banner(self):
        result = _run(["--agent", "4090-claude", "--banner"])
        assert result.returncode == 0
        assert "4090 Claude" in result.stdout
        assert "noise-reducer" in result.stdout

    def test_unknown_agent_fails(self):
        result = _run(["--agent", "nonexistent-agent", "--banner"])
        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_no_color_strips_ansi(self):
        result = _run(["--agent", "claude-opus", "--banner"], env_override={"NO_COLOR": "1"})
        assert result.returncode == 0
        assert "\033[" not in result.stdout
        assert "Claude Opus" in result.stdout


# ---------------------------------------------------------------------------
# Status bar
# ---------------------------------------------------------------------------
class TestStatusBar:
    def test_status_output(self):
        result = _run(["--agent", "4090-claude", "--status", "P7 live, 11/20 TAC"])
        assert result.returncode == 0
        assert "P7 live" in result.stdout
        assert "4090 Claude" in result.stdout


# ---------------------------------------------------------------------------
# Session header
# ---------------------------------------------------------------------------
class TestSessionHeader:
    def test_session_with_node(self):
        result = _run(["--agent", "4090-claude", "--session"])
        assert result.returncode == 0
        assert "RTX 4090" in result.stdout
        assert "noise-reducer" in result.stdout


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------
class TestJsonOutput:
    def test_agent_json(self):
        result = _run(["--agent", "4090-claude", "--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["agent_id"] == "4090-claude"
        assert data["color"] == "#0D9488"
        assert data["glyph"] == "\u25c9"
        assert "noise-reducer" == data["specialization"]

    def test_session_json_includes_node(self):
        result = _run(["--agent", "z890-claude", "--session", "--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["agent_id"] == "z890-claude"
        assert "node" in data
        assert data["node"]["hardware"]["gpu"] == "RTX 3090 Ti 24GB"

    def test_roster_json(self):
        result = _run(["--roster", "--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) >= 10
        ids = [a["agent_id"] for a in data]
        assert "claude-opus" in ids
        assert "4090-claude" in ids

    def test_demo_json(self):
        result = _run(["--demo", "--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert all("glyph" in a for a in data)


# ---------------------------------------------------------------------------
# Whoami
# ---------------------------------------------------------------------------
class TestWhoami:
    def test_whoami_with_env(self):
        result = _run(["--whoami", "--json"], env_override={"PMOVES_AGENT_ID": "4090-claude"})
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["agent_id"] == "4090-claude"
        assert data["source"] == "env"
        assert data["theme"]["color"] == "#0D9488"

    def test_whoami_heuristic_fallback(self):
        """Without PMOVES_AGENT_ID, whoami uses hostname heuristic."""
        env = {k: v for k, v in os.environ.items() if k != "PMOVES_AGENT_ID"}
        env["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, _SCRIPT, "--whoami", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, timeout=10,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "agent_id" in data
        assert data["source"] == "heuristic"


# ---------------------------------------------------------------------------
# Remote fallback
# ---------------------------------------------------------------------------
class TestRemoteFallback:
    def test_remote_falls_back_to_local(self):
        """When gateway is unreachable, --remote should fallback to local YAML."""
        result = _run(
            ["--agent", "claude-opus", "--remote", "--banner"],
            env_override={"BOTZ_GATEWAY_URL": "http://localhost:19999"},
        )
        assert result.returncode == 0
        assert "Claude Opus" in result.stdout
        assert "falling back" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Demo and roster
# ---------------------------------------------------------------------------
class TestDemoRoster:
    def test_demo_renders_all(self):
        result = _run(["--demo"])
        assert result.returncode == 0
        assert "Claude Opus" in result.stdout
        assert "4090 Claude" in result.stdout
        assert "Agent Roster" in result.stdout

    def test_roster_compact(self):
        result = _run(["--roster"])
        assert result.returncode == 0
        assert "Agent Roster" in result.stdout

    def test_no_args_shows_help(self):
        result = _run([])
        assert result.returncode == 1
        assert "usage:" in result.stdout.lower() or "usage:" in result.stderr.lower()


def test_host_map_keys_are_hostnames_not_hardware_descriptions():
    """The 4090 resolved to "unknown" because its key was a DESCRIPTION.

    `_HOST_MAP` had "z890" and "powerfulmoves" (hostnames) alongside "laptop"
    (what the machine is). When the box was named PMOVES-4090, nothing matched:
    the signature `4090-claude` existed, the node had an identity, and --whoami
    returned "unknown (not in signatures)".

    Asserted against the REAL signature list so a node cannot be mapped to an
    identity that does not exist, and so the 4090's own hostname keeps
    resolving.
    """
    import re
    src = open(_SCRIPT, encoding="utf-8").read()
    block = re.search(r"_HOST_MAP = \{(.*?)\}", src, re.S)
    assert block, "_HOST_MAP not found"
    pairs = re.findall(r'"([^"]+)":\s*"([^"]+)"', block.group(1))
    mapping = dict(pairs)

    # the concrete regression: this machine's real hostname must resolve
    assert "pmoves-4090" in mapping, "the 4090's real hostname is not mapped"
    assert mapping["pmoves-4090"] == "4090-claude"

    # and every target must be a signature that actually exists
    import yaml
    sig_path = os.path.join(os.path.dirname(__file__), "..", "config", "agent_signatures.yaml")
    sigs = yaml.safe_load(open(sig_path, encoding="utf-8"))["signatures"]
    known = set(sigs) if isinstance(sigs, dict) else {s.get("id") for s in sigs}
    unknown = {v for v in mapping.values() if v not in known}
    assert not unknown, f"_HOST_MAP points at signatures that do not exist: {unknown}"
