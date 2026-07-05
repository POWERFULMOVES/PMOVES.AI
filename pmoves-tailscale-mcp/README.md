# pmoves-tailscale-mcp

Thin stdio MCP bridge over the **local `tailscale` CLI** — durable, node-local control of
the PMOVES tailnet for agents and skills. Mirrors the `pmoves-nats-mcp` / `pmoves-hirag-mcp`
pattern. No retrieval/control is rebuilt (Integration Rule); every tool is a typed CLI
passthrough with no shell.

## Why this exists (vs the npm `tailscale-mcp`)

The repo already declares the npm `tailscale-mcp@2026.4.10-1` (admin **API** — needs
`TAILSCALE_API_KEY` + `TAILSCALE_TAILNET`). This package is the **complement**, not a
replacement:

| pmoves-tailscale-mcp (this) | npm tailscale-mcp (admin API) |
|---|---|
| node-local control + diagnostics, **no creds** (uses the joined daemon) | tailnet-wide admin, needs API key |
| exit-node use, Serve, Funnel, Tailscale-SSH, metrics, netcheck, ping | approve routes, edit ACL, tag/delete devices, rotate keys |

Use this one to *operate* a node; use the API one to *govern* the tailnet.

## Tools

| Tool | Backs onto | Use |
|------|-----------|-----|
| `ts_status` | `tailscale status --json` | tailnet inventory, who's online, approved exit nodes, current exit node |
| `ts_exit_node` | `tailscale exit-node list/suggest` + `tailscale set --exit-node=` | list/suggest/set/clear this node's egress exit node |
| `ts_serve` | `tailscale serve` | expose a local port to the tailnet over auto-TLS (Jellyfin :8096, Pinokio apps) |
| `ts_funnel` | `tailscale funnel` | **public** ingress on 443/8443/10000 (no port-forward) |
| `ts_ssh` | `tailscale ssh <host> <cmd>` | run a command on a fleet node over the tailnet (bypasses blocked port-22) |
| `ts_metrics` | `tailscale metrics print` | tailscaled Prometheus metrics for observability |
| `ts_netcheck` | `tailscale netcheck --format=json` | UDP/NAT/DERP diagnostics |
| `ts_ping` | `tailscale ping` | direct-vs-DERP path check |

### Integration seams unlocked
- **Jellyfin / Pinokio** → `ts_serve` (tailnet) or `ts_funnel` (public) exposes a localhost
  port without nginx/Cloudflare/port-forward.
- **Observability** → `ts_metrics` returns the tailscaled Prometheus exposition (throughput
  by path, advertised/approved routes); feed it to the stack (see
  `pmoves/monitoring/prometheus/tailscale-textfile-collector.md`).
- **Fleet ops** → `ts_ssh` is the out-of-band management plane (works even where port-22 is
  firewalled — e.g. kvm2).

## Run

```bash
uv run --directory ./pmoves-tailscale-mcp python -m tailscale_mcp.server
```

## Test (no live tailnet needed — the CLI seam is mocked)

```bash
uv run --directory ./pmoves-tailscale-mcp --extra dev pytest tests/ -v
```

## Register — `.claude/mcp.json`

```json
"pmoves-tailscale": {
  "command": "uv",
  "args": ["--directory", "./pmoves-tailscale-mcp", "run", "python", "-m", "tailscale_mcp.server"]
}
```

## Env (all optional)

| Var | Purpose |
|-----|---------|
| `TAILSCALE_BIN` | explicit path to the `tailscale` binary (else PATH, else the Windows default) |
| `TAILSCALE_SSH_ALLOWED_HOSTS` | comma-list restricting `ts_ssh` targets (defense-in-depth) |

## Safety notes
- `ts_funnel set` exposes a port to the **public internet** — use deliberately.
- `ts_ssh` runs commands on remote nodes as authorized by the tailnet SSH ACL (and its
  check-mode re-auth). Set `TAILSCALE_SSH_ALLOWED_HOSTS` to constrain targets.
- All calls are shell-free (`create_subprocess_exec`); hostnames are pattern-validated.
