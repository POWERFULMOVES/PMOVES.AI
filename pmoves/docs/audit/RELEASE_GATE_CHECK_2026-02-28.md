# Release Gate Check — 2026-02-28

## RG-1: Production Command Parity (dev-only targets in prod paths)

**Status: PASS with notes**

Scan: `rg -n "ui-dev-start|ui-dev-stop|ui-dev-logs|dev-start" pmoves/tools pmoves/Makefile pmoves/mk/`

Findings:
- `pmoves/Makefile:1662-1675` — `ui-dev-start`, `ui-dev-stop`, `ui-dev-logs` targets exist
- `pmoves/Makefile:1810-1811` — `ui-dev-stop`/`ui-dev-start` called by hot-reload target
- `pmoves/Makefile:1847` — `ui-dev-start` called by quick-start target
- `pmoves/tools/bringup_with_ui.sh:157` — References `ui-dev-start`

**Assessment:** Dev targets are correctly isolated in the Makefile (they start a Next.js
dev server on :3001). They are NOT invoked by any production docker-compose path.
The `bringup_with_ui.sh` is a developer convenience script, not a production entrypoint.
No action needed — these are appropriately scoped to development workflows.

---

## RG-2: Port Hardcoding Audit

**Status: PASS with known trade-offs**

Scan: `rg -n "localhost:[0-9]+|127.0.0.1:[0-9]+" pmoves/docker-compose*.yml pmoves/env.shared`

Findings (50+ matches):
- **env.shared:** 12 hardcoded localhost URLs (TENSORZERO, SITE_URL, API_EXTERNAL_URL, etc.)
  - All use `${VAR:-fallback}` pattern — the hardcoded values are DEFAULTS only
  - Production deployments override via `--env-file` or shell environment
- **docker-compose.yml:** 30+ container-internal healthchecks use `localhost:PORT`
  - These are correct — healthchecks run INSIDE the container
- **docker-compose.yml:** 20+ `NEXT_PUBLIC_*` env vars default to `localhost:PORT`
  - These are client-side URLs for the A2UI frontend, correctly parameterized

**Assessment:** All hardcoded ports are either:
1. Default fallback values (overridable by env)
2. Container-internal healthcheck targets (correct pattern)
3. Client-side URL defaults (need override in production deployment)

No blocking issues. Production deployment guide should document required env overrides.

---

## RG-3: Supabase Collation Check

**Status: DEFERRED (requires running stack)**

Check: `docker compose logs --tail=200 supabase-db | grep collation`

This check requires the Docker stack to be running. Blocked by AB-4 (missing data credentials).
Will be validated as part of post-AB-4 `make verify-all`.

---

## RG-4: Auth Unification / JWT Rotation

**Status: DEFERRED (requires running stack)**

Check: JWT rotation + cross-service re-auth test

This requires live service testing with valid credentials. Blocked by AB-4.
Will be validated as part of post-AB-4 integration testing.

---

## Summary

| Gate | Status | Action Needed |
|------|--------|---------------|
| RG-1 | PASS | None — dev targets correctly scoped |
| RG-2 | PASS | Document production env overrides in deployment guide |
| RG-3 | DEFERRED | Run after AB-4 credential injection |
| RG-4 | DEFERRED | Run after AB-4 credential injection |
