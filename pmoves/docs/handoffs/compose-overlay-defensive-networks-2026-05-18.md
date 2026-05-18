# Handoff: Compose Overlay Defensive Network Declarations

**Date:** 2026-05-18
**Lane:** Z890-CLAUDE (infra + fleet + compose)
**Operator authorization (verbatim, DARKXSIDE 2026-05-18):**
> "2 and or 3 this needs review and knownroads and runbook etc since this has caused many a issue the insight once again are golden Z890 and should be you roll"

**Scope** — single PR, atomic:
- Add `networks:` top-level block with `external: true` declarations to each of 6 overlay compose files
- Create `pmoves/docs/operations/COMPOSE_LAYERING_RUNBOOK.md` describing the layered-base + overlay pattern, the failure modes, and the correct invocations
- Add Known Road entry to `.claude/PATTERNS.md` for the compose-layering trap

---

## Why this PR exists

DARKXSIDE-on-SPARK reported a blocker during the activation cascade work on 2026-05-18:
- `docker compose -f docker-compose.core.yml ...` failed with `service "minio" refers to undefined network pmoves_data`

**Root cause (verified by Z890-CLAUDE this session):** every overlay file in the split-overlay layout (PR #1233, commit `92522fc7`) references shared networks (`pmoves_data`, `pmoves_api`, `pmoves_app`, `pmoves_bus`, `pmoves_external`, `pmoves_monitoring`) but **none of them declare those networks**. Definitions live exclusively in `docker-compose.base.yml:552-616`.

The intended invocation (`make overlay-up-core` / `make overlay-up-full`) layers `-f docker-compose.base.yml -f docker-compose.core.yml ...` so the networks merge. Any operator who invokes compose with a single overlay file in isolation — for `docker compose config`, ad-hoc `up <service>`, force-recreate flows, IDE compose extensions, CI snippets — hits this error.

Per DARKXSIDE: *"this has caused many a issue."* This PR closes the trap.

## What changes

### 1. Defensive network declarations (6 overlay files)

Each overlay gets a `networks:` block at the file's end declaring **only the networks that file actually references**, all marked `external: true`. This:
- Makes the file syntactically self-sufficient (parses standalone)
- Documents the network dependency in the file itself
- Improves error message: "network X declared as external, but could not be found" beats "service refers to undefined network X"
- Does NOT defeat overlay isolation — overlays still merge via base.yml during `make overlay-up-*`
- Does NOT make the file usable standalone at runtime — networks must EXIST (created by prior base.yml `up` OR manual `docker network create`)

| File | Networks declared (external: true) |
|---|---|
| `pmoves/docker-compose.core.yml` | pmoves_data, pmoves_api, pmoves_app, pmoves_bus, pmoves_external, pmoves_monitoring |
| `pmoves/docker-compose.agents.yml` | pmoves_data, pmoves_api, pmoves_app, pmoves_bus, pmoves_external |
| `pmoves/docker-compose.media.yml` | pmoves_data, pmoves_api, pmoves_app, pmoves_bus, pmoves_external, pmoves_monitoring |
| `pmoves/docker-compose.ui.yml` | pmoves_app, pmoves_bus, pmoves_external |
| `pmoves/docker-compose.workers.yml` | pmoves_data, pmoves_api, pmoves_app, pmoves_bus, pmoves_external, pmoves_monitoring |
| `pmoves/docker-compose.apps.yml` | pmoves_data, pmoves_api, pmoves_app, pmoves_bus, pmoves_external |

### 2. Runbook — `pmoves/docs/operations/COMPOSE_LAYERING_RUNBOOK.md`

Operator-facing reference for the compose layering pattern. Sections:
- **Two invocation patterns** — monolithic (`$(DC)` w/ root `docker-compose.yml`) vs overlay (`$(OVERLAY_DC)` w/ `docker-compose.base.yml` first)
- **Network ownership** — base.yml owns all 6 network definitions; overlays declare them as external
- **Failure modes + recovery** — undefined network, network already exists, force-recreate after env.shared edit
- **Allowed raw invocations** — when single-file compose IS okay (config validation, debugging)
- **Forbidden raw invocations** — `up`, `restart`, `recreate` against a single overlay without base.yml

### 3. Known Road entry — `.claude/PATTERNS.md`

Add to Known Roads section: "Compose overlay must layer base.yml first" — explain the trap, point to the runbook, give the canonical `make` targets.

## Why NOT just fix it differently

- **Don't move network defs into core.yml.** That breaks the overlay isolation pattern (Rec #9, PR #1233). Base is the single source of truth.
- **Don't add networks to root `docker-compose.yml` AND base.yml.** Already redundant — root has its own copy (line 4276). Don't make it triple.
- **Don't auto-create networks in the overlay file** with full subnet config. Subnets in two places = drift on next subnet change.
- **`external: true` is the right shape** — it says "we depend on this network existing, defined elsewhere," which is exactly the relationship.

## Test plan

- [ ] `docker compose -f pmoves/docker-compose.core.yml config` — parses cleanly (was failing before)
- [ ] Same for `agents.yml`, `media.yml`, `ui.yml`, `workers.yml`, `apps.yml`
- [ ] `make -C pmoves overlay-up-core` — regression check, still works (base.yml + core.yml layered, networks merge fine since `external: true` matches existing definition)
- [ ] `make -C pmoves up-data-tier` — regression check (root file path)
- [ ] Cold-start test: `docker compose -f pmoves/docker-compose.core.yml up -d minio` with no networks existing → fails with "network pmoves_data declared as external, but could not be found" (CORRECT error, clearer than "undefined network")
- [ ] With networks pre-created: same command succeeds

## Follow-ups (NOT in this PR)

- Audit other compose files for the same pattern (`docker-compose.n8n.yml`, `docker-compose.external.yml`, `docker-compose.jellyfin-ai.yml`, etc.) — if they have the same trap, batch-apply the fix in a follow-up PR.
- Consider whether `docker-compose.base.yml` should grow a corresponding `services: {}` placeholder so it can be invoked solo for network bootstrap without errors.

## Coordination

- SPARK / DARKXSIDE-on-SPARK: once this PR lands, SPARK's `make overlay-up-core` flow becomes more resilient. Stale-file blocker that surfaced this issue is operational on SPARK (git pull origin main on SPARK once this merges); the PR fixes the *next* occurrence even if SPARK still hits the trap from raw invocations.
- 5090-CLAUDE: lane attribution shared; this PR closes a multi-file pattern issue that's been costing fleet hours.

## Trail

CHIT trail will be signed at PR-creation time via `pmoves-chit-sign` skill. Trail-id captured in PR body.

ACK::Z890-CLAUDE::COMPOSE-OVERLAY-DEFENSIVE-NETWORKS::2026-05-18
