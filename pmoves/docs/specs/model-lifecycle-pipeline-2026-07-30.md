# PMOVES Model Lifecycle Pipeline — Design Spec

**Status:** DRAFT — awaiting operator approval
**Date:** 2026-07-30
**Author:** Crush (GLM-5.2 via Crush)
**Scope:** Full end-to-end model lifecycle: HF discovery → Unsloth fine-tune → GGUF convert → multi-engine serving (llama.cpp/vLLM/NIM/Ollama) → throughput benchmark → fitness scoring → TensorZero routing → AgentGym evaluation → Archon agent mint → CHIT attestation

---

## 1. Problem Statement

The pipeline's **backbone exists** (hf-agent, model-registry, fitness schema, NATS, Supabase tables, CHIT signing, AgentGym RL coordinator, TensorZero gateway). But the links between components are **broken or missing**. The single fatal gap is **G1**: the model-fitness endpoint (`POST /api/model-fitness`) is a fully-built write surface with **zero automatic producers**. Every upstream source (throughput-lab, AgentGym, TensorZero telemetry, Unsloth) would need to call it, but none do. The pipeline dead-ends at a push-API nobody pushes to.

Additionally, the serving tier is Ollama-only on SPARK — no llama.cpp, vLLM, or NIM despite all three being compatible with the GB10 chip. The Knuckles (B850/RDNA4) llama.cpp HIP installer exists but is operator-flash-pending.

---

## 2. Current State — Pipeline Diagram

```
┌─────────────────┐   ┌──────────────┐   ┌──────────────┐   ┌───────────────────┐
│ 1. HF Discovery │──▶│ 2. Unsloth   │──▶│ 3. GGUF      │──▶│ 4. Serving Tier   │
│    ✅ LIVE       │   │    Fine-Tune │   │    Convert   │   │    MIXED          │
│ hf-agent        │   │    ⏳ SCAFFOLD│   │    ❌ STUB   │   │ Ollama ✅         │
│ hf-research-    │   │              │   │              │   │ llama.cpp ❌      │
│ agent           │   │              │   │              │   │ vLLM ❌           │
│ hf-mcp-server   │   │              │   │              │   │ NIM ❌            │
└────────┬────────┘   └──────────────┘   └──────────────┘   └────────┬──────────┘
         │                                                       │
         │ NATS:                                                  │ OpenAI-compat
         │ hf.model.discovered.v1                                 │ endpoints
         │ hf.model.evaluated.v1                                  │
         │ hf.model.downloaded.v1                                 │
         │                                                       │
         │   ┌────────────────────────────────────────────┐      │
         │   │     G1: NO FITNESS PRODUCER (FATAL)       │      │
         │   │     POST /api/model-fitness               │      │
         │   │     exists but nobody calls it            │      │
         │   └────────────────────────────────────────────┘      │
         │                                                       │
         ▼                                                       ▼
┌──────────────────────┐   ┌──────────────────┐   ┌──────────────────────┐
│ 5. Throughput-Lab    │   │ 6. TensorZero    │   │ 7. AgentGym Eval     │
│    Benchmark         │   │    Route         │   │    ✅ LIVE (RL)       │
│    ✅ STANDALONE     │   │    ✅ LIVE        │   │    agentgym-rl-      │
│ Prom + NATS pub     │   │    :3030         │   │    coordinator       │
│ ❌ NOT FEEDING       │   │    ClickHouse    │   │    evo-controller    │
│   FITNESS            │   │    telemetry     │   │    ❌ NOT FEEDING     │
└──────────────────────┘   │    ❌ NOT EXTRACTED│   │    FITNESS           │
                           └────────┬─────────┘   └──────────┬───────────┘
                                    │                        │
                                    │                        │ NATS:
                                    │                        │ agentgym.train.*.v1
                                    │                        │ agentgym.model.published.v1
                                    ▼                        ▼
                           ┌──────────────────┐   ┌──────────────────────┐
                           │ 9. model-registry│   │ 10. model.fitness    │
                           │    ✅ LIVE :8110  │   │    .recorded.v1      │
                           │    POST /api/    │   │    ✅ SCHEMA          │
                           │    model-fitness │   │    ✅ DB TABLE        │
                           │    POST /api/    │   │    ✅ NATS PUBLISH    │
                           │    model-candidates│  │    ✅ CHIT SIGN       │
                           │    GET /api/tz   │   │    ❌ NO PRODUCER     │
                           │    config        │   │                       │
                           └──────────────────┘   └──────────────────────┘
                                    │
                                    ▼
                           ┌──────────────────┐
                           │ 8. Archon Mint   │
                           │    ⏳ STUB        │
                           │    mint-agent cmd│
                           │    ❌ NO MODEL_ID │
                           │    archon:create │
                           │    ❌ NOT IMPL   │
                           └──────────────────┘
```

