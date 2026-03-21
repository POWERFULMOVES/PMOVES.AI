# AGNOTE4482PHI — 5090 Submodule Drift Audit

GRAPHITI_MARK: `PHI-4482-5090::SUBMODULE-AUDIT::PMOVES`

> **Parent:** [AGNOTE4482.md](./AGNOTE4482.md) | **Claim Register:** [AGNOTE4482PHI.t1.md](./AGNOTE4482PHI.t1.md)
> **Author:** 5090-claude (♫ Note | #7C3AED | prosodic)
> **Date:** 2026-03-21
> **Context:** 28 submodules drifted from gitlinks on main. Audit before 5090 rebuild.

---

## Summary

| Category | Count | Action |
|----------|-------|--------|
| Docs/integration stubs (safe to sync) | 16 | Gitlink updated |
| Functional changes on Hardened (safe) | 5 | Gitlink updated |
| Feature/fix branches (active WIP) | 4 | Deferred — document |
| Large upstream sync | 2 | Deferred — review needed |
| Diverged/lost gitlink | 3 | Accept current HEAD or defer |

---

## Category A — Docs & Integration Stubs (Safe to Sync)

These submodules are on `PMOVES.AI-Edition-Hardened` with only documentation, PMOVES integration module stubs (`pmoves_announcer`, `pmoves_health`, `pmoves_registry`, `pmoves_common`), or cleanup changes.

| # | Submodule | Commits | Change Type |
|---|-----------|---------|-------------|
| 1 | PMOVES-Headscale | 1 | CLAUDE.md + PMOVES.AI_INTEGRATION.md |
| 2 | PMOVES-Neo4j | 1 | PMOVES.AI_INTEGRATION.md only |
| 3 | PMOVES-surf | 3 | PMOVES.AI_INTEGRATION.md only |
| 4 | PMOVES-a0-plugins | 3 | PMOVES.AI_INTEGRATION.md + README + plugin YAML |
| 5 | PMOVES-E2B-Danger-Room-Desktop | 2 | PMOVES.AI_INTEGRATION.md + poetry.lock + submodule ptr |
| 6 | PMOVES-Ultimate-TTS-Studio | 1 | Merge main into Hardened (sync commit) |
| 7 | PMOVES-BotZ-gateway | 2 | Cleanup: removed 1344 lines (stale env.tier-api + pmoves_* stubs) |
| 8 | PMOVES-E2b-Spells | 1 | Added pmoves_announcer/common/health/registry stubs |
| 9 | PMOVES-MAI-UI | 6 | Added pmoves_announcer/common/health/registry stubs |
| 10 | PMOVES-Tailscale | 1 | Added pmoves_announcer/common/health/registry stubs |
| 11 | PMOVES-tensorzero | 7 | Integration stubs + provider-proxy Dockerfile fix |
| 12 | Pmoves-AgentGym-RL | 2 | PMOVES.AI_INTEGRATION.md + submodule pointer |
| 13 | pmoves/integrations/archon | 1 | Cleanup: removed 529 lines (dead github_integration code) |
| 14 | PMOVES-autoresearch | 3 | NaN fast-fail + infinite loop guard (gitlink force-pushed, accept HEAD) |
| 15 | PMOVES-ClawZ | 3+ | Agent refactoring (gitlink force-pushed, accept HEAD) |
| 16 | Pmoves-cipher | 2 | API server fixes + test fixes |

---

## Category B — Functional Changes on Hardened (Safe to Sync)

On `PMOVES.AI-Edition-Hardened` with functional code changes that are intentional and reviewed.

| # | Submodule | Commits | Change Type |
|---|-----------|---------|-------------|
| 17 | Pmoves-hyperdimensions | 26 | New tools: generate_dossier.py, generate_topology.py, saves |
| 18 | PMOVES-transcribe-and-fetch | 22 | Major cleanup: 251K lines removed, env cleanup |
| 19 | PMOVES-Agent-Zero | 1 | QUICKSTART.md + PMOVES.AI_INTEGRATION.md (docs) |
| 20 | PMOVES.YT | 2 | Dockerfile fix + yt.py refactor |
| 21 | PMOVES-BoTZ | 2 | vl_sentinel refactor, mcp_bridge cleanup, test_mint.py |

---

## Category C — Feature/Fix Branches (Deferred)

Active work-in-progress on non-Hardened branches. Do NOT sync — these may be incomplete.

| # | Submodule | Branch | Commits | Status |
|---|-----------|--------|---------|--------|
| 22 | PMOVES-supabase | feat/pmoves-auth-module | 4 | New pmoves_auth module + integration stubs |
| 23 | Pmoves-Health-wger | feat/wger-django-signals | 8 | NATS publisher + Django signals (observability) |
| 24 | PMOVES-llama-throughput-lab | fix/dockerfile-audit-hardening | 1 | PMOVES.AI_INTEGRATION.md (docs-only but on fix/ branch) |
| 25 | PMOVES-Pinokio-Ultimate-TTS-Studio | fix/tts-start-js-regex | 2 | start.js regex fix + integration stubs |

---

## Category D — Large Upstream / Detached (Deferred)

Require dedicated review session before syncing.

| # | Submodule | State | Commits | Notes |
|---|-----------|-------|---------|-------|
| 26 | PMOVES-Pipecat | Detached v0.0.102+68 | 960 | Massive upstream sync. 727 files, 40K insertions. Review changelog. |
| 27 | PMOVES-Danger-infra | Hardened | 4 | 528 files changed, 11K ins / 24K del. Upstream E2B changes. |

---

## Category E — Diverged Branches (Investigate)

| # | Submodule | Issue | Notes |
|---|-----------|-------|-------|
| 28 | PMOVES-DoX | Gitlink → UNFCU enterprise commit (#138), HEAD → dependabot merge (#122). Not ancestor. | Branches diverged. The gitlink (832017f) has UNFCU features that HEAD doesn't. Need to determine which branch is authoritative. Likely needs branch reset per memory pattern. |

---

## Cross-Cutting Pattern: PMOVES Integration Modules

13 submodules received standardized integration stubs:

```
pmoves_announcer/__init__.py  — NATS service announcer
pmoves_common/__init__.py     — Shared utilities (ServiceTier enum)
pmoves_health/__init__.py     — Health check endpoints
pmoves_registry/__init__.py   — Service registry client
```

**Present in:** BoTZ, Danger-infra, DoX, E2b-Spells, MAI-UI, Pinokio-TTS, Pipecat, Tailscale, Ultimate-TTS-Studio, supabase, tensorzero, PMOVES.YT, integrations/archon

**BotZ-gateway removed its copies** (2 commits) — indicating these were moved/consolidated elsewhere.

---

## 5090 Rebuild Guidance

### Containers affected by synced submodules
- **tensorzero** — provider-proxy Dockerfile changed → rebuild `tensorzero-provider-proxy`
- **PMOVES.YT** — yt.py + Dockerfile → rebuild `pmoves-yt-service`
- **BoTZ** — vl_sentinel refactor → rebuild `botz` container
- **cipher** — API server fixes → rebuild `cipher-memory`

### No container rebuild needed
- All docs-only submodules
- Integration stubs (not yet wired into Docker builds)
- hyperdimensions (standalone tools)
- transcribe-and-fetch (cleanup only)

### Deferred items for next session
1. PMOVES-Pipecat: Review 960 upstream commits, decide whether to sync
2. PMOVES-Danger-infra: Review 528-file upstream diff
3. PMOVES-DoX: Resolve branch divergence
4. PMOVES-supabase: Complete and merge pmoves_auth feature
5. Pmoves-Health-wger: Complete and merge Django signals feature
6. PMOVES-Pinokio-Ultimate-TTS-Studio: Merge fix/tts-start-js-regex to Hardened

---

## Verdict

**21 of 28 submodules safe to sync.** Remaining 7 deferred (4 WIP branches, 2 large upstream, 1 diverged).
