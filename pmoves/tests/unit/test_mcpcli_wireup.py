"""
Hand-written pytest suite for the mcpcli-wireup slice.

Closes the wire-up drift detector: every entry added in PR (feat/mcpcli-wireup)
must remain in place across the 5 surfaces where the model-cascade forks
land. If any entry is removed, these tests catch it before the harness v0
loses a service it depends on.

Coverage:
  - pmoves_minimax_mcp in pmoves/config/agent_registry.yaml
  - pmoves-minimax-mcp in .claude/mcp.json
  - pmoves-minimax-mcp in .claude/BOOTSTRAP.md
  - pmoves-minimax-mcp + services.minimax in the example CGP
  - find-skills in pmoves/configs/skill-pairings.yaml
  - skills host CLI in pmoves/configs/cli_tools.yaml

The tests parse the actual files; no mocks, no fixtures that would mask
drift. If a file is renamed, the test path needs an update — that's
intentional, the test names the wire-up so a future rewire has to be
explicit about it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


# Repo root is two parents up from pmoves/tests/unit/.
REPO_ROOT = Path(__file__).resolve().parents[3]


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def agent_registry() -> dict:
    """The PMOVES agent registry as a parsed dict."""
    path = REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def mcp_json() -> dict:
    """The Claude Code MCP config as a parsed dict."""
    path = REPO_ROOT / ".claude" / "mcp.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def bootstrap_md() -> str:
    """The cold-start BOOTSTRAP.md as a string (we check by substring)."""
    path = REPO_ROOT / ".claude" / "BOOTSTRAP.md"
    with path.open(encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def example_cgp() -> dict:
    """The PMOVES bootstrap CGP example as a parsed dict."""
    path = (
        REPO_ROOT
        / "pmoves"
        / "contracts"
        / "schemas"
        / "pmoves-bootstrap"
        / "example.cgp.yaml"
    )
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def cli_tools() -> dict:
    """The canonical CLI tools registry as a parsed dict."""
    path = REPO_ROOT / "pmoves" / "configs" / "cli_tools.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def skill_pairings() -> dict:
    """The skill-pairings manifest as a parsed dict."""
    path = REPO_ROOT / "pmoves" / "configs" / "skill-pairings.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================================
# agent_registry.yaml: pmoves_minimax_mcp entry
# ============================================================================

def test_agent_registry_has_minimax_mcp(agent_registry: dict) -> None:
    """The mcp_servers section must have the pmoves_minimax_mcp entry.

    The entry is the discovery-plane twin of the harness v0 follow-ups'
    skill registry (pmoves/configs/submodule_skill_registry.json). If
    someone removes it, the harness v0 loses the model surface.
    """
    mcp_servers = agent_registry.get("mcp_servers", {})
    assert "pmoves_minimax_mcp" in mcp_servers, (
        "pmoves_minimax_mcp missing from agent_registry.yaml mcp_servers"
    )


def test_agent_registry_minimax_mcp_submodule_pointer(agent_registry: dict) -> None:
    """The pmoves_minimax_mcp entry must point at the right submodule."""
    entry = agent_registry["mcp_servers"]["pmoves_minimax_mcp"]
    assert entry.get("submodule") == "PMOVES-MiniMax-MCP", (
        f"pmoves_minimax_mcp.submodule is {entry.get('submodule')!r}, "
        "expected 'PMOVES-MiniMax-MCP'"
    )
    assert entry.get("status") == "active", (
        f"pmoves_minimax_mcp.status is {entry.get('status')!r}, expected 'active'"
    )


def test_agent_registry_minimax_mcp_capabilities(agent_registry: dict) -> None:
    """The capabilities list must include the model surface (text/image/video/TTS)."""
    entry = agent_registry["mcp_servers"]["pmoves_minimax_mcp"]
    caps = set(entry.get("capabilities", []))
    expected = {"text", "image", "video", "tts"}
    missing = expected - caps
    assert not missing, f"pmoves_minimax_mcp missing capabilities: {missing}"


# ============================================================================
# .claude/mcp.json: pmoves-minimax-mcp server
# ============================================================================

def test_mcp_json_has_minimax_server(mcp_json: dict) -> None:
    """The mcpServers dict must have the pmoves-minimax-mcp entry."""
    servers = mcp_json.get("mcpServers", {})
    assert "pmoves-minimax-mcp" in servers, (
        "pmoves-minimax-mcp missing from .claude/mcp.json mcpServers"
    )


def test_mcp_json_minimax_command(mcp_json: dict) -> None:
    """The minimax server must use uvx + minimax-mcp (the upstream entry point)."""
    server = mcp_json["mcpServers"]["pmoves-minimax-mcp"]
    assert server.get("command") == "uvx", (
        f"pmoves-minimax-mcp.command is {server.get('command')!r}, expected 'uvx'"
    )
    args = server.get("args", [])
    assert "minimax-mcp" in args, (
        f"pmoves-minimax-mcp.args is {args!r}, expected to contain 'minimax-mcp'"
    )


# ============================================================================
# .claude/BOOTSTRAP.md: pmoves-minimax-mcp row
# ============================================================================

def test_bootstrap_md_lists_minimax_mcp(bootstrap_md: str) -> None:
    """BOOTSTRAP.md must mention pmoves-minimax-mcp in the MCP Entrypoints table.

    A cold-start agent uses this table to discover the model surface. If
    the row is missing, the cold-start loses the model surface silently.
    """
    assert "pmoves-minimax-mcp" in bootstrap_md, (
        "pmoves-minimax-mcp missing from .claude/BOOTSTRAP.md MCP Entrypoints"
    )


# ============================================================================
# pmoves-bootstrap example CGP: pmoves-minimax-mcp + minimax service
# ============================================================================

def test_cgp_example_has_minimax_mcp(example_cgp: dict) -> None:
    """The example CGP must list pmoves-minimax-mcp in mcps."""
    mcps = example_cgp.get("mcps", [])
    assert "pmoves-minimax-mcp" in mcps, (
        f"pmoves-minimax-mcp missing from example.cgp.yaml mcps: {mcps}"
    )


def test_cgp_example_has_minimax_service_block(example_cgp: dict) -> None:
    """The example CGP must have a minimax service block naming the 3 submodules."""
    services = example_cgp.get("services", {})
    assert "minimax" in services, (
        f"minimax service block missing from example.cgp.yaml services: "
        f"{list(services.keys())}"
    )
    minimax = services["minimax"]
    # The 3 NEW submodules (PR #2589) are named in the service block.
    for key in ("mcp", "cli", "verifier"):
        assert key in minimax, (
            f"minimax.{key} missing from example.cgp.yaml services.minimax"
        )


# ============================================================================
# cli_tools.yaml: skills host CLI
# ============================================================================

def test_cli_tools_has_skills_host_cli(cli_tools: dict) -> None:
    """The host_clis block must have a skills entry (npx skills package manager)."""
    host_clis = cli_tools.get("host_clis", {})
    assert "skills" in host_clis, (
        f"skills host CLI missing from cli_tools.yaml host_clis: "
        f"{list(host_clis.keys())}"
    )


def test_cli_tools_skills_check_command(cli_tools: dict) -> None:
    """The skills host CLI must have a check command (npx skills --version)."""
    skills_entry = cli_tools["host_clis"]["skills"]
    check = skills_entry.get("check", "")
    assert "npx skills" in check, (
        f"skills host CLI check is {check!r}, expected to contain 'npx skills'"
    )


# ============================================================================
# skill-pairings.yaml: find-skills meta-skill
# ============================================================================

def test_skill_pairings_has_find_skills(skill_pairings: dict) -> None:
    """The skill_sources block must have a find-skills entry."""
    sources = skill_pairings.get("skill_sources", {})
    assert "find-skills" in sources, (
        f"find-skills missing from skill-pairings.yaml skill_sources"
    )


def test_skill_pairings_find_skills_path(skill_pairings: dict) -> None:
    """The find-skills path must point at the PMOVES-skills submodule."""
    path = skill_pairings["skill_sources"]["find-skills"]
    assert "skills/PMOVES-skills/skills/find-skills" in path, (
        f"find-skills path is {path!r}, expected to point at the PMOVES-skills"
        " submodule"
    )


def test_skill_pairings_has_cli_host_skills(skill_pairings: dict) -> None:
    """The skill_sources block must have a cli-host-skills entry (companion)."""
    sources = skill_pairings.get("skill_sources", {})
    assert "cli-host-skills" in sources, (
        "cli-host-skills missing from skill-pairings.yaml skill_sources"
    )
