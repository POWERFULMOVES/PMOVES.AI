# AGNOTE4482

GRAPHITI_MARK: `PHI-4482-GATEWAY::PMOVES`

## Canonical Pointer
Primary convergence record lives at:
- `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md` (cold-start orientation — **read this first** on fresh sessions)
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`
- `pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md` (shared merge-signoff gate for AGNOTE4482 lanes)
- `.claude/agents/` (agent definitions with Three-Body tool restrictions — enforced via Claude Code frontmatter)
- `pmoves/docs/AGENTS/GRAPHITI_SIG_REVIEW_2026-02-21.md` (Phase 5 signature and traversal review snapshot)
- `pmoves/docs/AGENTS/KRISS_KROSS_ACCORD.md` (Codex-led collision overlay and weave protocol)
- `pmoves/docs/TAC/TAC_MODEL_INFRA_PERSONA_PROD_READINESS.md` (model infrastructure + persona production readiness execution overlay)

All agents entering PMOVES lanes should read that file first, then claim work before edits.

## Signoff Rule

AGNOTE4482 prospectus updates should now use one shared signoff gate:

- `pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md`

Each participating agent signs only for the sections they actually reviewed or executed. Merge readiness is a multi-agent decision, not a single-agent vibe check.

### P7 — Room-Aware Stage Manager

Pinokio 7 (P7) is the PMOVES runtime launcher and fleet orchestrator. In the rooms-on-a-stage model, P7 is not just a process spawner — it is the **room-aware stage manager**: it knows which rooms exist (via `pmoves/config/rooms/catalog.json`), selects the appropriate room profile for a given workload, and manages the transition between rehearsal → live → review → archive states. P7's NATS subjects (`p7.nats.launch`, `p7.nats.session`) are the control plane for room entry and lifecycle. When agents claim work via AGNOTE4482, P7 is the context they launch into.

## Elder-Context Pattern
`LADY P` is the connector persona for pre-flight context:
- Role: elder guide that gives reminders and smooth context before an agent starts execution.
- Function: "grams to grams" continuity so agents carry family memory, not isolated fragments.
- Boundary: advisory context only; execution ownership still follows branch claim protocol.

## Village Rule
No agent operates alone in production validation:
- execution agents
- control/review agents
- memory/security agents

Elder-context support is always available to reduce drift and collision across parallel work.

## Agent ACK (Gateway)
- Agent: `CODEX-GPT5`
- Signature: `ACK::CODEX-GPT5::PHI-4482-GATEWAY`
- Timestamp: `2026-02-20T12:12:35.7340973-05:00`

## Topology Audit Record (2026-02-20)

### Work Performed
- Created TAC trees for 5 integration submodules: BoTZ, DoX, ToKenism, Health, Wealth
- Created `TAC_INTEGRATION_TOPOLOGY.md` master connectivity map
- Wired BPM-prosodic bridge between Flute and ToKenism `musicMapping.ts`
- Created `/chit:bpm` tool specification
- Updated NATS subject catalog with new subjects
- Updated agent registry with CHIT integration fields

### New TAC Trees
| File | Submodule | Status |
|------|-----------|--------|
| [`TAC_BOTZ.md`](../TAC/TAC_BOTZ.md) | PMOVES-BoTZ | Updated from stub |
| [`TAC_DOX.md`](../TAC/TAC_DOX.md) | PMOVES-DoX | Updated from stub |
| [`TAC_TOKENISM.md`](../TAC/TAC_TOKENISM.md) | PMOVES-ToKenism-Multi | **New** |
| [`TAC_HEALTH.md`](../TAC/TAC_HEALTH.md) | Pmoves-Health-wger | **New** |
| [`TAC_WEALTH.md`](../TAC/TAC_WEALTH.md) | PMOVES-Wealth | **New** |
| [`TAC_INTEGRATION_TOPOLOGY.md`](../TAC/TAC_INTEGRATION_TOPOLOGY.md) | Cross-repo | **New** |

### Key Findings
1. Health (wger) and Wealth (Firefly III) are **pre-stage** maturity — no healthz, metrics, NATS, or CHIT
2. BoTZ P1 JWT fail-open remains the highest security priority
3. DoX NATS auth block completely missing from `nats.conf`

> **ClaWZ Status Update (2026-04-19):** ClaWZ (PMOVES-ClawZ submodule) is now the **active** Discord agent, replacing the BoTZ Gateway pattern. BoTZ is **legacy/archived** — see `pmoves/docs/archive/founding-strategy/BOTZ_GATEWAY_AGENT_INTEGRATION.md`. BoTZ references below are retained for historical audit context only.
4. BPM-prosodic bridge resolves the TAC_FLUTE.md open item
5. `tokenism.prosodic.bpm.v1` is a new NATS subject connecting Flute → ToKenism

### Handoff Notes
- Health and Wealth TAC trees serve as hardening roadmaps — implement phases 1-4 in order
- BPM encoding is spec-only — implementation in `bpm_encoder.py` not yet written
- Agent registry needs Health/Wealth NATS subjects once they start publishing

## Agent ACK (Gateway)
- Agent: `CLAUDE-OPUS`
- Signature: `ACK::CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT`
- Timestamp: `2026-02-20`

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->

## Room Catalog Audit Record (2026-03-28)

### Work Performed
- Created typed room manifest contract schema (`room.manifest.v1.schema.json`)
- Defined 3 seed rooms: z890-infra (operator), 4090-field (scout), 5090-voice (creator)
- Built room catalog loader with parity validation (`rooms.ts`)
- Added `status` lifecycle field to app schema (active/planned/deprecated)
- Added dashboard routes: `/review`, `/voice`, `/media`
- Added runtime taxonomy (`team_refs`, `service_refs`, `launcher_refs`) bridging rooms to operational topology
- Updated `ROOM_MANIFEST_CONTRACT.md` with status lifecycle and taxonomy docs

### PRs
| PR | Title | Status |
|----|-------|--------|
| #1136 | Room catalog contracts + dashboard loader | MERGED |
| #1137 | Home launcher room entry paths | IN REVIEW |
| #1142 | Dashboard routes (review, voice, media) | IN REVIEW |
| #1143 | Runtime taxonomy fields | IN REVIEW |

### Agent ACK
- Agent: `4090-CLAUDE`
- Signature: `ACK::4090-CLAUDE::ROOM-CATALOG-AUDIT`
- Timestamp: `2026-03-28`

<!-- GRAPHITI_MARK: 4090-CLAUDE::ROOM-CATALOG-AUDIT::2026-03-28 -->

## Self-Review Audit Record (2026-04-01)

### Work Performed
- Full self-review of AGNOTE4482 documentation suite, AGENTS folder, and Known Gaps
- Verified P0/P2 gap resolutions via grep/read against current codebase
- Refreshed agent count, external contributor count, and file count against live registry
- Reviewed all convergence lanes since last audit (2026-03-28)
- Cataloged 10+ PRs merged to main since last audit

### Key Findings

| Finding | Status | Evidence |
|---------|--------|----------|
| BoTZ JWT fail-open (P0) | **RESOLVED** | `gateway.py:292-299` returns HTTPException 500 on missing HAS_JOSE or SUPABASE_JWT_SECRET. `auth.py:57-65` returns HTTPException 500 on missing HAS_JOSE or JWT_SECRET. Both fail-closed. |
| BPM encoder not implemented (P2) | **RESOLVED** | `pmoves/tools/bpm_encoder.py` exists, 574 lines, delivered in PR #1168 (Shift Crew tools) |
| NATS unauthenticated references (P0) | **NOT IMPROVED** | 57 unauthenticated references across 34 files in `pmoves/` (grep: `nats://(nats\|localhost):4222` excluding `@`; measured 2026-04-02). Not reduced from baseline — batch migration still needed. |
| A2A server not exposed (P0) | **RESOLVED** | `server.py` refactored: `create_a2a_router()` exports mountable APIRouter. `main.py` mounts it via `app.include_router()` on port 8080. `docker-compose.yml` adds `A2A_DISCOVERY_PUBLIC`/`A2A_TASKS_PUBLIC` env vars. Routes: `/.well-known/agent-card.json`, `/a2a/v1/tasks`, `/a2a/v1/discover`. Auth via `SUPABASE_JWT_SECRET` (from x-hardening). |
| Agent registry count | **STALE** | Registry has 71 entries, 13 external contributors. Docs said 60 agents, 7 contributors. |
| AGENTS file count | **STALE** | 107 documents (66 root + 41 SUBMODULE_CODEX_HOMES). Docs said 73+. |

