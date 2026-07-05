# PMOVES.AI Open Questions — Repo Research Report

Researched 2026-05-13 against repo at `/a0/usr/projects/pmoves_ai` (commit `edae14003`, branch `main`).

---

## Q1: Hardware Minimums

**Answer:** No single document states explicit minimums for the full stack. Hardware guidance is scattered across TTS requirements, model recommendation docs, and provisioning scripts. The implicit minimum for a useful local deployment is 24 GB VRAM (RTX 3090-class) with 64 GB RAM. CPU-only sidecar mode works on any device with Docker.

**Evidence:**
- `pmoves/docs/AGENTS/HARDWARE_TTS_REQUIREMENTS.md` line 14: Core GPU = RTX 3090 Ti / RTX 5090, VRAM 24-32 GB+, backend vLLM (mandatory for TTS)
- `Open-Source Model Recommendations for PMOVES by Service & Deployment Context.md` lines 9-17: Qwen-14B FP16 needs 24+ GB VRAM; Mistral-7B 4-bit fits ~4 GB; RTX 3090 (24 GB) handles ~13-14B FP16 or ~30B 8-bit; RTX 5090 (48 GB) handles 30B-70B
- `deploy/provision/glances-autodetect.sh` lines 40-42: Node type thresholds — `gpu-5090` requires >=64 GB RAM; `pve-member-fresh` requires >=10 GbE + >=2 NVMe + >=64 GB RAM; KVM nodes 8-16 GB RAM
- `deploy/provision/rdna4-gpu-install.sh` line 14: AMD R9700 (32 GB, RDNA4)
- Edge device: Jetson Orin Nano Super with 8 GB RAM for Phi-3-Mini 3.8B (4-bit quantized)
- `deploy/sidecar/README.md`: Sidecar mode has NO hardware minimum beyond Docker — GPU is explicitly optional

**Confidence:** Medium — strong evidence for per-service requirements but no canonical "minimum for full stack" document exists.

---

## Q2: Required vs Optional Compose Services

**Answer:** The stack is split into ~10 overlay files. Core (required for basic operation): Supabase (13 services), NATS, Qdrant, Neo4j, Meilisearch, MinIO, data workers, and agent services. GPU-only services sit behind `--profile gpu` and fail gracefully. Optional services include n8n, wger, Jellyfin, Invidious, tracing, and monitoring.

**Evidence:**
- `pmoves/docker-compose.yml` (4326 lines, 84 services) — preserved as canonical reference, split into overlays
- `pmoves/docker-compose.base.yml` — 0 services; only YAML anchors (x-env-tier-*, x-hardening-*), volumes, and networks
- `pmoves/docker-compose.agents.yml` — 16 services: agent-zero, archon, gateway-agent, hi-rag-gateway variants, mesh-agent, cipher-api, consciousness-service, evo-controller, space-agent
- GPU-only services (use `--profile gpu`, fail-open with `|| true`):
  - `pmoves/Makefile` line 1451: `$(DC) --profile gpu up -d hi-rag-gateway-v2-gpu || true`
  - `pmoves/Makefile` line 982-986: `up-model-management` conditionally starts `gpu-orchestrator` only if nvidia runtime detected
  - GPU profile services: hi-rag-gateway-gpu, hi-rag-gateway-v2-gpu, gpu-orchestrator, nvidia-nim
- Optional overlay files (not started by `make up` or `make first-run`):
  - `docker-compose.apps.yml` — wger, wger-db, botz-gateway, pmoves-yt
  - `docker-compose.n8n.yml` / `docker-compose.n8n.postgres.yml` — n8n
  - `docker-compose.voice.yml` — TTS services
  - `docker-compose.jellyfin.hosts.yml` — Jellyfin
  - `docker-compose.open-notebook.yml` — Open Notebook
  - `docker-compose.tracing.yml` — Jaeger, OTel
  - `docker-compose.rustdesk.yml` — RustDesk
