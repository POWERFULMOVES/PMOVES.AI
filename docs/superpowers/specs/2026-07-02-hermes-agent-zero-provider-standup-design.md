# Design: Node-Aware HERMES + Agent Zero Provider Standup (Knuckles + SPARK)

**Date:** 2026-07-02 (rev 3 — dynamic model plane: no hardcoded models, Supabase + APIs)
**Node:** B850 / PMOVES-Knuckles (dual AMD R9700 64GB, ROCm 7.1)
**Author:** B850-CLAUDE
**Status:** Rev 3 pending operator re-approval

## Rev 3 correction (operator, 2026-07-02)

**No hardcoded local model IDs anywhere in committed config.** Model selection
is API- and Supabase-driven, using infrastructure that already exists:

| Component | Port | Role |
|---|---|---|
| `model-registry` | 8110 | Supabase-backed model catalog ("replaces hardcoded TensorZero configuration"); generates TZ TOML from DB; `POST /api/model-candidates` **requires trusted agent identity + `signed_trail_ref`** — agent trails enforced at the API; `/api/models/{id}/enrich-hf` pulls HF metadata; `/api/model-fitness` records scored evidence |
| `gpu-orchestrator` | 8200 | Load/unload/optimize with VRAM tracking; `ollama_client` + `vllm_client` + `model_lifecycle` |
| `vllm-orchestrator` | — | Serves HF-native weights; `tensorzero.py` registers running vLLM instances as TZ providers dynamically |
| `spark-shape-worker` | — | Node-agnostic sidecar: subscribes to GPU inference results on NATS, emits `content.lexicon.shaped.v1` + `mesh.shape.handshake.v1` CHIT shape capsules — the worker-tier trail emitter |
| Supabase tables | — | `pmoves_core.model_candidates`, `pmoves_core.model_fitness_records` (migration `20260522000000`, RLS tightened `20260527`) |

Worker sibling selection flow (replaces rev 2's pinned matrix):
1. **Research** current-best sibling per family lane via the HuggingFace
   plugin/MCP (model search + `hf-mem` VRAM fit vs 64GB ROCm) + registry
   `enrich-hf`.
2. **Register** as signed candidate: `POST /api/model-candidates` with CHIT
   `signed_trail_ref` (pmoves-chit-sign).
3. **Score** via smoke runs → `POST /api/model-fitness`.
4. **Load** via gpu-orchestrator (`POST /models/load`); serve via vLLM
   (dynamic TZ registration) or llama.cpp/Ollama per backend fit.
5. **Shape** inference results onto the mesh via a shape-worker sidecar on
   Knuckles (same contract SPARK uses).

The rev 2 sibling matrix below is retained **as family-lane examples only** —
actual IDs resolve at standup from live HF/provider APIs and land in Supabase,
never in committed YAML/TOML. Cloud provider endpoints + routing functions
remain static config (they are API contracts, not model picks); worker model
rows in TZ are generated from the registry (marker-delimited section refreshed
by a sync tool), so the TOML carries them as build artifacts, not hand edits.
**AGNOTE lane:** HERMES integration TAC `phase_3_b850_knuckles` (PENDING → this session) + `phase_2_spark` (config-only, node offline)

## Goal

Stand up node-aware, PMOVES-aware HERMES Agent and Agent Zero on Knuckles as a
**cloud-hybrid system**: the subscribed **cloud coding plans are the
orchestrator tier** (z.ai Coding Plan, Kimi/Moonshot coding plan, Alibaba/
DashScope coding plan, Kilo Code plan, Ollama Pro cloud), and **local models
are the autonomous worker siblings of their cloud counterparts** — bounded
subagents that adsorb skill from their cloud parents through CHIT-signed agent
trails (the MOF gap-size transfer mechanism). TensorZero routes both tiers.
HuggingFace/Unsloth supply the local worker weights; a Pinokio launcher manages
local model selection/serving on this node. SPARK gets identical wiring as
config + runbook, applied live when it reappears on the tailnet.

**Primary quality bar: model & provider support best practices.** Every model
entry — cloud or local — carries correct context length, max output tokens,
temperature/sampling defaults, and capability flags, sourced from one canon
(`pmoves/configs/model-suits/`). PMOVES fits each model like a glove; no model
is forced into another model's shape.

## Rev 4 — Topology context (4-agent repo fan-out, 2026-07-02)

Four parallel explorations (P7/pbnj, Archon minting, runner fabric, agent
inventory) grounded this standup in the real topology. Findings that bind:

**Identity & trust (Archon lane).** Two decoupled systems: Archon's mint
factory is spec'd but stubbed (zero live `archon.mint.*` publishers; MCP tools
and `POST /api/agents` 404). The LIVE trust gate is the 3-YAML ledger —
`agent_signatures.yaml` + `agent_registry.yaml` + an **active card in
`signing_identity_cards.yaml`** — enforced by
`require_trusted_agent_identity()` (`pmoves/services/common/model_fitness.py:316-366`),
which guards `POST /api/model-candidates` and `/api/model-fitness`.
**Blocking gap:** `hermes-agent` has signature+registry entries but NO signing
card; `b850-claude` has NO entries at all (z890/5090/4090-claude do). Without
PR 0 below, the dynamic model pipeline 403s. Proper registration = 3-YAML
entries **plus** the archon-qa-agent gate review (QA validates NATS namespace,
branded defaults, CHIT tier) — either alone is a bypass.

