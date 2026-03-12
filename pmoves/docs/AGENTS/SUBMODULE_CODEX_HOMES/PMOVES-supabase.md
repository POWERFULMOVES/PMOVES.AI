# Codex Home Overlay: PMOVES-supabase

Scope:
- Supabase runtime, auth, state, persona seeds, and model-registry parity.

Use this when:
- the task touches auth/session behavior, SSR cookies, RLS, migrations, or PostgREST
- Codex needs the source of truth for personas, metadata, or model routing state
- the traversal question is about persisted PMOVES state instead of transient agent memory

PMOVES companions:
- `PMOVES-Agent-Zero` and `PMOVES-Archon` for agent state
- `Pmoves-cipher` for durable reasoning traces
- `pmoves/docs/AGENTS/PERSONAS.md`
- `pmoves/docs/MODEL_SOURCE_OF_TRUTH.md`

Core checks:
- `make -C pmoves supa-status`
- `make -C pmoves supabase-bootstrap`
- `docker compose -p pmoves up -d postgrest-cli`

Related parity tokens:
- `/db:migrate`
- `/db:query`
- `/deploy:bootstrap-env`

Related docs:
- `pmoves/docs/AGENTS/CODEX_ECOSYSTEM_TRAVERSAL.md`
- `pmoves/docs/services/supabase/README.md`
- `.claude/context/services-catalog.md`

