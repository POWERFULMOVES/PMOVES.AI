# PMOVES.AI Deployment Runbooks

## Runbooks

| Runbook | Status | Priority | Location |
|---------|--------|----------|----------|
| Hostinger VPS Deployment | TODO | P1 | [hostinger-vps-deploy.md](hostinger-vps-deploy.md) |
| Pinokio PBNJ Installation | TODO | P1 | [pinokio-pbnj-install.md](pinokio-pbnj-install.md) |
| GrapheneOS PWA (Pixel 10 Pro) | TODO | P2 | [grapheneos-pwa.md](grapheneos-pwa.md) |
| DGX Spark Ollama Setup | TODO | P1 | [dgx-spark-ollama.md](dgx-spark-ollama.md) |

## Notes

- **Hostinger VPS**: Terraform configs exist at `pmoves/terraform/`, Python SDK at `docs/Hostingerapi/`, MCP server available
- **Pinokio PBNJ**: Launcher configs at `pbnj/pinokio/api/pmoves-services/` (submodule — may be empty)
- **GrapheneOS**: No code exists yet. Strategy: PWA on Hostinger + Tailscale for device access
- **DGX Spark**: Ollama should be pre-installed on GB10. Verify port 11434 accessible via Tailscale

## Dependencies

All runbooks assume:
- Tailscale is installed and authenticated on the target node
- SSH access is available (direct or via Tailscale)
- PMOVES.AI repo is cloned with submodules initialized

Added: 2026-04-17
