# Supabase RLS Hardening Checklist (Draft)

This checklist is a starting point for non‑dev environments. Adapt per table and app surface.

- Enable RLS on all app‑facing tables and views.
- Create least‑privilege policies per role (anon, authenticated, service_role) with explicit `USING` predicates.
- Avoid blanket `USING true` policies. Prefer row ownership checks or role‑scoped conditions.
- Parameterize policy predicates via PostgREST headers when possible (e.g., `request.jwt.claims ->> 'sub'`).
- Deny by default: ensure there is no implicit access without matching policy.
- Restrict `INSERT/UPDATE/DELETE` separately; do not use a single `ALL` policy for write paths.
- Audit sensitive changes: add triggers to append to `it_audit` (table, op, rowid, actor, ts).
- Separate admin maintenance policies from runtime ones; guard with `service_role()` checks.
- For Storage buckets, enforce signed URL access or presign flows. Remove public buckets unless explicitly required.
- Review `rpc/*` and `SECURITY DEFINER` functions; ensure input validation and correct `search_path`.
- Rotate keys (service, anon) and enforce secrets via CI (never in repo); store in platform secrets.

See also:
- `docs/SUPABASE_FULL.md` for CLI bootstrap and local parity.
- `docs/LOCAL_DEV.md` for env setup and PostgREST health.
