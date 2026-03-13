# PMOVES-Tailscale — Status
_Last updated: 2026-03-12_

## Purpose
- Tailnet connectivity and secure access workflows for PMOVES operators.
- Self-hosted Headscale control plane for full sovereignty.
- Cloudflare integration for public-facing service endpoints.

## Implemented Items
- PMOVES-Tailscale submodule initialized (fork of tailscale/tailscale + deploy scripts)
- Universal deploy script: `deploy.sh` (Linux/macOS/WSL) + `deploy.ps1` (Windows)
- Role-based profiles: workstation, vps, proxmox-host, edge
- Platform detection library (OS, arch, GPU, init system)
- Post-deploy validation script
- Headscale Docker Compose + config template + ACL policy
- Docker Tailscale patterns: subnet router, sidecar
- Cloudflare tunnel config template + automated setup script
- Makefile targets: `tailscale-deploy`, `headscale-up/down`, `headscale-create-user/key`
- env.shared.example updated with Headscale vars
- Full documentation: architecture, setup guides, troubleshooting

## Current Tailnet Status
| Node | Tailscale IP | Status |
|------|-------------|--------|
| pmoves-z890 | 100.113.38.37 | Online |
| powerfulmoves (5090) | — | Offline (needs deploy) |
| pmoves-botz | — | Offline |
| pmoves-nano | — | Offline |
| pmoves-pro | — | Offline |

## Remaining Items
- [ ] Activate Hostinger VPS and deploy Headscale
- [ ] Configure Cloudflare tunnel for headscale.pmoves.ai
- [ ] Onboard powerfulmoves (5090 PC) using deploy script
- [ ] Migrate from Tailscale SaaS to self-hosted Headscale
- [ ] Set up Proxmox host-level Tailscale
- [ ] Enable Tailnet Lock across all nodes

## References
- [PMOVES-Tailscale Submodule](../../PMOVES-Tailscale/PMOVES-DEPLOY.md)
- [Architecture Docs](../../PMOVES-Tailscale/pmoves-docs/ARCHITECTURE.md)
- [Network Fabric Blueprint](../ARC/network_fabric.md)