- Makefile targets define the layering:
  - `up-minimal` (line 960): Supabase + Data + Bus only
  - `up-core` (line 950): obs + supabase + data + bus + workers + agents (no tensorzero/integrations)
  - `up` (line 1447): data + workers + both Hi-RAG gateways
  - `up-all` (line 200): up + up-agents-ui + up-bots + up-n8n + up-monitoring

**Confidence:** High — overlay structure and Makefile targets provide clear tier boundaries.

---

## Q3: What Does `make first-run` Actually Do?

**Answer:** An 8-step sequential bootstrap: tool validation, env file creation, Supabase startup, full data seeding (SQL migrations + Neo4j + Qdrant/Meili), core service startup, agent+UI startup, auth bootstrap, and MCP server seeding.

**Evidence:** `pmoves/Makefile` lines 719-753

| Step | Target | Line | What It Does |
|------|--------|------|-------------|
| 1 | `check-tools` | 734, 255-287 | Verifies docker, docker compose, supabase CLI, python3 installed; checks supabase version currency |
| 2 | `ensure-env-shared` | 735, 132-136 | Runs `tools/ensure_env_shared.py` — copies `env.shared.example` to `env.shared` if missing |
| 3 | `supa-start` | 736, 331-372 | Runs env-doctor, runtime guard, then starts Supabase (CLI mode: `supabase start`; compose mode: DB + Kong migrations + all Supabase services). Exports runtime env snapshot |
| 4 | `bootstrap-data` | 737, 704-717 | Umbrella that calls: `supabase-bootstrap` (tracked SQL migrations + seeds via `pmoves_bootstrap_history` table), `neo4j-bootstrap` (persona aliases + CHIT geometry), `seed-data` (Qdrant/Meili demo corpus via Hi-RAG v2) |
| 5 | `up` | 738, 1447-1452 | Starts core data + workers via `--profile data --profile workers`: qdrant, neo4j, minio, meilisearch, presign, render-webhook, langextract, extract-worker, hi-rag-gateway-v2, retrieval-eval. Attempts GPU gateway with `|| true` |
| 6 | `up-agents-ui` | 739, 2358-2361 | Starts 7 services via `--profile agents`: nats, agent-zero, archon, archon-ui, mesh-agent, deepresearch, supaserch, publisher-discord |
| 7 | `auth-bootstrap` | 740, 663-678 | Runs `secrets-runtime-hydrate`, then creates boot user (JWT mode default) via `tools/create_supabase_boot_user.py`, then runs `auth-check` |
| 8 | `a0-mcp-seed` | 741, 2363-2365 | Loads env.shared, runs `tools/seed_agent_zero_mcp.py` to write MCP server config into `data/agent-zero/runtime/mcp/servers.env` |

**Key detail:** `first-run` does NOT call `secrets-funnel`. Secrets must be pre-populated in env.shared/env.tier-* files before running.

**Confidence:** High — full target chain traced with line numbers.

---

## Q4: Running Without GPU / Laptop Mode

**Answer:** Yes, fully supported via two paths: (1) Sidecar standalone mode for any device with Docker, and (2) Compose mode where GPU services are behind `--profile gpu` and fail gracefully with `|| true`. No explicit CPU-only compose profile exists — GPU services simply don't start when nvidia runtime is absent.

**Evidence:**
- `deploy/sidecar/README.md`: "GPU is optional. The host prep script auto-detects nvidia-container-runtime: Detected → adds `--gpus all`; Not detected → runs CPU-only — works fine with Z.AI cloud providers"
- `PMOVES_AI_CONFIG.promptinclude.md`: TOPOLOGY_MODE=standalone, AGENTZERO_JETSTREAM=false, CHIT in dev mode
- `pmoves/Makefile` line 1451: `$(DC) --profile gpu up -d hi-rag-gateway-v2-gpu || true` — GPU gateway is best-effort
- `pmoves/Makefile` lines 982-986: `up-model-management` — `if docker info | grep -qi nvidia; then start gpu-orchestrator; else echo "skipping gpu-orchestrator"`
- `pmoves/env.tier-llm.example` lines 8-12: "OLLAMA is REQUIRED for local-first operation" but cloud providers are FALLBACK — can run entirely on cloud LLMs without local GPU
- No `docker-compose.cpu-only.yml` or `--profile cpu-only` found in the repo