**P7 / pbnj (the stage).** pbnj = "PMOVES Batch Node Jobs" (peanut butter &
jelly) — the launcher pack at `pbnj/pinokio/api/*` (includes an existing
`pmoves-model-registry` launcher). P7 control plane: `p7.nats.launch` (room+
suits) and `p7.nats.session` (stage), published by pbnj hooks
(`pmoves-pbnj/demo.js`, `nats-session-hook.js`). `hermes-agent.room.control`
already exists in `catalog.json` with a `p7{}` block — the standup publishes
launch/session events on bring-up. The Pinokio model-selector extends the
pbnj pack, not a new location. Known bug to fix en route: `demo.js:46` uses
`2>nul` (cmd.exe-ism; creates a file named `nul` on Linux).

**Runner fabric (where agents execute).** Two fabrics conflated in
`.claude/context/runner-topology.md`: (A) GitHub self-hosted CI runners
(ai-lab/vps/hotfix/spark/kvm4-1/kvm4-2/kvm2/cloudstartup — SPARK, hotfix,
cloudstartup missing from the doc) and (B) model runners (Knuckles
llama-server gfx1201 fork, SPARK Ollama-ARM64, TensorZero routing plane).
Announcement plane: `mesh-agent` → `mesh.node.announce.v1` every 15s →
`node-registry` :8115 → Supabase (queryable REST). Cloudflare today = CI
orchestration Worker (routing only, routes commented out) + tunnel + R2;
**Workers AI inference is a planned fallback tier, not wired** — that is the
"will need cloud" follow-up lane. Port conflict confirmed: the Knuckles node
profile (`workstation-9850x3d-dual-r9700.yaml`) documents llama-server :8080,
colliding with Agent Zero — the :8090 move must update that profile too.

**Agent inventory (who exists where).** Five layers: (a) compose agent
services (agent-zero 8080/8081, archon 8091/8051/8052, gateway-agent **8111**
— topology doc wrongly says 8100, hi-rag family, mesh-agent, cipher 8105,
a2ui-bridge 9224, consciousness 8106, evo 8113); (b) node-named CLI
contributors (z890/5090/4090-claude — **no b850-claude**); (c) 19
`.claude/agents/` subagent defs; (d) external contributor agents (kilocode,
codex, hermes-agent, gemini…); (e) persona suits (FlOO$, P7-loaded, not in
registry). Registry has 79 agents; `PMOVES_AGENT_TOPOLOGY.md` lists ~59 and
claims 76 — it is meant to be regenerated from the registry
(`python -m pmoves.tools.agent_taxonomy_helper mermaid`). Delegation paths:
A0 `/mcp/*` live; A2A server on but discovery/tasks flags default false;
`mesh.node.announce.v1` live; `agent.peer.heartbeat.v1` not yet.

