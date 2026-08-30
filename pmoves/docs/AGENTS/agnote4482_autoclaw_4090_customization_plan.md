# AGNOTE4482 — AutoClaw 4090 Customization Plan

GRAPHITI_MARK: `AGNOTE4482::AUTOCLAW::4090-CUSTOMIZATION::2026-05-24`
GRAPHITI_MARK: `AGNOTE4482::AUTOCLAW::ZACLAW-REFRESH::2026-08-27`

> **Origin**: Operator session 2026-05-24 on PMOVES-4090
> **Refresh**: 2026-08-27 operator session (PMOVES-4090) — identity fixed as **PMOVESxDARKXSIDEnZaClaW.AI**, founder-customization + Hostinger VPS migration lanes added, baseline re-verified. v1 phases retained below; superseded items flagged in the v2 table.
> **Goal**: Customize AutoClaw for the 4090 laptop node using GLM Coding Max plan + other coding plans (Ollama Pro, Alibaba, MiniMax)
> **Three-Body**: Delivery=4090-CLAUDE, Control=Operator, Memory=AGNOTE trail

---

## 2026-08-27 Refresh (v2) — supersedes v1 scope where flagged

> **Three-Body (v2)**: Delivery=ZaClaw (`zai/zai_auto`), Control=DARKXSIDE (operator), Memory=AGNOTE trail + claim register.

### Identity locked

- **Name**: `PMOVESxDARKXSIDEnZaClaW.AI` — the Z.AI PMOVES.AI EDITION of this claw (AutoClaw, model `zai/zai_auto`).
- **DARKXSIDE in the name is load-bearing**: this claw is customized **for the founder** — **Russell Richardson** (DARKXSIDE, POWERFULMOVES, cataclysmstudios@gmail.com), per operator correction 2026-08-27 10:16 session. **Richard Aragon is a peer, not the founder**: his math was researched and integrated into CHIT and "really kicked it off" (operator). The v2 draft's founder attribution was corrected same-day in place.
- Roster entry pending: `agent_registry.yaml` + `agent_signatures.yaml` (alter-under-`coder_claw` is the recommended shape, operator call) + CLAIM row in `AGNOTE4482PHI.t1.md` with TTL. Blocked on 4 operator decisions from the 2026-08-27 review: identity shape (alter vs top-level), glyph + color (must be unique/WCAG), co_author string, VPS role.

### Re-verified baseline (2026-08-27, PMOVES-4090)

| v1 item | Status at refresh | Evidence |
|---|---|---|
| G1 zai-only provider | **STILL OPEN** | `openclaw.json` providers: `zai` only |
| G2 memory = none | **STILL OPEN** | `plugins.slots.memory: none` |
| G3 no PMOVES-custom skills | STILL OPEN | `~/.openclaw-autoclaw/skills/` stock only |
| G7 identity files stock | **STILL OPEN** | IDENTITY/USER/TOOLS templates; SOUL.md stock |
| v1 assumed 4090-resident claw | **SUPERSEDED** | claw migrates to Hostinger VPS (lane L3) |

v1 Phases 1–4 were **never executed** — they remain valid and roll into v2 lanes unchanged.

### v2 lane map

