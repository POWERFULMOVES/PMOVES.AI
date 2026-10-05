# HyPeRAGInTZ Moniker — Integrated Fabric Design

> **GRAPHITI_MARK:** DARKXSIDE::HYPERAGINTZ-MONIKER-DESIGN::2026-10-05
> **Status:** DESIGN — research/worktree-only, awaiting operator scope pick
> **Worktree:** `PMOVES.AI-research-hyperagintz-moniker-design-2026-10-05` on `research/hyperagintz-moniker-design-2026-10-05`
> **Author:** 5090-claude (Mavis on the 5090 / POWERFULMOVES)
> **Companion:** `pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md` (metal-organic framework thesis), `pmoves/docs/architecture/PMOVES_GRAND_CONVERGENCE.md`, `pmoves/docs/architecture/DAMAGE_CONTROL_STRUCTURED_POLICY_RFC.md`

---

## Thesis

**HyPeRAGInTZ** (moniker, named 2026-09-17 in `pmoves/docs/AGENTS/AGNOTE4482.md:1684`) is **the integrated fabric** — harness + config + model support + PMOVES.AI integration — with Hi-RAG v2 and Cipher as first-class organs, governed by the Registry catalogs. **HyPeRAGInT** (singular) is a **per-agent identity** at "level-11 / Spynel framing / post-4090-claude" (per `pmoves/docs/architecture/DAMAGE_CONTROL_STRUCTURED_POLICY_RFC.md:280-284`). Neither exists yet as code/config — only as named concept.

This document maps the **six-piece architecture** that makes HyPeRAGInTZ real, and proposes a **slice plan** that lands each piece as its own PR/PR-series without breaking the no-SDK-hijack, no-Mavis-overlay-by-default principle the operator committed on 2026-10-03.

---

## Current State (what's broken on the 5090 today)

