Title: v5.12 Stabilization: Monitoring + Channel Monitor metrics, Archon MCP wiring, UI defaults

Summary
- Added channel-monitor GET health + Prometheus metrics and instrumented counters.
- Monitoring stack now probes channel-monitor `/healthz` and scrapes metrics; Grafana provision/mount paths fixed; dashboard shows channel-monitor panels.
- Gated cAdvisor behind a linux profile with Make toggle.
- Archon headless ports published (8091 API, 8051 MCP, 8052 agents); Archon UI defaults to `archon-server:8091` API inside Docker.
- Agent Zero MCP seeding script + Make targets; Archon MCP smoke target.
- Added Archon API `/mcp/describe` shim to report MCP bridge status in JSON.

Key Files
- Channel Monitor: `pmoves/services/channel-monitor/channel_monitor/main.py`, `requirements.txt`, `README.md`
- Monitoring: `pmoves/monitoring/prometheus/prometheus.yml`, `pmoves/monitoring/docker-compose.monitoring.yml`, `pmoves/monitoring/grafana/*`
- Agents: `pmoves/docker-compose.yml`, `pmoves/docker-compose.agents.images.yml`, `pmoves/docker-compose.agents.integrations.yml`, `pmoves/AGENTS.md`
- MCP: `pmoves/tools/seed_agent_zero_mcp.py`, `pmoves/Makefile` (a0-mcp-seed, archon-mcp-smoke, archon-ui-smoke)
- Docs: `pmoves/docs/SMOKETESTS.md`, `pmoves/docs/services/monitoring/README.md`, `pmoves/docs/context/pmoves_v_5.12_tasks.md`

How to Verify
1) Channel Monitor
   - `docker compose -p pmoves up -d --build channel-monitor`
   - `curl http://localhost:8097/healthz` → 200
   - `curl http://localhost:8097/metrics` → Prometheus text
2) Monitoring
   - `MON_INCLUDE_CADVISOR=true make -C pmoves up-monitoring`
   - Prometheus targets UP; Grafana at http://localhost:3002 → Services Overview shows channel-monitor panels
3) Archon
   - `make -C pmoves up-agents-ui`
   - `curl http://localhost:8091/healthz` → 200
   - `make -C pmoves archon-ui-smoke` → API/UI 200s
   - `make -C pmoves archon-mcp-smoke` → prints HTTP code for :8051 (404 acceptable)
   - `curl http://localhost:8091/mcp/describe` → JSON with endpoint + probe statuses
4) MCP Seeding (Agent Zero)
   - Add `A0_MCP_SERVERS` in `pmoves/env.shared` (examples in `env.shared.example`)
   - `make -C pmoves a0-mcp-seed` → writes runtime mapping to `pmoves/data/agent-zero/runtime/mcp/servers.env`

Reviewer Notes
- Node exporter remains optional on Desktop/WSL; cAdvisor covers container metrics and is now gated.
- Archon MCP bridge routes vary by upstream; `/mcp/describe` ensures we can assert liveness without knowing the exact route shape.
- No RLS/profile changes were required; Archon retains single‑env Supabase REST alignment.

