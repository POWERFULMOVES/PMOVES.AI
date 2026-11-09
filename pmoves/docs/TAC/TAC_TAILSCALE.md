# TAC Tree: Tailscale / Headscale VPN

> Technology-Architecture-Context tree for the Tailscale mesh VPN layer — node registration, auth key management, exit node routing, DNS, and the Headscale self-hosted migration path.

## Current State (verified live 2026-07-10) — supersedes stale tables below

Tailnet `tailcad9b4.ts.net`. Authoritative runbook: [`../operations/TAILSCALE_EXIT_NODE_RUNBOOK.md`](../operations/TAILSCALE_EXIT_NODE_RUNBOOK.md).

- **Exit nodes: ALL 3 KVMs live + approved** — `pmoves-kvm2`, `pmoves-kvm4-1` (designated egress), `pmoves-kvm4-2` (pilot exit). Reference by MagicDNS hostname, never public IP (repo no-IPs policy). Each has IP forwarding (sysctl) + `--advertise-exit-node` and carries `tag:exit`, so all three **self-approve** via the `autoApprovers.exitNode` rule. Verified from `pmoves-4090` on 2026-07-10: all three appear in `tailscale exit-node list`, and a live egress `curl` confirmed the 4090's traffic exits through `pmoves-kvm4-1` (egress IP == the KVM's DC address, direct WireGuard path, not DERP). Clients can auto-select via `tailscale exit-node suggest`.
- **Tailscale SSH server enabled on all KVMs** (`RunSSH=true`) — ACL `ssh: autogroup:admin → * (root)` + a member self-SSH `check` rule. This is the out-of-band fleet management plane and **retires the kvm2 blocked-port-22 P0** (manage hbbs/hbbr over the tailnet).
- **MCP control (two complementary)**: npm `tailscale-mcp` (admin API — ACL/routes/devices, needs `TAILSCALE_API_KEY`, wiring pending) + **custom `pmoves-tailscale-mcp/`** (local CLI wrapper — exit-node/serve/funnel/ssh/metrics/netcheck/ping, no creds; PR #1821).
- **Serve/Funnel** sanctioned: `tailscale serve` (tailnet HTTPS — Jellyfin/Pinokio) + `tailscale funnel` (public 443/8443/10000). ACL `nodeAttrs: tag:exit → funnel`.
- **Observability**: tailscaled Prometheus metrics → node-exporter textfile collector → Grafana "Tailscale Network Health" (PR #1822).
- **Still open**: `TAILSCALE_API_KEY`/`TAILSCALE_TAILNET` wiring for the admin MCP (operator-direct manifest edit); `tag:exit` reusable authkey for auto-approving new exit nodes; Headscale migration (unchanged, planned).

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | Tailscale Mesh VPN |
| **Control Plane** | Tailscale Cloud (Headscale planned) |
| **Ports** | — (overlay network, no dedicated port) |
| **Health** | `tailscale status` / `tailscale ping <host>` |
| **Metrics** | Headscale: `GET :8096/metrics` (when deployed) |
| **Submodules** | [`PMOVES-Tailscale`](../../PMOVES-Tailscale/), [`PMOVES-Headscale`](../../PMOVES-Headscale/) |
| **Docker Profile** | Standalone (`docker-compose.tailscale.yml`) |
| **Tier** | api (cross-cutting infrastructure) |
| **Class** | Utility |
| **Evolution** | Base |

## Node Registration Matrix

| Node | Install Mode | Hostname | Status | Auth |
|------|-------------|----------|--------|------|
| Z890 | Bare-metal (OS install) | `pmoves-z890` | Connected | Reusable auth key |
| POWERFULMOVES (RTX 5090) | Docker (userspace) | `pmoves-powerfulmoves` | Connected | Reusable auth key (`tag:pmoves`) |
| Jetson Nano | Bare-metal | `pmoves-nano` | Offline | Re-auth needed |
| Laptop | Bare-metal | `pmoves-laptop` | Offline | Re-auth needed |
| Pixel 9 Pro XL | Mobile | `google-pixel-9-pro-xl` | Offline | Re-auth needed |
| BoTZ Server | Unknown | `pmoves-botz` | Offline | Re-auth needed |
| KVM4-1 | Bare-metal (provision script) | `pmoves-kvm4-1` | Connected | Reusable auth key |
| KVM4-2 | Bare-metal (provision script) | `pmoves-kvm4-2` | Connected | Reusable auth key |
| KVM2 | Bare-metal (provision script) | `pmoves-kvm2` | Connected | Reusable auth key + exit node |

## Docker Deployment Pattern

For Windows / Docker Desktop nodes (no TUN device):

```yaml
# pmoves/docker-compose.tailscale.yml
services:
  tailscale:
    image: tailscale/tailscale:latest
    container_name: pmoves-tailscale
    hostname: pmoves-powerfulmoves
    environment:
      - TS_AUTHKEY=${TAILSCALE_AUTHKEY}
      - TS_USERSPACE=true          # No TUN device needed
      - TS_HOSTNAME=pmoves-powerfulmoves
      - TS_STATE_DIR=/var/lib/tailscale
      - TS_ACCEPT_DNS=true
      - TS_EXTRA_ARGS=--accept-routes
    network_mode: host
    volumes:
      - tailscale-state:/var/lib/tailscale
```

**Key:** `TS_USERSPACE=true` enables userspace networking (no kernel TUN module required). Works on Windows Docker Desktop, WSL2, and environments without `/dev/net/tun`.

## Auth Key Management

| Key Type | TTL | Use Case |
|----------|-----|----------|
| Reusable (tagged: `tag:pmoves`) | No expiry | VPS provisioning, Docker containers |
| Single-use | 90 days | One-time node registration |
| Pre-authorized | Varies | Automated onboarding (no admin approval) |

**Key source:** https://login.tailscale.com/admin/settings/keys

**Storage:** `TAILSCALE_AUTHKEY` in `env.shared` (gitignored). Reference key file path in `env.shared.example` line 310.

## Exit Node Configuration (KVM2)

KVM2 serves as the Tailscale exit node for home network routing:

```bash
# Provisioned by deploy/provision/kvm2-exit-node.sh
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=1
tailscale up --advertise-exit-node --accept-routes
```

**Admin approval required:** https://login.tailscale.com/admin/machines → KVM2 → Approve exit node

## Route Advertisement

| Node | Advertised Routes | Purpose |
|------|-------------------|---------|
| KVM2 | Exit node (all traffic) | Public internet egress |
| KVM4-1 | (none, accepts routes) | API gateway |
| KVM4-2 | (none, accepts routes) | Data services |
| Z890 | (none, accepts routes) | Dev + GPU |

All nodes use `--accept-routes` to receive advertised routes from exit node.

## DNS

| Mechanism | Status | Description |
|-----------|--------|-------------|
| Magic DNS | Active | `<hostname>.tailnet-name` resolution between all nodes |
| Custom DNS | Planned | Map Tailscale hostnames to `pmoves.ai` subdomains |
| `headscale.pmoves.ai` | Configured | DNS-only A record pointing to KVM2 (for future Headscale) |

**VPS override pattern:** Services reference home GPU via Tailscale DNS:
```yaml
# docker-compose.vps.override.yml
HOME_OLLAMA_URL: http://pmoves-home:11434  # Resolved via Tailscale Magic DNS
```

## Headscale Migration Path

Current: **Tailscale Cloud** (managed control plane)
Target: **Headscale** (self-hosted on KVM2)

| Phase | Action | Status |
|-------|--------|--------|
| 1 | PMOVES-Headscale submodule on Hardened branch | Done |
| 2 | Headscale Docker deployment on KVM2 | Planned |
| 3 | Migrate node registrations from Tailscale Cloud | Planned |
| 4 | ACL policy migration | Planned |
| 5 | Decommission Tailscale Cloud | Future |

**Headscale submodule resources:**
- `PMOVES-Headscale/CLAUDE.md` — Development guide
- `PMOVES-Headscale/Dockerfile.derper` — DERP relay server
- `PMOVES-Headscale/cmd/headscale/` — Main server binary
- `PMOVES-Headscale/integration/` — Docker-based test infrastructure

## Submodule Health

| Submodule | Branch | Purpose | Health |
|-----------|--------|---------|--------|
| PMOVES-Tailscale | PMOVES.AI-Edition-Hardened | Env anchors template (`docker-compose.pmoves.yml`) | Tracked |
| PMOVES-Headscale | PMOVES.AI-Edition-Hardened | Self-hosted VPN control server | Tracked |

## Security Stance

| Finding | Severity | Status |
|---------|----------|--------|
| Tailscale Cloud dependency (vendor lock-in) | P2 | Headscale migration planned |
| Auth keys stored in env.shared (gitignored) | P3 | Acceptable — not committed |
| No MFA on Tailscale admin console | P3 | Tracked |
| DERP relay uses Tailscale's servers | P3 | Custom DERP via Headscale planned |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| All production nodes on tailnet | Partial | KVM nodes + 4090 + POWERFULMOVES connected; offline: nano, laptop, pixel |
| Exit nodes approved | GREEN | **All 3 KVMs** (kvm2, kvm4-1, kvm4-2) advertised + approved (2026-06-15) |
| Tailscale SSH (out-of-band mgmt) | GREEN | `RunSSH=true` on all KVMs; retires kvm2 blocked-port-22 |
| Local control MCP | GREEN | `pmoves-tailscale-mcp/` (CLI wrapper) — PR #1821; registration operator-opt-in |
| Admin-API MCP creds | Pending | `TAILSCALE_API_KEY`/`TAILSCALE_TAILNET` manifest wiring (operator-direct) |
| Metrics → observability | GREEN | tailscaled metrics → node-exporter textfile → Grafana (PR #1822) |
| Auto-onboarding (tag:exit authkey) | Pending | mint reusable tagged authkey → new exit nodes self-approve |
| Auth key rotation | Partial | Reusable keys don't expire; single-use keys have 90d TTL |
| Headscale readiness | Pending | Submodule tracked, deployment not started |
| Firewall rules per node | GREEN | VPS provisioned with ufw |

## Cross-Links

- **Master Topology:** `pmoves/docs/operations/TOPOLOGY.md`
- **Infrastructure TAC:** [`TAC_INFRASTRUCTURE.md`](./TAC_INFRASTRUCTURE.md)
- **VPS Provisioning:** `deploy/provision/hostinger-kvm-setup.sh` (Tailscale step)
- **Exit Node Script:** `deploy/provision/kvm2-exit-node.sh`
- **VPS Override:** `pmoves/docker-compose.vps.override.yml` (Tailscale env vars)
- **Env Template:** `pmoves/env.shared.example` (lines 308-315: Tailscale section)

## Open Items

- ~~Register POWERFULMOVES via `make -C pmoves tailscale-docker-up`~~ ✅ Done (2026-03-15)
- Reconnect offline nodes: pmoves-nano, pmoves-laptop (re-auth with new key)
- Deploy Headscale on KVM2
- Configure custom DERP relay via `Dockerfile.derper`
- ACL policy definition for node-level access control
- Automated auth key rotation

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TAILSCALE::2026-07-10 -->