---

## 3. Gap Inventory

| # | Gap | From → To | Impact | Severity |
|---|-----|-----------|--------|----------|
| **G1** | No fitness producer — `POST /api/model-fitness` has zero callers | throughput-lab/AgentGym/TensorZero → model-registry | **Pipeline dead-ends** | FATAL |
| **G2** | GGUF convert is a stub | hf-mcp-server → Ollama/llama.cpp | Blocks Unsloth→serve | HIGH |
| **G3** | Unsloth training loop commented out | Unsloth scaffold → adapter output | Blocks fine-tuning | HIGH |
| **G4** | hf-research-agent → model-registry disconnected | `hf.model.evaluated.v1` → `POST /api/model-candidates` | Candidates never registered | MEDIUM |
| **G5** | AgentGym → model lifecycle disconnected | `agentgym.model.published.v1` → model-registry | RL models never registered | MEDIUM |
| **G6** | `model.minted.v1` design-only | DARKMATTER_FACTORY design → code | No model-level minting | MEDIUM |
| **G7** | `archon.mint.agent.v1` not in topic catalog | mint-agent command → contracts | No formal contract | LOW |
| **G8** | Mint manifest has no `model_id` field | mint-agent → TensorZero binding | Agents not bound to models | MEDIUM |
| **G9** | Model Nexus doesn't consume fitness scores | `model_fitness_records` → TensorZero weights | No auto-weighting | MEDIUM |
| **G10** | Throughput-lab NATS subject mismatch | `llama.benchmark.*` vs topic catalog | Benchmarks not consumed | LOW |

---

## 4. Serving Tier — Node Compatibility Matrix

| Engine | SPARK (GB10 ARM64 SM_121a) | Knuckles (R9700 gfx1201 ROCm) | Z890/5090/4090 (CUDA x86) | KVM (no GPU) |
|---|---|---|---|---|
| **Ollama** | ✅ Live (:11434) | ❌ (no gfx1201 kernels) | ✅ All nodes | ❌ |
| **llama.cpp** | ✅ ARM64+CUDA build (CUDA 13+, sm_121a) | ✅ HIP build (gfx1201, ROCm 7.1, installer ready) | ✅ CUDA build | ⚠️ CPU-only marginal |
| **vLLM** | ✅ Source build (CUDA 13, sm_121a, community images exist) | ⚠️ Source build (gfx1201, community forks) | ✅ Pre-built wheels | ❌ |
| **NIM** | ✅ DGX-Spark containers (`-dgx-spark` tags, model-free path) | ❌ (NVIDIA-only) | ✅ Model-free container | ❌ |

### Serving tier deployment model

Each engine runs as an **OpenAI-compatible endpoint** on a distinct port. TensorZero routes to them by provider name. No single engine replaces the others — each has a role:

| Engine | Role | Why |
|---|---|---|
| **Ollama** | Default local inference, model pulling, GGUF management | Simplest operator UX, already running |
| **llama.cpp** | Throughput benchmarking, custom builds, HIP path for Knuckles | The only path for RDNA4; the benchmark target |
| **vLLM** | High-throughput production serving, continuous batching | Best tok/s for concurrent loads; PagedAttention |
| **NIM** | NVIDIA-optimized serving, blueprint integration | Best GB10 performance; air-gap capable |

### Per-node deployment plan

**SPARK (GB10 128GB unified):**
- Ollama ✅ existing (:11434)
- llama.cpp → build ARM64+CUDA → :8082
- vLLM → community Docker `lharillo/vllm-blackwell-gb10-spark` → :8083
- NIM → model-free DGX-Spark container → :8084

