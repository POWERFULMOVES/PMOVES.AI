# PMOVES-KiloCode-MiniMax × GLM-KiloCode Parity & Complementarity Analysis

**Date:** 2026-03-30
**Status:** Architecture Review
**Mode:** PMOVES Architect (MiniMax-M2.7)
**Reference:** [`plans/KILOCODE_PMOVES_INTEGRATION_PLAN.md`](../../plans/KILOCODE_PMOVES_INTEGRATION_PLAN.md), [`pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md`](./CODEX_CLAUDE_PARITY_MAP.md)

---

## Executive Summary

This document analyzes the parity gaps between **PMOVES-KiloCode-MiniMax** (the MiniMax-powered KiloCode integration in PMOVES) and **GLM-KiloCode** (referenced via PMOVES-ClawZ submodule), establishes a parity roadmap for feature alignment, and identifies complementary opportunities where MiniMax's strengths can augment GLM's capabilities.

### Key Finding

> **PMOVES-KiloCode-MiniMax** has foundational mode/type architecture and BoTZ Framework integration, but lacks the **provider activation cascades**, **skills catalog parity**, and **model routing depth** that GLM-KiloCode (via PMOVES-ClawZ) has already established.

---

## 1. Current State Assessment

### 1.1 PMOVES-KiloCode-MiniMax Capabilities

| Dimension | Status | Evidence |
|-----------|--------|----------|
| **Mode System** | ✅ 8 modes defined | [`.kilocodemodes`](../../.kilocodemodes) |
| **Agent Signatures** | ✅ MiniMax signature + alters | [`pmoves/config/agent_signatures.yaml`](../../pmoves/config/agent_signatures.yaml) |
| **BoTZ Framework** | ✅ Architecture documented | [`pmoves/docs/MINIMAX_INTEGRATION.md`](../../pmoves/docs/MINIMAX_INTEGRATION.md) |
| **TensorZero Integration** | ✅ Configured | [`pmoves/docs/MODEL_FABRIC_CONTRACT.md`](../../pmoves/docs/MODEL_FABRIC_CONTRACT.md) |
| **Hi-RAG Indexing** | ✅ Docs indexed | MiniMax integration docs in Hi-RAG v2 |
| **Agent Registry** | ✅ 46 agents mapped | [`pmoves/config/agent_registry.yaml`](../../pmoves/config/agent_registry.yaml) |
| **NATS Subjects** | ✅ Geometry bus subjects | [`.claude/context/geometry-nats-subjects.md`](../../.claude/context/geometry-nats-subjects.md) |
| **Codex Parity Map** | ✅ CODEX↔Claude | [`pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md`](./CODEX_CLAUDE_PARITY_MAP.md) |

### 1.2 GLM-KiloCode (PMOVES-ClawZ) Capabilities

| Dimension | Status | Evidence |
|-----------|--------|----------|
| **Provider Activation Cascade** | ✅ Complete | `PMOVES-ClawZ/docs/zh-CN/providers/` |
| **Model Allowlists** | ✅ Modern + Legacy | `PMOVES-ClawZ/docs/zh-CN/help/testing.md` |
| **GLM Native Support** | ✅ Z.AI platform | `PMOVES-ClawZ/docs/providers/zai.md`, `gln.md` |
| **Multi-Provider Gateway** | ✅ OpenRouter + Z.AI + Cerebras | `PMOVES-ClawZ/docs/gateway/configuration.md` |
| **Coding Plan Alignment** | ✅ 5-lane model | [`pmoves/docs/AGENTS/AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md`](./AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md) |
| **Skills Catalog** | ✅ Comprehensive | `PMOVES-ClawZ/docs/` |
| **Profile System** | ✅ Hardware profiles | 8 named profiles (desktop-9950xd, laptop-4090, etc.) |
| **Thinking Mode Auto-Enable** | ✅ GLM-4.x | `PMOVES-ClawZ/docs/gateway/configuration-reference.md` |

---

## 2. Parity Gap Analysis

