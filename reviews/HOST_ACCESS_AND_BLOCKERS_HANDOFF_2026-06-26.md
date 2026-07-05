# PMOVES.AI — Host Access & Blocker Handoff
**Date:** 2026-06-28 (updated from 2026-06-26 compaction)  
**Author:** Agent Zero (agent0)  
**Context:** Post-compaction review of the 2026-06-26 Kong/PostgREST/MCP/CHIT workstream. `z890-CLAUDE` is the designated owner for DB-service fixes.

---

## 1. Verified current state (corrected from compaction summary)

| Area | Claim | Verified state |
|---|---|---|
| **Kong entrypoint** | Fixed with `/dev/tcp` bash wait, migrations idempotent, core compose aligned. | ✅ Committed in `main` (commits `f1c80a64d`, `ee95c7210`, `ea7b6e2a7`). `docker-compose.yml:717` and `docker-compose.core.yml:428` use `/bin/bash` `/dev/tcp/supabase-db/5432` wait. |
| **PMOVES-supabase submodule** | Empty / not populated. | ⚠️ Still empty: `git submodule status PMOVES-supabase` shows `-61116aee...`. Blocks edge-functions volume and forked configs. |
| **PostgREST `PGRST125`** | Fixed by adding `PGRST_DB_EXTRA_SEARCH_PATH` and `pmoves_kb` migrations. | ❌ Not committed. `env.tier-supabase.example` only sets `SUPABASE_SCHEMA=public,pmoves_core,pmoves_kb`. No `PGRST_DB_EXTRA_SEARCH_PATH` in compose or env. No `pmoves_kb` schema migration exists in `pmoves/supabase/migrations/`. |
| **Host port bindings** | `pmoves_public` network added, host ports mapped. | ⚠️ Partially committed? Current `docker-compose.yml` Kong port line uses `0.0.0.0` default with a Docker Desktop note. Core compose uses `127.0.0.1`. No `pmoves_public` network visible in the grep of `docker-compose.yml`. |
| **A2A server** | Implemented on port 8080 with routes. | ✅ Code exists: `pmoves/services/agent-zero/python/features/a2a/server.py` exports `create_a2a_router()`, exposes `/.well-known/agent-card.json`, `/a2a/v1/tasks`, `/a2a/v1/discover`. |
| **MCP/A2A registry** | Five root MCP servers exist but are not registered. | ❌ `pmoves/config/agent_registry.yaml` has no `mcp_servers` or `a2a_servers` top-level sections. `.a0proj/agents.json` is `{}`. `pmoves/config/rooms/catalog.json` has no MCP `apps` or `skill_bindings`. |
| **CHIT signing-card schema** | `pmoves/contracts/schemas/identity/signing-card.v1.schema.json` pending land. | ❌ `pmoves/contracts/schemas/identity/` does not exist. No signing-card schema committed. |
| **Docs alignment** | `AGNOTE4482.md` etc. need activation checklist. | ❌ No activation checklist for A2A/MCP env vars or CHIT mode transitions found in the docs query. |

---

## 2. Remaining blockers — ranked with owners

| Rank | Blocker | Severity | Owner | Proposed branch |
|---|---|---|---|---|
| 1 | `PMOVES-supabase` submodule is empty. | High | Agent Zero (git-ops) | `fix/supabase-submodule-checkout` |
| 2 | PostgREST `PGRST125` / `pmoves_kb` schema gap. | High | z890 (DB services) | `fix/postgrest-pmoves-kb-schema` |
| 3 | Host network `pmoves_public` and port-bind defaults lost/unclear. | Medium | z890 (DB services / infra) | `fix/host-network-pmoves-public` |
| 4 | MCP/A2A not registered in `agent_registry.yaml` or room manifests. | High | Agent Zero (registry) | `feat/agent-registry-mcp-a2a-discovery` |
| 5 | Room manifests lack MCP `apps` and `skill_bindings`. | High | Agent Zero (rooms) | `feat/rooms-mcp-planned-apps` |
| 6 | CHIT `signing-card.v1.schema.json` and carve-out missing. | Medium | Agent Zero (contracts) | `feat/chit-signing-card-schema-carveout` |
| 7 | AGNOTE4482 / room docs lack activation checklist. | Low | Agent Zero (docs) | `docs/p7-room-manifest-alignment` |

---

## 3. AGNOTE4482 register claims verification

