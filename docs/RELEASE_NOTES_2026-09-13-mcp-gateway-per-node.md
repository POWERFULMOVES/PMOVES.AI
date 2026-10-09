# Release Notes — MCP Gateway Profile Per Node (2026-09-13)

**PR:** #3043 · **Suit concern:** `pmoves/config/profiles/*` (§6.4)

## What changed

The Docker MCP Toolkit gateway profile is no longer a single literal that
served every node on every branch. Each of the three per-node profile files
(`desktop-9950xd.yaml`, `laptop-4090.yaml`, `workstation_5090.yaml`) now
declares its own `docker_mcp.gateway_profile` block:

```yaml
docker_mcp:
  gateway_profile: pmoves_5090_web   # (or pmoves_4090_web on the laptop)
```

The literal `pmoves_5090_web` is no longer hardcoded into `.claude/mcp.json`,
`pmoves/config/mcp_inventory.json`, or `pmoves/scripts/mcp-toolkit-connect.sh`
— those three surfaces now read the per-node value via
`pmoves/tools/node_gateway_profile.py`.

## Why it matters

`pmoves_5090_web` was the literal in **three** places at once. Measured on the
4090, 2026-09-13:

- `docker mcp profile ls` listed **both** `pmoves_4090_web` and
  `pmoves_5090_web`, so the wrong-profile gateway started silently — no
  error, just the wrong server set.
- Three launcher surfaces, two answers: root `.mcp.json` and
  `.claude/mcp.json` said `pmoves_5090_web`; `~/.config/crush/crush.json`
  said `pmoves_4090_web`. Whichever Claude session the operator opened
  picked up whichever the launcher had written last.
- `MCP_DOCKER` (per-node) and `pmoves-docker-gateway` (roster) **both**
  appeared in one session's failed-server list — different keys, so the
  launcher's deliberate non-strict merge loaded two gateways.

The per-node profile makes the answer canonical to the node, not to whichever
launcher surface the operator ran last.

## What this does NOT do

- It does not change the gateway roster. The set of servers a node exposes
  is unchanged.
- It does not change the merge surface between `MCP_DOCKER` and the roster.
  That is a separate lane.
- It does not touch `pmoves_5090_web` as a valid profile name. The 5090
  profile is still the canonical one for that node; the laptop profile
  (`pmoves_4090_web`) is the canonical one for that node. The literal
  `pmoves_5090_web` is just no longer applied to every node.

## Operator follow-up

- `make -C pmoves mcp-config-bootstrap` now renders per-node names into the
  client configs (`crush`, `kimi`, `opencode`, …). Re-run on each node
  that mounts `.claude/mcp.json`.
- `docker mcp profile ls` should now show only the per-node profile per
  node; cross-profile artifacts are the wrong-surface residual.
- The literal `pmoves_5090_web` survives as a string in `.claude/mcp.json`
  until the next `mcp-config-bootstrap` on this node, and as a key in
  the 5090's own profile.
