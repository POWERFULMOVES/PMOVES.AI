# Release Notes — jCodemunch MCP for Hermes Client (2026-09-13)

**PR:** #2899 · **Suit concern:** `pmoves/config/mcp_inventory.json` (§6.4)

## What changed

`pmoves/config/mcp_inventory.json` now lists `jcodemunch` as an active MCP
entry, registered directly to the `hermes` client. The entry uses the
forked `PMOVES-jcodemunch-mcp` tool (PyPI run; v1.108.316 verified) with
the standard stdio transport:

```json
{
  "key": "jcodemunch",
  "transport": "stdio",
  "command": "uvx",
  "args": ["jcodemunch-mcp", "serve", "--transport", "stdio"],
  "clients": ["hermes"]
}
```

The entry carries a `_note` documenting the live handshake, the indexing
recipe (`uvx jcodemunch-mcp index <repo>` one-time per repo; `watch`
keeps it fresh), the fleet priority index targets (PMOVES.AI parent,
PMOVES-pinokio, PMOVES-hermes-agent, PMOVES-composio), and the fact that
this is stdio-local with no secrets and no fail-closed risk surface.

## Why it matters

Hermes is provisioned through the documented profile-copy workflow
(`pmoves/config/profiles/hermes/README.md` and
`pmoves/docs/AGENTS/HERMES_AGENT_INTEGRATION.md`). A node YAML is copied
directly into the active profile without running the inventory generator;
without an inventory row, the profile carries no signal that jcodemunch
is available, and Hermes's token-efficient code-exploration lane was
invisible to every Hermes-equipped node.

Verified live 2026-09-03: initialize handshake clean against server
v1.108.316 (PyPI run of the forked tool). Index repos first via
`uvx jcodemunch-mcp index <repo>` (one-time per repo; `watch` keeps fresh).

## What this does NOT do

- It does not add jcodemunch to other clients (`crush`, `claude`,
  `kilocode`, `kimi`, `opencode`). The Codex review asked specifically
  for the `hermes` row, which is the profile that copies directly from
  the active node's YAML. Adding the row to other clients is a separate
  PR (and a separate profile audit) once Hermes's use of the tool is
  proven.
- It does not change the indexing recipe. The fleet-priority index list
  is in the `_note`, not in the tool's actual config.
- It does not touch the upstream jCodemunch registry. The forked
  `PMOVES-jcodemunch-mcp` runs from PyPI; no GitHub-side install needed.

## Operator follow-up

- `make -C pmoves mcp-config-bootstrap` re-renders the client configs.
  On a Hermes-equipped node, the rendered `hermes.json` should now
  carry the jcodemunch entry.
- The fleet-priority index targets should be indexed once per repo,
  before the operator expects Hermes sessions to land fast on cross-repo
  searches.