#### Post-2026-03-28 Deliverables
- **KiloCode claw config** (PR #1151): .kilo/ directory, GLM coding plan mode, 3 agents + 8 commands
- **4090 coding workstation** (PR #1155): Provider cascade (13 providers), function demands (18 functions)
- **MiniMax parity Phase 1-2** (PRs #1164, #1166): Provider cascade, TZ config, NATS wiring, BoTZ routing
- **MiniMax parity Phase 3-5** (landed on main via #1164/#1166): BoTZ tandem, DARKXSIDE triad, model fabric
- **Shift Crew tools** (PR #1168): BoTZ Trinity CLI, voice persona binding, beats-to-voice pipeline, BPM encoder, ClawZ field tests (8/8), AgentGym runner
- **Security**: Host environment leak guard consolidated (PR #1163)
- **Infra**: BIND defaults reverted to 0.0.0.0 for fleet connectivity (PR #1162)
- **TensorZero**: POSTGRES_URL fix (#1167), cross-profile depends_on removal

### Handoff Notes
- NATS auth P0 needs continued batch migration (57 refs remain across 34 files — hotspots: `services/work-marshaling/`, `services/chat-relay/`, `services/node-registry/`, `tools/`)
- A2A server needs runtime verification (compose exposure check)
- Signoff checklist sections 1, 3, 7 still unchecked — require prospectus/ClaWz/P7 runtime verification
- Agent registry count (71) should be reconciled with taxonomy docs that still reference 60

### Agent ACK
- Agent: `CLAUDE-OPUS`
- Signature: `ACK::CLAUDE-OPUS::SELF-REVIEW-AUDIT`
- Timestamp: `2026-04-01`

<!-- GRAPHITI_MARK: CLAUDE-OPUS::SELF-REVIEW-AUDIT::2026-04-01 -->

## A2A Server Runtime Wiring (2026-04-17)

### Work Performed
- Refactored `server.py`: extracted `create_a2a_router()` returning mountable `APIRouter` with all A2A routes (discovery, tasks, artifacts)
- Moved agent card from `app.state` to module-level `_agent_card` for router compatibility
- Excluded `/healthz` from router to avoid conflict with parent `main.py`
- `create_app()` preserved as backward-compatible standalone mode (internally uses `create_a2a_router()`)
- Updated `main.py`: added try/except import guard, `app.include_router(create_a2a_router())` after app creation
- Updated `docker-compose.yml`: added `A2A_DISCOVERY_PUBLIC` and `A2A_TASKS_PUBLIC` env vars (default: `false`)
- Updated `__init__.py`: exported `create_a2a_router` in `__all__`

### Files Changed
| File | Change |
|------|--------|
| `services/agent-zero/python/features/a2a/server.py` | Added `create_a2a_router()`, refactored to module-level `_agent_card`, `_register_a2a_routes()` shared by router and app |
| `services/agent-zero/python/features/a2a/__init__.py` | Added `create_a2a_router` to exports |
| `services/agent-zero/main.py` | Import guard + `include_router` mount |
| `docker-compose.yml` | `A2A_DISCOVERY_PUBLIC`, `A2A_TASKS_PUBLIC` env vars |

### Agent ACK
- Agent: `AGENT-ZERO-GLM`
- Signature: `ACK::AGENT-ZERO-GLM::A2A-RUNTIME-WIRING`
- Timestamp: `2026-04-17`



## Post-Merge Review & SPARK Node Onboarding (2026-04-18)

### Work Performed
- **PR Review**: Reviewed 3 open PRs (#1275, #1279, #1287) via specialized subordinates
- **PR #1275 (CHIT crypto P0)**: Fixed lazy accessor, sys.path resolution, numpy guard, key separation
- **PR #1279 (GRAPHITI/NATS/TAC)**: Fixed JetStream syntax, stream coverage, TAC tree schema, media stubs, shared SubjectEntry
- **PR #1287 (port audit tests)**: Fixed Path.read_text module-scoped patch
- **PR #1289 (env.shared)**: Corrected path to `pmoves/env.shared`
- **PR #1290 (geometry_decoder)**: Fail-closed passphrase, versioned KDF (PBKDF2 + scrypt fallback)
- **PR #1291 (CodeQL dedup)**: Removed duplicate CodeQL job from merge-gate.yml
- **PR #1294**: Superseded #1275+#1279 (add/add conflict on chit_common.py)
- **Post-merge**: Verified all fixes on main (79+13 tests pass), cleaned 10 stale branches
- **Test fixes**: Resolved 3 pre-existing issues (sys.exit mock, typer importorskip, Pydantic V2 migration)
- **SPARK runner**: Registered `pmoves-spark-runner` (self-hosted, spark, Linux, ARM64) — online at `/opt/actions-runner-spark`

### Files Changed (this session)
| File | Change |
|------|--------|
| `pmoves/tools/chit_common.py` | New — shared canon() extracted |
| `pmoves/services/common/nats_types.py` | New — shared SubjectEntry dataclass |
| `pmoves/tests/services/test_pr1279_fixes.py` | New — 13 regression tests |
| `pmoves/tools/chit_security_validator.py` | @validator → @field_validator (Pydantic V2) |
| `pmoves/tests/test_wger_cgp_validation.py` | sys.exit mock, test data fix |
| `pmoves/tests/test_mini_cli.py` | pytest.importorskip('typer') |
| `pmoves/services/gateway/gateway/api/chit.py` | Lazy accessor, numpy guard |
| `pmoves/tools/local_cert_runners.py` | env.shared path fix |
| `.github/workflows/merge-gate.yml` | CodeQL dedup |

### Agent ACK
- Agent: `PMOVES-AGENT-ZERO-SPARK`
- Signature: `ACK::PMOVES-AGENT-ZERO-SPARK::POST-MERGE-REVIEW-SPARK-ONBOARD`
- Timestamp: `2026-04-18`

<!-- GRAPHITI_MARK: PMOVES-AGENT-ZERO-SPARK::POST-MERGE-REVIEW-SPARK-ONBOARD::2026-04-18 -->

## Convergence Wave: Apr 17–19 Merge Sprint (2026-04-19)

### Work Performed
- **PRs #1293–#1308**: 16 PRs merged in 72-hour convergence wave, +8,800 lines
- A2A server wired into compose stack (PR #1293) — discovery + task routes exposed
- Portable sidecar config (PR #1299) — Agent Zero runs standalone on any Docker device
- CHIT crypto hardening (PR #1294) — passphrase fail-closed, versioned KDF
- Rooms-on-a-stage framework (PR #1308) — room manifest contracts, lifecycle states
- Model Integration Framework additions across configs and tooling

### ClaWZ / BoTZ Transition
ClaWZ is now the active Discord agent (PMOVES-ClawZ submodule). All BoTZ Gateway references in this document and linked TAC trees are historical. The BOTZ_GATEWAY_AGENT_INTEGRATION.md document has been archived to `pmoves/docs/archive/founding-strategy/`.

### New Reference Paths
- **Model Integration Framework**: `pmoves/docs/PMOVES_MODEL_INTEGRATION_FRAMEWORK.md`
- **Model Suit Profiles**: `pmoves/configs/model-suits/` (rooms → stage → suits → profile taxonomy)

### Agent ACK
- Agent: `AGENT-ZERO-SIDECAR`
- Signature: `ACK::AGENT-ZERO-SIDECAR::CONVERGENCE-WAVE-APR19`
- Timestamp: `2026-04-19`

<!-- GRAPHITI_MARK: AGENT-ZERO-SIDECAR::CONVERGENCE-WAVE-APR19::2026-04-19 -->
<!-- GRAPHITI_MARK: AGENT-ZERO-GLM::A2A-RUNTIME-WIRING::2026-04-17 -->
