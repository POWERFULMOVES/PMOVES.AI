# TAC Tree: Tailscale / Headscale VPN

> Technology-Architecture-Context tree for the Tailscale mesh VPN layer — node registration, auth key management, exit node routing, DNS, and the Headscale self-hosted migration path.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | Tailscale Mesh VPN |
| **Control Plane** | Tailscale Cloud (Headscale planned) |
| **Ports** | — (overlay network, no dedicated port) |
| **Health** | `tailscale status` / `tailscale ping <host>` |
| **Metrics** | Headscale: `GET :8181/metrics` (when deployed) |
| **Submodules** | [`PMOVES-Tailscale`](../../PMOVES-Tailscale/), [`PMOVES-Headscale`](../../PMOVES-Headscale/) |
| **Docker Profile** | Standalone (`docker-compose.tailscale.yml`) |
| **Tier** | api (cross-cutting infrastructure) |
| **Class** | Utility |
| **Evolution** | Base |

## Node Registration Matrix

| Node | Install Mode | Hostname | Status | Auth |
|------|-------------|----------|--------|------|
| Z890 | Bare-metal (OS install) | `100.113.38.37` | Connected | Reusable auth key |
| POWERFULMOVES | Docker (userspace) | `pmoves-powerfulmoves` | Pending | `TS_AUTHKEY` via env.shared |
| 5090 PC | TBD | (pending) | Not started | — |
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
| All production nodes on tailnet | Partial | KVM nodes connected; POWERFULMOVES + 5090 pending |
| Exit node approved | GREEN | KVM2 approved as exit node |
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

- Register POWERFULMOVES via `make -C pmoves tailscale-up`
- Onboard 5090 PC (install mode TBD: Docker vs bare-metal)
- Deploy Headscale on KVM2
- Configure custom DERP relay via `Dockerfile.derper`
- ACL policy definition for node-level access control
- Automated auth key rotation

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TAILSCALE::2026-03-15 -->
