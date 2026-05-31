# Handoff: DoX JWT env-var rename (boot-failure fix)

**Date:** 2026-05-31 · **Node:** Z890-CLAUDE · **Urgency:** high (standalone-supabase mode fails to boot)

## What

Rename the PostgREST JWT env var in `PMOVES-DoX/docker-compose.supabase.yml`:

```
- PGRST_JWT_SECRET: ${SUPABASE_JWT_SECRET:?SUPABASE_JWT_SECRET required}
+ PGRST_JWT_SECRET: ${JWT_SECRET:?JWT_SECRET required}
```

## Why

The secrets pipeline emits **`JWT_SECRET`** (`pmoves/env.shared.example`, `PMOVES-DoX/.env.local.example`), and `PMOVES-DoX/docker-compose.yml` already uses `${JWT_SECRET}`. Only `docker-compose.supabase.yml` still hard-requires the sunset alias `SUPABASE_JWT_SECRET` via a `${VAR:?required}` guard — which turns the name mismatch into a **hard container-startup failure** (supabase-rest exits immediately) rather than a silent fallback. main's "sunset SUPABASE_JWT_SECRET alias" commit was the fix; it was declined `--ours` during the 2026-05-31 hardened reconciliation (PR #172/#173) to avoid an unrelated compose conflict.

This is the env-var dependency-direction pattern now in `.claude/PATTERNS.md` § Hardened-Branch Reconciliation Patterns.

## Edit-pass note

Submodule compose files were previously un-editable (the `compose` Known Road predicate only matched parent `/pmoves/` paths). The `_is_compose_target` predicate in `.claude/hooks/damage-control/known_roads.py` was extended this session to cover any PMOVES-owned compose file, so this edit proceeds via `KNOWN_ROAD=compose:handoff:dox-jwt-rename-2026-05-31.md`.

`docker-compose.unfcu.yml` already defines both vars (no change needed). Docked mode does not use `docker-compose.supabase.yml`.
