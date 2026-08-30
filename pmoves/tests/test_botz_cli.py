"""Tests for botz_cli.py — W6-P3 Persona Selector + Identity Tool."""
import json
import os
import subprocess
import sys

import pytest

_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "tools", "botz_cli.py")


def _run(args: list[str], env_override: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run the BoTZ CLI and return result."""
    env = {**os.environ, "PYTHONUTF8": "1", **(env_override or {})}
    return subprocess.run(
        [sys.executable, _SCRIPT, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=10,
    )


# ---------------------------------------------------------------------------
# whoami
# ---------------------------------------------------------------------------
class TestWhoami:
    def test_whoami_with_env(self):
        result = _run(["whoami", "--json"], env_override={"PMOVES_AGENT_ID": "4090-claude"})
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["agent_id"] == "4090-claude"
        assert data["source"] == "env"
        assert data["glyph"] == "\u25c9"

    def test_whoami_text_output(self):
        result = _run(["whoami"], env_override={"PMOVES_AGENT_ID": "claude-opus"})
        assert result.returncode == 0
        assert "Claude Opus" in result.stdout

    def test_whoami_heuristic(self):
        env = {k: v for k, v in os.environ.items() if k != "PMOVES_AGENT_ID"}
        env["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, _SCRIPT, "whoami", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, timeout=10,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["source"] in ("hostname", "fallback")


# ---------------------------------------------------------------------------
# theme
# ---------------------------------------------------------------------------
class TestTheme:
    def test_theme_known_agent(self):
        result = _run(["theme", "z890-claude"])
        assert result.returncode == 0
        assert "Z890 Claude" in result.stdout
        assert "infrastructure-coordinator" in result.stdout

    def test_theme_json(self):
        result = _run(["theme", "4090-claude", "--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["agent_id"] == "4090-claude"
        assert data["color"] == "#0D9488"
        assert data["specialization"] == "noise-reducer"
        assert len(data["alters"]) >= 1

    def test_theme_unknown_agent(self):
        result = _run(["theme", "nonexistent"])
        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_theme_shows_alters(self):
        result = _run(["theme", "4090-claude"])
        assert result.returncode == 0
        assert "4090-field" in result.stdout


# ---------------------------------------------------------------------------
# persona list
# ---------------------------------------------------------------------------
class TestPersonaList:
    def test_list_text(self):
        result = _run(["persona", "list"])
        assert result.returncode == 0
        assert "Available Personas" in result.stdout
        assert "Claude Opus" in result.stdout

    def test_list_json(self):
        result = _run(["persona", "list", "--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) >= 10
        ids = [p["agent_id"] for p in data]
        assert "4090-claude" in ids
        assert "claude-opus" in ids

    def test_list_shows_current_marker(self):
        result = _run(["persona", "list"], env_override={"PMOVES_AGENT_ID": "4090-claude"})
        assert result.returncode == 0
        assert "* = current" in result.stdout


# ---------------------------------------------------------------------------
# persona select
# ---------------------------------------------------------------------------
class TestPersonaSelect:
    def test_select_text(self):
        result = _run(["persona", "select", "4090-claude"])
        assert result.returncode == 0
        assert "4090 Claude" in result.stdout
        assert "selected" in result.stdout

    def test_select_export(self):
        result = _run(["persona", "select", "z890-claude", "--export"])
        assert result.returncode == 0
        assert 'export PMOVES_AGENT_ID="z890-claude"' in result.stdout
        assert 'export PMOVES_AGENT_COLOR="#1E40AF"' in result.stdout
        assert 'export PMOVES_AGENT_VOICE="analytical"' in result.stdout

    def test_select_json(self):
        result = _run(["persona", "select", "claude-opus", "--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["selected"] == "claude-opus"
        assert data["env"]["PMOVES_AGENT_ID"] == "claude-opus"

    def test_select_unknown(self):
        result = _run(["persona", "select", "fake-agent"])
        assert result.returncode == 1
        assert "not found" in result.stderr


# ---------------------------------------------------------------------------
# persona current
# ---------------------------------------------------------------------------
class TestPersonaCurrent:
    def test_current_with_env(self):
        result = _run(["persona", "current"], env_override={"PMOVES_AGENT_ID": "darkxside"})
        assert result.returncode == 0
        assert "DARKXSIDE" in result.stdout

    def test_current_json(self):
        result = _run(["persona", "current", "--json"], env_override={"PMOVES_AGENT_ID": "crush"})
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["agent_id"] == "crush"
        assert data["source"] == "env"

    def test_current_no_persona(self):
        env = {k: v for k, v in os.environ.items() if k != "PMOVES_AGENT_ID"}
        env["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, _SCRIPT, "persona", "current"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, timeout=10,
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_no_args_shows_help(self):
        result = _run([])
        assert result.returncode == 1

    def test_no_color(self):
        result = _run(["theme", "claude-opus"], env_override={"NO_COLOR": "1"})
        assert result.returncode == 0
        assert "\033[" not in result.stdout
        assert "Claude Opus" in result.stdout
