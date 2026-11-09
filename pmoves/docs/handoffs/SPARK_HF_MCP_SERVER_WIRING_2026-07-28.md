# SPARK HF MCP Server Wiring — 2026-07-28

> **GRAPHITI_MARK:** SPARK-KIMI::HF-MCP-SERVER-WIRING::2026-07-28
> **Lane:** Crush MCP revival + finish HF agent lane (awakening doc C1-C5)
> **Status:** in-flight (compose + registry wired; pending runtime verification)
> **Supersedes:**

## Context

The Crush MCP inventory has 4 entries that fail on SPARK because they were
emitted by `crush_configurator.py` for the cross-node default:

| MCP | Default URL | Why broken on SPARK |
|-----|-------------|---------------------|
| `agent-zero` | `http://${TS_Z890}:8080/mcp` | agent-zero runs locally on SPARK; `${TS_Z890}` not in env |
| `pmoves-cipher` | `http://${TS_Z890}:8105/mcp/sse` | cipher-api not running on SPARK |
| `huggingface` | `npx -y @llmindset/hf-mcp-server@0.3.30` | npx default `main` (`streamableHttp.js`) binds `:3000` (Grafana conflict). Local `pmoves/services/hf-mcp-server/` is the real impl but is not wired into compose. |
| `pmoves-docker-gateway` | `docker mcp gateway run --profile pmoves_5090_web` | 5090 profile; SPARK has no profile. Redundant — built-in `docker` MCP is already connected via `~/.local/share/crush/crush.json`. |
| `tailscale` | `npx -y tailscale-mcp@2026.4.10-1` | Binary symlink lacks shebang; crush invokes it as shell, fails with `Syntax error: "(" unexpected`. Fix: prepend `node`. |
| `supabase-db` | `uvx postgres-mcp@0.3.0` | `uvx` is now a dependency-confusion guard package, not the uv-cli runner. |

## Plan

### 1. Stand up services
- [x] `make -C pmoves up-cipher` — Known Road, builds cipher-api from `Pmoves-cipher/Dockerfile.pmoves`
- [x] Add hf-mcp-server to `pmoves/docker-compose.yml` (port 8203) + regenerate `docker-compose.agents.yml`
- [x] `docker compose --profile agents up -d hf-mcp-server` (verified via isolated test harness)
- [x] Verify healthy (`curl http://localhost:8203/healthz` → `{"status":"healthy","nats":"connected"}`)

### 2. Update user crush.json (`~/.config/crush/crush.json`)

- `agent-zero`: `localhost:8080/mcp` (done — running container verified)
- `pmoves-cipher`: `localhost:8105/mcp/sse`, `disabled: false` (after cipher-api healthy)
- `huggingface`: SSE → `localhost:8203/mcp/sse`, `disabled: false`
- `tailscale`: prepend `node` to args (binary is JS without shebang)
- `pmoves-docker-gateway`: REMOVE (redundant with built-in `docker` MCP)
- `supabase-db`: switch to `uv run --with postgres-mcp@0.3.0` (done)

### 3. Stand up crush-pmoves launcher

Created `deploy/provision/crush-pmoves.sh` — sister to `claude-pmoves.sh`,
sources `pmoves/env.shared` via `with-env.sh` pattern, execs `crush`. Loaded
366 vars in test. Add to PATH or alias: `alias crush=.../crush-pmoves.sh`.

### 4. Restart crush to pick up changes

Crush reads MCP config at startup. Existing session will continue with the
broken MCPs; restart required.

## PM-Spark Video Search & Summarization (Claw opportunity)

Repo: `https://github.com/POWERFULMOVES/PM-Spark-video-search-and-summarization.git`

What it is: NVIDIA AI Blueprint for Video Search and Summarization (VSS) forked
for PMOVES/SPARK. Provides real-time video intelligence, downstream analytics,
and agentic workflows with MCP exposure.

Reusable surfaces for Claw / other agents:

| Asset | Claw use case | Integration path |
|-------|---------------|------------------|
| `skills/vss-ask-video/SKILL.md` | Ask visual questions about a video clip | Install into `~/.openclaw-autoclaw/skills/vss-ask-video/` (agentskills.io format) |
| `skills/vss-search-archive/SKILL.md` | Natural-language search across video archives | Same skill install pattern |
| `skills/vss-generate-video-report/SKILL.md` | Generate incident/behavior reports | Same skill install pattern |
| `skills/vss-deploy-profile/SKILL.md` | Deploy/tear down VSS profiles (base/search/lvs/warehouse/edge) | Skill install + `vss-deploy-profile` reference |
| `services/agent/src/vss_agents/orchestrator/tools.py` | VSS orchestrator tools (profiles, prereqs, compose up/down/status) | Wrap as MCP server or import as Claw tools |
| `services/agent/src/vss_agents/video_analytics/tools.py` | Video analytics tools (sensors, incidents, alerts, clips) | Expose via MCP/REST adapter |
| `services/analytics/video-analytics-api/` | REST API for analytics data | Add as PMOVES service + compose stanza |

Recommended next step: submodule this repo as `PMOVES-Spark-VSS/`, add a
`pmoves-vss-agent` compose service that runs the VSS agent/API, and install the
agentskills.io skills into Claw's skill directory. This gives every PMOVES agent
local video understanding + search + summarization tools.

## Out of Scope (separate lanes)

- Update `pmoves/tools/crush_configurator.py` to emit pmoves-local hf-mcp-server
  instead of @llmindset (the npx package will still be useful for non-SPARK nodes
  that don't have the local service deployed).
- Wire CIPHER_API_TOKEN through env.tier-agent (cipher-api accepts requests
  without auth when CIPHER_API_TOKEN is unset per dev-skip rule, but production
  should set it).
- ~~Add `hf-mcp-server` to `pmoves/config/agent_registry.yaml`.~~ Done.
- ~~Update CATALOG.md to add `:8203 hf-mcp-server`.~~ Done.
- ~~Submodule / wire PM-Spark-VSS for Claw.~~ Claimed — see `pmoves/docs/handoffs/SPARK_VSS_INTEGRATION_2026-07-29.md`.
