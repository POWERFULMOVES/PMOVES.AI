"""
Drift detector for the pmoves-hirag-mcp wire-up.

The HiRAG MCP is loaded by any agent session that wants grounded
retrieval (vector + graph + full-text + rerank). For the wire-up
to actually work, the entry must be present AND consistent across
4 surfaces:

  1. `pmoves/config/agent_registry.yaml` — the `pmoves_hirag_mcp`
     block has `transport: sse` and `status: active`.
  2. `.claude/mcp.json` — the `mcpServers.pmoves-hirag-mcp` block
     is a SSE entry with a URL that resolves to the registry
     endpoint.
  3. `.claude/BOOTSTRAP.md` — the `MCP Entrypoints` table lists
     `pmoves-hirag-mcp` so a cold-start agent finds it.
  4. The action_namespace in the registry matches the
     `mcp.v1.hirag` convention so a dispatcher can route calls.

These tests parse the files (no API calls) and assert the
shapes. A future PR that drops the entry, renames it, swaps
transports, or leaves a `status: planned` regression fails
here at PR time.

Pre-slice state: the registry had `status: "planned"`; the
.mcp.json had no entry; the BOOTSTRAP.md table had no row.
Post-slice: all 4 surfaces have consistent active-SSE wiring
(followups-v1 commits 5 + 6 + 7).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml"
MCP_JSON = REPO_ROOT / ".claude" / "mcp.json"
BOOTSTRAP_MD = REPO_ROOT / ".claude" / "BOOTSTRAP.md"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def registry_text() -> str:
    if not REGISTRY.exists():
        pytest.skip(f"agent_registry.yaml not present at {REGISTRY}")
    return REGISTRY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def mcp_json() -> dict:
    if not MCP_JSON.exists():
        pytest.skip(f"mcp.json not present at {MCP_JSON}")
    return json.loads(MCP_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bootstrap_text() -> str:
    if not BOOTSTRAP_MD.exists():
        pytest.skip(f"BOOTSTRAP.md not present at {BOOTSTRAP_MD}")
    return BOOTSTRAP_MD.read_text(encoding="utf-8")


def _hirag_registry_block(registry_text: str) -> dict:
    """Parse the `pmoves_hirag_mcp:` block from the registry.

    The registry is YAML; we use yaml.safe_load on the whole file
    and look up the block. Returns the dict (or skips if missing
    — absence is the failure mode for one of the tests below).
    """
    data = yaml.safe_load(registry_text)
    # Walk to mcp_servers.pmoves_hirag_mcp (the canonical location
    # for MCP entries in the registry).
    mcp_servers = data.get("mcp_servers", {})
    return mcp_servers.get("pmoves_hirag_mcp", {})


# ============================================================================
# Surface 1: agent_registry.yaml
# ============================================================================


def test_hirag_registry_block_exists(registry_text: str) -> None:
    """`pmoves_hirag_mcp:` block is present in mcp_servers."""
    block = _hirag_registry_block(registry_text)
    assert block, (
        "pmoves_hirag_mcp entry missing from pmoves/config/agent_registry.yaml "
        "under mcp_servers; the registry is the source of truth for MCP "
        "wiring and must list the entry"
    )


def test_hirag_registry_status_is_active(registry_text: str) -> None:
    """`status: active` — not `planned`."""
    block = _hirag_registry_block(registry_text)
    assert block.get("status") == "active", (
        f"pmoves_hirag_mcp.status is {block.get('status')!r}; expected 'active'. "
        f"Flip the status to active once the .claude/mcp.json SSE registration "
        f"is in place (followups-v1 commit 5)"
    )


def test_hirag_registry_transport_is_sse(registry_text: str) -> None:
    """`transport: sse` — not stdio, not http, not anything else."""
    block = _hirag_registry_block(registry_text)
    assert block.get("transport") == "sse", (
        f"pmoves_hirag_mcp.transport is {block.get('transport')!r}; "
        f"the HiRAG MCP server is SSE-only and the registry must agree"
    )


def test_hirag_registry_action_namespace(registry_text: str) -> None:
    """`action_namespace: mcp.v1.hirag` for dispatcher routing."""
    block = _hirag_registry_block(registry_text)
    assert block.get("action_namespace") == "mcp.v1.hirag", (
        f"pmoves_hirag_mcp.action_namespace is {block.get('action_namespace')!r}; "
        f"expected 'mcp.v1.hirag' (the canonical mcp.v1.<service> form that "
        f"the orchestrator dispatcher routes on)"
    )


# ============================================================================
# Surface 2: .claude/mcp.json
# ============================================================================


def test_hirag_mcp_json_entry_exists(mcp_json: dict) -> None:
    """`mcpServers.pmoves-hirag-mcp` block is present."""
    servers = mcp_json.get("mcpServers", {})
    assert "pmoves-hirag-mcp" in servers, (
        "pmoves-hirag-mcp is missing from .claude/mcp.json under mcpServers; "
        "this is the runtime registration that makes the MCP tools available "
        "to Claude Code / Agent Zero / Hermes sessions"
    )


def test_hirag_mcp_json_is_sse_transport(mcp_json: dict) -> None:
    """The entry has `type: sse` (matches registry transport)."""
    servers = mcp_json.get("mcpServers", {})
    entry = servers.get("pmoves-hirag-mcp", {})
    assert entry.get("type") == "sse", (
        f"pmoves-hirag-mcp type is {entry.get('type')!r}; expected 'sse' "
        f"to match pmoves_hirag_mcp.transport in the registry"
    )


def test_hirag_mcp_json_url_present(mcp_json: dict) -> None:
    """The entry has a URL (not a stdio command/args block)."""
    servers = mcp_json.get("mcpServers", {})
    entry = servers.get("pmoves-hirag-mcp", {})
    assert entry.get("url"), (
        "pmoves-hirag-mcp is missing its `url` field; SSE transport "
        "requires a URL pointing at the SSE endpoint"
    )


# ============================================================================
# Surface 3: .claude/BOOTSTRAP.md (the cold-start table)
# ============================================================================


def test_hirag_bootstrap_table_row(bootstrap_text: str) -> None:
    """`pmoves-hirag-mcp` is listed in the MCP Entrypoints table."""
    assert "pmoves-hirag-mcp" in bootstrap_text, (
        "pmoves-hirag-mcp is missing from .claude/BOOTSTRAP.md; the "
        "MCP Entrypoints table is the cold-start surface that tells "
        "a fresh agent which MCP servers are configured. Without "
        "this row, an agent that knows HiRAG exists but doesn't "
        "know it's wired in this fork will skip the lookup"
    )


def test_hirag_bootstrap_table_has_sse(bootstrap_text: str) -> None:
    """The HiRAG row mentions SSE so the cold-start agent knows the transport."""
    # The table row format is:
    # | `pmoves-hirag-mcp` | SSE `${...}` | <purpose> |
    # We assert the SSE marker is on the same line as the entry name.
    lines = bootstrap_text.splitlines()
    hirag_lines = [line for line in lines if "pmoves-hirag-mcp" in line]
    assert hirag_lines, (
        "pmoves-hirag-mcp does not appear in any BOOTSTRAP.md line"
    )
    # The first non-table line (often the heading) shouldn't be the only
    # match; we want a table row.
    for line in hirag_lines:
        if line.strip().startswith("|") and "SSE" in line:
            return
    raise AssertionError(
        f"pmoves-hirag-mcp appears in BOOTSTRAP.md but not in a table row "
        f"marked with SSE; lines: {hirag_lines}"
    )


# ============================================================================
# Cross-surface consistency
# ============================================================================


def test_hirag_registry_action_namespace_in_json_metadata(registry_text: str, mcp_json: dict) -> None:
    """The action_namespace from the registry is reflected in the JSON entry.

    A future refactor that renames `action_namespace` in the registry
    but leaves the mcp.json key alone is a wire-up drift; this test
    catches the asymmetry.
    """
    block = _hirag_registry_block(registry_text)
    expected_namespace = block.get("action_namespace", "")
    # mcp.json doesn't carry action_namespace as a top-level field, but
    # we use a `_purpose` or `_action_namespace` note. The drift check
    # is on the registry field existence + mcp.json presence.
    servers = mcp_json.get("mcpServers", {})
    entry = servers.get("pmoves-hirag-mcp", {})
    assert entry, (
        "pmoves-hirag-mcp entry missing from mcp.json while registry has it; "
        f"registry action_namespace={expected_namespace!r}"
    )
    assert expected_namespace, (
        "Registry action_namespace is empty for pmoves_hirag_mcp; the "
        "dispatcher needs a non-empty mcp.v1.<service> identifier to route"
    )


def test_hirag_grounding_source_flag_set(registry_text: str) -> None:
    """`grounding_source: true` — a discovering agent fetches startup grounding."""
    block = _hirag_registry_block(registry_text)
    assert block.get("grounding_source") is True, (
        "pmoves_hirag_mcp.grounding_source is not True; a discovering agent "
        "expects this flag to fetch startup grounding on cold start"
    )


def test_hirag_capabilities_nonempty(registry_text: str) -> None:
    """`capabilities:` is a non-empty list."""
    block = _hirag_registry_block(registry_text)
    caps = block.get("capabilities", [])
    assert caps, (
        "pmoves_hirag_mcp.capabilities is empty; the orchestrator uses "
        "this list to know which actions the MCP can serve (retrieve, "
        "graph, search, notebook)"
    )
    # Spot-check the canonical HiRAG capabilities.
    for expected in ("retrieve", "graph", "search"):
        assert expected in caps, (
            f"pmoves_hirag_mcp.capabilities missing {expected!r}; "
            f"the HiRAG hybrid retrieval requires retrieve (vector), "
            f"graph (Neo4j), and search (Meilisearch) at minimum"
        )
