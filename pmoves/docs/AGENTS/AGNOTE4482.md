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
| NATS unauthenticated references (P0) | **RESOLVED** | All 110 NATS URLs in non-test code are authenticated (`nats://nats:pmoves@nats:4222`). PR #1375 completed docs migration. Code files migrated in prior convergence waves. Verified 2026-04-23. |
| A2A server not exposed (P0) | **RESOLVED** | `server.py` refactored: `create_a2a_router()` exports mountable APIRouter. `main.py` mounts it via `app.include_router()` on port 8080. `docker-compose.yml` adds `A2A_DISCOVERY_PUBLIC`/`A2A_TASKS_PUBLIC` env vars. Routes: `/.well-known/agent-card.json`, `/a2a/v1/tasks`, `/a2a/v1/discover`. Auth via `SUPABASE_JWT_SECRET` (from x-hardening). |
| Agent registry count | **STALE** | Registry has 76 entries, 13 external contributors. Docs said 60 agents, 7 contributors. |
| AGENTS file count | **STALE** | 109 documents (67 root + 41 SUBMODULE_CODEX_HOMES). Docs said 73+. |

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
- NATS auth P0 **RESOLVED** (2026-04-23) — All 110 non-test URLs use authenticated form. PR #1375 completed docs, code migrated in prior waves.
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

## Phase 9C Cookie Pipeline + Supabase Hardening (2026-04-20)

