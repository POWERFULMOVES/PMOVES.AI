# PMOVES-Agent-Zero-SPARK: Sidecar Promotion Plan

> **Instance**: PMOVES-Agent-Zero-SPARK | Port 5080 | Image: agent0ai/agent-zero:latest
> **Date**: 2026-04-19 | **Status**: PLANNING (read-only analysis)
> **Note**: This document is read-only analysis. Implementation steps reference separate operational procedures (see deploy/sidecar/ for canonical templates).

> ⚠️ **CRITICAL CORRECTION (2026-04-23)**: This plan was written under incorrect assumptions that PMOVES-SPARK is a minimal/degraded sidecar. SPARK is a FULL PMOVES.AI node with: GH_PAT push capability, CHIT crypto hardened (fail-closed passphrase, versioned KDF PBKDF2+scrypt), NATS auth P0 resolved (0 unauthenticated refs), A2A server wired, 76 registered agents, ClaWZ active Discord agent, P7 stage manager, TeraFormer, IC, and pmoves-spark-runner online. The `standalone`/`degraded` decisions below apply to a GENERIC sidecar on an arbitrary device — NOT to SPARK specifically. See AGNOTE4482 for canonical SPARK state.

---

## Table of Contents

1. [Current State Assessment](#1-current-state-assessment)
2. [Mini CLI Command Reference](#2-mini-cli-command-reference)
3. [Target State Analysis (from docker-compose.agents.yml)](#3-target-state-analysis)
4. [Gap Analysis: Isolated to Sidecar](#4-gap-analysis-isolated--sidecar)
5. [Step-by-Step Promotion Plan](#5-step-by-step-promotion-plan)
6. [Corrected Docker Run Command](#6-corrected-docker-run-command)
7. [Risk Register](#7-risk-register)

---

## 1. Current State Assessment

### What Exists

| Component | Status | Notes |
|-----------|--------|-------|
| Container | Running | Port 5080, agent0ai/agent-zero:latest |
| Ollama LLM | Reachable | 172.17.0.1:11434, llama3.2:3b via host gateway |
| GPU Passthrough | MISSING | No --gpus all flag on container |
| agents.json | Empty | {} no agent profiles configured |
| secrets.env | Empty | 0 bytes |
| variables.env | Empty | 0 bytes |
| env.shared | Missing | Not bootstrapped |
| env.tier-agent | Missing | Not bootstrapped |
| NATS Connectivity | None | No bus network, no nats service reachable |
| TensorZero | None | No gateway reachable |
| Supabase | None | No DB/Kong reachable |
| code_execution_remote | Working | Direct host access via CLI connector |
| Project Mount | Mounted | host usr dir to /a0/usr |

### SPARK-Specific Correction

The assessment above describes a bare container state. The ACTUAL SPARK node (as of 2026-04-19 convergence wave) has:
- CHIT crypto: Hardened (fail-closed, versioned KDF)
- NATS: Auth P0 resolved, runner registered
- A2A: Server wired and exposed
- Agents: 76 registered, 13 contributors
- Push: Direct GH_PAT to origin/main
- ClaWZ: Active Discord agent (BoTZ archived)

The promotion steps below are valid for deploying Agent Zero as a sidecar on a NEW/EMPTY device. For SPARK specifically, only Phase 0 (GPU passthrough) and Phase 5 (container hardening) are needed — the rest is already operational.

### LLM Routing (Current)


- Custom provider ollama_spark pointing to http://172.17.0.1:11434
- Model: llama3.2:3b (Tier 2 fallback in PMOVES cascade)
- No TensorZero routing, no OpenAI-compatible gateway

---

## 2. Mini CLI Command Reference

**Module**: pmoves/tools/mini_cli.py (1856 lines)
**Invocation**: python3 -m pmoves.tools.mini_cli <command> [subcommand] [options]

### Top-Level Commands

| Command | Description | Key Options |
|---------|-------------|-------------|
| init | Run onboarding helper (status or generate) | --generate/-g, --manifest/-m |
| bootstrap | Bootstrap env files + stage provisioning bundle | --registry, --service/-s, --accept-defaults, --output/-o, --with-glancer |
| status | Summarize secret outputs + active profile + provisioning bundle | --manifest/-m, --provisioning-path |

### Sub-App: secrets (CHIT operations)

| Command | Description |
|---------|-------------|
| secrets encode | Encode env.shared to CHIT bundle (CGP format) |
| secrets decode | Decode CHIT bundle to env format |

### Sub-App: credentials (GitHub/Docker API)

| Command | Description |
|---------|-------------|
| credentials fetch | Fetch credentials from GitHub/Docker APIs |
| credentials list-github | List GitHub Secrets (metadata only) |
| credentials list-docker | List Docker registry credentials |
| credentials to-env-shared | Fetch and write directly to env.shared |

### Sub-App: profile (Hardware profiles)

| Command | Description |
|---------|-------------|
| profile list | List available hardware profiles |
| profile show <id> | Show profile details |
| profile detect | Suggest best matching profiles (--top N) |
| profile apply <id> | Set active profile |
| profile current | Display active profile |

### Sub-App: mcp (MCP toolkits)

| Command | Description |
|---------|-------------|
| mcp list | List configured MCP toolkits with availability |
| mcp health | Run MCP health checks |
| mcp setup <tool_id> | Show setup instructions for a toolkit |

### Sub-App: automations (n8n)

| Command | Description |
|---------|-------------|
| automations list | List n8n automations and channels |
| automations webhooks | Show webhook endpoints |
| automations channels <keyword> | Filter automations by channel |

### Sub-App: crush (Crush CLI)

| Command | Description |
|---------|-------------|
| crush setup | Generate Crush configuration for PMOVES |
| crush status | Show Crush configuration details |
| crush preview | Print generated Crush config JSON |

### Sub-App: agent-sdk (PMOVES Agent SDK)

| Command | Description | Key Options |
|---------|-------------|-------------|
| agent-sdk create | Create agent via interactive wizard | --role/-r, --model/-m, --agent-id, --connect/--no-connect, --config-only |
| agent-sdk run | Execute a task with existing agent | --agent-id, task prompt |
| agent-sdk list | List all PMOVES agents | |

**Agent SDK Roles**: researcher, code-reviewer, media-processor, knowledge-manager, general
**Default Model**: openai::qwen3:8b (TensorZero-routed)

### Sub-App: deps (Host dependencies)

| Command | Description |
|---------|-------------|
| deps check | Report whether host dependencies are available (make, jq, pytest) |
| deps install | Install missing deps (--manager, --yes, --use-container) |

### Sub-App: tailscale

| Command | Description |
|---------|-------------|
| tailscale authkey | Capture Tailnet auth key, persist to env.shared + secret file |
| tailscale join | Join tailnet via tailscale_brand_init.sh |
| tailscale rejoin | Force re-auth join |

### Sub-App: env (Tier layout management)

| Command | Description | Key Options |
|---------|-------------|-------------|
| env init | Initialize env from CHIT CGP + manifest v2 | --profile/-p (dev/prod/hybrid), --cgp, --manifest/-m, --force/-f |
| env validate | Validate tier env files | --tier/-t (all/data/api/llm/media/agent/worker), --connectivity/-c, --json |
| env doctor | Comprehensive environment diagnostics | --verbose/-v |
| env migrate-to-tiers | Migrate legacy .env.generated to tier layout | --backup/--no-backup |

### Bootstrap Internals

bootstrap delegates to pmoves.scripts.bootstrap_env which:
1. Loads pmoves/bootstrap/registry.json (declarative registry of required config values)
2. Prompts operator for missing secrets/endpoints (or --accept-defaults for CI)
3. Supports value generators: random_hex, random_urlsafe, passphrase
4. Writes appropriate .env tier overlays
5. Then stages provisioning bundle to CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/

---

## 3. Target State Analysis (from docker-compose.agents.yml)

### agent-zero Service Definition

```yaml
services:
  agent-zero:
    <<: &tier-agent-hardened          # env.shared + env.tier-agent, cap_drop ALL
    build:
      context: .
      dockerfile: ./services/agent-zero/Dockerfile
    restart: unless-stopped
    environment:
      - PORT=8080
      - AGENTZERO_JETSTREAM=true
      - AGENTZERO_JS_UNAVAILABLE_THRESHOLD=1
      - TENSORZERO_URL=http://tensorzero-gateway:3000
      - CHIT_REQUIRE_SIGNATURE=true
      - CHIT_DECRYPT_ANCHORS=true
      - CHIT_PASSPHRASE=${CHIT_PROD_PASSPHRASE:?set CHIT_PROD_PASSPHRASE in env.shared}
      - DOCKED_MODE=true
      - TOPOLOGY_MODE=docked
      - PARENT_SYSTEM=PMOVES.AI
      - PARENT_VERSION=1.0.0-hardened
      # LLM routing via TensorZero OpenAI-compatible endpoint
      - OPENAI_API_KEY=tensorzero-routed
      - A0_SET_chat_model_provider=openai
      - A0_SET_chat_model_name=tensorzero::function_name::agent_zero
      - A0_SET_chat_model_api_base=http://tensorzero-gateway:3000/openai/v1
      - A0_SET_util_model_provider=openai
      - A0_SET_util_model_name=tensorzero::function_name::agent_zero
      - A0_SET_util_model_api_base=http://tensorzero-gateway:3000/openai/v1
      - A0_SET_embed_model_provider=openai
      - A0_SET_embed_model_name=openai/tensorzero::embedding_model_name::gemma_embed_local
      - A0_SET_embed_model_api_base=http://tensorzero-gateway:3000/openai/v1
      - A0_SET_browser_model_provider=openai
      - A0_SET_browser_model_name=tensorzero::function_name::agent_zero
      - A0_SET_browser_model_api_base=http://tensorzero-gateway:3000/openai/v1
      # Host env leak guard (empty = unset)
      - SSL_CERT_FILE=
      - SSL_CERT_DIR=
      - REQUESTS_CA_BUNDLE=
      - CURL_CA_BUNDLE=
      - NODE_EXTRA_CA_CERTS=
      - HTTP_PROXY=
      - HTTPS_PROXY=
      - NO_PROXY=
    depends_on:
      nats: condition: service_healthy
      nats-init: condition: service_completed_successfully
      tensorzero-gateway: condition: service_healthy
    ports:
      - "127.0.0.1:8080:8080"    # API
      - "127.0.0.1:8081:80"       # UI
    volumes:
      - ./data/agent-zero/memory:/a0/memory
      - ./data/agent-zero/knowledge:/a0/knowledge
      - ./data/agent-zero/instruments:/a0/instruments
      - ./data/agent-zero/logs:/a0/logs
      - ./data/agent-zero/runtime:/a0/runtime
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:80/ || curl -fsS http://localhost:8080/healthz || exit 1"]
      interval: 30s; timeout: 10s; retries: 3; start_period: 30s
    networks:
      - pmoves_app        # 172.30.2.0/24 (internal)
      - pmoves_bus        # 172.30.3.0/24 (internal, NATS)
      - pmoves_external   # 172.30.6.0/24 (LLM APIs, internet)
    deploy:
      resources:
        limits: { cpus: 2.0, memory: 2G }
```

### x-env-tier-agent Anchor (from docker-compose.base.yml)

```yaml
x-env-tier-agent:
  env_file:
    - env.shared
    - env.tier-agent
  cap_drop: [ALL]
  cap_add: [NET_BIND_SERVICE, CHOWN, SETGID, SETUID]
  security_opt: [no-new-privileges:true]
```

### Network Topology

| Network | Subnet | Purpose | Agent-Zero Access |
|---------|--------|---------|-------------------|
| pmoves_app | 172.30.2.0/24 | Internal app services | Joined |
| pmoves_bus | 172.30.3.0/24 | NATS message bus | Joined |
| pmoves_external | 172.30.6.0/24 | LLM APIs, internet | Joined |
| pmoves_api | 172.30.1.0/24 | API tier | NOT joined |
| pmoves_data | 172.30.4.0/24 | Data tier (DBs) | NOT joined |
| pmoves_monitoring | 172.30.5.0/24 | Monitoring | NOT joined |

### Required Env Vars (from env.tier-agent.example)

```bash
NATS_URL=nats://nats:pmoves@nats:4222
SUPABASE_URL=http://supabase-kong:8000
SUPABASE_SERVICE_ROLE_KEY=<REQUIRED>
SUPA_REST_URL=http://supabase-kong:8000/rest/v1
HIRAG_URL=http://hi-rag-gateway-v2:8086
TENSORZERO_URL=http://tensorzero-gateway:3000
AGENT_ZERO_API_BASE=http://127.0.0.1:80
AGENTZERO_JETSTREAM=true
```

### Required Env Vars (from env.shared.example - CHIT section)

```bash
CHIT_CODEBOOK_PATH=datasets/structured_dataset.jsonl
CHIT_DECRYPT_ANCHORS=false          # Dev default
CHIT_REQUIRE_SIGNATURE=false        # Dev default
CHIT_PASSPHRASE=                    # Set from GitHub Secret
CHIT_PROD_REQUIRE_SIGNATURE=true    # Compose hard requirement
CHIT_PROD_DECRYPT_ANCHORS=true      # Compose hard requirement
CHIT_PROD_PASSPHRASE=               # REQUIRED: docker compose up fails if empty
```

### Sidecar Topology Vars

```bash
DOCKED_MODE=true
TOPOLOGY_MODE=docked               # docked | hybrid | standalone | auto
PARENT_SYSTEM=PMOVES.AI            # Set in compose environment block (not env.shared)
PARENT_VERSION=1.0.0-hardened
```

---

## 4. Gap Analysis: Isolated to Sidecar

### Critical Blockers (cannot proceed without compose stack)

| Gap | Impact | Workaround |
|-----|--------|------------|
| NATS bus unreachable | No JetStream pub/sub, no agent coordination | Set AGENTZERO_JETSTREAM=false, accept degraded mode |
| TensorZero unreachable | No LLM routing via gateway | Keep Ollama direct as primary, prepare TensorZero env vars for future |
| Supabase unreachable | No persistent storage, no auth | Accept memory-only mode, no Supabase queries |
| CHIT_PROD_PASSPHRASE | Compose :? syntax would fail startup | Not applicable in standalone docker run (no compose variable interpolation) |

### Achievable in Isolated Mode

| Item | Action | Complexity |
|------|--------|------------|
| GPU passthrough | Add --gpus all to docker run | Low |
| agents.json profiles | Create PMOVES-appropriate agent profiles | Medium |
| env.shared bootstrap | Create minimal env.shared with reachable endpoints | Medium |
| env.tier-agent bootstrap | Create minimal env.tier-agent | Medium |
| DOCKED_MODE/TOPOLOGY_MODE | Set via env vars in docker run | Low |
| PARENT_SYSTEM | Set via env var | Low |
| Skills configuration | Reference pmoves skills from agents.json | Low |
| CHIT_PASSPHRASE | Set a local dev value (not production CHIT_PROD) | Low |
| CHIT full enforcement | Enable CHIT_REQUIRE_SIGNATURE=true, CHIT_DECRYPT_ANCHORS=true | Low (SPARK already has hardened crypto) |

### LLM Routing Transition Path
```
Current:  Ollama direct (172.17.0.1:11434) -> llama3.2:3b
          |
Hybrid:   Ollama primary + TensorZero env vars pre-staged (unreachable, graceful fallback)
          |
Full:     TensorZero gateway -> agent_zero function -> cascade through model providers
```

---

## 5. Step-by-Step Promotion Plan

### Phase 0: Prerequisites (on host, outside container)

#### 0.1 Verify GPU availability on host

```bash
nvidia-smi
# Confirm driver version, GPU model, CUDA version
```

#### 0.2 Verify Ollama models on host

```bash
ollama list
# Confirm llama3.2:3b (or larger model) is available
```

#### 0.3 Stop existing container (will recreate with corrected args)

```bash
docker stop PMOVES-Agent-Zero-SPARK
docker rm PMOVES-Agent-Zero-SPARK
```

---

### Phase 1: Mini CLI Bootstrap

#### 1.1 Run bootstrap with accept-defaults (non-interactive)

From the **host** (where pmoves repo is cloned):

```bash
cd /home/powerfulmoves/agent-zero/PMOVES-Agent-Zero-SPARK
python3 -m pmoves.tools.mini_cli bootstrap \
  --accept-defaults \
  --service agent-zero \
  --without-glancer
```
> **SPARK Shortcut**: On PMOVES-SPARK, skip Phase 1 entirely — env.shared and env.tier-agent are already bootstrapped with hardened CHIT values. Only verify with `env validate --tier agent`.

**What this does:**

1. Loads pmoves/bootstrap/registry.json
2. Generates missing values using registry generators (random_hex, passphrase, etc.)
3. Writes pmoves/env.shared and pmoves/env.tier-agent with generated defaults
4. Stages provisioning bundle to CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/

#### 1.2 Validate generated env files

```bash
python3 -m pmoves.tools.mini_cli env validate --tier agent
python3 -m pmoves.tools.mini_cli env doctor --verbose
```

#### 1.3 Patch env.shared for local-dev sidecar mode

After bootstrap generates the files, manually adjust these values in pmoves/env.shared:

```bash
# CHIT: Use dev-mode (non-enforcing) for local dev
CHIT_DECRYPT_ANCHORS=false
CHIT_REQUIRE_SIGNATURE=false
CHIT_PASSPHRASE=<generated-by-bootstrap-or-set-manually>

# DO NOT set CHIT_PROD_* vars -- those are compose-only interpolation

# Topology
DOCKED_MODE=true
TOPOLOGY_MODE=standalone    # NOT docked -- compose stack is not running

# TensorZero: Pre-stage for future, but unreachable now
TENSORZERO_BASE_URL=http://tensorzero-gateway:3000
TENSORZERO_URL=http://tensorzero-gateway:3000
```

#### 1.4 Patch env.tier-agent for local-dev

```bash
# NATS: Unreachable but pre-staged
NATS_URL=nats://nats:pmoves@nats:4222

# Supabase: Unreachable but pre-staged
SUPABASE_URL=http://supabase-kong:8000
SUPABASE_SERVICE_ROLE_KEY=
SUPA_REST_URL=http://supabase-kong:8000/rest/v1

# TensorZero
TENSORZERO_URL=http://tensorzero-gateway:3000

# Agent Zero
AGENT_ZERO_API_BASE=http://127.0.0.1:80
AGENTZERO_JETSTREAM=false    # Disable -- NATS not reachable
```

---

### Phase 2: Agent Profiles (agents.json)

#### 2.1 Profile Strategy

The agents.json file defines agent profiles that appear in Agent Zero UI dropdown. For sidecar mode:

| Profile ID | Role | LLM Config | Purpose |
|------------|------|------------|---------|
| pmoves-sidecar | Default sidecar operator | Ollama llama3.2:3b (local) | General PMOVES tasks, deployment workflows |
| pmoves-tensorzero | TensorZero-routed | TensorZero gateway (when available) | Full model cascade, production parity |
| pmoves-researcher | Deep research | Ollama/TensorZero | SupaSerch + Hi-RAG integration |
| pmoves-code-reviewer | Security review | Ollama/TensorZero | Code audit, OWASP checks |

#### 2.2 agents.json Content

Write to .a0proj/agents.json:

```json
{
  "pmoves-sidecar": {
    "name": "PMOVES Sidecar",
    "description": "PMOVES.AI sidecar operator -- local Ollama LLM, deployment workflows",
    "prompt": "You are a PMOVES.AI sidecar agent operating in docked mode. PARENT_SYSTEM=PMOVES.AI. You handle deployment workflows, infrastructure tasks, and coordinate with the PMOVES ecosystem. Follow PMOVES behavioral rules and CHIT security protocols. Use code_execution_remote for host access.",
    "model_settings": {
      "provider": "ollama_spark",
      "model": "llama3.2:3b"
    },
    "tools": [
      "code_execution_tool", "code_execution_remote", "text_editor",
      "text_editor_remote", "browser_agent", "response", "call_subordinate",
      "memory_load", "memory_save", "memory_delete", "memory_forget",
      "scheduler", "skills_tool", "search_engine", "document_query", "notify_user"
    ],
    "custom_providers": {
      "ollama_spark": {
        "base_url": "http://host.docker.internal:11434",
        "provider": "ollama",
        "api_key": "ollama"
      }
    }
  },
  "pmoves-tensorzero": {
    "name": "PMOVES TensorZero",
    "description": "PMOVES.AI via TensorZero gateway -- full model cascade (requires compose stack)",
    "prompt": "You are a PMOVES.AI agent routed through TensorZero. PARENT_SYSTEM=PMOVES.AI. All LLM calls go through the TensorZero gateway for observability and model cascade. Follow PMOVES behavioral rules.",
    "model_settings": {
      "provider": "openai",
      "model": "tensorzero::function_name::agent_zero",
      "api_base": "http://tensorzero-gateway:3000/openai/v1",
      "api_key": "tensorzero-routed"
    }
  },
  "pmoves-researcher": {
    "name": "PMOVES Researcher",
    "description": "Deep research agent -- SupaSerch + Hi-RAG knowledge retrieval",
    "prompt": "You are a PMOVES.AI research agent specializing in deep research via SupaSerch and Hi-RAG. PARENT_SYSTEM=PMOVES.AI. Conduct thorough research, synthesize findings, and produce structured reports.",
    "model_settings": {
      "provider": "ollama_spark",
      "model": "llama3.2:3b"
    },
    "tools": [
      "code_execution_tool", "code_execution_remote", "text_editor",
      "text_editor_remote", "browser_agent", "response", "call_subordinate",
      "search_engine", "document_query", "memory_load", "memory_save", "skills_tool"
    ]
  },
  "pmoves-code-reviewer": {
    "name": "PMOVES Code Reviewer",
    "description": "Security-focused code review -- OWASP, hardening, vulnerability analysis",
    "prompt": "You are a PMOVES.AI security auditor. PARENT_SYSTEM=PMOVES.AI. Conduct thorough code reviews focusing on security vulnerabilities, OWASP top 10, container hardening, and PMOVES CHIT compliance.",
    "model_settings": {
      "provider": "ollama_spark",
      "model": "llama3.2:3b"
    },
    "tools": [
      "code_execution_tool", "code_execution_remote", "text_editor",
      "text_editor_remote", "response", "code_search", "context_answer",
      "symbol_graph", "search_callers", "search_tests",
      "memory_load", "memory_save", "skills_tool"
    ]
  }
}
```

#### 2.3 Profile Notes

- **pmoves-sidecar**: Default profile for isolated operation. Uses existing Ollama setup.
- **pmoves-tensorzero**: Prepared for when compose stack is available. Will fail gracefully if TensorZero unreachable.
- **pmoves-researcher / pmoves-code-reviewer**: Specialized roles matching Agent SDK roles (researcher, code-reviewer).
- All profiles include code_execution_remote for host access and PARENT_SYSTEM=PMOVES.AI in their prompt.
- custom_providers is only needed on profiles that use Ollama directly (TensorZero profiles use standard OpenAI-compat).
> **Note:** Per-profile `custom_providers` depends on Agent Zero version support. Verify your Agent Zero build supports this feature before relying on it.

---

### Phase 3: Required Env Vars for Sidecar Mode

#### 3.1 Canonical Template

**See `deploy/sidecar/sidecar-env.template`** — canonical sidecar env template (added PR #1299). This template contains the complete set of env vars for standalone sidecar mode. Do NOT maintain a separate copy.

#### 3.2 Key Decision Rationale

| Decision | Value | Why |
|----------|-------|-----|
| TOPOLOGY_MODE | `standalone` | Compose stack is not running — cannot use `docked` |
| AGENTZERO_JETSTREAM | `false` | NATS bus unreachable in standalone — prevents connection errors |
| CHIT_REQUIRE_SIGNATURE | `false` | Dev mode — CHIT enforcement requires compose-provided secrets |
| CHIT_DECRYPT_ANCHORS | `false` | Dev mode — same rationale as above |
| CHIT_PROD_* vars | Omitted | Compose-only `${:?}` interpolation — does not apply to `docker run` |

#### 3.3 Applying the Template

```bash
# Option A: Reference the template directly
--env-file deploy/sidecar/sidecar-env.template

# Option B: Copy and customize for this host
cp deploy/sidecar/sidecar-env.template /path/to/sidecar.env
# Edit /path/to/sidecar.env with host-specific values, then:-env-file /path/to/sidecar.env
```

---

### Phase 4: Skills Configuration

#### 4.1 PMOVES Skills (in repo -- manifest.yaml format)

Located at pmoves/skills/:

| Skill | Tier | Category | Agent Binding | Dependencies |
|-------|------|----------|---------------|-------------|
| remotion-render | agent | visualization | creator | a2ui-renderer, minio, presign |
| youtube-upload | agent | content | youtube_publisher | minio, presign |
| podcast-publish | agent | content | podcast_producer | minio, presign |
| threejs-render | agent | visualization | hyperdimensions | hyperdimensions, minio, presign |

**Status for local dev**: These skills depend on services that are NOT reachable in isolated mode. They should be listed in agents.json for discovery but will fail at runtime until the compose stack is available.

#### 4.2 Host Skills (SKILL.md format -- on host filesystem)

Located on host at ~/.agents/skills/:

| Skill | Purpose |
|-------|---------|
| gepeto | Gepeto integration |
| microsoft-foundry | Azure AI Foundry agent deployment, model management, RBAC |
| pinokio | Pinokio/PBNJ installation workflows |

**Status**: On the host filesystem, not inside the container. Accessible via code_execution_remote but not via Agent Zero native skills_tool.

#### 4.3 Skills Integration Approach

PMOVES skills use manifest.yaml (not SKILL.md), so they need either:

1. **Conversion**: Create SKILL.md wrappers for each manifest.yaml skill
2. **Direct reference**: Mount the skills directory and configure skills_tool path
3. **Agent SDK**: Use pmoves agent-sdk create which handles MCP + skill wiring internally

**Recommendation for Phase 1**: Do not try to load PMOVES manifest.yaml skills into Agent Zero skills_tool. Instead:
- Keep skills_tool available in tool lists for Agent Zero native skills
- Use code_execution_remote to invoke PMOVES skills via their service endpoints when available
- Document the skill mapping in each agent profile prompt

#### 4.4 Skills for Deployment Workflow

| Priority | Skill | How to Use |
|----------|-------|------------|
| P0 | pinokio (host) | Via code_execution_remote -- PBNJ install on VPS |
| P0 | microsoft-foundry (host) | Via code_execution_remote -- model deployment |
| P1 | gepeto (host) | Via code_execution_remote -- Gepeto integration |
| P2 | youtube-upload (pmoves) | Via HTTP to gateway-agent:8111 when available |
| P2 | remotion-render (pmoves) | Via HTTP to a2ui-renderer:8105 when available |

---

### Phase 5: Corrected Docker Run Command

#### 5.1 Full Command

```bash
docker run -d \
  --name PMOVES-Agent-Zero-SPARK \
  --gpus all \
  --restart unless-stopped \
  --cap-drop ALL \
  --cap-add NET_BIND_SERVICE \
  --cap-add CHOWN \
  --cap-add SETGID \
  --cap-add SETUID \
  --security-opt no-new-privileges:true \
  -p 5080:8080 \
  -p 5081:80 \
  -v /home/powerfulmoves/agent-zero/PMOVES-Agent-Zero-SPARK/usr:/a0/usr \
  -v /home/powerfulmoves/agent-zero/PMOVES-Agent-Zero-SPARK/data/memory:/a0/memory \
  -v /home/powerfulmoves/agent-zero/PMOVES-Agent-Zero-SPARK/data/knowledge:/a0/knowledge \
  -v /home/powerfulmoves/agent-zero/PMOVES-Agent-Zero-SPARK/data/instruments:/a0/instruments \
  -v /home/powerfulmoves/agent-zero/PMOVES-Agent-Zero-SPARK/data/logs:/a0/logs \
  -v /home/powerfulmoves/agent-zero/PMOVES-Agent-Zero-SPARK/data/runtime:/a0/runtime \
  --env-file /home/powerfulmoves/agent-zero/PMOVES-Agent-Zero-SPARK/sidecar.env \
  --add-host host.docker.internal:host-gateway \
  agent0ai/agent-zero:latest
```

#### 5.2 Changes from Current Configuration

| Change | Current | New | Reason |
|--------|---------|-----|--------|
| --gpus all | Missing | Added | GPU passthrough for Ollama/local inference |
| --cap-drop ALL | Missing | Added | Security hardening (matches compose x-env-tier-agent) |
| --cap-add NET_BIND_SERVICE,CHOWN,SETGID,SETUID | Missing | Added | Minimum capabilities for Agent Zero operation |
| --security-opt no-new-privileges:true | Missing | Added | Prevents privilege escalation |
| Port 5081 | Missing | Added | UI port (80 to 5081, matches compose 8081:80) |
| Memory/Knowledge/Instruments/Logs/Runtime volumes | Missing | Added | Persistent data dirs (matches compose volumes) |
| --env-file sidecar.env | Missing | Added | Sidecar env vars (see Phase 3) |
| --add-host host.docker.internal:host-gateway | Missing | Added | Reliable host gateway for Ollama (172.17.0.1) |

#### 5.3 sidecar.env File Content

See `deploy/sidecar/sidecar-env.template` — canonical sidecar env template (added PR #1299). Do NOT maintain a separate copy. The template contains the complete env configuration for standalone sidecar mode including topology, CHIT dev settings, JetStream disable, pre-staged endpoints, and host env leak guard.
> **SPARK Note**: The template above is for GENERIC sidecar devices. SPARK should use its existing hardened env.shared with CHIT_REQUIRE_SIGNATURE=true and CHIT_DECRYPT_ANCHORS=true (not the dev-mode false values in the template).

#### 5.4 Data Directory Setup (on host, before docker run)

#### 5.4 Data Directory Setup (on host, before docker run)

```bash
mkdir -p /home/powerfulmoves/agent-zero/PMOVES-Agent-Zero-SPARK/data/{memory,knowledge,instruments,logs,runtime}
```

---

### Phase 6: Verification Checklist

#### 6.1 Post-Startup Checks

```bash
# Container running with GPU
docker exec PMOVES-Agent-Zero-SPARK nvidia-smi

# Ollama reachable from container
docker exec PMOVES-Agent-Zero-SPARK curl -s http://172.17.0.1:11434/api/tags

# Sidecar env vars set
docker exec PMOVES-Agent-Zero-SPARK env | grep -E "PARENT_SYSTEM|DOCKED_MODE|TOPOLOGY_MODE|CHIT_"

# JetStream disabled (no NATS errors)
docker logs PMOVES-Agent-Zero-SPARK 2>&1 | grep -i jetstream | head -5

# Health check
curl -s http://localhost:5080/ | head -20
curl -s http://localhost:5081/ | head -20

# Agent profiles loaded
curl -s http://localhost:5080/api/agents | python3 -m json.tool
```

#### 6.2 Functional Checks

- [ ] Switch to pmoves-sidecar profile in UI -- verify LLM responds via Ollama
- [ ] Switch to pmoves-tensorzero profile -- verify graceful failure (no crash)
- [ ] Use code_execution_remote -- verify host access works
- [ ] Use browser_agent -- verify browser launches
- [ ] Check memory persistence -- create a memory, restart container, verify recall

---

## 7. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| --gpus all fails (no NVIDIA runtime) | Medium | High | Verify nvidia-container-toolkit installed; fall back to CPU-only Ollama via host gateway |
| Bootstrap generates incompatible values | Low | Medium | Review generated env.shared/tier-agent before use; env validate --tier agent |
| agents.json format mismatch | Low | Medium | Test with a single profile first; Agent Zero silently ignores malformed entries |
| JetStream disabled breaks A0 features | Low | Low | Most A0 features work without JetStream; only pub/sub coordination affected |
| CHIT_PASSPHRASE mismatch with future compose | Medium | Low | When transitioning to compose, regenerate CHIT_PROD_PASSPHRASE and update both env.shared and GitHub Secrets |
| Volume mounts conflict with existing data | Low | Medium | Check existing /a0/memory etc. before adding new volume mounts; backup first |
| Port 5081 conflicts with another service | Low | Low | Change host port mapping if needed (e.g., 5082:80) |

---

## Appendix A: Transition to Full Compose Mode

When the full PMOVES compose stack is brought up on this host:
### SPARK-Specific Transition

SPARK does NOT need the full transition path — it already operates as a full PMOVES.AI node. When the compose stack is brought up on SPARK's host:
1. Change TOPOLOGY_MODE=docked in existing env.shared (already has CHIT_PROD_PASSPHRASE)
2. Set AGENTZERO_JETSTREAM=true (NATS auth already configured)
3. Start via compose — no env regeneration needed

The generic transition steps below apply to OTHER devices being promoted from generic sidecar to docked mode.

1. Stop standalone container: docker stop PMOVES-Agent-Zero-SPARK

1. Stop standalone container: docker stop PMOVES-Agent-Zero-SPARK
2. Run python3 -m pmoves.tools.mini_cli env init --profile prod to apply CHIT production secrets
3. Set CHIT_PROD_PASSPHRASE in env.shared (required by compose ${:?})
4. Change TOPOLOGY_MODE=docked in env.shared
5. Start via compose: docker compose -f docker-compose.base.yml -f docker-compose.agents.yml up -d agent-zero
6. The compose definition will override PORT, LLM routing, and network config
7. Remove standalone sidecar.env file (compose env_files take over)

## Appendix B: Files to Create/Modify Summary

| File | Action | Location |
|------|--------|----------|
| sidecar.env | Create | Host: PMOVES-Agent-Zero-SPARK/sidecar.env |
| agents.json | Modify | Container: /a0/usr/projects/pmoves/.a0proj/agents.json |
| pmoves/env.shared | Create (via bootstrap) | Container: /a0/usr/projects/pmoves/pmoves/env.shared |
| pmoves/env.tier-agent | Create (via bootstrap) | Container: /a0/usr/projects/pmoves/pmoves/env.tier-agent |
| data/{memory,knowledge,instruments,logs,runtime}/ | Create (dirs) | Host: PMOVES-Agent-Zero-SPARK/data/ |

## Appendix C: Quick Reference -- Mini CLI All Commands

```
python3 -m pmoves.tools.mini_cli init [--generate] [--manifest PATH]
python3 -m pmoves.tools.mini_cli bootstrap [--accept-defaults] [--service ID] [--output DIR] [--with-glancer]
python3 -m pmoves.tools.mini_cli status [--manifest PATH] [--provisioning-path DIR]
python3 -m pmoves.tools.mini_cli secrets encode
python3 -m pmoves.tools.mini_cli secrets decode
python3 -m pmoves.tools.mini_cli credentials fetch
python3 -m pmoves.tools.mini_cli credentials list-github
python3 -m pmoves.tools.mini_cli credentials list-docker
python3 -m pmoves.tools.mini_cli credentials to-env-shared
python3 -m pmoves.tools.mini_cli profile list
python3 -m pmoves.tools.mini_cli profile show <ID>
python3 -m pmoves.tools.mini_cli profile detect [--top N]
python3 -m pmoves.tools.mini_cli profile apply <ID>
python3 -m pmoves.tools.mini_cli profile current
python3 -m pmoves.tools.mini_cli mcp list
python3 -m pmoves.tools.mini_cli mcp health
python3 -m pmoves.tools.mini_cli mcp setup <TOOL_ID>
python3 -m pmoves.tools.mini_cli automations list
python3 -m pmoves.tools.mini_cli automations webhooks
python3 -m pmoves.tools.mini_cli automations channels <KEYWORD>
python3 -m pmoves.tools.mini_cli crush setup
python3 -m pmoves.tools.mini_cli crush status
python3 -m pmoves.tools.mini_cli crush preview
python3 -m pmoves.tools.mini_cli agent-sdk create [--role R] [--model M] [--agent-id ID] [--no-connect] [--config-only]
python3 -m pmoves.tools.mini_cli agent-sdk run --agent-id <ID> "<task>"
python3 -m pmoves.tools.mini_cli agent-sdk list
python3 -m pmoves.tools.mini_cli deps check
python3 -m pmoves.tools.mini_cli deps install [--manager M] [--yes] [--use-container]
python3 -m pmoves.tools.mini_cli tailscale authkey [--env-file PATH] [--secret-file PATH]
python3 -m pmoves.tools.mini_cli tailscale join [--env-file PATH]
python3 -m pmoves.tools.mini_cli tailscale rejoin [--env-file PATH]
python3 -m pmoves.tools.mini_cli env init [--profile P] [--cgp PATH] [--manifest PATH] [--force]
python3 -m pmoves.tools.mini_cli env validate [--tier T] [--connectivity] [--json]
python3 -m pmoves.tools.mini_cli env doctor [--verbose]
python3 -m pmoves.tools.mini_cli env migrate-to-tiers [--backup/--no-backup]
```