| Claim in review doc | Source doc / file | Status |
|---|---|---|
| P7 maintains authoritative room topology via `pmoves/config/rooms/catalog.json`. | `AGNOTE4482.md` | ✅ `catalog.json` exists with 6 rooms. |
| Room manifest schema requires `apps` and `skill_bindings` arrays. | `ROOM_MANIFEST_CONTRACT.md`, `room.manifest.v1.schema.json` | ✅ Schema requires both; validator checks them. |
| A2A server routes exist and are auth-gated. | `server.py` | ✅ `create_a2a_router()` present. |
| Default A2A/MCP enablement incomplete. | `env.shared.example`, `.a0proj/agents.json`, `agent_registry.yaml` | ❌ Confirmed missing. |
| Five root MCP servers are not declared as room skills. | `catalog.json`, room manifests | ❌ Confirmed missing. |
| CHIT `signing-card.v1.schema.json` pending. | `pmoves/contracts/schemas/identity/` | ❌ File missing. |

---

## 4. Atomic PR plan (targeted, merge-ordered)

1. **`fix/supabase-submodule-checkout`** — `git submodule update --init PMOVES-supabase` and commit the updated gitlink. Scope: submodule only.
2. **`fix/postgrest-pmoves-kb-schema`** — Add `pmoves_kb` schema creation migration, grants, and set `PGRST_DB_EXTRA_SEARCH_PATH=pmoves_core,pmoves_kb,public` in compose/env. **Owner: z890.**
3. **`fix/host-network-pmoves-public`** — Restore `pmoves_public` network in `docker-compose.yml`, tighten Kong default bind to `127.0.0.1`, add host port mappings for Supabase services. **Owner: z890 / infra.**
4. **`feat/agent-registry-mcp-a2a-discovery`** — Add top-level `mcp_servers:` and `a2a_servers:` sections to `pmoves/config/agent_registry.yaml`; add A2A/MCP env toggles to `pmoves/env.shared.example`.
5. **`feat/rooms-mcp-planned-apps`** — Add planned `apps[]` entries with `action_namespace=mcp.v1.*` and matching `skill_bindings` to `z890-infra.room.fabric.json`, `4090-field.room.control.json`, and `hermes-agent.room.control.json`; update `validate_room_manifests.py` if new cross-references needed.
6. **`feat/chit-signing-card-schema-carveout`** — Create `pmoves/contracts/schemas/identity/signing-card.v1.schema.json`; add `patterns.yaml` carve-out for versioned identity schemas if needed.
7. **`docs/p7-room-manifest-alignment`** — Update `AGNOTE4482.md`, `ROOMS_ON_A_STAGE.md`, `ROOM_MANIFEST_CONTRACT.md` with MCP/A2A bindings and a CHIT mode-transition activation checklist.

---

## 5. Next actions

- [x] Agent Zero: verify `PMOVES-supabase` submodule gitlink — already correct at `61116aee`. Directory just needs `git submodule update --init PMOVES-supabase` on each clone.
- [x] Agent Zero: implement `feat/agent-registry-mcp-a2a-discovery` — **opened as PR #1893**.
- [x] Agent Zero: implement `feat/rooms-mcp-planned-apps` — **opened as PR #1894**.
- [ ] Review & merge PRs #1893 and #1894.
- [ ] z890: pick up `fix/postgrest-pmoves-kb-schema` and `fix/host-network-pmoves-public`.
- [ ] Agent Zero: open `feat/chit-signing-card-schema-carveout` and `docs/p7-room-manifest-alignment` after registry/room PRs land.

---

## 6. Implementation status

