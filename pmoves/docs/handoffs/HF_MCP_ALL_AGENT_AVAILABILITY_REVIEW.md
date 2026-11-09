# HF MCP — All-Agent Availability Review

**Directive #2 (founder, 2026-07-22):** "hf-mcp → REVIEW, do NOT delete. HF MCP must be available to ALL agents. Review the wiring, ensure all agents can reach HF MCP."

**Verdict:** The in-repo `hf-mcp-server` is **NOT superseded and must not be deleted** — it is a *distinct capability* from the npm/remote HF MCP. But it is **orphaned** (undeployed + unregistered), so containerized agents currently cannot reach the fleet-provisioning HF tools. Discovery-only HF MCP *is* broadly available. Fix = deploy + register (below), not delete.

## Two distinct HF MCP capabilities (not duplicates)

| Capability | Provider | Tools | Reachable by |
|---|---|---|---|
| **Discovery / search** | `@llmindset/hf-mcp-server` (npm, = evalstate/hf-mcp-server); remote `https://huggingface.co/mcp`; claude.ai connector | model/dataset/paper/doc search, Hub repo details, Space exec | ✅ Claude Code CLI (`.claude/mcp.json`), ✅ node MCP clients (`config/mcp/pmoves-ai-profile.yaml` remote entry), ✅ claude.ai (`mcp__claude_ai_Hugging_Face__*`) |
| **Fleet provisioning** | in-repo `pmoves/services/hf-mcp-server` (1073 lines, FastAPI + `/sse`) | `hf.model.search/info/download/convert_gguf`, vLLM compat, NATS `hf.model.*` events, download to **shared model volume** | ❌ **nobody** — undeployed + unregistered |

The provisioning service is the PMOVES-unique value (downloads to the shared fleet cache, GGUF-converts for Ollama, checks vLLM compat, emits NATS events) — exactly what the fleet-adaptive HF model work needs. The npm/remote server cannot do any of that.

## The gap (why "all agents" fails today)

1. **Undeployed.** `pmoves/services/hf-mcp-server` is in **no** `docker-compose*.yml` overlay. (The `:8096` matches in compose are all **Jellyfin**, whose default port is 8096.)
2. **Port collision.** The service defaults to `PORT=8096` and the `huggingface-integration.tac.yaml` audit expects it healthy at `:8096` — but **8096 is Jellyfin's**. It must serve on a different port.
3. **Unregistered.** `config/agent_registry.yaml` → `mcp_servers:` lists `cipher, e2b, hirag, nats, tailscale` (all `transport: sse`, `endpoint: http://pmoves-<x>-mcp:8080/sse`, `status: planned`). There is **no `pmoves_hf_mcp` entry**, so agents can't discover it by capability/namespace.
4. **Agents not wired.** `hf_agent` (model patrol → `hf.model.discovered.v1`) and `hf_research_agent` (→ `hf.model.evaluated.v1`) exist but call the Hub directly, not the provisioning MCP.

## Apply-ready wiring plan (do NOT delete — deploy + register)

### 1. Serve on the internal SSE convention, not 8096
The service already exposes `/sse` (main.py:984). Run it container-internal on `:8080` (matching every other registry MCP server) so the endpoint is `http://pmoves-hf-mcp:8080/sse`. Any host-published port must avoid **8096 (Jellyfin)** — pick the next free per `.claude/CATALOG.md`.

### 2. Register in `config/agent_registry.yaml` → `mcp_servers:` (mirror the cipher/hirag shape)
```yaml
  pmoves_hf_mcp:
    name: "pmoves-hf-mcp"
    # in-repo service (pmoves/services/hf-mcp-server), not a submodule
    class: utility
    transport: "sse"
    endpoint: "${PMOVES_HF_MCP_ENDPOINT:-http://pmoves-hf-mcp:8080/sse}"
    action_namespace: "mcp.v1.hf"
    capabilities: ["model-search", "model-info", "model-download", "gguf-convert", "vllm-compat"]
    rooms: ["4090-field.room.control", "z890-infra.room.fabric"]
    status: "planned"
```
> Confirm the registry's pydantic schema accepts an entry without `submodule:` (every existing entry has one because they're submodule-backed). If `submodule` is required, add an in-repo marker field or set it to the service path — this is the one schema decision to make before committing.

### 3. Deploy in compose (source `docker-compose.yml`, then `make -C pmoves compose-split`)
Add an `pmoves-hf-mcp` service: build `services/hf-mcp-server/Dockerfile`, `PORT=8080`, mount the shared model-cache volume, `HF_TOKEN` from the secrets pipeline, `NATS_URL`, healthcheck `GET /healthz`, `profile: workers` (matches `hf_agent`'s `compose_profile: workers`). Protected compose file → Known Road `compose:add-service`.

### 4. Secrets
`HF_TOKEN` / `HUGGINGFACE_HUB_TOKEN` via the machine-emitted secrets pipeline (never hand-edit the manifest) — the discovery surfaces already reference `${HF_TOKEN}`.

### 5. Correct the TAC tree
`configs/tac_trees/huggingface-integration.tac.yaml` health check `http://localhost:8096/healthz` → the chosen port (and note the SSE endpoint). The `:8096` there is the collision bug.

## Scope note
Discovery HF MCP already reaches CLI + node clients + claude.ai, so interactive agents are covered today. This plan closes the **provisioning** gap for the containerized fleet. Steps 3–4 touch protected compose + secrets (operator Known Roads); step 2 is a low-risk registry edit pending the one schema confirmation above.
