# Design: Node-Aware HERMES + Agent Zero Provider Standup (Knuckles + SPARK)

**Date:** 2026-07-02
**Node:** B850 / PMOVES-Knuckles (dual AMD R9700 64GB, ROCm 7.1)
**Author:** B850-CLAUDE
**Status:** Approved by operator (DARKXSIDE) 2026-07-02
**AGNOTE lane:** HERMES integration TAC `phase_3_b850_knuckles` (PENDING → this session) + `phase_2_spark` (config-only, node offline)

## Goal

Stand up node-aware, PMOVES-aware HERMES Agent and Agent Zero on Knuckles, with
TensorZero as the single routing brain across all subscribed providers:
z.ai Coding Plan, Ollama Pro (ollama.com cloud), Kilo Code plan, Kimi (Moonshot)
coding plan, Alibaba (DashScope) coding plan, HuggingFace router, and local
Unsloth GGUF serving via a Pinokio launcher. SPARK gets identical wiring as
config + runbook, applied live when the node reappears on the tailnet.

## Verified current state (2026-07-02, live probes)

| Component | State |
|---|---|
| TensorZero gateway :3030 | Healthy (gateway/clickhouse/postgres/valkey ok); catalog is ollama_local + generic cloud only |
| Ollama :11434 | Native, v0.30.5, ROCm backend |
| NATS | Healthy (`pmoves-nats-1`) |
| Hermes Agent | Installed v0.15.1 (20 commits behind) via `PINOKIO_HOME/api/hermes-agent.pinokio.git`; `default` profile → ollama-cloud `glm-5.2`; gateway stopped; auth.json holds MiniMax OAuth only |
| Agent Zero | Container not running on this node |
| SPARK (`pmoves-spark` 100.89.7.106) | Offline, last seen <1h — flappy; two stale spark hostnames also on tailnet |
| Provider secrets | `pmoves/bootstrap/registry.json` has **no** ZAI/MOONSHOT/DASHSCOPE/KILOCODE/HF/OLLAMA_API_KEY entries — funnel cannot provision them yet |

## Architecture

TensorZero is the impedance matcher (MOF role): every agent points at TZ's
OpenAI-compatible endpoint; TZ owns the cascade.

```
Hermes (pmoves-hermes-knuckles) ─┐
Agent Zero (8080) ───────────────┼─▶ TensorZero :3030 (/openai/v1)
Kilo / other agents ─────────────┘        │
   ┌──────────────┬───────────────┬───────┴──────┬────────────┬─────────────┐
 ollama_local  llamacpp_unsloth  ollama_cloud   zai        kimi/alibaba  kilocode/HF
 (ROCm :11434) (GGUF row-split,  (Pro plan,     (GLM       (Moonshot /  (fallback)
                Pinokio launcher) ollama.com)    coding)     DashScope)
```

### Provider blocks (TensorZero, all OpenAI-compatible)

| Provider key | Base URL | Credential (canonical) | Plan |
|---|---|---|---|
| `ollama_local` | `http://<node-ollama>:11434/v1` | none | local ROCm/CUDA |
| `llamacpp_unsloth` | `http://localhost:8090/v1` | none | Unsloth GGUF via llama.cpp-ROCm |
| `ollama_cloud` | `https://ollama.com/v1` | `OLLAMA_API_KEY` | Ollama Pro |
| `zai` | z.ai coding endpoint | `ZAI_API_KEY` (+`ZAI_API_KEYS` pool) | GLM Coding Plan |
| `kimi` | Moonshot API | `MOONSHOT_API_KEY` (alias KIMI_API_KEY) | Kimi coding plan |
| `alibaba` | DashScope compatible-mode | `DASHSCOPE_API_KEY` (alias ALIBABA_API_KEY) | Alibaba coding plan |
| `kilocode` | Kilo Code OpenRouter-compatible | `KILOCODE_API_KEY` | Kilo Code plan |
| `huggingface` | HF router | `HF_TOKEN` | HF Pro / Inference |

Exact vendor base URLs are confirmed against current provider docs at
implementation time, not hardcoded from memory.

### Routing functions

- `pmoves_coding`: ollama_local → zai → kimi → alibaba → kilocode → huggingface
- `pmoves_chat`: ollama_local → ollama_cloud → kilocode → huggingface
- `pmoves_embed`: ollama_local (gemma/nomic embed) → huggingface

