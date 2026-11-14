"""The harness_scope team: registry rows, agent definitions and team list agree.

Pins what makes the team durable rather than a set of prompts:
- every member has a registry row, an agent definition, and the team list names it;
- the definition's frontmatter matches the row (name, role_class);
- the reviewer withholds Write/Edit/Agent; writers do not spawn arbitrary agents;
- every member measures the platform first (Windows / WSL / Linux, Docker
  linux vs windows containers) and treats Windows containers as host-admin.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml"
TEAMS = REPO_ROOT / "pmoves" / "configs" / "agent-teams.yaml"
MEMBERS = ["harness_scope_auditor", "harness_provisioner", "skills_plugin_curator"]


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text.replace("\r\n", "\n"), re.S)
    assert match, f"{path} has no frontmatter"
    return yaml.safe_load(match.group(1))


def _tools(value: str | None) -> set[str]:
    return {t.strip() for t in (value or "").split(",") if t.strip()}


@pytest.fixture(scope="module")
def registry() -> dict:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["agents"]


def test_the_team_lists_exactly_its_members():
    teams = yaml.safe_load(TEAMS.read_text(encoding="utf-8"))["teams"]
    assert teams["harness_scope"]["agents"] == MEMBERS


@pytest.mark.parametrize("key", MEMBERS)
def test_row_and_definition_agree(registry, key):
    row = registry[key]
    assert row["topology"]["team"] == "harness_scope"
    assert row["scope"]["host_access"] == "repo", "a team member never holds the host"
    path = REPO_ROOT / row["agent_definition"]
    fm = _frontmatter(path)
    assert fm["name"] == key.replace("_", "-")
    assert fm["role_class"] == row["role_class"]


def test_the_auditor_cannot_write_or_delegate(registry):
    fm = _frontmatter(REPO_ROOT / registry["harness_scope_auditor"]["agent_definition"])
    assert {"Write", "Edit", "Agent"} <= _tools(fm["disallowedTools"])
    assert not {"Write", "Edit"} & _tools(fm["tools"])


@pytest.mark.parametrize("key", ["harness_provisioner", "skills_plugin_curator"])
def test_writers_only_spawn_named_agents(registry, key):
    fm = _frontmatter(REPO_ROOT / registry[key]["agent_definition"])
    agent_tools = [t for t in _tools(fm["tools"]) if t.startswith("Agent")]
    assert agent_tools and all(t.startswith("Agent(") for t in agent_tools), (
        f"{key}: a bare `Agent` would let it spawn any agent, including wider ones")


@pytest.mark.parametrize("key", MEMBERS)
def test_every_member_measures_the_platform_first(registry, key):
    body = (REPO_ROOT / registry[key]["agent_definition"]).read_text(encoding="utf-8")
    for needle in ("uname -s", "{{.OSType}}", "docker context show", "ContainerAdministrator"):
        assert needle in body, f"{key} never mentions {needle!r}"