| # | Symptom | Root cause | Where |
|---|---------|-----------|--------|
| 1 | `claude-pmoves` cannot load MiniMax models cleanly | Launcher's `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` blocklist (`deploy/provision/claude-pmoves.ps1:17-19, 24`) strips the SDK-routed keys, so the settings.json `modelPicker` entries (`MiniMax-M3[1m]`) point at a base URL the process env doesn't have | Live on 5090 |
| 2 | `~/.claude/settings.json:5-8, 13-32` is hijacked by the Mavis SDK with `ANTHROPIC_MODEL: MiniMax-M3[1m]` + `modelPicker.replaceBuiltInOptions: true` | Mavis SDK (~2026-09-10) injects these on every Claude Code launch; the env-strip lane (PR #3149) couldn't reach `settings.json` (only process env) | Live on 5090 |
| 3 | `MiniMax Code` is `status: available` in `pmoves/configs/acp_registry_map.json:185-190` — not `linked` | No PMOVES integration has touched the ACP registry entry; the link field (`pmoves: "kilocode_glm"` pattern from `kilo`) is unset | Repo state |
| 4 | Only `kilo` is `status: linked` out of ~50 ACP entries | Single-organ integration; PMOVES uses GLM as the only first-class agent; everything else (Claude, Codex, MiniMax, Kimi, Gemini, etc.) is "available but not adopted" | Repo state |
| 5 | Cipher mindmap (L1 per-node Neo4j + Cipher API :8105) is built per `HERMES_CIPHER_LOCAL_ARCHITECTURE.md` — but the HyPeRAGInT identity has no entrypoint that ensures Cipher reachability before exec | No launcher binding | Repo state |
| 6 | Hi-RAG v2 (L3 document retrieval) is wired at `http://localhost:8086` (or `http://${TS_Z890}:8086`) — but no agent boot path exercises it | No launcher binding | Repo state |
| 7 | `PMOVES-MiniMaXX-AGInT` exists as a draft shell ("A minimal yet professional single agent demo project that showcases the core execution pipeline") but is not yet the HyPeRAGInT fork | Org repo state | GitHub |

---

## The Six-Piece Architecture

Each piece is a **distinct PR or PR-series**. None of them hijack Claude Code on its own; they compose into a single HyPeRAGInT identity that is opt-in.

```
                  ┌──────────────────────────────────────────────────────┐
                  │ HyPeRAGInT identity (per-node, level-11, post-4090) │
                  │   pmoves/configs/agents/forms/hyperagint.yaml      │
                  └──────────────┬───────────────────────────────────────┘
                                 │
            ┌────────────────────┼─────────────────────┐
            │                    │                     │
            ▼                    ▼                     ▼
    ┌───────────────┐   ┌──────────────────┐   ┌──────────────────┐
    │ 1. Launcher   │   │ 3. Cipher        │   │ 5. PMOVES        │
    │    shim       │   │    mindmap (L1)  │   │    integration   │
    │               │   │                  │   │    contract      │
    │ claude-pmoves-│   │ Neo4j + Cipher   │   │ compose/         │
    │ mavis.{sh,ps1}│   │ :8108           │   │ models/         │
    │ + per-node    │   │ writes to local  │   │ n8n/flows/      │
    │ variants      │   │ Neo4j (L1) +     │   │ events/         │
    │               │   │ fleet sync      │   │ secrets/        │
    │ (transient    │   │ (L2 via Z890) │   │ auth/            │
    │  env overlay) │   │                  │   │                  │
    └───────┬───────┘   └────────┬─────────┘   └────────┬─────────┘
            │                    │                     │
            ▼                    ▼                     ▼
    ┌───────────────┐   ┌──────────────────┐   ┌──────────────────┐
    │ 2. ACP        │   │ 4. Hi-RAG v2     │   │ 6. miniagent     │
    │    registry   │   │    (L3 docs)     │   │    spawn         │
    │               │   │                  │   │                  │
    │ pmoves/configs│   │ Qdrant + Hi-RAG  │   │ Archon creates   │
    │ /acp_registry_│   │ gateway :8086 │   │ sub-agents via   │
    │ map.json →    │   │ per-node        │   │ scoped HyPeRAGInT│
    │ status:       │   │ document index   │   │ instances; each  │
    │ linked        │   │                  │   │ miniagent is an │
    │               │   │                  │   │ ACP entry under │
    │ PMOVES-       │   │                  │   │ HyPeRAGInTZ     │
    │ registry PR   │   │                  │   │                  │
    └───────────────┘   └──────────────────┘   └──────────────────┘
```

### 1. Launcher shim (`claude-pmoves-mavis`)

**Goal:** Vanilla `claude-pmoves` stays clean (Claude Max by default); a new `claude-pmoves-mavis` and per-node `-mavis` variants apply a **transient env overlay only** (no settings.json write).

| Item | Where |
|------|-------|
| Source of truth for the overlay | `pmoves/configs/claude_settings/minimax.json` (from PR #3184, canonical) |
| Bash launcher | `deploy/provision/claude-pmoves-mavis.sh` (NEW, ~50 lines) |
| PowerShell launcher | `deploy/provision/claude-pmoves-mavis.ps1` (NEW, ~60 lines) |
| Windows wrapper | `deploy/provision/claude-pmoves-mavis.cmd` (NEW, ~5 lines) |
| 5090 identity + overlay | `deploy/provision/claude-pmoves-5090-mavis.{sh,ps1,cmd}` (NEW) |
| Tests | `pmoves/tools/tests/test_claude_pmoves_mavis.py` (NEW, 6 tests: env-overlay, no-settings-json-write, node-id-pin, no-blocklist-when-mavis, mavis-overlay-strips-when-default, node-id-precedence) |
| LEARNINGS | `pmoves/docs/AGENTS/claude_pmoves_mavis_launcher_LEARNINGS.md` (NEW, 4-bucket + 5-class taxonomy) |
| AGNOTE row | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` `RELEASE` row at `2026-10-05T02:30:00Z` |

**Why a separate launcher name, not a flag:** the operator explicitly committed on 2026-10-03 to "default clean Claude Code settings" — the Mavis overlay must NOT auto-inject on vanilla `claude-pmoves`. A `-mavis` suffix makes the opt-in unambiguous at the run-name level.

**Relationship to PR #3184:** PR #3184's `--backend=minimax` flag is acceptable as the underlying mechanism. After #3184 lands, the launcher collapses to `exec claude-pmoves --backend=minimax "$@"` (one-line). Until then, the launcher sources the JSON directly.

### 2. ACP registry link (`MiniMax Code: linked`)

**Goal:** Flip `pmoves/configs/acp_registry_map.json` entry for `minimax-code` from `status: "available"` → `status: "linked"`, with `pmoves: "minimax-code"` field following the `kilocode_glm` pattern.

| Item | Where |
|------|-------|
| Repo state | `pmoves/configs/acp_registry_map.json` (MODIFY line 185-190) |
| Regeneration | `pmoves/tools/acp_registry_map.py` (verify no regression) |
| Org-side registry PR | `POWERFULMOVES/PMOVES-registry` (NEW PR adding `agent.json` + `manifest.json` for HyPeRAGInT — repo-side manifest, schema follows `agentclientprotocol` upstream) |
| Fork naming | `POWERFULMOVES/PMOVES-HyPeRAGInT` (NEW fork from `PMOVES-MiniMaXX-AGInT` or fresh) — TBD by operator |

**Identity vocabulary integration:** per `DAMAGE_CONTROL_STRUCTURED_POLICY_RFC.md:280-284`, when `HyPeRAGInT` lands in the registry, `AgentIdentity` picks it up from the vocabulary with no code change. This is the intended adoption path.

### 3. Cipher mindmap (L1 per-node Neo4j)

**Goal:** Each HyPeRAGInT instance writes to its own L1 Neo4j via Cipher :8105. The launcher ensures Cipher reachability before exec.

| Item | Where |
|------|-------|
| Memory contract | `pmoves/docs/AGENTS/HERMES_CIPHER_LOCAL_ARCHITECTURE.md` (existing PLANNED doc) — flip to LANDING once per-node Cipher is up |
| Per-node Cipher compose | `pmoves/integrations/cipher/` (NEW integration following `_template/pmoves-integrations` scaffold) |
| Launcher hook | `deploy/provision/claude-pmoves-mavis.{sh,ps1}` — pre-exec check `curl -sf http://localhost:8105/health`; if missing, surface warning + offer to bring up the cipher compose |
| Mindmap schema | `pmoves/integrations/cipher/events/subjects.yaml` (NATS subjects `cipher.memory.store.v1`, `cipher.memory.search.v1`) |

### 4. Hi-RAG v2 (L3 document retrieval)

**Goal:** Per-node document index via Qdrant + Hi-RAG gateway. Optional at first; bind only after Cipher mindmap is stable.

| Item | Where |
|------|-------|
| Compose | `pmoves/services/hi-rag-gateway/` (existing) + `qdrant` (existing) |
| Launcher hook | Same launcher pre-exec surface: `curl -sf http://localhost:8086/hirag/admin/stats` |
| Document index spec | Per-node scope; SEAP/H3 review surface becomes the first indexed corpus |

### 5. PMOVES integration contract

**Goal:** `HyPeRAGInT` follows the `_template/pmoves-integrations` contract — same shape as `archon/`, `firefly-iii/`, `health-wger/`, `pr-kits/`.

| Item | Where |
|------|-------|
| Compose wiring | `pmoves/integrations/hyperagint/compose/` |
| Model mappings | `pmoves/integrations/hyperagint/models/mappings/` |
| n8n flows | `pmoves/integrations/hyperagint/n8n/flows/` |
| Event subjects | `pmoves/integrations/hyperagint/events/subjects.yaml` |
| CHIT/GitHub secret labels | `pmoves/integrations/hyperagint/secrets/labels.yaml` |
| Auth/bootstrap | `pmoves/integrations/hyperagint/auth/bootstrap.sh` |
| Contract check | `pmoves/tools/integration_contract_check.py pmoves/integrations/hyperagint/` |

### 6. miniagent spawn protocol

**Goal:** Archon creates scoped miniagents for tasks; each miniagent is itself an ACP entry under HyPeRAGInTZ.

| Item | Where |
|------|-------|
| Spawn protocol | `pmoves/integrations/archon/agents/miniagent_spawn.yaml` (NEW — Archon-side miniagent creation recipe) |
| ACP entry | Each spawned miniagent gets its own `pmoves/configs/acp_registry_map.json` entry with `pmoves: "miniagent-<task-id>"` |
| Lifecycle | miniagent lives for task duration; archived after; mindmap snapshot to L2 fleet cipher for replay |

---

## Slice Plan

Per the operator's "first fix the claude-code bootstrap" instruction (2026-10-03), the order is:

| # | Slice | Files | PR target | Status |
|---|-------|-------|-----------|--------|
| **A** | Launcher shim | 7 NEW + 2 MODIFY (generator + LEARNINGS) + 1 AGNOTE row | `feat/claude-pmoves-mavis-launcher` off `feat/claude-backend-switch` (PR #3184 tip) | **NEXT** — gated on operator scope pick |
| **B** | ACP registry link | 1 MODIFY (`acp_registry_map.json`) + 1 NEW fork (`POWERFULMOVES/PMOVES-HyPeRAGInT`) + 1 NEW PR against `POWERFULMOVES/PMOVES-registry` | After A lands | Pending |
| **C** | Cipher mindmap (L1) | 6 NEW files (full PMOVES integration contract for cipher) + 1 MODIFY (cipher compose YAML) + 1 LEARNINGS + 1 AGNOTE row | `feat/pmodes/cipher-mindmap-l1` off `PMOVES.AI-Edition-Hardened` | Pending |
| **D** | Hi-RAG v2 (L3) | Per-node index spec + launcher hook + LEARNINGS + AGNOTE | After C | Pending |
| **E** | PMOVES integration contract for `hyperagint/` | 6 NEW files following `_template/pmoves-integrations/` | `feat/pmodes/hyperagint-integration` off `PMOVES.AI-Edition-Hardened` | Pending |
| **F** | miniagent spawn protocol | 1 NEW (spawn.yaml) + archon-side recipe + ACP entries per spawn | After C, D, E | Pending |

---

## Open Questions (TBD with operator)

1. **HyPeRAGInT fork origin** — rename `PMOVES-MiniMaXX-AGInT` to `POWERFULMOVES/PMOVES-HyPeRAGInT`, or create fresh from upstream, or keep `MiniMaXX-AGInT` and add `HyPeRAGInT` as a separate fork?
2. **First slice scope** — start with **A only** (matches operator's "first fix the bootstrap" instruction), or jump to **A + B** (launcher + ACP registration) as a paired PR?
3. **Identity file** — does `pmoves/configs/agents/forms/hyperagint.yaml` exist yet, or does slice A create it (lighter)? Or does slice E create it (heavier but with full contract)?
4. **miniagent scope** — is miniagent creation an Archon-side feature for slice F, or a HyPeRAGInT-side feature exposed to other agents?
5. **Push mode** — push A as draft, or push and request review on #3184 simultaneously? (Same Q from prior turn; not answered yet.)
6. **Defer other lanes** — pause SEAP/H3 Tier 1 + VSS + combiner + HyPeRAGInT fork until slice A lands, or keep SEAP Tier 1 going in a parallel worktree? (Same Q from prior turn; not answered yet.)
7. **AGNOTE trail format** — single `RELEASE` row in `AGNOTE4482PHI.t1.md` for the whole moniker landing, or per-slice `RELEASE` row?

---

## SDK + doc provenance (no-workarounds principle, 2026-09-16)

- **SDK file:line** (current bug):
  - `deploy/provision/claude-pmoves.ps1:17-19` — ANTHROPIC_* blocklist
  - `deploy/provision/claude-pmoves.sh:24` — bash twin blocklist
  - `C:\Users\russe\.claude\settings.json:5-8, 13-32` — Mavis SDK hijack (live)
- **SDK file:line** (canonical overlay):
  - `pmoves/configs/claude_settings/minimax.json` (PR #3184 — the canonical source for the Mavis overlay env)
- **AGNOTE** (planned trail):
  - `pmoves/docs/AGENTS/AGNOTE4482.md:1684` — HyPeRAGInTZ moniker (named 2026-09-17)
  - `pmoves/docs/AGENTS/AGNOTE4482.md:1689` — B850-CLAUDE agent ACK
  - `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — RELEASE row at `2026-10-05T02:30:00Z` (slice A) + subsequent rows for B–F
- **LEARNINGS** (planned files):
  - `pmoves/docs/AGENTS/claude_pmoves_mavis_launcher_LEARNINGS.md` (slice A)
  - `pmoves/docs/AGENTS/hyperagint_registration_LEARNINGS.md` (slice B)
  - `pmoves/docs/AGENTS/cipher_mindmap_l1_LEARNINGS.md` (slice C)
  - `pmoves/docs/AGENTS/hi_rag_v2_integration_LEARNINGS.md` (slice D)
  - `pmoves/docs/AGENTS/hyperagint_integration_LEARNINGS.md` (slice E)
  - `pmoves/docs/AGENTS/miniagent_spawn_LEARNINGS.md` (slice F)
- **Branch + PR**:
  - Slice A: `feat/claude-pmoves-mavis-launcher` off `feat/claude-backend-switch` (`b9d62c9186`)
  - Slice B: `feat/hyperagint-acp-registry-link` off `PMOVES.AI-Edition-Hardened` + side-PR to `POWERFULMOVES/PMOVES-registry`
  - Slice C: `feat/pmodes/cipher-mindmap-l1` off `PMOVES.AI-Edition-Hardened`
  - Slice D: `feat/pmodes/hi-rag-v2-binding` off `PMOVES.AI-Edition-Hardened`
  - Slice E: `feat/pmodes/hyperagint-integration` off `PMOVES.AI-Edition-Hardened`
  - Slice F: `feat/pmodes/miniagent-spawn-protocol` off `PMOVES.AI-Edition-Hardened`

---

## Verification commands

```bash
# Slice A verification
cd "C:\Users\russe\Documents\PMOVES.AI-research-hyperagintz-moniker-design-2026-10-05"
make -C pmoves health-quick
"C:\Users\russe\AppData\Local\Programs\Python\Python312\python.exe" -m pytest \
  pmoves/tools/tests/test_claude_pmoves_mavis.py \
  pmoves/tools/tests/test_pmoves_launcher_generator.py -v

# Manual smoke: vanilla launcher (no Mavis)
deploy/provision/claude-pmoves.cmd --help        # exits clean (Claude Max default)
# Manual smoke: -mavis launcher (overlay only, no settings.json write)
deploy/provision/claude-pmoves-5090-mavis.cmd --help
# Verify settings.json unchanged after -mavis exit
diff ~/.claude/settings.json ~/.claude/settings.json.backup-$(date +%Y%m%d)
```