**Consequence — delivery gains a PR 0 (foundational, before providers):**
trust-ledger entries for `b850-claude` + `hermes-agent` (3 YAMLs, QA-gated),
topology regeneration + port/room-count/stub-link corrections, runner-fabric
doc refresh (two-fabric split, add SPARK/hotfix/cloudstartup). Cloudflare
Workers AI provider wiring and Archon mint-pipeline liveness are recorded as
follow-up lanes, not this session's scope.

## Verified current state (2026-07-02, live probes)

| Component | State |
|---|---|
| TensorZero gateway :3030 | Healthy (gateway/clickhouse/postgres/valkey ok); catalog has ollama_local qwen3.5 family + generic cloud; **no coding-plan providers** |
| Ollama :11434 | Native v0.30.5 ROCm; **only `nomic-embed-text` pulled** — no local chat/worker models yet |
| NATS | Healthy (`pmoves-nats-1`) |
| Hermes Agent | Installed v0.15.1 (20 commits behind) via `PINOKIO_HOME/api/hermes-agent.pinokio.git`; `default` profile → ollama-cloud `glm-5.2`; gateway stopped; auth.json holds MiniMax OAuth only |
| Agent Zero | Container not running on this node |
| SPARK (`pmoves-spark` 100.89.7.106) | Offline, last seen <1h — flappy |
| Model suits | `pmoves/configs/model-suits/` already defines per-model `model_config` (context_window, max_output_tokens, temperature_range, capability flags) for glm-4.7/5.1/5-turbo, qwen3.6, minimax, claude, nemotron — **this is the parameter canon** |
| Provider secrets | `pmoves/bootstrap/registry.json` has **no** ZAI/MOONSHOT/DASHSCOPE/KILOCODE/HF/OLLAMA_API_KEY entries — funnel cannot provision them yet |

## Architecture — cloud orchestrators, local worker siblings

```
                    ORCHESTRATOR TIER (cloud coding plans)
   z.ai GLM ─── Kimi/Moonshot ─── Alibaba Qwen ─── Kilo Code ─── Ollama Pro
       │              │                │               │             │
       └──────────────┴───────┬────────┴───────────────┴─────────────┘
                              ▼
                   TensorZero :3030 (/openai/v1)
              routing + observability + CHIT trail hooks
                              ▼
                    WORKER TIER (local siblings, this node)
   glm4 local ──── kimi-dev local ── qwen3-coder local ── hermes3:8b ── Unsloth GGUF
   (Ollama ROCm)   (pending fit)     (Ollama ROCm)        (Ollama)      (llama.cpp-ROCm
                                                                         row-split, Pinokio)
                              ▼
        Agent trails: hermes.delegate.completed.v1 + CHIT signing
        (cloud parent delegates bounded work → local sibling executes
         → trail records provenance → MOF skill transfer)
```

Hermes and Agent Zero both point at TensorZero. Orchestrator sessions resolve
to cloud functions; subagent/worker delegations resolve to local-sibling
functions. One path, goal-oriented, with room to branch: new providers or
siblings are added as rows in the pairing matrix, not new architectures.

### Sibling pairing matrix (cloud parent ↔ local worker)

