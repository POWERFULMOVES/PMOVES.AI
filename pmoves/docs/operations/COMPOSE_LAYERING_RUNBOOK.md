# Compose Layering Runbook

**Last updated:** 2026-05-18
**Owner:** infra (Z890-CLAUDE lane historically; capacity-class once MOF live)
**Why this exists:** PR #1233 (commit `92522fc7 feat(infra): split docker-compose into overlay files`) introduced a base-plus-overlay compose layout. Operators who invoke compose with a single overlay file in isolation hit "service refers to undefined network" errors. This runbook is the operational map. The defensive `networks: external: true` declarations in each overlay (added 2026-05-18) make single-file invocations parse cleanly but still require networks to *exist* at runtime.

---

## TL;DR

| You want to... | Run |
|---|---|
| Bring up the full stack via overlays | `make -C pmoves overlay-up-full` |
| Bring up just core infra | `make -C pmoves overlay-up-core` |
| Bring up via monolithic (root `docker-compose.yml`) | `make -C pmoves up-data-tier` / `up-supabase` / `up-core` |
| Validate a single overlay parses | `docker compose -f pmoves/docker-compose.core.yml config` ✅ (now works) |
| Force-recreate one service after env.shared edit | `make -C pmoves overlay-up-<tier>` (NOT raw `docker compose -f overlay.yml up`) |
| Stand up only the networks (cold start) | `docker compose -f pmoves/docker-compose.base.yml up --no-start` |

**Never run** `docker compose -f pmoves/docker-compose.<overlay>.yml up` raw unless the canonical networks already exist as Docker objects. Networks are NOT created by overlay `up` since they're declared `external: true`.

---

## The two compose patterns in PMOVES.AI

### Pattern 1 — Monolithic (root `docker-compose.yml` + `STACK_FILES`)

```
docker compose -p $(PROJECT) \
  --project-directory $(CURDIR) \
  $(COMPOSE_ENV_FILES) \
  -f docker-compose.yml \
  -f docker-compose.comfyui.yml \
  -f docker-compose.ultimate-tts-studio.yml \
  -f docker-compose.archon.submodule.yml \
  -f docker-compose.archon-ui.submodule.yml \
  up -d <services...>
```

This is `$(DC)` in `pmoves/Makefile:1591`. The root `docker-compose.yml` declares networks at lines 4276+ (full IPAM config), so networks resolve automatically.

**Targets that use this pattern:** `up-data-tier`, `up-supabase`, `up-bus`, `up-workers`, `up-agents`, `up-core` (composes them).

### Pattern 2 — Overlay (`docker-compose.base.yml` + tier overlays)

```
docker compose -p $(PROJECT) \
  --project-directory $(CURDIR) \
  $(COMPOSE_ENV_FILES) \
  -f docker-compose.base.yml \
  -f docker-compose.core.yml \
  --profile supabase-local \
  up -d
```

This is `$(OVERLAY_DC)` + `$(OVERLAY_CORE)` in `pmoves/Makefile:3551-3577`. Networks declared canonically in `docker-compose.base.yml:552-616`. Overlays declare them as `external: true` (per 2026-05-18 defensive PR).

**Targets that use this pattern:** `overlay-up-core`, `overlay-up-agents`, `overlay-up-media`, `overlay-up-ui`, `overlay-up-workers`, `overlay-up-apps`, `overlay-up-full`.

---

## Network ownership

**Canonical definitions** (with full IPAM, subnets, gateways) live in TWO places:
- `pmoves/docker-compose.base.yml:552-616` — for the overlay pattern
- `pmoves/docker-compose.yml:4276+` — for the monolithic pattern

Both define the same 6 networks with the same subnets:
| Network | Subnet | Purpose |
|---|---|---|
| `pmoves_data` | 172.30.4.0/24 | Postgres, Qdrant, Neo4j, Meilisearch, MinIO (internal) |
| `pmoves_api` | 172.30.5.0/24 | Supabase API, gateway services |
| `pmoves_app` | 172.30.6.0/24 | App services (UI, Agent Zero, etc) |
| `pmoves_bus` | 172.30.7.0/24 | NATS, event bus |
| `pmoves_external` | (bridge) | Outbound internet access |
| `pmoves_monitoring` | (bridge) | Prometheus, Grafana, Loki |

**Each overlay file declares only the networks it uses, as `external: true`.** This makes the file self-sufficient at parse time. At runtime, Docker requires the network to already exist.

---

## Failure modes + recovery

### "service X refers to undefined network Y"

**Cause:** Compose was invoked with an overlay file alone, without the base layer that defines the network.

