# AGNOTE4482 — AutoClaw 4090 Customization Plan

GRAPHITI_MARK: `AGNOTE4482::AUTOCLAW::4090-CUSTOMIZATION::2026-05-24`

> **Origin**: Operator session 2026-05-24 on PMOVES-4090
> **Goal**: Customize AutoClaw for the 4090 laptop node using GLM Coding Max plan + other coding plans (Ollama Pro, Alibaba, MiniMax)
> **Three-Body**: Delivery=4090-CLAUDE, Control=Operator, Memory=AGNOTE trail

---

## Phase 0: Baseline Audit ✅

### Node Profile
- **Hostname**: PMOVES-4090
- **Class**: Laptop / GPU-medium (16GB VRAM, mobile, island-capable)
- **Role**: Operator node, provider proximity (per AGNOTE4482_SITREP)
- **Branch**: `feat/w0-pr4-ghost-detector`
- **AutoClaw config**: `~/.openclaw-autoclaw/openclaw.json` (v1.3.0, `zai` provider only)

### Gaps Identified

| # | Gap | Severity | Blocking? |
|---|-----|----------|-----------|
| G1 | Only `zai` provider configured — no Ollama, MiniMax, Alibaba, Anthropic fallback | HIGH | Yes |
| G2 | Memory plugin = `none` — no persistence across sessions | HIGH | Yes |
| G3 | No PMOVES-custom skills in `~/.openclaw-autoclaw/skills/` | MEDIUM | No |
| G4 | Web search disabled (by policy) — intentional but limits research | MEDIUM | No |
| G5 | Browser disabled (by policy) — intentional but limits web automation | MEDIUM | No |
| G6 | Hermes evolution at default intensity — no node-specific tuning | LOW | No |
| G7 | SOUL.md / IDENTITY.md / USER.md / TOOLS.md are stock templates | LOW | No |
| G8 | No local Ollama models confirmed running | MEDIUM | Depends |
| G9 | AGENTS.md has unstaged autoclaw-injected blocks (2026-05-23) | MEDIUM | No |

---

## Phase 1: Multi-Provider Cascade (G1)

### Target Provider Stack

Following the AGNOTE4482 coding plan alignment policy (local-first, profile-governed, seat/token-aware):

```
Local-First Tier (Ollama)
  ├── ollama/qwen3:14b         — daily driver (fits 16GB VRAM)
  ├── ollama/qwen3-embedding:4b — embeddings
  └── ollama/llama3.2:3b       — fast/small fallback

Coding Plan Tier (Role-Bound)
  ├── zai/zai_auto             — primary (GLM auto-routing) [ALREADY ACTIVE]
  ├── zai/glm-5-turbo          — coding/review fallback [ALREADY ACTIVE]
  └── zai/glm-5.1              — max context overflow (coding plan Max)

Escalation Tier
  ├── minimax/m2.7             — token-budget overflow (1M context)
  ├── alibaba/qwen-max         — auxiliary coding lane
  └── anthropic/claude-opus    — high-trust operator review
```

### Implementation

**1a. Add Ollama provider to openclaw.json**
```json
{
  "models": {
    "providers": {
      "ollama": {
        "baseUrl": "http://localhost:11434/v1",
        "apiKey": "ollama",
        "api": "openai-completions",
        "models": [
          { "id": "qwen3:14b", "name": "Qwen3 14B", "contextWindow": 32768 },
          { "id": "llama3.2:3b", "name": "Llama 3.2 3B", "contextWindow": 8192 }
        ]
      }
    }
  }
}
```

**1b. Add MiniMax provider**
```json
{
  "models": {
    "providers": {
      "minimax": {
        "baseUrl": "https://api.minimax.chat/v1",
        "apiKey": "${MINIMAX_TOKEN_PLAN_API_KEY}",
        "api": "openai-completions",
        "models": [
          { "id": "m2.7", "name": "MiniMax M2.7", "contextWindow": 1048576 }
        ]
      }
    }
  }
}
```

**1c. Add Alibaba provider**
```json
{
  "models": {
    "providers": {
      "alibaba": {
        "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "apiKey": "${ALIBABA_CODING_PLAN_API_KEY}",
        "api": "openai-completions",
        "models": [
          { "id": "qwen-max", "name": "Qwen Max", "contextWindow": 32768 }
        ]
      }
    }
  }
}
```