**Knuckles (B850/RDNA4 64GB):**
- llama.cpp → HIP installer already written → :8080 (systemd)
- vLLM → optional, community fork `patcarter883/rdna4-vllm` → :8083
- Ollama ❌ (no gfx1201 kernels)

**Z890/5090/4090 (CUDA x86):**
- Ollama ✅ existing (:11434)
- llama.cpp → standard CUDA build → :8082
- vLLM → pre-built wheel → :8083
- NIM → model-free container → :8084

**KVM4-1/KVM4-2 (no GPU):**
- No local inference. Route to GPU nodes via TensorZero over Tailscale.
- Optional: CPU-only llama.cpp for tiny models (Qwen2.5-3B) — low priority.

---

## 5. Implementation Phases

### Phase 1 — Serving Tier on SPARK

**Goal:** Stand up llama.cpp, vLLM, and NIM alongside Ollama on this node.

| Step | What | How | Deliverable |
|---|---|---|---|
| 1.1 | llama.cpp ARM64+CUDA build | Clone llama.cpp, `cmake -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=121`, build `llama-server` | Binary at `/usr/local/bin/llama-server`, systemd unit on :8082 |
| 1.2 | Model for benchmarking | Export `qwen3.5:35b-a3b-q8_0` from Ollama to GGUF, or `ollama show --modelfile` + `cp` | GGUF at `/models/spark-qwen35.gguf` |
| 1.3 | vLLM ARM64+CUDA container | Pull `lharillo/vllm-blackwell-gb10-spark:latest`, compose service on :8083 | Docker container `pmoves-vllm-1` |
| 1.4 | NIM DGX-Spark container | Pull `nvcr.io/nim/meta/llama-3.1-8b-instruct-dgx-spark`, compose service on :8084 | Docker container `pmoves-nim-1` |
| 1.5 | TensorZero provider registration | Add `llamacpp_spark`, `vllm_spark`, `nim_spark` to tensorzero.toml with `weight=0.0` | TOML entries |
| 1.6 | Throughput-lab benchmark sweep | Point throughput-lab at each endpoint, run sweep | CSV results + Prometheus metrics |

**Validation:** `make llama-throughput-smoke` passes; `curl :8082/v1/models`, `:8083/v1/models`, `:8084/v1/models` all return model lists.

### Phase 2 — Close the Pipeline Gaps

**Goal:** Make every link in the pipeline actually fire. Close G1 (fatal) first, then G2, G4-G10 in parallel.

#### G1 — Model Fitness Bridge (FATAL — close first)

**What:** A new service `pmoves/services/model-fitness-bridge/` that subscribes to benchmark + telemetry events and calls `POST /api/model-fitness`.

**Architecture:**
```
throughput-lab ──→ NATS: llama.benchmark.completed.v1 ──┐
                                                        ├──→ model-fitness-bridge ──→ POST /api/model-fitness
TensorZero ClickHouse telemetry ──→ periodic scrape ────┘    (FastAPI + NATS sub)       (CHIT-signed,
                                                                                          normalized 0-1 score)
AgentGym RL coordinator ──→ NATS: agentgym.train.completed.v1 ─┘
```

**NATS subscriptions:**
- `llama.benchmark.completed.v1` — from throughput-lab
- `agentgym.train.completed.v1` — from AgentGym RL coordinator
- `agentgym.model.published.v1` — from AgentGym (register as candidate)

**ClickHouse scrape (periodic, every 5 min):**
- Query TensorZero ClickHouse for per-model latency, success rate, token count
- Normalize to 0-1 using the existing `build_model_fitness_event()` weights

**Output:** CHIT-signed `model.fitness.recorded.v1` events via `POST /api/model-fitness` + NATS publish.

**Files:**
- `pmoves/services/model-fitness-bridge/app.py` — FastAPI service
- `pmoves/services/model-fitness-bridge/bridge.py` — NATS subscriber + ClickHouse scraper + fitness API caller
- `pmoves/services/model-fitness-bridge/Dockerfile`
- `pmoves/docker-compose.yml` — service definition under `agents` profile