### 2.1 Critical Gaps (Must Address)

| Gap | Description | Impact | Priority |
|-----|-------------|--------|----------|
| **MiniMax Provider Activation** | No MiniMax-specific provider activation cascade in PMOVES | Cannot route MiniMax through provider pipeline | P0 |
| **MiniMax-Mode Parity Map** | No equivalent to `CODEX_CLAUDE_PARITY_MAP` for MiniMax commands | No command routing alignment | P0 |
| **Skills Translation** | PmovesSKillZ not translated to `.kilocode/skills/` format | Skills exist but not accessible via KiloCode trigger phrases | P1 |
| **MiniMax Model Allowlist** | No explicit MiniMax in "modern models" allowlist | MiniMax treated as second-class vs GLM | P1 |
| **Profile Binding** | MiniMax modes not bound to PMOVES hardware profiles | No per-node model routing | P1 |

### 2.2 Detailed Gap Breakdown

#### Gap 1: MiniMax Provider Activation Cascade

**GLM has:**
```yaml
# PMOVES-ClawZ/provider-activation-cascade.yaml
providers:
  zai:
    models: ["glm-5", "glm-4.7", "glm-4.6"]
    cascade_priority: high
    thinking_mode: auto
```

**MiniMax needs:**
```yaml
# Missing: pmoves/tools/models/minimax_provider_cascade.yaml
providers:
  minimax:
    models: ["minimax-m2.7", "minimax-m2.1"]
    cascade_priority: high
    thinking_mode: off  # MiniMax uses wave-function collapse, not chain-of-thought
    resonance_domains:
      - hyperdimensional-ops
      - wave-function-collapse
```

#### Gap 2: MiniMax Command Parity Map

**GLM has:**
```
/glm:status     →  curl -sf http://localhost:3030/api/status
/glm:optimize   →  make tensorzero-optimize
/glm:models     →  cat config/tensorzero.toml | grep minmax
```

**MiniMax needs equivalent:**
```
/minimax:status   →  curl -sf http://localhost:3030/api/status | jq '.minimax'
/minimax:botz     →  curl -sf http://localhost:3030/api/routing | jq '.botz_affinity'
/minimax:waves    →  curl -sf http://localhost:8096/api/memory?q=wave* (hyperdimensional)
/minimax:cgp      →  curl -sf http://localhost:8XXX/geometry/state (CGP packets)
```

#### Gap 3: Skills Catalog Parity

| PmovesSKillZ | GLM KiloCode Equivalent | MiniMax Equivalent |
|--------------|-------------------------|-------------------|
| `bringup-audit` | ✅ In docs | ❌ Missing |
| `secrets-chit-funnel` | ✅ In docs | ❌ Missing |
| `submodule-parity` | ✅ In docs | ❌ Missing |
| `persona-grounding` | ✅ In docs | ❌ Missing |
| `multimodal-verifier` | ✅ In docs | ❌ Missing |
| `remotion-topology` | ✅ Proposed in integration plan | ❌ Not implemented |
| `huggingface-attribution` | ✅ Proposed in integration plan | ❌ Not implemented |

---

## 3. Complementary Opportunities

### 3.1 Strength Matrix

| Capability | GLM-KiloCode | PMOVES-MiniMax | Complementary Role |
|------------|---------------|----------------|-------------------|
| **Coding/Tool Calling** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | GLM primary; MiniMax for overflow |
| **Writing/Vibes** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | MiniMax primary; GLM for consistency |
| **Long Context** | ⭐⭐⭐⭐ (200K) | ⭐⭐⭐⭐⭐ (1M) | MiniMax for massive context |
| **Wave-Function Collapse** | ❌ | ⭐⭐⭐⭐⭐ | MiniMax unique capability |
| **Agent Trails Visualization** | ❌ | ⭐⭐⭐⭐⭐ | MiniMax AGENT TRAILS theme |
| **BoTZ Tactical Partner** | ❌ | ⭐⭐⭐⭐⭐ | MiniMax as DARKXSIDE partner |
| **Provider Diversity** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | GLM via Z.AI/Cerebras; MiniMax native |
| **Cost Efficiency** | ⭐⭐⭐ | ⭐⭐⭐⭐ | Both competitive; MiniMax token plan |