**Confidence:** High — multiple independent evidence paths confirm CPU-only operation.

---

## Q5: Canonical Branch

**Answer:** `main` is the active development branch (HEAD). `PMOVES.AI-Edition-Hardened` exists as a remote branch used for submodule pinning and integration promotion. Recent commits and PRs all target `main`.

**Evidence:**
- `git log --oneline -15`: HEAD is `main`, all recent merges target `main`
- `git branch -a`: `* main` (checked out), `remotes/origin/main` (HEAD), `remotes/origin/PMOVES.AI-Edition-Hardened`
- `pmoves/mk/preflight.mk` line 42: `SUBMODULE_BRANCH_DEFAULT ?= PMOVES.AI-Edition-Hardened` — used for submodule branch policy checks
- `pmoves/mk/codex.mk` line ~280: `submodule-promote` creates PR from `integration` → `PMOVES.AI-Edition-Hardened`
- `reviews/BRANCH_STRATEGY_ANTI_PATTERNS.md`: Documents 91 trimmed branches; recommends `feat/`, `fix/`, `infra/`, `docs/`, `refactor/` prefixes; forbids `feature/`, `pr/`, `p1/`-`p7/`
- PR monitor default base: `PR_MONITOR_BASE:-main` (preflight.mk line with pr-monitor target)

**Confidence:** High — git state and multiple config references all confirm `main` as canonical.

---

## Q6: Health Verification After Bring-Up

**Answer:** Multiple layered health mechanisms: Docker-native healthchecks on 15+ services, Makefile wait targets with curl polling, `make status-all` for a full dashboard, `make smoke` for behavioral testing, and `make flight-check` for runtime diagnostics.

**Evidence:**
- **Docker healthchecks** (`docker-compose.agents.yml`): agent-zero (curl /healthz), archon (python urllib /healthz), gateway-agent, hi-rag-gateway (4 variants), mesh-agent (process liveness), cipher-api (wget /health), consciousness-service (httpx /healthz), evo-controller, space-agent — all with interval/timeout/retries/start_period
- **`make status-all`** (line 1095-1121): Docker ps grep for each tier (observability, supabase, data, bus, workers, agents, tensorzero) + calls `health-summary`
- **`make health-summary`** (line 1123-1128): Runs `tools/flight_check_retro.py`, saves to `.validation/`
- **Wait targets**: `wait-data` (line 1141, curl Qdrant/Neo4j/Meili/MinIO), `wait-workers` (curl :8083/:8084), `wait-agents` (curl :8080 + docker inspect health status)
- **`make supa-health`** (line 468-514): DB pg_isready + REST/Auth/Studio HTTP checks
- **`make smoke`** (line 1608-1614): Dispatches to `scripts/smoke-tests.sh` — behavioral smoke tests
- **`make flight-check`** / `flight-check-retro`: Retro diagnostics with CRT boot animation
- **`make health-dormant`** (line 989): Checks health of optional/dormant services

**Confidence:** High — extensive multi-layer health verification infrastructure.

---

## Q7: Error Recovery When Make Targets Fail

**Answer:** No single `make troubleshoot` target exists. Error recovery is distributed across: (1) deploy/runbooks/ with hardware-specific troubleshooting tables, (2) diagnostic Makefile targets (env-doctor, runtime-guard, flight-check), (3) the Circuit Breaker principle in prompt includes, and (4) individual service scripts. There is no centralized "when make X fails, do Y" runbook.