#### G2 — GGUF Convert (wire the stub)

**What:** Replace `hf_model_convert_gguf()` stub with actual llama.cpp subprocess invocation.

**Implementation:**
```python
# In pmoves/services/hf-mcp-server/main.py, replace the stub:
async def hf_model_convert_gguf(model_id: str, quantization: str = "q4_k_m"):
    # 1. Resolve model path from HF cache
    model_path = resolve_hf_cache_path(model_id)
    # 2. Spawn llama.cpp convert_hf_to_gguf.py
    gguf_path = await run_subprocess(
        "python3", "/opt/llama.cpp/convert_hf_to_gguf.py",
        model_path, "--outfile", f"/models/{model_id}.gguf"
    )
    # 3. Quantize if requested
    if quantization != "f16":
        await run_subprocess(
            "/usr/local/bin/llama-quantize",
            gguf_path, f"/models/{model_id}-{quantization}.gguf", quantization.upper()
        )
    # 4. Publish completion event
    publish("hf.model.gguf.converted.v1", {"model_id": model_id, "gguf_path": ...})
```

**Dependency:** llama.cpp must be installed on the node running hf-mcp-server (Phase 1 step 1.1).

#### G3 — Unsloth Training Loop

**What:** Uncomment + implement the training loop in `unsloth_finetune.py`.

**Out of scope for this spec** — requires Unsloth package install (CUDA-specific, heavy dependency). Documented as a follow-on. The pipeline works without it (HF discovery → download → GGUF convert → serve → benchmark → fitness → route → eval → mint covers the non-fine-tuning path).

#### G4 — hf-research-agent → model-registry bridge

**What:** model-registry subscribes to `hf.model.evaluated.v1` and auto-registers high-scoring models as candidates.

**Implementation:** Add a NATS subscriber in `model-registry/main.py`:
```python
async def on_hf_evaluated(msg):
    data = json.loads(msg.data)
    if data["score"] > 70:  # threshold
        # Register as candidate
        await register_candidate(
            hf_id=data["model_id"],
            lane=data.get("lane", "chat"),
            signed_trail_ref=data.get("trail_ref"),
        )
```

#### G5 — AgentGym → model-registry bridge

**What:** model-registry subscribes to `agentgym.model.published.v1` and registers RL-trained models as candidates + records training fitness.

**Implementation:** Add NATS subscriber in `model-registry/main.py`:
```python
async def on_agentgym_published(msg):
    data = json.loads(msg.data)
    await register_candidate(
        hf_id=data["model_id"],
        lane="agentgym",
        signed_trail_ref=data.get("trail_ref"),
    )
    # Record training metrics as fitness
    await record_fitness(
        model_id=data["model_id"],
        source="evoswarm",
        score=data["mean_reward_normalized"],
        metrics=data["training_metrics"],
    )
```

#### G6 — `model.minted.v1` schema + publisher

**What:** Create the formal schema and wire it into the pipeline.

**Files:**
- `pmoves/contracts/schemas/model/minted.v1.schema.json` — schema
- `pmoves/contracts/topics.json` — topic registration
- publisher: model-registry, when a candidate is promoted to active

#### G7 — `archon.mint.agent.v1` in topic catalog

**What:** Add to `contracts/topics.json` with publisher/subscriber declarations.

#### G8 — `model_id` field in mint manifest

**What:** Add `model_id` (optional) to the mint-agent command + agent_registry.yaml schema.

```yaml
# In agent_registry.yaml, per-agent:
model:
  primary: "qwen3.5:35b-a3b"       # default model
  tensorzero_function: "agent_zero" # TZ function name
  fitness_threshold: 0.7            # minimum fitness to activate
```

#### G9 — Model Nexus fitness feedback loop

**What:** model-registry reads fitness scores and adjusts TensorZero variant weights.

**Implementation:**
```python
# In model-registry, periodic job:
async def rebalance_tensorzero_weights():
    # 1. Query model_fitness_records grouped by lane
    # 2. For each lane, normalize scores to [0, 1] weights
    # 3. Rewrite tensorzero.toml variant weights
    # 4. Reload TensorZero config (or signal gateway)
```

