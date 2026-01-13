# Tailnet + Discord Deployment Runbook

_Last updated: 2025-10-07_

This runbook walks through launching PMOVES services on a Tailscale-connected host so they can back Discord automations from both a local workstation and a self-hosted VPS. It also records how to pre-seed RustDesk so you can remote in for maintenance.

## 1. Architecture Overview

| Component | Purpose | Notes |
| --- | --- | --- |
| **Tailnet** | Private mesh that links your workstation, VPS, and optional edge nodes. | Use tagged ACLs so PMOVES services can be discovered by name/IP while restricting admin surfaces to trusted devices. |
| **PMOVES services** | Core workers (Agent Zero, Archon, hi-rag, publisher) that expose HTTP + MCP endpoints. | Docker Compose provides service discovery; Tailscale lets hosts reach each other when split across machines.【F:pmoves/AGENTS.md†L1-L52】|
| **Discord publisher / bots** | Webhook and bot automations triggered by PMOVES events. | Requires populated `.env` variables and healthy outbound HTTPS connectivity.【F:pmoves/Makefile†L438-L480】【F:pmoves/docs/N8N_SETUP.md†L1-L63】|
| **RustDesk** | Optional remote desktop bridge for headless or remote workers. | Bundle `server.conf` during provisioning so the machine auto-pairs with your relay.【F:CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/README.md†L49-L104】|

### Network Layout

1. Workstation and VPS join the same Tailscale tailnet using device auth keys (ephemeral for personal machines, tagged for servers).
2. Docker Compose runs on each host; services that must be reachable from Discord automations (publisher-discord, n8n, hi-rag) bind to `0.0.0.0` and are firewalled to the tailnet subnets.
3. Discord integrations call out to the public internet; inbound webhook verification stays behind Tailscale.

## 2. Prepare Tailscale Access

1. **Create auth keys:** In the Tailscale admin console, generate two reusable auth keys: one with the `tag:pmoves-vps` tag and server ACLs, another with device approval for your workstation.
2. **Provision hosts:**
   - **Workstation:** Run the Cataclysm post-install scripts (`linux/scripts/pop-postinstall.sh` or `windows/win-postinstall.ps1`). They install Docker, Tailscale, and RustDesk, then join the tailnet automatically if `tailscale_authkey.txt` is present on the provisioning media.【F:CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/README.md†L54-L104】
   - **VPS:** SSH in with the provider credentials and execute `curl -fsSL https://tailscale.com/install.sh | sh` followed by `sudo tailscale up --authkey=<server-key> --hostname=pmoves-vps --advertise-tags=tag:pmoves-vps`.
3. **Confirm routing:** From either host run `tailscale status` to ensure both nodes are connected. Use `tailscale ping <other-host>` to verify direct connectivity.
4. **Lock down admin paths:** Update your ACLs so only trusted devices (tagged or specific users) can reach PMOVES admin endpoints such as `/hirag/admin/*`, which already expect Tailscale gating.【F:pmoves/services/hi-rag-gateway/gateway.py†L291-L301】

## 3. Bootstrap PMOVES Services

1. **Clone the repository and copy `.env.example` to `.env`.** Populate the following variables to enable Discord:
   - `DISCORD_WEBHOOK_URL`
   - `DISCORD_WEBHOOK_USERNAME` (optional)
   - `PMOVES_CONTRACTS_DIR` (defaults usually ok)
   - Any Supabase credentials referenced in `docs/N8N_SETUP.md` for the publish workflow.
2. **Launch core services:** On each host run `make up PROFILE=data,workers` (or the subset you need). See `docs/MAKE_TARGETS.md` for all profile combinations.【F:pmoves/docs/MAKE_TARGETS.md†L1-L118】
3. **Expose MCP agents over Tailscale:** Ensure the `AGENT_ZERO_HOST` or similar bindings in `.env` use the Tailscale IP/hostname so Discord-triggered automations can resolve them when originating from another node.
4. **Publisher health check:** Use the built-in Make targets to validate Discord connectivity:
   ```bash
   make health-publisher-discord
   make discord-ping MSG="Tailnet wiring check"
   ```
   Both commands should return `OK` and a message in your Discord channel. Run `make discord-smoke` if you want a full health + publish exercise.【F:pmoves/Makefile†L154-L163】【F:pmoves/Makefile†L435-L460】
5. **Run local Discord bot flows:** If you rely on n8n, import `pmoves/n8n/flows/echo_publisher.json`, update the Discord webhook credential, and trigger the workflow to confirm the embed formatting.【F:pmoves/docs/N8N_SETUP.md†L1-L63】

## 4. Hybrid Local + VPS Operation

1. **Decide service placement:**
   - Keep latency-sensitive Discord publishing and Supabase listeners on the VPS so they are always-on.
   - Run heavy creative agents (ComfyUI, hi-rag GPU) on the workstation and advertise them over Tailscale.
2. **Share event bus:** Point both stacks at the same NATS instance. Either expose the VPS NATS port over Tailscale or run a lightweight `nats-server` locally and bridge via JetStream mirroring if you need offline capability.
3. **Synchronize env files:** Store canonical secrets in a password manager. When rotating the Discord webhook or Supabase keys, update `.env` on both nodes and restart the affected services (`docker compose restart publisher-discord`).
4. **Observability:** Expose Prometheus scrapes over Tailscale (e.g., `http://pmoves-vps:8094/metrics`) and use `make telemetry-scan` targets to confirm Discord metrics ingest.【F:pmoves/docs/TELEMETRY_ROI.md†L15-L55】

## 5. RustDesk Remote Access

1. **Bundle configuration:** Place your `server.conf` (relay/ID settings) in `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/windows/rustdesk/` before imaging. The provisioning scripts copy it into the right AppData directory so RustDesk knows how to contact your relay.【F:CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/windows/rustdesk/README.md†L1-L7】
2. **Linux hosts:** After provisioning, verify `/usr/lib/rustdesk/rustdesk` (or the systemd service) is active. If you used the bundle, `pop-postinstall.sh` already installed the package and repository.【F:CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/linux/scripts/pop-postinstall.sh†L55-L92】
3. **Sign in & trust:** Launch RustDesk, enter your relay credentials, and note the device ID. Because the host is also on Tailscale, you can fall back to the tailnet IP if the relay is unreachable.
4. **Security tips:**
   - Use one-time passwords or pre-shared keys when sharing access.
   - Maintain separate RustDesk accounts for automation vs. admin usage.
   - Document remote sessions in your ops log for auditability.

## 6. Validation Checklist

| Step | Workstation | VPS |
| --- | --- | --- |
| `tailscale status` shows both nodes | ☐ | ☐ |
| `make health-publisher-discord` reports OK | ☐ | ☐ |
| Discord channel receives echo publisher embed | ☐ | ☐ |
| n8n workflow posts to Discord | ☐ | ☐ |
| RustDesk device reachable | ☐ | ☐ |
| Metrics accessible via Tailscale (`/metrics`) | ☐ | ☐ |

Record evidence (screenshots, log excerpts) in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` once the checklist is complete.【F:pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md†L6-L189】

## 7. Next Steps

- Expand Tailscale ACLs to include Jetson or creative nodes as you add them.
- Integrate Supabase triggers per `docs/NEXT_STEPS.md` so published events flow automatically into Discord and Jellyfin.【F:pmoves/docs/NEXT_STEPS.md†L8-L193】
- Schedule periodic tests using `make smoke-discord` (once implemented) to catch webhook failures early.

