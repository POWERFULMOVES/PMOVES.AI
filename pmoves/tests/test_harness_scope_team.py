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


# --- Claude Desktop template: Desktop runs no damage-control hooks, so the folder
# list IS the scope. Every folder it opens must hold no zero-access file.

DESKTOP_DIR = REPO_ROOT / "deploy" / "provision" / "claude-desktop"
DESKTOP_TEMPLATES = ["claude_desktop_config.windows.json", "claude_desktop_config.macos.json"]
PLACEHOLDER = "<PMOVES_REPO>"


def _desktop_roots(name: str) -> list[str]:
    import json

    servers = json.loads((DESKTOP_DIR / name).read_text(encoding="utf-8"))["mcpServers"]
    args = servers["pmoves-filesystem"]["args"]
    return [a.replace("\\", "/")[len(PLACEHOLDER) + 1:] for a in args if a.startswith(PLACEHOLDER)]


def _zero_access_hit(rel: str) -> str | None:
    import fnmatch

    patterns = yaml.safe_load(
        (REPO_ROOT / ".claude/hooks/damage-control/patterns.yaml").read_text(encoding="utf-8")
    )["zeroAccessPaths"]
    base = rel.rsplit("/", 1)[-1]
    for pat in patterns:
        if pat.startswith("~"):
            continue
        p = pat.rstrip("/")
        if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(base, p) or f"/{p}/" in f"/{rel}/":
            return pat
    return None


@pytest.mark.parametrize("name", DESKTOP_TEMPLATES)
def test_desktop_template_opens_only_named_repo_subfolders(name):
    text = (DESKTOP_DIR / name).read_text(encoding="utf-8")
    assert "${" not in text, "Desktop does not expand ${VAR}; a template must not rely on it"
    servers = yaml.safe_load(text)["mcpServers"]
    assert set(servers) == {"pmoves-filesystem"}, "docker/secret-bearing servers are per-node, not template"
    args = servers["pmoves-filesystem"]["args"]
    folders = [a for a in args if a not in ("/c", "npx", "-y") and not a.startswith("@")]
    assert all(a.startswith(PLACEHOLDER) for a in folders), (
        f"{name}: every folder must sit under {PLACEHOLDER}, never a drive or home root")
    roots = _desktop_roots(name)
    assert roots, f"{name} opens no folder"
    for root in roots:
        assert root not in ("", "pmoves", ".claude"), f"{root}: too wide"
        assert (REPO_ROOT / root).is_dir(), f"{root} does not exist in the repo"


def test_desktop_templates_agree_across_platforms():
    assert _desktop_roots(DESKTOP_TEMPLATES[0]) == _desktop_roots(DESKTOP_TEMPLATES[1])


@pytest.mark.parametrize("root", _desktop_roots(DESKTOP_TEMPLATES[0]))
def test_desktop_roots_hold_no_zero_access_file(root):
    import os

    hits = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT / root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules")]
        for f in filenames:
            rel = Path(dirpath, f).relative_to(REPO_ROOT).as_posix()
            pat = _zero_access_hit(rel)
            if pat:
                hits.append(f"{rel} ({pat})")
    assert not hits, f"Desktop would expose zero-access files under {root}: {hits}"