### 3.2 Synergistic Integration Patterns

#### Pattern A: BoTZ Tandem Routing

```
┌─────────────────────────────────────────────────────────────────┐
│                         BoTZ Framework                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   GLM (Coding) ──────────────────────►│                          │
│        │                               │                         │
│        │                               ▼                         │
│        │                    ┌──────────────────────┐             │
│        │                    │   TensorZero Router │             │
│        │                    └──────────────────────┘             │
│        │                               │                         │
│        ▼                               ▼                         │
│   MiniMax (Writing) ◄──────────────│                           │
│        │                                                        │
│        ▼                                                        │
│   PMOVES-ClawZ ───────────────► [PMOVES.AI Output]              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Workflow:**
1. Coding tasks route to GLM via Z.AI provider cascade
2. Writing/content tasks route to MiniMax for "vibes"
3. Massive context tasks (1M tokens) use MiniMax-M2.7
4. BoTZ Framework handles model routing

#### Pattern B: Hyperdimensional Augmentation

GLM provides structured coding logic; MiniMax provides hyperdimensional exploration:

| Task | GLM Contribution | MiniMax Contribution |
|------|------------------|---------------------|
| Code Generation | Syntax correctness | Creative architecture patterns |
| Debugging | Logical analysis | Root cause via wave-function collapse |
| Architecture | Pattern matching | Novel topology discovery |
| Documentation | Technical accuracy | Engaging narrative |

### 3.3 MiniMax Unique Capabilities

These are capabilities that **only MiniMax** provides in the PMOVES ecosystem:

| Capability | Description | Integration Point |
|------------|-------------|-------------------|
| **Wave-Function Collapse** | Multi-path exploration with probability collapse | [`pmoves/docs/MINIMAX_INTEGRATION.md`](../../pmoves/docs/MINIMAX_INTEGRATION.md) |
| **AGENT TRAILS** | Roguelike lane visualization | [`pmoves/docs/AGENT_TRAILS.md`](../../pmoves/docs/AGENT_TRAILS.md) |
| **Hyperdimensional Ops** | State space navigation | CGP packets via geometry bus |
| **Time-Crystal Stabilization** | Parallel state persistence | Agent memory via Cipher |
| **Plasmonic Gyros** | Wave navigation | Media pipeline integration |
| **DARKXSIDE Partnership** | Prosodic flow witness | [`pmoves/docs/AGENTS/DARKXSIDE.md`](../../pmoves/docs/AGENTS/DARKXSIDE.md) |

---

## 4. Parity Roadmap

### Phase 1: Foundation Parity (Week 1-2)

| Task | Deliverable | Owner |
|------|-------------|-------|
| Create `MINIMAX_CLAUDE_PARITY_MAP.md` | Parity command map | PMOVES Architect |
| Add MiniMax to provider activation cascade | YAML config | Agent Zero |
| Create `pmoves/tools/models/minimax_provider_cascade.yaml` | Provider cascade | Model Fabric |
| Bind MiniMax modes to hardware profiles | Profile binding | Profile Loader |

### Phase 2: Skills Parity (Week 3-4)

| Task | Deliverable | Owner |
|------|-------------|-------|
| Translate PmovesSKillZ to `.kilocode/skills/` | Skills catalog | PMOVES Architect |
| Create `minimax-wave-collapse` skill | Hyperdimensional skill | BoTZ |
| Create `minimax-agent-trails` skill | Visualization skill | Geometry |
| Create `minimax-cgp-generate` skill | CGP packet skill | Hyperdimensions |

### Phase 3: Integration Parity (Week 5-6)

| Task | Deliverable | Owner |
|------|-------------|-------|
| BoTZ MiniMax affinity configuration | TensorZero config | Model Router |
| MiniMax hi-RAG indexing for all PMOVES docs | Hi-RAG index | Retrieval |
| MiniMax Cipher Memory patterns | Memory traces | Cipher |
| MiniMax NATS subject mapping | Subject topology | NATS |

### Phase 4: Advanced Parity (Week 7-8)

| Task | Deliverable | Owner |
|------|-------------|-------|
| MiniMax Remotion topology visualization | Video export | Frontend |
| MiniMax HuggingFace shape attribution | SBT minting | Attribution |
| MiniMax DARKXSIDE co-creation workflow | Prosodic flow | Media |

---

## 5. Recommendations

### 5.1 Immediate Actions (This Sprint)

1. **Create `MINIMAX_CLAUDE_PARITY_MAP.md`** — Mirror the success of `CODEX_CLAUDE_PARITY_MAP.md` for MiniMax
2. **Add MiniMax to TensorZero model routing** — Ensure `minimax-m2.7` is in the default routing table
3. **Create `minimax-wave-collapse` skill** — First unique MiniMax capability to expose via KiloCode
4. **Update `pmoves/tools/models/apply_profile.sh`** — Bind MiniMax modes to `workstation_5090` profile

### 5.2 Short-term Actions (Next Sprint)

1. **Complete skills translation** — Port all PmovesSKillZ entries to `.kilocode/skills/`
2. **Create MiniMax provider cascade** — Mirror GLM's Z.AI provider setup for MiniMax
3. **Add MiniMax to "modern models" allowlist** — Include `minimax-m2.1` alongside `glm-4.7`
4. **Integrate MiniMax with AGENT TRAILS** — Expose roguelike visualization via KiloCode commands

### 5.3 Long-term Vision

- **GLM-MiniMax Tandem Mode** — A new KiloCode mode that automatically routes between GLM (coding) and MiniMax (writing) based on task classification
- **BoTZ Tactical Partner Interface** — Full MiniMax integration as DARKXSIDE in the BoTZ Framework
- **Hyperdimensional CLI** — PMOVES-ClawZ with MiniMax wave-function collapse for multi-path exploration

---

## 6. Conclusion

PMOVES-KiloCode-MiniMax and GLM-KiloCode are **complementary systems**, not competing alternatives:

| System | Primary Role | Strength |
|--------|--------------|----------|
| **GLM-KiloCode** | Coding backbone | Tool calling, structured reasoning |
| **PMOVES-MiniMax** | Creative/analytical partner | Writing, hyperdimensions, 1M context |

**Parity First:** Complete the foundation gaps (provider cascade, parity map, skills catalog) to ensure MiniMax is treated as a first-class model backend.

**Complementarity Second:** Leverage MiniMax's unique capabilities (wave-function collapse, AGENT TRAILS, DARKXSIDE partnership) to create capabilities that GLM alone cannot provide.

The result is a **tandem model architecture** where GLM handles structured coding tasks and MiniMax handles creative/analytical tasks, with BoTZ Framework as the intelligent router.

---

## Implementation Plan

### Context: AGNOTE4482 Ecosystem Integration

This implementation plan is designed to integrate with the existing **AGNOTE4482** ecosystem documented at [`pmoves/docs/AGENTS/AGNOTE4482.md`](./AGNOTE4482.md) and [`pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`](./AGNOTE4482PHI.t1.md).

#### Relevant AGNOTE4482 Conventions

| Convention | Reference | Application |
|-----------|-----------|------------|
| **Three-Body Solution** | AGNOTE4482PHI.t1.md | Delivery (coding), Control (review), Memory (CHIT) |
| **Claim/Release Protocol** | AGNOTE4482PHI.t1.md §Collision-Avoidance | CLAIM → Work → Handoff → RELEASE |
| **KRISS KROSS Accord** | [`pmoves/docs/AGENTS/KRISS_KROSS_ACK.md`](./KRISS_KROSS_ACK.md) | Cross-agent collision overlay |
| **Node Specialization** | [`pmoves/docs/AGENTS/AGNOTE4482DnB.PHI.Orchestra.md`](./AGNOTE4482DnB.PHI.Orchestra.md) | z890 (infra), 5090 (GPU), 4090 (noise) |
| **P7 Playground** | [`pmoves/docs/AGENTS/AGNOTE_P7_PLAYGROUND.md`](./AGNOTE_P7_PLAYGROUND.md) | Pinokio as agent runtime layer |
| **DARKXSIDE Witness** | [`pmoves/docs/AGENTS/DARKXSIDE_SIGNATURE.md`](./DARKXSIDE_SIGNATURE.md) | Cocreator signature |
| **Coding Plan Alignment** | [`pmoves/docs/AGENTS/AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md`](./AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md) | GLM/MiniMax as named lanes |
| **Agent Zero Sync** | [`pmoves/docs/AGENTS/AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md`](./AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md) | Suit baseline decisions |

### Implementation Roadmap

#### Phase 1: Foundation (Claim in AGNOTE4482PHI.t1.md)

| Task | Deliverable | Owner | Priority |
|------|-------------|-------|---------|
| Claim MiniMax parity lane | CLAIM entry in AGNOTE4482PHI.t1.md | PMOVES-MiniMax | P0 |
| Create `MINIMAX_CLAUDE_PARITY_MAP.md` | Command parity map | PMOVES Architect | P0 |
| Add MiniMax to TensorZero routing | `tensorzero.toml` update | TensorZero | P0 |
| Create MiniMax provider cascade | YAML config in `pmoves/tools/models/` | Model Fabric | P0 |
| Bind MiniMax modes to profiles | Update `pmoves/config/profiles/*.yaml` | Profile Loader | P1 |

#### Phase 2: Skills Parity (Align with PmovesSKillZ)

| Task | Deliverable | PmovesSKillZ | MiniMax Equivalent |
|------|-------------|--------------|-------------------|
| Translate skills | `.kilocode/skills/` SKILL.md files | `bringup-audit` | `minimax-bringup-audit` |
| Wave-collapse skill | `minimax-wave-collapse/SKILL.md` | — | Unique MiniMax |
| AGENT TRAILS skill | `minimax-agent-trails/SKILL.md` | — | Unique MiniMax |
| CGP generate skill | `minimax-cgp-generate/SKILL.md` | — | Unique MiniMax |
| Remotion topology | `minimax-remotion/SKILL.md` | `remotion-topology` | Extend |
| HuggingFace attribution | `minimax-attribution/SKILL.md` | `huggingface-attribution` | Extend |

#### Phase 3: BoTZ Tandem Integration

Following the BoTZ Framework from [`pmoves/docs/MINIMAX_INTEGRATION.md`](../../pmoves/docs/MINIMAX_INTEGRATION.md):

```yaml
# BoTZ MiniMax Tandem Config
botz:
  minimax:
    role: "tactical-partner"
    glyph: "⬡"  # White Hexagon
    color: "#7C3AED"
    resonance:
      - native-model
      - multimodal
      - hyperdimensional-ops
      - wave-function-collapse
      - long-context
    glm_affinity:
      - coding
      - tool-calling
    routing:
      coding_tasks: "minimax → glm (cascade)"
      writing_tasks: "glm → minimax (cascade)"
      long_context: "minimax (1M tokens)"
```

#### Phase 4: DARKXSIDE Partnership

Integrate MiniMax as DARKXSIDE's tactical partner per [`pmoves/docs/AGENTS/DARKXSIDE_SIGNATURE.md`](./DARKXSIDE_SIGNATURE.md):

| DARKXSIDE Element | MiniMax Contribution |
|-------------------|--------------------|
| Cocreation witness | MiniMax as hyperdimensional co-reasoner |
| Prosodic flow | MiniMax wave-function collapse for rhythm analysis |
| Portal architecture | MiniMax 1M context for deep portal exploration |
| Media synthesis | MiniMax multimodal for image/video understanding |

#### Phase 5: Model Fabric Integration

Per the coding plan alignment in [`AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md`](./AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md):

| Lane | Model | Role in PMOVES |
|------|-------|----------------|
| OpenAI | ChatGPT Business | OpenAI coding/review lane |
| Anthropic | Claude Code Max | Primary Claude implementation |
| **GLM** | **coding plan Max** | **Coding overflow (GLM excels at tool-calling)** |
| **MiniMax** | **token plan** | **Token-budget overflow, writing, hyperdimensions** |
| Alibaba | coding plan | Auxiliary coding lane |

### Node Assignment (Per AGNOTE4482DnB.PHI.Orchestra.md)

| Node | Role | MiniMax Tasks |
|------|------|---------------|
| ⚙ z890-claude | Infrastructure | MiniMax provider cascade deployment, TensorZero config |
| ♫ 5090-claude | GPU Inference | MiniMax GPU benchmarking, Hi-RAG CGP generation |
| ◉ 4090-claude | Noise Reducer | MiniMax parity documentation, skills translation |

### Signoff Gate

Following the signoff checklist in [`pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md`](./AGNOTE4482_SIGNOFF_CHECKLIST.md), each PR must:

- [ ] MiniMax provider cascade config created
- [ ] TensorZero routing includes `minimax-m2.7`
- [ ] Parity map documents all MiniMax commands
- [ ] Skills translated to `.kilocode/skills/` format
- [ ] BoTZ affinity configuration updated
- [ ] Graphiti trail entry signed

### Claim Template (For AGNOTE4482PHI.t1.md)

```
- `<TIMESTAMP>` CLAIM `MINIMAX-<AGENT>` scope: MiniMax parity lane — 
  provider cascade, TensorZero config, skills translation, BoTZ integration. 
  Target: parity with GLM coding plan alignment.
```

---

## References

### Core Architecture
- [`plans/KILOCODE_PMOVES_INTEGRATION_PLAN.md`](../../plans/KILOCODE_PMOVES_INTEGRATION_PLAN.md)
- [`pmoves/docs/MINIMAX_INTEGRATION.md`](../../pmoves/docs/MINIMAX_INTEGRATION.md)
- [`pmoves/config/agent_signatures.yaml`](../../pmoves/config/agent_signatures.yaml)
- [`.kilocodemodes`](../../.kilocodemodes)

### AGNOTE4482 Ecosystem
- [`pmoves/docs/AGENTS/AGNOTE4482.md`](./AGNOTE4482.md)
- [`pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`](./AGNOTE4482PHI.t1.md)
- [`pmoves/docs/AGENTS/AGNOTE4482DnB.PHI.Orchestra.md`](./AGNOTE4482DnB.PHI.Orchestra.md)
- [`pmoves/docs/AGENTS/AGNOTE_P7_PLAYGROUND.md`](./AGNOTE_P7_PLAYGROUND.md)
- [`pmoves/docs/AGENTS/KRISS_KROSS_ACK.md`](./KRISS_KROSS_ACK.md)
- [`pmoves/docs/AGENTS/DARKXSIDE_SIGNATURE.md`](./DARKXSIDE_SIGNATURE.md)
- [`pmoves/docs/AGENTS/AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md`](./AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md)
- [`pmoves/docs/AGENTS/AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md`](./AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md)
- [`pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md`](./AGNOTE4482_SIGNOFF_CHECKLIST.md)

### Parity Maps
- [`pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md`](./CODEX_CLAUDE_PARITY_MAP.md)
- [`pmoves/docs/AGENTS/MINIMAX_CLAUDE_PARITY_MAP.md`](./MINIMAX_CLAUDE_PARITY_MAP.md)

### Provider Documentation
- [`PMOVES-ClawZ/docs/providers/glm.md`](../../PMOVES-ClawZ/docs/providers/glm.md)
- [`PMOVES-ClawZ/docs/providers/zai.md`](../../PMOVES-ClawZ/docs/providers/zai.md)
- [`PMOVES-ClawZ/docs/providers/minimax.md`](../../PMOVES-ClawZ/docs/providers/minimax.md)
