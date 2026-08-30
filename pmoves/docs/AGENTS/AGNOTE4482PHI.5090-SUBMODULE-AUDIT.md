# AGNOTE4482PHI — 5090 Submodule Drift Audit

GRAPHITI_MARK: `PHI-4482-5090::SUBMODULE-AUDIT::PMOVES`

> **Parent:** [AGNOTE4482.md](./AGNOTE4482.md) | **Claim Register:** [AGNOTE4482PHI.t1.md](./AGNOTE4482PHI.t1.md)
> **Author:** 5090-claude (♫ Note | #7C3AED | prosodic)
> **Date:** 2026-03-21
> **Context:** 28 submodules drifted from gitlinks on main. Audit before 5090 rebuild.

---

## Summary

| Category | Count | Action | Parent PR |
|----------|-------|--------|-----------|
| Docs/integration stubs | 16 | SYNCED | #1059 |
| Functional changes on Hardened | 5 | SYNCED | #1059 |
| Feature/fix branches (WIP) | 4 | MERGED + SYNCED | #1060, #1061, #1062 |
| Large upstream sync | 2 | SYNCED (accepted HEAD) | #1059 |
| Diverged branch (DoX) | 1 | RESOLVED + SYNCED | #1061 |

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

## Category C — Feature/Fix Branches (COMPLETED)

All WIP branches merged to their target branches and gitlinks synced.

| # | Submodule | Branch | Resolution | Parent PR |
|---|-----------|--------|------------|-----------|
| 22 | PMOVES-supabase | feat/pmoves-auth-module | PR #1 merged (pmoves_auth JWT lifecycle) | #1062 |
| 23 | Pmoves-Health-wger | feat/wger-django-signals | PR #4 merged (14 Critical/Major fixes) | #1061 |
| 24 | PMOVES-llama-throughput-lab | fix/dockerfile-audit-hardening | PR #1 merged | #1060 |
| 25 | PMOVES-Pinokio-Ultimate-TTS-Studio | fix/tts-start-js-regex | PR #2 merged | #1060 |

---

## Category D — Large Upstream / Detached (SYNCED)

Accepted current HEAD to clear drift. Changelog review recommended for breaking changes.

| # | Submodule | State | Commits | Resolution | Parent PR |
|---|-----------|-------|---------|------------|-----------|
| 26 | PMOVES-Pipecat | Detached v0.0.102+68 | 960 | Accepted HEAD | #1059 |
| 27 | PMOVES-Danger-infra | Hardened | 4 | Accepted HEAD | #1059 |

> **Follow-up:** Pipecat 960-commit changelog review still recommended to identify breaking API changes.

---

## Category E — Diverged Branches (RESOLVED)

| # | Submodule | Issue | Resolution | Parent PR |
|---|-----------|-------|------------|-----------|
| 28 | PMOVES-DoX | Gitlink → UNFCU enterprise commit, HEAD → dependabot merge. Not ancestor. | Stale detached HEAD — both commits on Hardened. Resolved. | #1061 |

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

### ~~Deferred items~~ — ALL COMPLETED
1. ~~PMOVES-Pipecat~~ — SYNCED (accepted HEAD, PR #1059)
2. ~~PMOVES-Danger-infra~~ — SYNCED (accepted HEAD, PR #1059)
3. ~~PMOVES-DoX~~ — RESOLVED (stale detached HEAD, PR #1061)
4. ~~PMOVES-supabase~~ — PR #1 MERGED (pmoves_auth module, PR #1062)
5. ~~Pmoves-Health-wger~~ — PR #4 MERGED (14 fixes, PR #1061)
6. ~~PMOVES-Pinokio-Ultimate-TTS-Studio~~ — PR #2 MERGED (PR #1060)

---

## Verdict

**28 of 28 submodules synced. 0 drift. Audit complete.**

---

## Completion — 2026-03-21

### Session Arc

| Phase | PRs | Scope |
|-------|-----|-------|
| Initial sync (Categories A+B) | Parent #1059 | 21 safe gitlinks |
| WIP branch merges (Category C partial) | Parent #1060 | 5 deferred submodules (llama-lab, Pinokio-TTS, + 3 others) |
| DoX + Health-wger + BoTZ (Categories C+E) | Parent #1061 | DoX divergence resolved, Health-wger PR #4, BoTZ PR #84 |
| Final two (Categories C remaining) | Parent #1062 | BoTZ PR #79 (gateway auth), Supabase PR #1 (pmoves_auth) |

### BoTZ PR #79 Resolution Detail
- 8 merge conflicts in `gateway.py` — two competing auth implementations
- Kept fail-closed JWT validation (python-jose) with CHIT attestation over `mcp_bridge.auth` import pattern
- Added `PUBLIC_ENDPOINTS` as `frozenset` (addresses Ruff RUF012)
- Fixed Critical: broken `DISTRIBUTED_SUBMODULES.md` doc link
- Fixed Major: corrected endpoint paths in `distributed-context.md`
- Fixed Minor: markdown code block language specifiers (MD040)

### Final State
- `git submodule status | grep "^+" | wc -l` = **0**
- Open PRs (main repo): **0**
- Open PRs (BoTZ): **2** (Dependabot only — #89, #91)

### Remaining Follow-ups
1. **Pipecat changelog review** — 960 upstream commits accepted without detailed review
2. **Container rebuilds** — tensorzero-provider-proxy, pmoves-yt-service, botz, cipher-memory
3. **BoTZ Dependabot** — PRs #89 (npm), #91 (uv) — housekeeping
