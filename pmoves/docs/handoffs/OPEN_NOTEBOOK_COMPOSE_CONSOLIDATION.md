# Handoff: Open Notebook compose consolidation + healthcheck

**Status:** apply-ready. The compose edits below are **Known-Road-gated** (editing `docker-compose*.yml`
trips the damage-control guard). Apply with this brief as the provable reason:

```
KNOWN_ROAD=compose:handoff:OPEN_NOTEBOOK_COMPOSE_CONSOLIDATION.md
```

Then make the two edits, validate, and open the PR. This brief is the source of truth for the change;
it exists so the guard bypass is recorded and provable (see `.claude/PATTERNS.md` § Known Roads).

## Why (verified by tandem review, 2026-07-09/10)

Two P-level gaps in the Open Notebook compose topology, both code-verified:

1. **Duplicate service + host-port collision (P1).** `open-notebook`
   (`pmoves/docker-compose.open-notebook.yml:14-69`) and `open-notebook-ext`
   (`pmoves/docker-compose.external.yml:119-148`) are the **same fork image** publishing the **same host
   ports** `8503:8502` (UI) + `5055:5055` (API). Running both collides. `make up-open-notebook` starts only
   `open-notebook` (`NOTEBOOK_COMPOSE=docker-compose.open-notebook.yml`, `Makefile:1749`) but that file does
   **not** define SurrealDB — it points `SURREAL_ADDRESS` at `open-notebook-surrealdb-ext`, which lives in
   `external.yml`. So `make up-open-notebook` alone can't reach the DB; you must also `make up-external`,
   which drags in the duplicate `open-notebook-ext`. Two ways to run "Open Notebook", only one owns the DB.

2. **No healthcheck (P0-ops).** The fork exposes `/healthz` (`PMOVES-Open-Notebook/api/main.py:298`,
   auth-excluded), but **neither** compose service wires a Docker `healthcheck:`, so `depends_on:
   service_healthy` and `docker compose ps` can't gate on it.

## Decision (canonical topology)

- **Canonical service = `open-notebook`** in `docker-compose.open-notebook.yml` (it has `container_name:
  pmoves-open-notebook`, the full network-alias set, and is what the Make target + docs already point at).
- **Co-locate SurrealDB** into `docker-compose.open-notebook.yml` so `make up-open-notebook` is a single
  self-contained command (no hidden dependency on `up-external`).
- **Retire `open-notebook-ext`** from `docker-compose.external.yml` (the duplicate). Keep
  `open-notebook-surrealdb-ext` defined once — moved to the canonical file.
- **Wire the `/healthz` healthcheck** on `open-notebook`.

## Edit 1 — `pmoves/docker-compose.open-notebook.yml`

**(a)** Add a healthcheck to the `open-notebook` service (after the `ports:` block, before `volumes:`):

```yaml
    healthcheck:
      # /healthz is auth-excluded (api/main.py:145). curl ships in the fork image;
      # if a future image drops it, switch to: ["CMD","python","-c","import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:5055/healthz').status==200 else 1)"]
      test: ["CMD", "curl", "-fsS", "http://localhost:5055/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 40s
```

**(b)** Add the SurrealDB service to this file (co-located), lifted verbatim from `external.yml:93-117`
so the canonical stack is self-contained. Preserve `container_name: pmoves-open-notebook-surrealdb`, the
`pmoves_app` network + `open-notebook-surrealdb-ext` alias (so the existing `SURREAL_ADDRESS` default still
resolves), the `user: "0:0"` note, and the `./data/open-notebook/surreal_data:/mydata` volume. Add
`depends_on: [open-notebook-surrealdb-ext]` to the `open-notebook` service so the DB comes up first.

## Edit 2 — `pmoves/docker-compose.external.yml`

**Remove** the `open-notebook-ext` service block (`:119-148`) and the now-relocated
`open-notebook-surrealdb-ext` block (`:93-117`) — both now live in the canonical file. Leave the other
external services (Wger/Firefly/Jellyfin/etc.) untouched. If any of those `depends_on:
open-notebook-surrealdb-ext`, re-point them at the canonical file's service (grep first — none found at
review time).

## Optional — `pmoves/Makefile`

`make up-open-notebook` needs no change once SurrealDB is co-located (it already targets
`docker-compose.open-notebook.yml`). Confirm `up-external` no longer references the removed services.

## Validate (all must pass before PR)

```bash
# structural parse — pipe to a file, NEVER paste raw (it renders live secrets)
docker compose -f pmoves/docker-compose.open-notebook.yml config > /tmp/onb.yml && echo PARSE_OK
docker compose -f pmoves/docker-compose.external.yml     config > /tmp/ext.yml && echo PARSE_OK
grep -c "open-notebook-ext" /tmp/ext.yml        # expect 0 (duplicate gone)
grep -c "healthcheck"       /tmp/onb.yml        # expect >=1
grep -c "open-notebook-surrealdb-ext" /tmp/onb.yml   # expect >=1 (surreal co-located)
# smoke (on a node with the stack): single command brings up API+DB
make -C pmoves up-open-notebook
docker inspect --format '{{.State.Health.Status}}' pmoves-open-notebook   # expect healthy
curl -fsS http://localhost:5055/healthz
```

## Acceptance gates

| Gate | Expected |
|------|----------|
| No duplicate service | `open-notebook-ext` absent from rendered `external.yml` config |
| Self-contained bring-up | `make up-open-notebook` starts API **and** SurrealDB (no separate `up-external`) |
| Healthcheck live | `docker inspect` reports `pmoves-open-notebook` → `healthy` |
| No port collision | only one service binds `8503`/`5055` |
| Secret hygiene | `docker compose config` output was piped to a file, never pasted |

## Related
- Design context: `pmoves/docs/integrations/OPEN_NOTEBOOK_JWT_AUTH.md` (finalized; §Sunset "implementation-ready follow-ups").
- Auth Phase A brief: `.kilo/command/pmoves-auth-phase-a-5090.md`.
- notebooklm-agent (Google path) parked — Open Notebook is the sovereign notebook lane.

<!-- GRAPHITI_MARK: 4090-CLAUDE::OPEN-NOTEBOOK-COMPOSE-CONSOLIDATION-HANDOFF::2026-07-10 -->