**Evidence:**
- **No `troubleshoot` make target found** — searched all .mk files and Makefile
- `deploy/runbooks/dgx-spark-ollama.md` lines 181-188: Troubleshooting table (connection refused → check OLLAMA_HOST; Tailscale ACL → tag:pmoves; model pull fails → df -h; slow inference → nvidia-smi)
- `deploy/runbooks/autodetect-unknown-system.md` lines 152-207: Explicit: "There is no silent fallback — passing auto with unknown fails with non-zero exit code"
- `deploy/runbooks/fresh-install-fleet.md` lines 150-157: USB boot failures, autoinstall stalls, first-boot hook failures
- `pmoves/Makefile` line 319-323: `supa-env-doctor` / `supa-env-doctor-strict` — layered env conflict detection
- `pmoves/Makefile` line 325-329: `supa-runtime-guard` / `supa-runtime-reconcile` — detects conflicting Supabase runtimes
- `CIRCUIT_BREAKER_PRINCIPLE.promptinclude.md`: Documents failure multiplication, fail-fast, fail-open, stop-and-reflect principles
- `pmoves/docs/operations/COMPLETE_BRING_UP_RUNBOOK.md`: Referenced by `make docs-runbook` (line 170) — likely contains recovery guidance but not read in this research

**Confidence:** Medium — evidence confirms distributed diagnostics but absence of centralized recovery doc is itself a finding.

---

## Q8: Bootstrap Ordering (Secrets-Funnel Before First-Run?)

**Answer:** NO. `make first-run` does NOT call `secrets-funnel`. The dependency chain is: env files must be pre-populated manually → `first-run` reads them → `auth-bootstrap` calls `secrets-runtime-hydrate` (a subset of secrets-funnel) but NOT the full funnel. `secrets-funnel` is a separate, independent target.

**Evidence:**
- `pmoves/Makefile` lines 734-741: `first-run` calls exactly: check-tools, ensure-env-shared, supa-start, bootstrap-data, up, up-agents-ui, auth-bootstrap, a0-mcp-seed — NO secrets-funnel
- `pmoves/mk/codex.mk` `secrets-funnel` target: local-hydrate → runtime-hydrate → credential_urlencoder → funnel-sync (chit-manifest-sync + chit-export) → secrets-audit → tooling-audit → optional supabase-boot-user
- `pmoves/mk/codex.mk` `auth-bootstrap` in Makefile (line 663-678): calls `secrets-runtime-hydrate` (pulls runtime labels into env.shared) then `supabase-boot-user` then `auth-check` — this is a SUBSET of secrets-funnel
- `scripts/bootstrap_credentials.sh` (v5): Independent script with 6-tier credential source chain (Active Fetcher → GitHub Secrets → CHIT → git-crypt → Docker Secrets → Parent env.shared) — not called by first-run
- `pmoves/chit/secrets_manifest_v2.yaml`: Defines required secrets with targets — used by secrets-funnel-sync, not by first-run
- Implicit requirement: User must manually `cp env.shared.example env.shared` and `cp env.tier-*.example env.tier-*` with real values before running first-run

**Confidence:** High — target dependency chain is fully traced.

---

## Q9: Required Credentials for New Users

**Answer:** At minimum, a new user must provide credentials in 4 tier env files plus env.shared. The hard requirements are: data tier secrets (8 vars), API tier secrets (4+ vars), a Supabase JWT secret, and the CHIT passphrase (compose-time fail if missing). Cloud LLM keys are optional fallbacks.

**Evidence:**
- **env.tier-data.example** (all marked REQUIRED):
  - `MEILI_MASTER_KEY` — `openssl rand -hex 32`
  - `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_USER`, `MINIO_PASSWORD`
  - `NEO4J_AUTH`, `NEO4J_PASSWORD`
  - `POSTGRES_PASSWORD`
  - `QDRANT__API_KEY`
- **env.tier-api.example** (marked REQUIRED):
  - `POSTGRES_PASSWORD` (must match tier-data)
  - `SUPABASE_JWT_SECRET` — `openssl rand -base64 32`
  - `PRESIGN_SHARED_SECRET` — `openssl rand -hex 32`
  - `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` (must match tier-data)
  - `MEILI_MASTER_KEY` (must match tier-data)
  - `SUPABASE_SERVICE_ROLE_KEY`