### Node awareness

- Profiles keyed by node id. Knuckles carries the ROCm dual-R9700 local tier;
  `spark.yaml` carries 70B-primary local tier with identical TZ wiring.
- Tailscale mesh fallback (`pmoves-spark:11434`, `pmoves-5090:11434`) stays in
  config; activates automatically when peers are online.
- 70B models remain SPARK-only per integration spec.

### HERMES standup (Knuckles)

1. `hermes update` (20 commits behind), then `hermes doctor`.
2. Create `pmoves-hermes-knuckles` profile from repo `pmoves/config/profiles/hermes/b850.yaml`,
   upgraded: model provider → TZ endpoint, provider fallbacks per cascade,
   NATS subjects per integration spec (publish `hermes.gateway.*` etc.,
   subscribe `p7.nats.launch/session`, `mesh.node.announce.v1`).
3. Secrets into `~/.hermes/profiles/pmoves-hermes-knuckles/.env` via secrets
   funnel — never committed.
4. Gateway on :7700 (Tailscale-internal), verify `/api/health`, observe
   `hermes.gateway.health.v1` on NATS.

### Agent Zero standup (Knuckles)

- Bring up via compose (agent tier), model env pointed at TZ.
- Verify `/healthz` on 8080 and MCP surface (`/mcp/*`).

### Pinokio local model selection

- Extend/add launcher in `PINOKIO_HOME/api/` for llama.cpp-ROCm serving Unsloth
  GGUFs row-split across both R9700s (`HIP_VISIBLE_DEVICES=0,1`), exposing
  OpenAI-compatible :8090, registered in TZ as `llamacpp_unsloth`.
- Launcher follows Pinokio guide (`.claude/PINOKIO_LAUNCHER_GUIDE.md`); mirrors
  an existing example script; URL capture via the mandated `on/local.set` pattern.

### Naming canon

Registry-canonical env names are `MOONSHOT_API_KEY` and `DASHSCOPE_API_KEY`.
The integration spec's `KIMI_API_KEY`/`ALIBABA_API_KEY` become documented
aliases (CANONICAL_NAMES.md) — no new drift.

## Deliverables — 3 stacked PRs (<400 lines each)

1. **feat(providers):** `bootstrap/registry.json` slots (ZAI_API_KEY[S],
   MOONSHOT_API_KEY, DASHSCOPE_API_KEY, KILOCODE_API_KEY, HF_TOKEN,
   OLLAMA_API_KEY) + `env.tier-llm.example` + TensorZero provider/model/function
   blocks.
2. **feat(hermes-profile)+feat(agent-zero):** Knuckles profile v2 (`b850.yaml`),
   `spark.yaml` v2, TAC status flips (`phase_3_b850_knuckles` → done,
   node profiles → done for b850), Agent Zero TZ wiring, AGNOTE convergence
   entry + CLAIM/RELEASE in `AGNOTE4482PHI.t1.md` (identity: B850-CLAUDE).
3. **feat(pinokio)+docs(spark):** Unsloth/llama.cpp launcher + SPARK apply
   runbook.

Live standup happens alongside PR 2; PR 1 must land (or at least exist locally)
first so env slots exist.

## Error handling / gaps surfaced to operator

- Providers with empty keys are wired but reported as a fill-list (operator
  updates GH/CHIT source, reruns `make -C pmoves secrets-funnel`).
- SPARK offline → runbook only; retry live apply if it reappears mid-session.
- Hermes `.env`/`auth.json` never committed (gitignore verified).
- `env.tier-llm` is zero-access to agents (damage-control) — all edits go
  through registry + example + funnel, never direct.

## Testing

- TZ: `curl /openai/v1/chat/completions` per model alias (skip/flag empty-key providers).
- Hermes: `hermes doctor`, `hermes chat -q` smoke through TZ, gateway health,
  NATS subject observation.
- Agent Zero: `/healthz`, MCP status skill.
- Repo: `cd pmoves && python -m pytest tests/ -q` before each PR.
- Signoff: HERMES section of `AGNOTE4482_SIGNOFF_CHECKLIST.md` items ticked
  for what this session actually verified.
