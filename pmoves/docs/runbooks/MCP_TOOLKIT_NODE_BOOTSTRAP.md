# Runbook — Bootstrap a Node onto the Docker MCP Toolkit

**Known Road.** Load the per-node MCP profile so an agent on that node has the full
tool surface — "just like the vps-deployer agent." Copy-paste, ~5 minutes per node.
Full reference: [`../operations/MCP_TOOLKIT.md`](../operations/MCP_TOOLKIT.md). Agent that
orchestrates this: `.claude/agents/fleet-node-deployer.md`.

> **Must run ON the target node** (a session on that node), per MCP_TOOLKIT.md §3–4.
> It CANNOT be driven from another node's session unless a Tailscale **remote-exec
> connector** is configured — and you must NOT sidestep SSH host-key checking to fake
> one (raw-SSH accept is a Known-Roads / governance violation; fail closed instead).

## Pre-flight

```bash
docker mcp version          # need >= v0.42.0
make -C pmoves help | grep mcp-toolkit   # confirms the targets exist in this checkout
```

- **Windows nodes** (4090, 5090, Z890): Docker Desktop + Toolkit enabled — straightforward.
- **Linux-headless nodes** (SPARK, B850): the Toolkit needs a credential provider; set up
  `docker-pass` FIRST — `mcp-toolkit-connect` is **not headless-safe** without it. If you
  can't confirm `docker-pass`, STOP and treat the node as BLOCKED-headless.

## Bootstrap + connect (the two Known-Road targets)

```bash
make -C pmoves mcp-toolkit-bootstrap    # pull + import profile pmoves_5090_web (idempotent)
make -C pmoves mcp-toolkit-connect       # connect claude-code; makes a pre-connect .bak backup
```

- OAuth-mediated Cloudflare servers (13 of 25) failing discovery during bootstrap is
  **expected + non-fatal** — they need a one-time interactive browser authorize per node
  (MCP_TOOLKIT.md §5), which headless bootstrap can't do.
- `mcp-toolkit-connect` writes the **gitignored repo-root `.mcp.json`** (+ `.pre-toolkit-connect.bak`),
  NOT the tracked `.claude/mcp.json`. If it would touch a tracked file, STOP and report.

## Verify

```bash
docker mcp profile ls        # expect pmoves_5090_web listed
docker mcp tools ls | head    # expect ~200 tools (GitHub / DockerHub / Context7 / Hostinger DNS+VPS / Cloudflare)
```

**Then restart the Claude Code session on that node** to actually consume the new
`MCP_DOCKER` gateway (the connect prints this reminder).

## After bootstrap

Flip the node's row in [`../operations/MCP_TOOLKIT.md`](../operations/MCP_TOOLKIT.md)
§ "Per-node status" from TODO → ✅. Per-node status as of 2026-07: **4090 ✅**, 5090 ✅;
Z890 / SPARK / B850 = TODO (SPARK/B850 need `docker-pass` first).

## Anti-patterns

- ❌ Driving the bootstrap onto a remote node via `tailscale ssh` with host-key
  acceptance — that's a raw-SSH security sidestep. Run it in a session ON the node.
- ❌ Forcing `mcp-toolkit-connect` on a Linux-headless node without `docker-pass`.
- ❌ Committing `.mcp.json` / `.pre-toolkit-connect.bak` — both are per-node + gitignored.