**Constraint:** TensorZero `weight` changes require config reload. Use the model-registry's existing `GET /api/tensorzero/config` endpoint (already generates TOML from DB) + add a "weight from fitness" mode.

#### G10 — Throughput-lab subject alignment

**What:** Add `llama.benchmark.*` subjects to `contracts/topics.json` + ensure model-fitness-bridge subscribes to them.

### Phase 3 — Fleet Expansion (operator-side)

**Goal:** Deploy the serving tier on Knuckles + verify cross-node benchmarking.

| Step | What | Who |
|---|---|---|
| 3.1 | Operator flashes B850 + runs `rdna4-gpu-install.sh` | Operator |
| 3.2 | `make -C pmoves rdna4-llamacpp-up` starts llama-server on :8080 | Operator or Crush on Knuckles |
| 3.3 | Optional: vLLM gfx1201 source build on Knuckles | Operator |
| 3.4 | Throughput-lab benchmarks Knuckles over Tailscale | Crush on any node |
| 3.5 | Fix Knuckles hostname drift (`pmoves-rdna4` vs `pmoves-9850x3d-r9700`) | Crush |
| 3.6 | TensorZero `llamacpp_rocm` weight flip from 0.0 → 0.3 | Crush |

---

## 6. NATS Subject Catalog (new + existing)

| Subject | Publisher | Subscriber | Status |
|---|---|---|---|
| `hf.model.discovered.v1` | hf-agent | hf-research-agent | ✅ existing |
| `hf.model.evaluated.v1` | hf-research-agent | **model-registry (G4)** | ✅ pub / ❌ no sub |
| `hf.model.downloaded.v1` | hf-mcp-server | AgentGym, evo-controller | ✅ existing |
| `hf.model.gguf.converted.v1` | **hf-mcp-server (G2)** | **model-registry** | ❌ NEW |
| `llama.benchmark.started.v1` | throughput-lab | model-fitness-bridge | ✅ pub / ❌ no sub |
| `llama.benchmark.cell.v1` | throughput-lab | model-fitness-bridge | ✅ pub / ❌ no sub |
| `llama.benchmark.completed.v1` | throughput-lab | **model-fitness-bridge (G1)** | ✅ pub / ❌ no sub |
| `agentgym.train.completed.v1` | agentgym-rl-coordinator | **model-fitness-bridge (G1)** | ✅ pub / ❌ no sub |
| `agentgym.model.published.v1` | agentgym-rl-coordinator | **model-registry (G5)** | ✅ pub / ❌ no sub |
| `model.fitness.recorded.v1` | model-registry | **model-nexus (G9)** | ✅ pub / ❌ no sub |
| `model.registry.updated.v1` | model-registry | TensorZero config reload | ✅ existing |
| `model.minted.v1` | **model-registry (G6)** | Archon, agent_registry | ❌ NEW |
| `archon.mint.agent.v1` | mint-agent command | archon-qa-agent | ⏳ stub |
| `archon.qa.result.v1` | archon-qa-agent | operator | ⏳ stub |
| `archon.mint.confirmed.v1` | operator | agent_registry reload | ⏳ stub |
| `mesh.gpu.model.loaded.v1` | gpu-orchestrator | model-registry | ✅ existing |
| `mesh.gpu.model.unloaded.v1` | gpu-orchestrator | model-registry | ✅ existing |

---

## 7. File Manifest (all changes)

### Phase 1 — Serving Tier
| File | Change |
|---|---|
| `pmoves/docker-compose.yml` | Add `vllm`, `nim`, `llama-server` services |
| `pmoves/tensorzero/config/tensorzero.toml` | Add `llamacpp_spark`, `vllm_spark`, `nim_spark` providers |
| `pmoves/mk/infra.mk` | Add `up-vllm`, `up-nim`, `up-llama-server` targets |
| `deploy/provision/spark-llamacpp-build.sh` | NEW — ARM64+CUDA llama.cpp build script |