| Branch | PR | Status |
|---|---|---|
| `feat/agent-registry-mcp-a2a-discovery` | [#1893](https://github.com/POWERFULMOVES/PMOVES.AI/pull/1893) | ✅ Adds `mcp_servers`/`a2a_servers` to `agent_registry.yaml` and A2A/MCP env toggles to `env.shared.example`. Pushed and PR opened. |
| `feat/rooms-mcp-planned-apps` | [#1894](https://github.com/POWERFULMOVES/PMOVES.AI/pull/1894) | ✅ Adds planned MCP apps/skill bindings to `z890-infra.room.fabric.json` and `4090-field.room.control.json`. Validated. Pushed and PR opened. |
| `fix/supabase-submodule-checkout` | N/A | ✅ Gitlink already correct; submodule initialized in worktree. Just run `git submodule update --init PMOVES-supabase` on fresh clones. |

---

## 7. SPARK node next steps

Opened the SPARK deliverables as focused, atomic PRs:

| Branch | PR | What it does |
|---|---|---|
| `feat/spark-gpu-mesh-jetstream` | **[#1895](https://github.com/POWERFULMOVES/PMOVES.AI/pull/1895)** | Adds `MESH_GPU` (`mesh.gpu.>`) and `CONTENT_PROVENANCE` (`content.>`) JetStream streams to `pmoves/scripts/nats/init_streams.sh` (nats-init sidecar). |
| `feat/spark-shape-worker` | **[#1898](https://github.com/POWERFULMOVES/PMOVES.AI/pull/1898)** | Adds `pmoves/services/spark-shape-worker/main.py`. **Group A** quick-wins (secret loader, URL redaction, non-object guard, README) applied by Z890. **Group B** contract-correctness (lexicon schema, mesh handshake envelope, inline validation) applied and pushed. |

### Recommended SPARK sequence

1. **Review/merge #1895** so `mesh.gpu.*` and `content.*` streams are live.
2. **Review/merge #1898** so the shape worker is available to route attested packets to HiRAG / Hyperdimensions.
3. **Execute Phase 1 model deployment** on the physical DGX Spark GB10 host using `scripts/spark_deploy_models.sh` (P0 bundle: `qwen3.5-35b-a3b-q4_K_M`, `qwen2.5-coder:32b-q4_K_M`).
4. **Pick up audio/cloud API work** (`process_audio_with_cloud_api`) and A2UI Remotion hologram viewport scaling when the node has host-side GPU cycles.

---

## 8. Files to watch

- `pmoves/docker-compose.yml` (Kong entrypoint, host binds, PostgREST env)
- `pmoves/docker-compose.core.yml` (Kong hardened values)
- `pmoves/env.tier-supabase.example`
- `pmoves/env.shared.example`
- `pmoves/config/agent_registry.yaml`
- `pmoves/config/rooms/catalog.json` and `*.room.*.json` manifests
- `pmoves/contracts/schemas/identity/signing-card.v1.schema.json` (to be created)
- `pmoves/scripts/validate_room_manifests.py`
- `pmoves/supabase/migrations/` (z890 domain)

## 9. 2026-06-30 merge update

All four pending PRs from the handoff have been rebased onto `origin/main`, review threads resolved, and admin-merged on green merge-gate checks:

| PR | Merged commit | Notes |
|---|---|---|
| #1893 | `f10b933b4` | Registry MCP/A2A server discovery sections + `A2A_ENABLED` env toggle. |
| #1894 | `4191c4d5d` | Planned MCP apps + skill bindings in `z890-infra.room.fabric.json` and `4090-field.room.control.json`. |
| #1895 | `33bc690b5` | `MESH_GPU` (`mesh.gpu.>`) and `CONTENT_PROVENANCE` (`content.>`) JetStream catch-all streams; granular YAMLs marked superseded. |
| #1898 | `ff30d94f0` | `pmoves/services/spark-shape-worker/main.py` with Group A quick-wins, Group B contract-correctness, and a follow-up fix coercing `model_id`/`node_id` to strings in shaped-packet labels/meta for schema compliance. |

Updated after #1924 (z890 infra blocker PR):

| PR | Merged commit | Notes |
|---|---|---|
| #1924 | `03ff60229` | `pmoves_kb` migration + `PGRST_DB_EXTRA_SEARCH_PATH`, `pmoves_public` host network, Kong 127.0.0.1 default binds, Makefile bootstrap db user fix. |

Updated 2026-06-30 after #1925 (CHIT signing-card schema + activation checklist):

| PR | Merged commit | Notes |
|---|---|---|
| #1925 | `3258d8762` | Canonical `signing-card.v1.schema.json`; audit script loads from disk; activation checklist added to AGNOTE4482.md, ROOMS_ON_A_STAGE.md, ROOM_MANIFEST_CONTRACT.md; SIGNING_IDENTITY_CARDS.md marked as landed. |

Updated 2026-07-01 after #1926 (SPARK KIMI worktree delta reconciliation):

| PR | Merged commit | Notes |
|---|---|---|
| #1926 | `c1b549466` | Reconciled Agent Zero SPARK worktree deltas (migrations, generated kong.yml, tokenism-simulator files, env.shared.pre-funnel, etc.) and landed the Kong /bin/bash + /dev/tcp entrypoint fix. Submodule gitlink promotion removed from this PR because the 21 pins were rollbacks/sideways relative to the new origin/main; a separate submodule pass is needed after alignment. |

All 2026-06-26 handoff blockers and the SPARK KIMI dirty-PR issue are now closed. The local `main` remains divergent because the handoff-doc updates live only in `/a0/usr/projects/project_2`; recommend a housekeeping pass to fast-forward/merge the handoff doc into a PR or to `origin/main`.
