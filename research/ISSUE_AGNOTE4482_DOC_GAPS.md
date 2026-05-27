## Overview

Comprehensive review of 15+ AGNOTE4482-related documents across 7 axes (vision, taxonomy, gaps, LONGBOW, playlist/models, skills, ELI Computer Guy). Found 3 critical stale-data sources, multiple taxonomy contradictions, and missing operational docs.

---

## CRITICAL: Stale Data Sources (Fix Immediately)

### C1. LONGBOW_COMPARATIVE_ANALYSIS.md - Stale Signoff Figures — **RESOLVED**
- **Line 18:** `32/37 signoff` → patched to `36/36`
- **Line 245:** `31/36 signoff` → patched to `36/36`
- **Correct:** `36/36` (per PR #1502, 2026-05-16)
- **Impact:** This doc was the **source** that corrupted downstream memories with wrong signoff counts
- **Fix:** Applied via PR #1502

### C2. LIVING_TEMPLATE_AGENT_TAXONOMY.md - Hardcoded Agent Count — **RESOLVED**
- **Header:** `v1.4.0 (59 agents)` → updated to `v1.5.0 (76 agents)`
- **CGP samples:** `K: 59` → `K: 76`
- **Impact:** Any agent generating CGPs from this template produces malformed packets
- **Fix:** Applied in prior session (verified 2026-05-17)

### C3. IMPLEMENTATION_GAP_ANALYSIS.md - References Dead Branch — **RESOLVED**
- 3 deprecation notices already added (2026-05-08, 2026-05-08, 2026-05-15)
- Active branch noted: `PMOVES.AI-Edition-v1.9`
- **Fix:** Already applied in prior sessions

---

## HIGH: Missing Operational Docs

### H1. No DGX SPARK Model Strategy Doc — **RESOLVED**
- Created: `pmoves/docs/SPARK_MODEL_STRATEGY.md` (785 lines, 2026-05-15)
- Covers: model selection, Ollama pull strategy, TensorZero routing, provider cascade, hardware profiles
- **Fix:** Delivered in docs/spark PR

### H2. Flute Vision Unresolved References — **RESOLVED**
`FLUTE_VISION_MULTIMODAL.md` line 181 now contains deprecation notice: "The `internal:` links above are stranded from a worktree promotion and do not resolve. They are preserved for citation numbering stability."
- **Fix:** Already applied in prior session

### H3. 5 Taxonomy Docs Pre-MOF — **RESOLVED**
`AGENT_TAXONOMY_CROSS_REFERENCE.md` line 18 now marks BoTZ as "archived 2026-04-19". `PMOVES_UNIFIED_AGENT_TAXONOMY.md` has no active BoTZ references.
- **Fix:** Already applied in prior session

---

## MEDIUM: Skills and Vision Gaps — DEFERRED (Future Work)

> All M-items are known gaps that require new feature development, not doc fixes.
> Deferred to future sprint. No action required for AGNOTE4482 closure.

### M1. Remotion/ThreeJS Skills Spec-Only — DEFERRED
Both `remotion-render` and `threejs-render` have complete manifests but no implementation code. Not in agent registry. Potential port conflict: Remotion calls `localhost:8105` (same as Cipher Memory per gap analysis). **Action:** Implement when video rendering pipeline is prioritized.

### M2. Pretext Has No Skill Manifest — DEFERRED
`pretextLayout.ts` exists in `pmoves/services/a2ui-renderer/src/remotion/pretextLayout.ts` but has no skill manifest. Not integrated into skill system. **Action:** Create manifest when pretext layout is promoted to agent-facing skill.

### M3. agent_vision_notes.md — RESOLVED (Deprecated)
File properly deprecated 2026-05-08 with notice pointing to `FLUTE_VISION_MULTIMODAL.md`. No further action.

### M4. Unsloth Recipe Targets Fireworks Not Local — DEFERRED
`PMOVES-tensorzero/recipes/supervised_fine_tuning/unsloth/` uses `firectl` + Fireworks API. No SPARK-local deployment path. **Action:** Create SPARK-local Unsloth recipe when on-device fine-tuning is prioritized.

---

## ELI Computer Guy - Playlist Positions

Found at 4 positions in the AI playlist (PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8):

| Position | Video ID | Title |
|----------|----------|-------|
| #14 | GKRCUlYpuKg | Intro to Systems Architecture for AI Projects |
| #110 | N_UZDrxNaZo | Install Linux on PS5 - Running Ubuntu Clusters on Game Systems |
| #144 | EU9o9kETl00 | Anthropic Claude AI Deletes PocketOS Production Database |
| #177 | tzjoXcmZHv4 | Microsoft Employee Voluntary Buyouts |

Position #14 transcript already analyzed in PLAYLIST_BATCH_ANALYSIS.md. Additional standalone video Intro to Cyber Security for AI Projects (iUkXEMmIXcc, 2026-03-26) is from Silicon Dojo in-person class - transcript saved to `research/transcripts/eli_computer_guy_cybersecurity_ai.en.vtt`.

---

## Related: CHIT Intrusion Source

LONGBOW_COMPARATIVE_ANALYSIS.md is confirmed as the **source document** that seeded stale signoff figures into agent memories. Patching lines 18 and 245 will prevent future contamination.

## Files to Update

- [x] `research/LONGBOW_COMPARATIVE_ANALYSIS.md` - lines 18, 245 → PR #1502
- [x] `pmoves/docs/PMOVESCHIT/LIVING_TEMPLATE_AGENT_TAXONOMY.md` - header + CGP samples → prior session
- [x] `pmoves/docs/AGENTS/IMPLEMENTATION_GAP_ANALYSIS.md` - deprecation header → prior sessions (3 notices)
- [x] `pmoves/docs/context/FLUTE_VISION_MULTIMODAL.md` - resolve/remove internal refs → deprecation notice added
- [x] `pmoves/docs/AGENTS/AGENT_TAXONOMY_CROSS_REFERENCE.md` - update BoTZ refs → marked archived 2026-04-19
- [x] `pmoves/docs/AGENTS/PMOVES_UNIFIED_AGENT_TAXONOMY.md` - refresh for MOF → no active BoTZ refs
- [x] `pmoves/docs/AGENTS/agent_vision_notes.md` - deprecated 2026-05-08, points to FLUTE_VISION_MULTIMODAL.md
- [x] New: `pmoves/docs/intelligence/SPARK_MODEL_STRATEGY.md` → delivered (785 lines)

---

## Closure — 2026-05-19

**Status: CLOSED**
All CRITICAL and HIGH items resolved. MEDIUM items deferred to future sprint (require new feature development, not doc fixes). Checklist verified against actual file state. No further action on AGNOTE4482.