- **env.tier-llm.example**: `OLLAMA_BASE_URL` is REQUIRED (local-first). All cloud API keys (OPENAI, ANTHROPIC, GEMINI, etc.) are FALLBACK — empty values are valid
- **env.tier-agent.example**: `SUPABASE_SERVICE_ROLE_KEY` marked REQUIRED
- **env.shared.example**: Only 2 vars explicitly tagged `# REQUIRED`: `PMOVES_BRIDGE_API_KEY` (line 576), `GATE_API_KEY` (line 579)
- **docker-compose.agents.yml** line ~80: `CHIT_PROD_PASSPHRASE=${CHIT_PROD_PASSPHRASE:?set CHIT_PROD_PASSPHRASE in env.shared}` — compose-time hard fail using bash `:?` syntax
- **secrets_manifest_v2.yaml**: 6+ entries with `required: true` (agent_zero_events_token, anthropic_api_key, cohere_api_key, deepseek_api_key, etc.)
- **scripts/bootstrap_credentials.sh** (v5): Tries 6 credential sources in order — can partially automate loading but requires GITHUB_PAT or CHIT packet

**Practical minimum for `make first-run` to succeed:** All env.tier-data vars, env.tier-api vars, CHIT_PROD_PASSPHRASE, and OLLAMA_BASE_URL (or a cloud LLM key).

**Confidence:** High — tier example files have explicit REQUIRED annotations; compose fail-syntax confirms hard requirements.

---

## Q10: Agent Types and How to Invoke Them

**Answer:** Two distinct agent systems exist:

1. **Docker service agents** (76 registered in `agent_registry.yaml`): Invoked via `make up-agents` or `docker compose --profile agents up -d`. These are long-running containerized services.
2. **Claude Code sub-agents** (5 defined in `.claude/agents/`): Invoked via `claude --agent <name>`. These are ephemeral coding agents with tool restrictions and isolation.

Additionally, the sidecar has 4 Agent Zero profiles switchable in Settings.

**Evidence:**
- **Agent Registry** (`pmoves/config/agent_registry.yaml`): 76 agents, taxonomy v1.4.0, 4 classes (legendary/standard/specialized/utility), 7 tiers (data/api/llm/worker/media/agent/ui). Query: `python -m pmoves.tools.agent_taxonomy_helper list`
- **Docker agent services** started by `up-agents-ui` (line 2358): agent-zero, archon, archon-ui, mesh-agent, deepresearch, supaserch, publisher-discord (7 services)
- **Claude Code sub-agents** (`.claude/agents/`):
  | Agent | File | Invocation | Model | Max Turns | Key Constraint |
  |-------|------|------------|-------|-----------|---------------|
  | delivery-agent | `.claude/agents/delivery-agent.md` | `claude --agent delivery-agent` | opus | 50 | No EnterPlanMode |
  | control-agent | `.claude/agents/control-agent.md` | `claude --agent control-agent` | opus | 30 | No Write/Edit/EnterPlanMode |
  | memory-agent | `.claude/agents/memory-agent.md` | `claude --agent memory-agent` | sonnet | 20 | No Write/Edit; uses Cipher/CHIT |
  | test-runner | `.claude/agents/test-runner.md` | `claude --agent test-runner` | sonnet | 20 | No Write/Edit; isolation: worktree |
  | pr-trimmer | `.claude/agents/pr-trimmer.md` | `claude --agent pr-trimmer` | opus | 40 | No EnterPlanMode; isolation: worktree |
- **Documented in**: `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md` lines 76-83 (invocation table), `AGNOTE4482PHI.t1.md` lines 20-32 (Three-Body Solution definitions)
- **Sidecar profiles** (`deploy/sidecar/README.md`): sidecar (Ollama local), tensorzero (compose required), researcher (GLM-5-turbo), code-reviewer (GLM-5-turbo) — switch in Agent Zero Settings
- **Also in Makefile**: `pr-trim` target (preflight.mk) — Makefile wrapper that calls `pr-trim-analyze` + `pr-trim-resolve` + `sign-trail`, functionally equivalent to the Claude Code pr-trimmer agent

**Confidence:** High — two systems clearly documented with exact invocation syntax.