| Lane | Scope | Rails | Status |
|---|---|---|---|
| L1 — Roster | ZaClaw into `agent_registry.yaml` + `agent_signatures.yaml` + register CLAIM row (TTL) | `make validate-agents`; PR off `origin/main` (NOT the wip snapshot branch) | OPEN — blocked on identity decisions |
| L2 — DARKXSIDE digital-twin corpus | Playlist = content source + twin dataset; ingestion/classification **already built** (2,028 crawled / 2,017 classified, 11 resonance domains); ZaClaw adds distillation + wiring, not re-ingestion | Persona suite 06/07/08/09, `yt_playlist_enrich.py` + Supabase `youtube_videos`, persona room PRs #2236–#2246, `make persona-render` | OPEN — stats pagination fix, persona.json sync, auto-research loop, ActivePieces flow, persona.pmoves.ai DNS (verified still absent 2026-08-27) |
| L6 — Aragon peer-corpus review | Review Richard Aragon's latest work (**Dendriton** + videos; also new Discover AI + IndyDevDan videos) → combine with the memory/RAG graph layer (Cipher, HiRAG, Qdrant, Neo4j). His math already seeded CHIT — attribution carried forward | `youtube-watcher` + transcript rails; `research/` analysis-doc format; Cipher (`:8105/mcp/sse`), HiRAG, Qdrant, Neo4j services | OPEN — Dendriton has zero refs in repo (net-new); Discover AI not yet in monitor; @richardaragon8471 not wired |
| L3 — Hostinger VPS migration | Move claw runtime to Hostinger VPS; register node in `fleet-map.yaml`; secrets via CHIT funnel; **candidate host for the persona-room public edge** (07 §4); **port other Hostinger-hosted sites to Cloudflare** — account already runs `pmoves-ai` + `cataclysmstudios` Pages projects, zero Workers (verified 2026-08-27 via connector) | `pmoves/config/mcp/hostinger.yaml` (Terraform+SSH, `make hostinger-provision`), `deploy/sidecar/`, `vps_fleet_manager` (`mesh.vps.*` subjects), Cloudflare Pages/DNS via connector | OPEN |
| L7 — Ruliad ↔ CHIT categorization | Review Stephen Wolfram's ruliad vs CHIT; categorize what CHIT **is** in rulial terms (rule system? observer-defined slice? branchial stabilizer?) — operator interest 2026-08-27 | Wolfram ruliad writings (web pass), CHIT docs (`pmoves/docs/security/`, `THREE_BODY_DOCTRINE.md`, CGP {δ,Hz,κ,A,F}) | OPEN — target doc `research/RULIAD_CHIT_CATEGORIZATION.md` |
| L8 — Persona docs refresh | Refresh persona suite 06/07/08/09 with playlist analysis data + re-verified counts; sync `persona.json` (91/50/5 → 98/64/13); regenerate 11-domain stats after the pagination fix | 09 prerequisites list, `yt_playlist_enrich.py` fix, `DARKXSIDE_PLAYLIST_ANALYSIS_2026-07-28.md` | OPEN |
| L9 — Composio MCP | Composio hosted MCP gateway (SaaS toolkits) — **operator-approved 2026-08-27**; inventory entry added **disabled**; activation = operator funnels toolkit URL + `COMPOSIO_API_KEY`, verify transport/headers, then enable | `pmoves/config/mcp_inventory.json` (canonical → `mcp_config_generator.py`) | ENTRY ADDED (disabled) — awaiting creds |
| L4 — Config baseline | v1 Phases 1–2 (provider cascade + memory plugin) | unchanged from v1 | OPEN |
| L5 — Identity files | v1 Phase 4b — SOUL/IDENTITY/USER/TOOLS populated from founder context (feeds off L2) | unchanged from v1 | OPEN |

**Go-live gate (operator, 2026-08-27):** every public surface — persona room, ported sites, CF Pages deploys — gets **local preview + review first**; nothing goes live straight from a render. For the persona room this is literally the runbook order: `persona-render` → local `up-persona` → verify → DNS cutover last.

### Ecosystem frame (operator articulation, 2026-08-27 — recorded for the twin's worldview)