| Family | Cloud parent (plan) | Local worker sibling | Node fit (64GB ROCm) | Status |
|---|---|---|---|---|
| GLM | z.ai Coding Plan (`glm-5.x`) | `glm4:9b` (Ollama) | ~6GB — easy | pull at standup |
| Qwen | Alibaba DashScope (`qwen3-coder`) | `qwen3-coder:30b` (Ollama) | ~20GB Q4 — fits | pull at standup |
| Kimi | Moonshot coding plan (`kimi-k2.x`) | Kimi-Dev-72B GGUF Q4 row-split | ~40GB — fits dual R9700 | pending validation |
| Hermes | Ollama Pro / OpenRouter (`hermes` family) | `hermes3:8b` (Ollama) | ~5GB — easy | pull at standup |
| Open pool | Ollama Pro cloud (`glm-5.2`, others) | same-tag local pulls where published | varies | as-needed |
| HF | HF router (fallback) | Unsloth GGUFs via llama.cpp-ROCm :8090 | varies | Pinokio launcher |

70B+ dense models remain SPARK-only per integration spec; Knuckles caps at
~40GB Q4 MoE/row-split.

### Provider blocks (TensorZero, all OpenAI-compatible)

| Provider key | Tier | Credential (canonical) | Plan |
|---|---|---|---|
| `zai` | orchestrator | `ZAI_API_KEY` (+`ZAI_API_KEYS` pool) | GLM Coding Plan |
| `kimi` | orchestrator | `MOONSHOT_API_KEY` (alias KIMI_API_KEY) | Kimi coding plan |
| `alibaba` | orchestrator | `DASHSCOPE_API_KEY` (alias ALIBABA_API_KEY) | Alibaba coding plan |
| `kilocode` | orchestrator | `KILOCODE_API_KEY` | Kilo Code plan |
| `ollama_cloud` | orchestrator | `OLLAMA_API_KEY` | Ollama Pro |
| `huggingface` | fallback | `HF_TOKEN` | HF router |
| `ollama_local` | worker | none | local ROCm :11434 |
| `llamacpp_unsloth` | worker | none | Unsloth GGUF :8090 |

Vendor base URLs are confirmed against current provider docs at implementation
time, not hardcoded from memory.

### Routing functions

- `pmoves_orchestrator_coding`: zai → kimi → alibaba → kilocode → ollama_cloud → huggingface
- `pmoves_orchestrator_chat`: ollama_cloud → zai → kilocode → huggingface
- `pmoves_worker_glm` / `pmoves_worker_qwen` / `pmoves_worker_hermes` /
  `pmoves_worker_kimi`: local sibling first → **same-family cloud parent** as
  fallback (sibling escalation, never cross-family — keeps trails meaningful)
- `pmoves_embed`: ollama_local (nomic/gemma embed) → huggingface

Each function variant pins per-model parameters **from the model suit**:
context window, max output tokens, temperature (coding ≈0.1–0.3, chat ≈0.7,
per suit `temperature_range`), stop/tool-call behavior.

### Model-suit canon (the "glove")

- Every model referenced by TZ or Hermes has a suit file in
  `pmoves/configs/model-suits/` (existing files reused; new worker suits added:
  `glm-4-9b-worker.yaml`, `qwen3-coder-30b-worker.yaml`,
  `hermes3-8b-worker.yaml`, `kimi-dev-72b-worker.yaml`).
- Suits declare `model_config` (context_window, max_output_tokens,
  temperature_range, capability flags) + worker/orchestrator `tier` + sibling
  linkage (`sibling_of: glm-5.1` etc.).
- A small generator/check keeps TZ TOML and suits in sync (drift check in
  tests, mirroring the naming-drift gate pattern).

### Agent trails (the point of the exercise)

- Every worker delegation publishes `hermes.delegate.completed.v1` (and Agent
  Zero equivalents) with `signing_card_id` per the 5×5 trail handshake
  invariant — cloud parent, worker sibling, task, and outcome all on the trail.
- Trails feed Cipher/CHIT memory so worker siblings accumulate provenance-
  signed experience from their cloud parents (MOF adsorption).

### HERMES standup (Knuckles)

