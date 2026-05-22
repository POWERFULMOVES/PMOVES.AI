# CLAUDE.md Fleet Audit — 2026-05-20

**Branch:** `chore/submodules-promote-tier-b-2026-05-19`
**Auditor:** `researcher` subagent invoked from `claude-md-management:claude-md-improver` skill
**Scope:** Root + 25 top-level `PMOVES-*` submodules + `pmoves/services/*` + `.worktrees/*` overrides

## Top-line

- **Files reviewed:** 26 distinct CLAUDE.md / `.claude/CLAUDE.md` files (excluding `node_modules/`, vendored `external/`, glob duplicates)
- **Average score:** 63 / 100
- **Verified false positive:** Subagent flagged Cipher port drift (8096 vs 8105) in parent `.claude/CLAUDE.md`. Manual verification: parent file already uses 8105. No action needed.

## Per-file table

| File | Score | Grade | Headline issue | Recommended fix | Owner |
|------|-------|-------|----------------|-----------------|-------|
| `CLAUDE.md` (root keystone) | 78 | B+ | Thin keystone correct; missing branch-context line | Add one-liner noting current `chore/submodules-*` work | parent |
| `.claude/CLAUDE.md` | 88 | A | Best in fleet; submodule count was stale (20 → 50) | **FIXED 2026-05-20** | parent |
| `PMOVES-Archon/CLAUDE.md` | 85 | A- | Excellent; minor squash-merge note missing | Add parent squash-merge note | submodule PR |
| `PMOVES-BoTZ/.claude/CLAUDE.md` | 72 | B | No archived/legacy banner in file itself | Add deprecation banner | submodule PR |
| `PMOVES-Agent-Zero/CLAUDE.md` | 80 | B+ | Missing `AGENT_ZERO_API_BASE` sidecar gotcha (PR #1544) | Add gotcha | submodule PR |
| `PMOVES-ClawZ/CLAUDE.md` | 5 | F | **One-word stub: `AGENTS.md`** | Write proper CLAUDE.md | submodule PR (P1) |
| `PMOVES-DoX/CLAUDE.md` (root) | 60 | C | Old architecture; `docker-compose` hyphen syntax | Sync with `.claude/CLAUDE.md` version | submodule PR |
| `PMOVES-DoX/.claude/CLAUDE.md` | 82 | B+ | Hardcoded `feat/integrate-internal-agents` branch; TensorZero URL `:3000/v1` wrong | Fix branch ref + TensorZero URL → `:3030/openai/v1` | submodule PR (P0) |
| `PMOVES-HiRAG/CLAUDE.md` | 84 | A- | `all-MiniLM-L6-v2` listed as primary; Qwen3 is primary now | Note MiniLM as legacy fallback | submodule PR |
| `PMOVES-tensorzero/CLAUDE.md` | 8 | F | **`@AGENTS.md` delegation stub only** — no PMOVES wrapper | Add PMOVES wrapper: port 3030, `/openai/v1/embeddings`, `tensorzero.toml`, weight=0.0 rule | submodule PR (P1) |
| `PMOVES-Headscale/CLAUDE.md` | 8 | F | Same `@AGENTS.md` stub problem | Add PMOVES fleet wrapper | submodule PR (P1) |
| `PMOVES.YT/CLAUDE.md` | 83 | B+ | MinIO P2 flagged but no remediation path | Add remediation pointer | submodule PR |
| `PMOVES-ToKenism-Multi/CLAUDE.md` | 45 | D+ | **Hardcoded `C:\Users\russe\OneDrive\...` path (line 23)** | Replace with `../PMOVES-DoX` relative ref | submodule PR (P0) |
| `PMOVES-Danger-infra/CLAUDE.md` | 62 | C+ | E2B upstream content; zero PMOVES wrapper | Add PMOVES wrapper section | submodule PR |
| `PMOVES-space-agent/CLAUDE.md` | 52 | C- | No startup/test commands or health endpoint | Add commands + endpoint | submodule PR |
| `PMOVES-Open-Notebook/CLAUDE.md` | 74 | B | Frontend port collision with Grafana (3000); stale timestamp | Fix port → 3001, refresh date | submodule PR |
| `pmoves/services/archon/CLAUDE.md` | 88 | A | Best service file; TAC tree TODO marker | Create `pmoves/docs/TAC/TAC_ARCHON.md` | parent |
| `pmoves/services/ffmpeg-whisper/CLAUDE.md` | 76 | B | No port (8078) / health endpoint | Add port + endpoint | parent |
| `pmoves/services/consciousness-service/CLAUDE.md` | 82 | B+ | No port (8105) / startup commands | Add port + curl test | parent |
| `pmoves/services/cast-tts-gateway/CLAUDE.md` | 74 | B | No port; no compose fallback when no make target | Add port + fallback | parent |
| `pmoves/services/extract-worker/CLAUDE.md` | 80 | B | Best gotcha file; missing port (8083) + startup cmd | Add port + cmd | parent |
| `pmoves/integrations/archon/CLAUDE.md` | 5 | F | `AGENTS.md` stub only | Add one-paragraph integration orientation | parent |
| `.worktrees/*/.claude/CLAUDE.md` (5 files) | 20 | D | All five contain Pinokio launcher guide content (wrong context for the worktree's actual purpose) | Delete or gitignore; worktrees should inherit parent CLAUDE.md | parent (.gitignore) |
| `pbnj/pinokio/api/pmoves-pbnj/CLAUDE.md` | 70 | B- | Canonical Pinokio guide; hardcoded `D:\pinokio\...` path | Soften path reference | parent |
| `pmoves/docs/ARTSTUFF/realtime/CLAUDE.md` | 70 | B- | Pinokio guide variant with different hardcoded path | Remove from VC or gitignore | parent |

## Cross-file drift list

1. ~~**Cipher Memory port 8096 vs 8105** in `.claude/CLAUDE.md`~~ — **FALSE POSITIVE**, parent already 8105.
2. **Archon port confusion** — three different port pictures across `pmoves/services/archon/CLAUDE.md` (8090/8051/8052 internal, 8091/3737 external), worktree Bootstrap (8091/3737), and `PMOVES-Archon/CLAUDE.md` (3090/8051). Pick one canonical view.
3. **TensorZero URL** — `PMOVES-DoX/.claude/CLAUDE.md` uses `:3000/v1`; canonical is `:3030/openai/v1/embeddings`. Fix.
4. **Submodule count 20 → 50** — **FIXED 2026-05-20** in `.claude/CLAUDE.md`. `.claude/context/submodules.md` itself still needs sync.
5. **NATS WebSocket port** — DoX `.claude/CLAUDE.md` says standalone 9223 / docked 9222; Bootstrap says opposite. Reconcile.
6. **BoTZ archived status** — parent says archived, BoTZ's own file doesn't acknowledge. Add banner.
7. **DoX hardcoded branch ref** — `feat/integrate-internal-agents` baked in.
8. **`docker-compose` vs `docker compose`** — legacy hyphen form in DoX/ToKenism/BoTZ. Migrate to space form.
9. **HiRAG embedding model** — `all-MiniLM-L6-v2` listed primary; Qwen3-Embedding-4B is actual primary. Mark MiniLM legacy.
10. **ToKenism hardcoded Windows path** — `C:\Users\russe\OneDrive\Documents\GitHub\PMOVES-DoX` (line 23).

## Priority queue

**P0 (next merge):**
- `PMOVES-ToKenism-Multi/CLAUDE.md`: remove `C:\Users\russe\...` path → relative ref
- `PMOVES-DoX/.claude/CLAUDE.md`: fix TensorZero URL `:3000/v1` → `:3030/openai/v1`; drop hardcoded branch ref

**P1 (this sprint):**
- `PMOVES-ClawZ/CLAUDE.md`: replace one-word stub with proper content
- `PMOVES-tensorzero/CLAUDE.md`: add PMOVES wrapper (port 3030, embedding endpoint, weight=0.0 rule)
- `PMOVES-Headscale/CLAUDE.md`: add PMOVES fleet wrapper
- NATS WebSocket port: determine canonical mapping, fix both sides
- `.worktrees/*/.claude/CLAUDE.md`: delete the 5 Pinokio-guide injections OR `.gitignore` worktree contexts

**P2 (next cycle):**
- `PMOVES-BoTZ/.claude/CLAUDE.md`: archived banner
- `pmoves/integrations/archon/CLAUDE.md`: replace `AGENTS.md` stub
- Service files (`ffmpeg-whisper`, `cast-tts-gateway`, `consciousness-service`): add ports + startup commands
- `PMOVES-Open-Notebook/CLAUDE.md`: frontend port 3001, refresh date
- `.claude/context/submodules.md`: sync count from 20 → 50

## Fixes applied this session

- `.claude/CLAUDE.md` line 60: `(20 submodules)` → `(50 submodules per git submodule status)`

## Don't-bother list

- `pmoves/services/archon/CLAUDE.md` — exemplary, only minor TAC tree TODO
- `pmoves/services/consciousness-service/CLAUDE.md` — CGP versioning rules best in fleet
- `pmoves/services/extract-worker/CLAUDE.md` — TensorZero embedding gotcha captured correctly
- `PMOVES-Archon/CLAUDE.md` — comprehensive monorepo guide
- `PMOVES-HiRAG/CLAUDE.md` — solid except model-drift footnote
- `PMOVES-Agent-Zero/CLAUDE.md` — `normalize_settings()` + `A0_SET_*` correctly captured