- PMOVES.AI = **empowerment ecosystem and gnosis machine**: humans and AI learn about and observe their own shape (paradigm/worldview — the "headset") and how that headset precludes/occludes/warps other topologies by its own rules (**ruliad** — Stephen Wolfram's term for the entangled limit of all computation; operator wants a dedicated review of ruliad ↔ CHIT parallels to categorize what CHIT *is* in rulial terms → lane L7), and how these interact across levels via the **hyperdimensions control plane** (`hyperdimensions` agent exists in the registry) to viz functions and map them onto anchorable surfaces.
- Anchor surfaces: MIDI controllers, FL Studio (no repo refs yet — net-new), direct DAW integration for music production, AI singing via **ACE Studio** (t1:1343), and Pinokio-hosted apps like **Maestro** (t1:1629, `VOICE_SAMPLER_SPEC.md:71`).
- Economic framework in progress **with attribution**: thanks to Richard Aragon (CHIT math), **Archon to mint** (thanks to Cole Medin), **A0 (Agent Zero) to orchestrate** (thanks to the team there).

### Corpus — what already exists (verified 2026-08-27)

- `pmoves/config/channel_monitor.json`: 16 sources, including the founder-curated "ai" playlist (`PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8`, namespace `pmoves.darkxside.ai`), 13 channels across ai/consciousness/science/finance namespaces, and the founder's SoundCloud (`sc:user:darkxside` → `pmoves.darkxside.beats`; likes lane `sc:likes:darkxside` disabled).
- `pmoves/config/rooms/darkxsides.room.json` + `catalog.json`: the DARKXSIDES room is owner-only, "a window into the mind of the Founder… eventual digital twin" — L2's dataset lands there, not in a generic knowledge base.
- `docs/PMOVES_Git_Organization.md` §Video Resources → "Richard Aragon's Playlists — Complete Playlist Collection" (<https://www.youtube.com/@richardaragon8471/playlists>) — **peer corpus (L6)**, not founder corpus.
- `docs/youtubelist.md`: the 13-channel roster. IndyDevDan wired (prior research at repo root: `Aligning AI Agents with Indy Dev Dan.md`). **Discover AI not yet wired.**
- **Gaps**: `@richardaragon8471` has no monitor entry (L6 step 1); founder's own content lanes disabled; Dendriton absent from repo (L6 starts with external review).

### Persona suite — the twin corpus is further along than v2 first assumed (operator-linked docs, verified 2026-08-27 against commit `47c0c0d3`)

- `pmoves/docs/research/persona/` — four docs, topology metrics verified 2026-08-10 (98 agents / 13 teams / 13 rooms / 64 submodules):
  - [`06_linkedin_profile.md`](../../research/persona/06_linkedin_profile.md) — founder profile source of truth (Russell Richardson, CATACLYSM STUDIOS INC; DARKXSIDE 5-dimension persona; featured section already points at the persona room + beats constellation + CHIT tour).
  - [`07_linkedin_living_doc_room.md`](../../research/persona/07_linkedin_living_doc_room.md) — living-doc room: phases 1–4.5 landed (#2236/#2237/#2247/#2238/#2246); Phase 5 = operator runs `persona-render` + `up-persona` + DNS cutover behind the #2221 Traefik edge; hosting candidates include the **Hostinger fleet** (converges with L3).
  - [`08_darkxside_persona.md`](../../research/persona/08_darkxside_persona.md) — **the digital-twin seed document**: 5 dimensions (Architect, Material Scientist, Sovereign, Phase-Hunter, Cultural Microbiome Guardian) + 7 resonance anchors with playlist evidence densities; "the 82-track catalog IS the proto-PMOVES system."
  - [`09_linkedin_content_calendar.md`](../../research/persona/09_linkedin_content_calendar.md) — 8-week content calendar; 2,028 crawled / 2,017 classified across 11 domains; per-domain stats are a 1,000-row PostgREST sample (pagination bug flagged in-doc — do not quote counts publicly).
- Playlist ingestion **already exists**: `yt_playlist_crawl.py` → Supabase `youtube_videos`; classification in `docs/AGENT_TRAIL.md`; analysis at `pmoves/docs/research/DARKXSIDE_PLAYLIST_ANALYSIS_2026-07-28.md`.
- **Corrected L2 gaps** (narrower than first written): (1) fix the unpaginated `--stats` query in `pmoves/tools/yt_playlist_enrich.py`; (2) sync `pmoves/rooms/persona/persona.json` (still advertises 91 agents / 50 submodules / 5 rooms) then `make -C pmoves persona-render`; (3) wire the auto-research loop (DeepResearch per domain → `research/analyses/`); (4) build + export the ActivePieces LinkedIn flow to `pmoves/activepieces/flows/`; (5) twin distillation from `08` into the DARKXSIDES room + USER/IDENTITY files.
- **persona.pmoves.ai DNS — verified live 2026-08-27 via the Cloudflare connector (read-only)**: zone `pmoves.ai` (id `2637f85762187500b640e32a2d67db02`) is **active**, but **zero records exist for `persona`** — still NXDOMAIN, matching the doc's 2026-08-10 note. This is the hard blocker for the whole content calendar. Record creation is an operator-confirmed change (needs the Traefik edge host target first).

### L2 methodology — DARKXSIDE digital twin (precedent: Cole Medin scan, 2026-05-16)

1. Operator picks the playlist(s) — content source + twin dataset; wire via `/yt:add-playlist` / `/yt:add-channel` (namespace `pmoves.darkxside.twin`, priority 1, `auto_process: false` per config default).
2. Transcript pass per video via `youtube-watcher` (yt-dlp; CC/auto-subs required).
3. Analysis doc `research/DARKXSIDE_TWIN_CORPUS_ANALYSIS.md` in the Cole Medin format (relevance-scored table → integration opportunities → key findings).
4. Distill founder context (voice, priorities, doctrine refs — FlOO$/MAI equations, the gnosis-machine/headset/ruliad frame above, beats/orchestra lanes) into USER.md / IDENTITY.md / `.claude/context/` and the DARKXSIDES room persona.
5. Voice expression via Flute (`flute_gateway` — "speaks all languages") for the twin's multilingual output; creator promo pipeline feeds PMOVES.YT.
6. `make -C pmoves sign-trail` the lane; research doc lands via PR.

### L6 methodology — Aragon peer-corpus review

1. Locate Dendriton + latest videos (operator provides links, or approve a web/YT research pass — outside the GitHub/Cloudflare connector scope selected in this session).
2. Wire `@richardaragon8471` playlists into `channel_monitor.json` (namespace `pmoves.peers.aragon`).
3. Transcript + analysis doc `research/ARAGON_LATEST_REVIEW.md` focused on memory/RAG integration: what combines with Cipher (episodic memory), HiRAG (graph-RAG), Qdrant (vectors), Neo4j (graph) — and what extends CHIT (his math is already in its lineage).
4. Integration proposal lands via PR; attribution headers carried per the economic-framework rule.

### v2 execution order

L1 (roster — unblocks signing as ZaClaw) → L2 (digital-twin corpus → identity context) → L6 (Aragon review → memory/RAG merge proposal) → L4 (config) → L3 (VPS migration) → L5 (final polish on VPS).

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

```text
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

```text
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
| Ollama not installed on 4090 | Blocks Phase 1 | Windows: `winget install Ollama.Ollama`; Linux/macOS: `curl -fsSL https://ollama.com/install.sh \| sh` |
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