1. `hermes update` (20 commits behind), then `hermes doctor`.
2. Create `pmoves-hermes-knuckles` profile: **default model = cloud
   orchestrator via TZ**; `delegation.model` = local worker sibling via TZ;
   NATS subjects per integration spec.
3. Secrets into profile `.env` via secrets funnel — never committed.
4. Gateway :7700 (Tailscale-internal); verify `/api/health`; observe
   `hermes.gateway.health.v1` on NATS.

### Agent Zero standup (Knuckles)

- Bring up via compose (agent tier); chat/utility model envs → TZ orchestrator
  function; subordinate-agent model env → TZ worker function.
- Verify `/healthz` on 8080 and MCP surface.

### Pinokio local model selection

- Launcher in `PINOKIO_HOME/api/` for llama.cpp-ROCm serving Unsloth GGUFs
  row-split across both R9700s (`HIP_VISIBLE_DEVICES=0,1`), OpenAI-compatible
  :8090, registered in TZ as `llamacpp_unsloth`.
- Follows `.claude/PINOKIO_LAUNCHER_GUIDE.md`; mirrors an example script; URL
  capture via the mandated `on`/`local.set` pattern.

### Node awareness

- Knuckles profile carries the ROCm dual-R9700 worker tier; `spark.yaml`
  carries the 70B-worker tier with identical TZ wiring.
- Tailscale mesh worker fallback (`pmoves-spark:11434`, `pmoves-5090:11434`)
  configured; activates when peers are online.

### Naming canon

Registry-canonical env names are `MOONSHOT_API_KEY` and `DASHSCOPE_API_KEY`.
The integration spec's `KIMI_API_KEY`/`ALIBABA_API_KEY` become documented
aliases (CANONICAL_NAMES.md) — no new drift.

## Deliverables — 3 stacked PRs (<400 lines each)

1. **feat(providers):** registry slots (ZAI_API_KEY[S], MOONSHOT_API_KEY,
   DASHSCOPE_API_KEY, KILOCODE_API_KEY, HF_TOKEN, OLLAMA_API_KEY) +
   `env.tier-llm.example` + TZ provider/model/function blocks + worker suit
   files + suit↔TZ drift check.
2. **feat(hermes-profile)+feat(agent-zero):** Knuckles profile v2 (`b850.yaml`),
   `spark.yaml` v2, worker model pulls, TAC status flips, Agent Zero TZ wiring,
   AGNOTE convergence entry + CLAIM/RELEASE in `AGNOTE4482PHI.t1.md`
   (identity: B850-CLAUDE).
3. **feat(pinokio)+docs(spark):** Unsloth/llama.cpp launcher + SPARK apply
   runbook.

Live standup happens alongside PR 2; PR 1 must exist first so env slots exist.

## Error handling / gaps surfaced to operator

- Providers with empty keys are wired but reported as a fill-list (operator
  updates GH/CHIT source, reruns `make -C pmoves secrets-funnel`).
- SPARK offline → runbook only; retry live apply if it reappears mid-session.
- Kimi local sibling (Kimi-Dev-72B Q4 row-split) is pending-validation; the
  worker function falls back to its cloud parent until validated.
- Hermes `.env`/`auth.json` never committed (gitignore verified).
- `env.tier-llm` is zero-access to agents (damage-control) — all edits go
  through registry + example + funnel, never direct.

## Testing

- TZ: `curl /openai/v1/chat/completions` per function (orchestrator + worker);
  empty-key providers skipped and flagged.
- Parameter fidelity: assert TZ model entries match suit `model_config`
  (context window, max tokens, temperature) via the drift check.
- Hermes: `hermes doctor`, orchestrator smoke, one `delegate_task` worker smoke
  with trail observed on NATS.
- Agent Zero: `/healthz`, MCP status skill.
- Repo: `cd pmoves && python -m pytest tests/ -q` before each PR.
- Signoff: HERMES section of `AGNOTE4482_SIGNOFF_CHECKLIST.md` ticked for what
  this session actually verified.