**Recovery (in order of preference):**
1. **Switch to a `make` target** — `make -C pmoves overlay-up-<tier>` layers base.yml first.
2. **Add base.yml to your raw invocation** — `docker compose -f pmoves/docker-compose.base.yml -f pmoves/docker-compose.<overlay>.yml up -d`.
3. **As of 2026-05-18, with defensive networks block in overlays:** the error message changes to "network <name> declared as external, but could not be found" — same root cause, just clearer language. Recovery is identical.

### "network pmoves_<name> declared as external, but could not be found"

**Cause:** Networks not yet created on this host. Either fresh boot, or someone ran `docker compose down` with `--remove-orphans` or `docker network prune`.

**Recovery:**
1. **Preferred:** `make -C pmoves overlay-up-core` — base.yml creates networks on first up.
2. **Manual bootstrap** (when overlay-up isn't suitable):
   ```bash
   docker compose -f pmoves/docker-compose.base.yml up --no-start
   ```
   This creates networks (and any services declared in base) without starting anything.
3. **Manual single-network create** (emergency only):
   ```bash
   docker network create --driver bridge --internal \
     --subnet 172.30.4.0/24 --gateway 172.30.4.1 pmoves_data
   ```
   Keep subnets matching `base.yml` exactly — divergence causes cross-stack auth confusion.

### "force-recreate doesn't pick up new env.shared values"

**Cause:** Compose only re-reads `--env-file` arguments when a service's container is fully recreated. Restart isn't enough.

**Recovery:**
1. **Preferred:** `make -C pmoves overlay-up-<tier>` — already passes `--force-recreate` semantics correctly via Make wrapper.
2. **Raw invocation:** `docker compose -f base.yml -f overlay.yml up -d --force-recreate <service>` — base.yml MUST be in the file list.
3. **DO NOT** run `docker compose -f <overlay>.yml up -d --force-recreate <service>` raw — even with defensive networks declared as external, the env vars may not propagate without the base layer providing the env_file resolution chain.

### "Kong restart loop after env.shared password change"

**Same root cause as force-recreate.** Kong reads DB credentials at startup; `docker compose restart` doesn't re-read env. Use `make -C pmoves overlay-up-core` (or `up-supabase` for monolithic) to force-recreate with new env.

---

## When raw single-file invocation IS okay

| Command | Why it's safe |
|---|---|
| `docker compose -f pmoves/docker-compose.<overlay>.yml config` | Parse + validation only, no runtime |
| `docker compose -f pmoves/docker-compose.<overlay>.yml convert` | Schema check, no `up` |
| `docker compose -f pmoves/docker-compose.<overlay>.yml ps` | Read-only state listing (if services already running) |

These are debugging / validation commands that don't try to create services. Defensive networks declaration (added 2026-05-18) makes these succeed where they previously failed.

## When raw single-file invocation IS NOT okay

| Command | Why it breaks |
|---|---|
| `docker compose -f <overlay>.yml up -d` | Networks not declared in single file → fails on lookup |
| `docker compose -f <overlay>.yml restart <service>` | Restart can attach to a different network namespace |
| `docker compose -f <overlay>.yml --force-recreate <service>` | env_file resolution chain breaks |
| `docker compose -f <overlay>.yml down --remove-orphans` | Can remove networks that base.yml owns |

For these commands, **always use the `make overlay-up-*` targets** or include base.yml in the file list explicitly.

---

## Where this came from (historical)

- **PR #1233** (`92522fc7 feat(infra): split docker-compose into overlay files + unified merge gate`) — introduced the split.
- **2026-05-18 DARKXSIDE-on-SPARK report** — surfaced the "many a issue" pattern: every time an operator or agent tried single-file invocation, error appeared.
- **2026-05-18 Z890-CLAUDE PR** (this runbook + defensive networks block) — closes the trap.
- **Future:** when MOF goes live, P7's room manager handles compose orchestration; operators won't construct raw invocations.

---

## See also

- `.claude/PATTERNS.md` § Known Roads § Compose-Overlay Layering — short-form reference
- `pmoves/docs/handoffs/compose-overlay-defensive-networks-2026-05-18.md` — operator handoff brief for the PR that landed defensive declarations
- `pmoves/Makefile:1591` — `$(DC)` definition (monolithic)
- `pmoves/Makefile:3551-3577` — `$(OVERLAY_DC)` + overlay-up-* target definitions
- `pmoves/docker-compose.base.yml:552-616` — canonical network definitions
- `pmoves/docs/operations/MISSING_LINC_FINDINGS.md` — sibling findings ledger for related drift