**1d. Add Anthropic provider**
```json
{
  "models": {
    "providers": {
      "anthropic": {
        "baseUrl": "https://api.anthropic.com/v1",
        "apiKey": "${ANTHROPIC_API_KEY}",
        "api": "anthropic-messages",
        "models": [
          { "id": "claude-opus-4-6", "name": "Claude Opus 4.6", "contextWindow": 200000 }
        ]
      }
    }
  }
}
```

### Dependencies
- [ ] Ollama installed and running on PMOVES-4090 (verify: `ollama list`)
- [ ] Pull models: `ollama pull qwen3:14b`, `ollama pull qwen3-embedding:4b`, `ollama pull llama3.2:3b`
- [ ] API keys configured: `MINIMAX_TOKEN_PLAN_API_KEY`, `ALIBABA_CODING_PLAN_API_KEY`, `ANTHROPIC_API_KEY`
- [ ] Provider keys in env.shared or Windows env vars (NOT in openclaw.json — use `${ENV_VAR}`)

### Operator Decision Gates

| Gate | Question | Default |
|------|----------|---------|
| D1 | Which Ollama models to pull? (VRAM budget: 16GB) | qwen3:14b (primary) + qwen3-embedding:4b |
| D2 | Enable MiniMax provider? (requires Token Plan API key) | Yes, if key available |
| D3 | Enable Alibaba provider? (requires Coding Plan API key) | Yes, if key available |
| D4 | Enable Anthropic provider? (requires API key) | Yes, if key available |
| D5 | OpenClaw model routing strategy? | `zai/zai_auto` primary, Ollama local-first for non-coding |

---

## Phase 2: Memory Plugin (G2)

### Current State
```json
"plugins": { "slots": { "memory": "none" } }
```

### Target
Enable OpenClaw's built-in file-based memory for session continuity.

```json
"plugins": { "slots": { "memory": "file" } }
```

This writes to `~/.openclaw-autoclaw/memory/` — already gitignored, machine-local.

### Future: Cipher Memory
When Cipher API is reachable (currently on Z890 at port 8105), upgrade to:
```json
"plugins": { "slots": { "memory": "cipher" } }
```
Requires Cipher NATS bus to be accessible from 4090 (Tailscale mesh).

---

## Phase 3: PMOVES Custom Skills (G3)

### Target Skills

Create PMOVES-specific skills to replace generic upstream equivalents:

| Skill | Replaces | Purpose |
|-------|----------|---------|
| `pmoves-sitrep` | — | Node health check + AGNOTE4482 orientation |
| `pmoves-model-routing` | — | Multi-provider model selection per task |
| `pmoves-chit-sign` | — | CHIT trail signing for PMOVES work |
| `pmoves-pr-review` | `github-1` | PMOVES-specific PR review workflow |
| `pmoves-deploy` | `vercel-deploy-1.0.0` | PMOVES deployment (compose + sidecar) |

Each skill follows the `~/.openclaw-autoclaw/skills/<name>/SKILL.md` format and is self-contained.

---

## Phase 4: AGENTS.md + SOUL.md Customization (G7, G9)

### 4a. Review and merge AGENTS.md autoclaw-injected blocks

The 2026-05-23 autoclaw injection added sections to AGENTS.md. Review the intensity and customize for 4090:
- Hermes evolution intensity: 100% → 60% (aggressive is fine for 5090; 4090 is mobile, island-capable, should be more conservative)
- Autoclaw skill path standards
- Browser/vision agent integration docs

Branch: `feat/hermes-4090-evolution`

### 4b. Populate identity files

| File | Current | Target |
|------|---------|--------|
| `SOUL.md` | Stock AutoClaw | Customized for PMOVES operator context |
| `IDENTITY.md` | Template (empty) | Fill with persona |
| `USER.md` | Template (empty) | Fill with operator context |
| `TOOLS.md` | Template (empty) | Add PMOVES-4090 specifics (Ollama port, provider keys aliases, Tailscale mesh) |

---

## Phase 5: TAC Tree + Documentation (G6)