### Phase 2 — Pipeline Gaps
| File | Change |
|---|---|
| `pmoves/services/model-fitness-bridge/app.py` | NEW — FastAPI health + config |
| `pmoves/services/model-fitness-bridge/bridge.py` | NEW — NATS sub + ClickHouse scrape + fitness API |
| `pmoves/services/model-fitness-bridge/Dockerfile` | NEW |
| `pmoves/services/hf-mcp-server/main.py` | EDIT G2 — wire GGUF convert |
| `pmoves/services/model-registry/main.py` | EDIT G4/G5 — add NATS subscribers |
| `pmoves/contracts/schemas/model/minted.v1.schema.json` | NEW G6 |
| `pmoves/contracts/topics.json` | EDIT G6/G7/G10 — add subjects |
| `.claude/commands/archon/mint-agent.md` | EDIT G8 — add model_id field |
| `pmoves/config/agent_registry.yaml` | EDIT G8 — add model block schema comment |
| `pmoves/services/model-registry/main.py` | EDIT G9 — add weight rebalance job |
| `pmoves/docker-compose.yml` | EDIT — add model-fitness-bridge service |

### Phase 3 — Fleet
| File | Change |
|---|---|
| `pmoves/config/profiles/*.yaml` | Fix Knuckles hostname drift |
| `pmoves/tensorzero/config/tensorzero.toml` | Flip `llamacpp_rocm` weight |

---

## 8. Validation Gates

| Gate | Command | Expected |
|---|---|---|
| Serving tier live | `curl :8082/v1/models && curl :8083/v1/models && curl :8084/v1/models` | 3 model lists |
| Throughput benchmark | `make llama-throughput-smoke` | PASS (tokens/sec > 0) |
| Fitness bridge live | `curl :8120/healthz` | 200 |
| Fitness event produced | After benchmark, query Supabase `model_fitness_records` | Row with score > 0 |
| NATS round-trip | `nats sub model.fitness.recorded.v1` during benchmark | Event received |
| GGUF convert | `hf.model.convert_gguf` MCP tool on small model | `.gguf` file produced |
| Agent mint with model | `/archon:mint-agent` with `model_id` field | Manifest includes model_id |

---

## 9. Dependencies + Risks

| Risk | Mitigation |
|---|---|
| llama.cpp ARM64+CUDA build may fail on GB10 (SM_121a is new) | Use community-verified build flags; fallback to Ollama-only if build fails |
| vLLM ARM64 container may be stale (community-maintained) | Pin to specific digest; build from source if container fails |
| NIM requires NGC API key for initial pull | Air-gap model: pull once while connected, run offline after |
| ClickHouse telemetry scrape may be expensive | Batch query every 5 min, not per-request |
| TensorZero weight rebalance requires config reload | Use graceful reload signal, not container restart |
| Knuckles hostname drift breaks TensorZero routing | Fix before Phase 3 |
| Unsloth not installed (G3) | Documented as follow-on; pipeline works without fine-tuning |

---

## 10. Operator Decisions Required

1. **Serving tier scope on SPARK:** Build all 3 (llama.cpp + vLLM + NIM) or start with just llama.cpp?
2. **NIM NGC API key:** Do you have an NGC key for the initial NIM container pull?
3. **Fitness bridge port:** I propose `:8120` (next after P7's `:8122`). OK?
4. **G3 Unsloth scope:** Include in this spec as follow-on, or defer to a separate lane?
5. **KVM CPU-only llama.cpp:** Skip entirely (recommended) or build minimal?
6. **Approval to proceed with implementation against this spec?**

---

## Cross-References

- `pmoves/docs/architecture/DARKMATTER_FACTORY.md` — original design vision (Stage 4-6)
- `pmoves/services/model-registry/main.py` — the live registry + fitness API
- `pmoves/services/common/model_fitness.py` — normalization + CHIT signing
- `pmoves/contracts/schemas/model/fitness.recorded.v1.schema.json` — fitness schema
- `PMOVES-llama-throughput-lab/PMOVES.AI_INTEGRATION.md` — benchmark integration plan
- `pmoves/docs/SPARK_MODEL_STRATEGY.md` — SPARK model deployment strategy
- `pmoves/docs/AGENTS/AGNOTE-pmoves-rdna4.md` — Knuckles/RDNA4 setup
- Big Ball 5090 CODEX Gap Closure (AGNOTE4482.md) — "Remaining 5090 CODEX Work" §3 model-fitness integration