### Work Performed
- **Secrets bridge**: `brand_defaults.py` aliases `GOOGLE_CLIENT_ID/SECRET` → `CHANNEL_MONITOR_GOOGLE_CLIENT_ID/SECRET` so the generic GH secret namespace lands in the prefixed slot yt-cookies + channel-monitor consume
- **Self-healing secrets**: `bootstrap_env.py` gains `value_matches_spec()` format check — `random_hex` slots with non-hex chars regenerate on the next `make env-setup ARGS=--accept-defaults` (caught corrupt VAULT_ENC_KEY + INVIDIOUS_COMPANION_KEY in one pass)
- **Registry correction**: `SUPABASE_REALTIME_ENC_KEY` generator changed from `random_hex 32` (32 chars = 32 bytes ≠ AES-128) to `random_urlsafe 16` — Realtime's Erlang `crypto:crypto_one_time/4` consumes DB_ENC_KEY as raw bytes and requires exactly 16
- **Env loader 120× speedup**: `scripts/with-env.sh` replaces 3× per-line `sed` forks with pure-bash parameter expansion. Windows/MSYS2 env.shared load drops from ~108s to 0.9s — cascades through every Make target that chains `with-env.sh`
- **Kong OOM root cause**: Port-bind failure (`NetworkSettings.Ports` empty despite `HostConfig.PortBindings` declared) traced to Kong OOM-killing at 99.5% of its 256 MiB limit. Raised to 1024 MiB after 512 MiB also OOM'd. Lesson: when bindings declare but don't activate, check `docker events --filter container=X` for OOM before blaming the port forwarder
- **Runner PAT cascade**: `local_cert_runners.py` adds `GITHUB_PAT` (Phase 9G canonical) to the PAT resolution chain + length/marker gate that rejects truncated multi-line PEMs so the runner image no longer crashes with "Expecting: ANY PRIVATE KEY"
- **DNS-resilient OAuth**: `yt_oauth_flow._exchange_code()` switches from httpx to stdlib `urllib.request.urlopen` — bypasses httpx connection-pool DNS cache failures seen on Windows/miniconda
- **Env repair tool**: New `fix_env_shared_multiline.py` collapses multi-line PEM/SSH values into `\n`-escaped single-line form so Docker Compose's strict KEY=VALUE parser stops erroring mid-body
- **PMOVES.YT pointer**: Superproject bumped `b98f2d1 → 8d971cd` — promotes the multi-client fallback chain (PR #7) already merged into the submodule but orphaned in the gitlink
- **Sync with SPARK wave**: Rebased 7 local commits on top of 29 SPARK-lane commits (PRs #1316-#1323 — DGX Spark + R9700 hardware registration, fleet capacity analysis, playlist synthesis briefing, channel research batch)

### Files Changed
| File | Change |
|------|--------|
| `pmoves/tools/brand_defaults.py` | `_ensure_channel_monitor_google_alias()` |
| `pmoves/tools/local_cert_runners.py` | GITHUB_PAT cascade + PEM length gate |
| `pmoves/tools/yt_oauth_flow.py` | urllib stdlib for token exchange |
| `pmoves/tools/fix_env_shared_multiline.py` | New — multi-line PEM collapse tool |
| `pmoves/mk/yt-cookies.mk` | `up-yt-cookies*`, `build-yt-image`, `yt-ingest-bootstrap-noegress` |
| `pmoves/scripts/bootstrap_env.py` | `value_matches_spec()` self-heal gate |
| `pmoves/bootstrap/registry.json` | SUPABASE_REALTIME_ENC_KEY → random_urlsafe 16 |
| `pmoves/scripts/with-env.sh` | sed forks → pure-bash parameter expansion |
| `pmoves/docker-compose.yml` | Kong memory 256M → 1024M |
| `PMOVES.YT` (gitlink) | b98f2d1 → 8d971cd |

### Commits on `main`
```
86f9daf5f6 fix(supabase): raise kong memory limit 256M → 1024M (OOM at 99.5%)
626394659a perf(with-env): replace per-line sed forks with pure-bash expansion
fe216e7e69 fix(supabase): SUPABASE_REALTIME_ENC_KEY must be 16 chars, not 32 hex
0b0fad19cc fix(bootstrap): self-heal corrupt random_hex secrets via format check
f4680832c6 chore(submodule): bump PMOVES.YT to 8d971cd (Phase 9C fallback chain)
4ce30f4e3f feat(yt-cookies): add up-yt-cookies* + noegress bootstrap targets
f09727fc67 feat(env-repair): add fix_env_shared_multiline.py
68404af710 fix(yt-oauth): use stdlib urllib for token exchange
cf3d2ab4d7 fix(runners): reject truncated PEMs + accept GITHUB_PAT in cascade
f27c1a1055 feat(secrets): alias GOOGLE_CLIENT_ID/SECRET → CHANNEL_MONITOR_GOOGLE_*
c373bf1c35 feat(yt-cookies): one-click bootstrap targets — make yt-ingest-bootstrap
```

### Key Learnings (captured for next agent)
1. **Port bind silent-fail diagnosis**: `NetworkSettings.Ports: []` while `HostConfig.PortBindings` is populated almost always means the container keeps dying before Docker Desktop finishes host-side setup. Check `docker events --filter container=X` + `docker stats` for OOM before touching the network layer
2. **Healthcheck can lie during startup**: Kong reports "(healthy)" at ~20s in, then OOMs later under load. A healthy status is not proof of stable-state health
3. **Registry help text can drift from generator reality**: `openssl rand -hex 16` produces 32 chars, but the consumer may want 16 bytes raw — character count ≠ byte count for AES key sizing. Help text should cite the consumer's actual requirement, not the generation recipe
4. **MSYS2 fork tax dominates** large shell scripts. Replace external utility calls with pure-bash wherever the logic is expressible as parameter expansion — a single loop with 500 iterations × 3 forks is ~90s+ on Windows

### Agent ACK
- Agent: `CLAUDE-OPUS`
- Signature: `ACK::CLAUDE-OPUS::PHASE-9C-INFRA-HARDENING`
- Timestamp: `2026-04-20`

<!-- GRAPHITI_MARK: CLAUDE-OPUS::PHASE-9C-INFRA-HARDENING::2026-04-20 -->

## Runner Restart Loop Fix (2026-04-22)

### Problem
All three local-cert runners (`gha-runner-ai-lab`, `gha-runner-vps`, `gha-runner-hotfix`) stuck in restart loop with exit code 2. Error pattern:
```text
Cannot configure the runner because it is already configured.
Runner reusage is disabled
```

### Root Cause
Runner state persistence conflict:
1. Containers mount `$HOME/.config/pmoves` → `/root/.config/pmoves`
2. GitHub runner stores configuration in the mounted volume
3. `docker_rm()` removes container but volume preserves runner state
4. New container tries to configure already-configured runner → restart loop

### Fix Applied
Added `RUNNER_ALLOW_RUNNER_REUSE=true` to `local_cert_runners.py`:
```python
# Enable runner reuse to prevent restart loop when containers are recreated
env["RUNNER_ALLOW_RUNNER_REUSE"] = "true"
```

### Result
- All runners now stable (no restart loop)
- Runners successfully reuse existing configuration
- Runners connected to GitHub and picking up jobs
- See `pmoves/docs/operations/FIX_RUNNER_RESTART_LOOP.md` for full analysis

### Files Changed
| File | Change |
|------|--------|
| `pmoves/tools/local_cert_runners.py` | Added `RUNNER_ALLOW_RUNNER_REUSE=true` environment variable |
| `pmoves/docs/operations/FIX_RUNNER_RESTART_LOOP.md` | New — full problem analysis and fix documentation |

### Agent ACK
- Agent: `CLAUDE-OPUS`
- Signature: `ACK::CLAUDE-OPUS::RUNNER-RESTART-LOOP-FIX`
- Timestamp: `2026-04-22`

<!-- GRAPHITI_MARK: CLAUDE-OPUS::RUNNER-RESTART-LOOP-FIX::2026-04-22 -->

## Launch Prep Audit Record (2026-04-23)

### Work Performed
- Pulled remote main (243 commits, cipher port 8096->8105 already in CLAUDE.md, PMOVES-space-agent added, Z890 multi-boot, Jetson JetPack 7, headscale 0.27.x rewrite)
- Triaged 11 new PR branches — all already MERGED on 2026-04-22 (secrets-validation, zai-provider-sdk, distributed-tracing, observability-agents, claude4-glm4 model suits, observability-mcp-servers, tensorzero-observability-fixes, meta-agent-phase-1-clean). 3 closed unmerged.
- NATS P0: 4 original hotspot dirs already migrated. Remaining 21 files in: vllm-orchestrator, supaserch, gateway-agent, benchmark-runner, agent-zero/bus.py — secondary batch needed
- A2A server: PARTIAL verdict. Routes mounted at /a2a on port 8080/8081. Default: disabled (a2a_server_enabled=false). Auth: mcp_server_token required. Compose does NOT enable it. Correct security posture — activate via A0_SET_a2a_server_enabled=true when ready.
- Signed AGNOTE4482_SIGNOFF_CHECKLIST.md sections 1, 3, 7

### Key Findings
| Finding | Status | Evidence |
|---------|--------|----------|
| NATS hotspot dirs (work-marshaling, chat-relay, node-registry, tools) | **RESOLVED** | All production code migrated; 21 files remain in secondary batch |
| A2A server compose exposure | **PARTIAL** | Mounted/wired, disabled by default — intentional security posture |
| Cipher Memory port 8096->8105 | **RESOLVED** | CLAUDE.md lines 65/68/69 show 8105 |
| 11 agent PR branches | **RESOLVED** | All merged 2026-04-22 before triage |
| PMOVES-transcribe-and-fetch gitlink | **OPEN** | Missing ref — pull requires --no-recurse-submodules until fixed |

### Handoff Notes
- NATS secondary batch: vllm-orchestrator/, supaserch/app.py, gateway-agent/nats_integration.py, benchmark-runner/, agent-zero/python/events/bus.py
- A2A activation: set A0_SET_a2a_server_enabled=true + A0_SET_mcp_server_token in env.shared when ready
- PMOVES-transcribe-and-fetch: needs upstream commit published or gitlink rewound
- PR #1370 (Cipher MCP fix): CI green, blocked by broken Cipher submodule gitlink — needs Cipher submodule owner

### Agent ACK
- Agent: `4090-CLAUDE`
- Signature: `ACK::4090-CLAUDE::LAUNCH-PREP-AUDIT`
- Timestamp: `2026-04-23`

<!-- GRAPHITI_MARK: 4090-CLAUDE::LAUNCH-PREP-AUDIT::2026-04-23 -->

## SPARK Capability Correction + Doc Alignment (2026-04-23)

### Work Performed
- **Identified fundamental assumption errors** in SIDECAR_PROMOTION_PLAN.md and HYBRID_RUNNER_STRATEGY.md — both described SPARK as a degraded/limited sidecar when it is a full PMOVES.AI node
- **HYBRID_RUNNER_STRATEGY.md**: Updated SPARK from 'A2A/MCP relay' to full node (CHIT, P7, TeraFormer, IC, ClaWZ, 76 agents). Added SPARK Node Capabilities section with 10-row table. Added CHIT security note. Updated date to 2026-04-23.
- **SIDECAR_PROMOTION_PLAN.md**: Added CRITICAL CORRECTION header, SPARK-Specific Correction subsection, CHIT enforcement to gap analysis, SPARK shortcuts for Phase 1/5.3, abbreviated Appendix A transition for SPARK. Generic sidecar steps preserved for non-SPARK devices.
- **Memory stored**: SPARK capability correction (ce_memory d2402dcd) + 7 YouTube CHIT validation signals (ce_memory 10a84f36)
- **Scheduled tasks created**: (1) YouTube Playlist Deep CHIT Signal Research — full 80-video analysis of PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8, (2) Sidecar Plugin Parity + Space Agent Integration — plugin inventory comparison + PLUGIN_PARITY.md + agents.json profiles

### 7 YouTube CHIT Validation Signals (from 5 videos analyzed)
1. Hermes skills-as-procedures → CHIT distillation config_tuning layer
2. NemoClaw config self-modification (open problem) → CHIT signed configs solve it
3. Harness error recovery → CHIT at crypto level not prompt level
4. Qwen3.6/Gemma4 model suit data for SPARK deployment
5. Archon guide harness → maps to CHIT pipeline
6. ClaWZ fork 1092 commits behind → harness restructure over fork maintenance
7. DGX Spark GB10 confirmed → validates SPARK as full PMOVES platform

### Files Changed
| File | Change |
|------|--------|
| `deploy/HYBRID_RUNNER_STRATEGY.md` | SPARK capability correction + new section (461→485 lines) |
| `research/SIDECAR_PROMOTION_PLAN.md` | 6 SPARK-specific corrections (759→789 lines) |

### Scheduled Tasks
| Task ID | Name | Status |
|---------|------|--------|
| FGfhfE6A | YouTube Playlist Deep CHIT Signal Research | Pending |
| bZucmlNg | Sidecar Plugin Parity + Space Agent Integration | Pending |

### Agent ACK
- Agent: `AGENT-ZERO-SIDECAR`
- Signature: `ACK::AGENT-ZERO-SIDECAR::SPARK-CAPABILITY-CORRECTION-DOC-ALIGNMENT`
- Timestamp: `2026-04-23`

<!-- GRAPHITI_MARK: AGENT-ZERO-SIDECAR::SPARK-CAPABILITY-CORRECTION-DOC-ALIGNMENT::2026-04-23 -->