### Create 4090-Specific TAC Node
Add to `pmoves/configs/tac_trees/node-4090-laptop.tac.yaml`:
- Phase 7 subtree for AutoClaw customization
- Service contracts for autoglm browser/vision agents
- Multi-provider routing rules
- Memory persistence policy

### Update AGNOTE4482 Trail
- Signoff checklist: new §10 "AutoClaw Node Customization"
- Claim register: add AutoClaw 4090 entry
- Roadmap: link customization plan

---

## Phase 6: Agentic Coding Integration (Stretch)

### KiloCode GLM on 4090
Currently `.kilo/` config is designed for 5090 node (GPU inference node with 32GB VRAM). Adapt for 4090:
- Reduce VRAM-expected models
- Use `zai/glm-5-turbo` instead of `zai/glm-5.1` for coding
- Point to local Ollama for embeddings

### Three-Body Split for 4090
| Role | Agent | Tool |
|------|-------|------|
| Delivery | AutoClaw (GLM auto) | Code changes via openclaw.json + skills |
| Control | Operator (DARKXSIDE) | Review, signoff, API keys |
| Memory | AutoClaw file memory | Session continuity |

---

## Implementation Order

```
Week 1: Phases 1-2 (Provider Cascade + Memory)
  ├── Day 1: Verify Ollama, pull models
  ├── Day 2: Add Ollama provider to openclaw.json
  ├── Day 3: Add MiniMax/Alibaba/Anthropic providers
  └── Day 4: Enable file memory, verify persistence

Week 2: Phases 3-4 (Skills + Identity)
  ├── Day 1: Create pmoves-sitrep + pmoves-model-routing skills
  ├── Day 2: Create pmoves-chit-sign + pmoves-deploy skills
  ├── Day 3: Review AGENTS.md blocks, create hermes-4090-evolution branch
  └── Day 4: Populate SOUL.md / IDENTITY.md / USER.md / TOOLS.md

Week 3: Phase 5 (TAC + Docs)
  ├── Day 1: Create 4090 TAC subtree
  ├── Day 2: Update AGNOTE4482 trail
  └── Day 3: Operator signoff + merge

Week 4: Phase 6 (Stretch — Agentic Coding)
  ├── Adapt .kilo/ for 4090
  └── Test Three-Body split on 4090
```

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Ollama not installed on 4090 | Blocks Phase 1 | Install via `winget install Ollama.Ollama` |
| VRAM budget exceeded (16GB) | Models OOM | qwen3:14b (~9GB) + embedding:4b (~2.5GB) + OS (~2GB) = ~13.5GB, safe margin |
| MiniMax/Alibaba API keys unavailable | Blocks those providers | Defer to Phase 1b; proceed with Ollama + GLM only |
| Cipher Memory not reachable from 4090 | Blocks Cipher plugin | Use file memory as immediate; Cipher when Z890 mesh confirmed |
| AGENTS.md merge conflict | Blocks Phase 4 | Create branch `feat/hermes-4090-evolution` from main, apply curated blocks |
| openclaw.json syntax error | Blocks everything | Backup to openclaw.json.known-good before editing; validate with `openclaw gateway restart` |

---

## Signoff

| Agent | Role | Scope | Status | Timestamp |
|-------|------|-------|--------|-----------|
| 4090-CLAUDE | Delivery | Plan authorship, audit, Phase 1-6 spec | PENDING | — |
| OPERATOR | Control | API keys, provider decisions, merge approval | PENDING | — |
| AGNOTE4482 | Memory | Trail entry, signoff checklist update | PENDING | — |

---

## References

- `AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md` — approved coding lane inventory
- `AGNOTE4482_CLAWZ_GAP_REPORT.md` — ClaWz branch/pin reality
- `AGNOTE4482_SITREP.md` — node capacity quick reference
- `.kilo/command/autoclaw-integration.md` — 3 pending autoclaw workstreams
- `.kilo/agent/kilocode-glm.md` — 5090 KiloCode config (adapt for 4090)
- `pmoves/configs/tac_trees/node-4090-laptop.tac.yaml` — 4090 TAC tree
- `pmoves/docs/MODEL_FABRIC_CONTRACT.md` — model routing contract
- `~/.openclaw-autoclaw/openclaw.json` — current AutoClaw config
