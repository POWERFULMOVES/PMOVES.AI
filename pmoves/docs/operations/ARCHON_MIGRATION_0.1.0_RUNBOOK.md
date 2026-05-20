# Archon Database Migration 0.1.0 — Operator Runbook

**Runbook ID:** `ARCHON-MIGRATION-0.1.0-2026-05-20`
**Author:** 5090-CLAUDE (Opus 4.7)
**Lane:** L1 of 5-lane orchestration (see `~/.claude/plans/nested-sniffing-pancake.md`)
**Status:** PR — operator runs SQL; this runbook is the doc that ships.

## When to use this

Run this when `curl -sf http://localhost:8091/api/health` returns:

```json
{
  "status": "migration_required",
  "ready": false,
  "migration_required": true,
  "migration_instructions": "Open Supabase Dashboard → SQL Editor → Run: migration/add_source_url_display_name.sql"
}
```

…or any other `migration_required` response. The Archon service `/healthz` returns 200 but `/api/health` flags schema-behind status. Until the schema catches up, Archon's mint/RAG operations (knowledge ingest, agent factory, signing card issuance) cannot proceed.

This runbook is also a hard prerequisite for the **5090-CLAUDE signing card** mint (deferred since 2026-05-19 — see `~/.claude/plans/nested-sniffing-pancake.md` § L1 follow-up).

## Pre-flight

1. **Verify current state:**
   ```bash
   curl -sf http://localhost:8091/api/health | jq .
   ```
   Expect: `"status": "migration_required"`. If you see `"ready": true`, this runbook is not needed.

2. **Confirm DB container is up:**
   ```bash
   docker ps --filter name=pmoves-supabase-db --format '{{.Names}}\t{{.Status}}'
   ```
   Expect: `pmoves-supabase-db-1  Up <time> (healthy)`. If unhealthy, fix that first (Kong restart loop guidance: PR #1534).

3. **Confirm Archon container is up:**
   ```bash
   docker ps --filter name=pmoves-archon --format '{{.Names}}\t{{.Status}}'
   ```
   Expect: `pmoves-archon-1  Up <time> (healthy)`.

4. **Snapshot the schema (recommended):** Method 1 below uses Supabase Studio which keeps a query history; Method 2 (docker exec) does not. If you're using Method 2, consider:
   ```bash
   docker exec pmoves-supabase-db-1 pg_dump -U postgres -d postgres -s > /tmp/archon-schema-before.sql
   ```

## Migration files (sequence)

There are **11 migration scripts** in `pmoves/integrations/archon/migration/0.1.0/` plus the upgrade-instructions doc. The README in that dir mentions `backup_database.sql` but the file isn't present in this version — skip backup, idempotency + IF-NOT-EXISTS guards make the migrations safe to retry.

| # | File | What it does | Idempotent? | Safe to skip? |
|---|---|---|---|---|
| 001 | `001_add_source_url_display_name.sql` | Display name on sources table | Yes (IF NOT EXISTS) | No |
| 002 | `002_add_hybrid_search_tsvector.sql` | tsvector columns + hybrid search indexes | Yes | No |
| 003 | `003_ollama_add_columns.sql` | Multi-dim embedding columns (384/768/1024/1536/3072) | Yes | No |
| 004 | `004_ollama_migrate_data.sql` | Migrate existing embeddings + drop legacy column | Yes (BEGIN/COMMIT) | No — required for 005 |
| 005 | `005_ollama_create_functions.sql` | Multi-dim search functions | Yes (CREATE OR REPLACE) | No |
| 006 | `006_ollama_create_indexes_optional.sql` | Vector indexes (may timeout on large datasets) | Yes | Yes — fallback to brute-force scan |
| 007 | `007_add_priority_column_to_tasks.sql` | Task prioritization | Yes | No (Archon UI references priority) |
| 008 | `008_add_migration_tracking.sql` | Migration tracking table | Yes (idempotent) | No — needed by 010+ |
| 009 | `009_add_cascade_delete_constraints.sql` | CASCADE DELETE on source FKs (fixes large-source delete timeouts) | Partially (DROP CONSTRAINT IF EXISTS) | No |
| 010 | `010_add_provider_placeholders.sql` | Placeholder rows for OpenRouter/Anthropic/Grok API keys in `archon_settings` | Yes (ON CONFLICT) | Yes — only matters if those providers used |
| 011 | `011_add_page_metadata_table.sql` | Page metadata table for RAG metadata | TBD — verify first | No (latest) |

**Run order is strict 001 → 011.** Skipping is allowed only for files marked "Safe to skip" above, and even then, prefer to run them all so `archon_migrations` records a complete history.

## Method 1 — Supabase Studio (RECOMMENDED — query history, visible errors)

1. Open Supabase Studio in your browser:
   ```
   http://localhost:8000
   ```
   Log in if prompted (credentials in `pmoves/env.shared`, never paste in chat; the secrets pipeline handles this).

2. Navigate to **SQL Editor** in the left sidebar.

3. For each file 001–011 in order:
   a. Open the file from `pmoves/integrations/archon/migration/0.1.0/<file>.sql` (use your editor; do not paste from a copy that may strip semicolons).
   b. Click **+ New query** in Studio.
   c. Paste the full file contents.
   d. Click **Run** (or Ctrl/Cmd+Enter).
   e. Wait for the status table at the bottom of the script to render — these scripts intentionally end with a status query so Supabase shows the rollup row even though it only renders the last query's result.
   f. If you see any red ERROR rows, **stop** and inspect. Most likely: a partial prior run. The IF-NOT-EXISTS guards will let you re-run, but if 004 partially ran (data migration), see `## Troubleshooting` below.

4. After 011 completes, **restart Archon**:
   ```bash
   docker compose -f pmoves/docker-compose.yml -f pmoves/docker-compose.hardened.yml restart archon
   # Or via canonical pipeline:
   make -C pmoves restart-archon
   ```

5. **Verify ready:**
   ```bash
   curl -sf http://localhost:8091/api/health | jq '.ready, .status'
   ```
   Expect: `true` and `"healthy"` (or equivalent ready state — *not* `"migration_required"`).

## Method 2 — Docker exec (one-shot scripted)

Faster than the Studio loop if you trust the migrations to be safe. Runs all 11 in sequence; abort-on-first-error semantics via `set -e`.

```bash
#!/usr/bin/env bash
set -euo pipefail

DB_CONTAINER=pmoves-supabase-db-1
SRC=pmoves/integrations/archon/migration/0.1.0

# Verify container responsive
docker exec "$DB_CONTAINER" pg_isready -U postgres -d postgres

# Copy all migrations into the container
for f in "$SRC"/[0-9][0-9][0-9]_*.sql; do
  echo "Staging: $(basename "$f")"
  docker cp "$f" "$DB_CONTAINER:/tmp/$(basename "$f")"
done

# Execute in order (relies on lexical sort 001 → 011)
for f in "$SRC"/[0-9][0-9][0-9]_*.sql; do
  base=$(basename "$f")
  echo "===== Running $base ====="
  docker exec -i "$DB_CONTAINER" psql -U postgres -d postgres -v ON_ERROR_STOP=1 -f "/tmp/$base"
  echo
done

# Restart Archon
docker compose -f pmoves/docker-compose.yml -f pmoves/docker-compose.hardened.yml restart archon

# Wait for ready
for i in {1..30}; do
  ready=$(curl -sf http://localhost:8091/api/health | jq -r .ready 2>/dev/null || echo false)
  if [ "$ready" = "true" ]; then
    echo "✔ Archon ready"
    exit 0
  fi
  echo "Waiting for Archon ready ($i/30)…"
  sleep 2
done
echo "✘ Archon did not flip ready=true within 60s"
curl -sf http://localhost:8091/api/health | jq .
exit 1
```

Save as `pmoves/scripts/archon-migration-0.1.0.sh` and run from repo root. (Do not commit secrets in any wrapper — the script touches only the local DB container, no env files.)

## Method 3 — Single-statement Studio (for one missing migration)

If `/api/health` calls out a specific file (e.g., `migration_instructions: ".../001_add_source_url_display_name.sql"`), and you've already run prior ones, just run that one in Studio. The other migrations are idempotent — running them again won't hurt, but if you're in a hurry, single-file is fine.

## Troubleshooting

**004 partially ran (data migration step):** The script uses `BEGIN/COMMIT` transactions, so a partial run rolls back automatically. If you see legacy embedding columns still present after a "successful" 004, the rollback fired. Re-run 003 then 004 and verify by inspecting `\d archon_crawled_pages` — the `embedding` column (legacy) should be gone post-004.

**006 timeout (vector index creation):** Expected on large datasets. Skip this migration; Archon falls back to brute-force vector scan. Re-attempt later with `SET statement_timeout = '30min';` prepended.

**009 partial constraint state:** If the script aborted between `DROP CONSTRAINT` and `ADD CONSTRAINT`, the table has no FK enforcement. Re-run 009 — it uses `DROP CONSTRAINT IF EXISTS` so the second pass is safe.

**`/api/health` still `migration_required` after all 11:** Check Archon logs:
```bash
docker logs pmoves-archon-1 --tail 50 | grep -E "(migration|schema)"
```
The error trail will name the specific column/table the schema check is failing on. Compare against the migration files to find which file should have added it.

**Kong returns 404 on `/api/health`:** Kong restart loop from PR #1534 SPARK lane may be recurring. Check `docker logs pmoves-supabase-kong-1` for `crash` or `init failure`. Not in scope for this runbook — escalate to SPARK lane.

## Post-migration — re-attempt 5090-CLAUDE signing card mint

Once `/api/health` flips `ready: true`, the deferred signing-card mint from prior sessions can complete:

```bash
# Profile file already exists (created via PR #1523)
cat pmoves/configs/agents/forms/5090-CLAUDE.yaml | head -5

# Invoke the mint skill (Claude Code session, not bash)
# /archon:mint-agent role=5090-CLAUDE profile=pmoves/configs/agents/forms/5090-CLAUDE.yaml

# Verify card landed in registry
grep -A 2 "5090-CLAUDE" pmoves/config/signing_identity_cards.yaml
# Expect a row with a UUID and timestamp

# Verify sign-trail no longer warns
make -C pmoves sign-trail AGENT=5090-CLAUDE 2>&1 | grep -i "signing card\|advisory"
# Expect: no "no active signing card" warning
```

The signing card is *registered* at this point but the trail is still `unsigned-local` until `CHIT_PASSPHRASE` is exported (operator-side, per `vision_secrets_pipeline_never_chat.md` — never paste in chat, pull from secrets pipeline).

## Verification checklist

- [ ] `curl -sf http://localhost:8091/api/health | jq '.ready'` returns `true`
- [ ] `curl -sf http://localhost:8091/api/health | jq '.status'` returns `"healthy"` (not `migration_required`)
- [ ] Archon UI loads `/projects` page without "schema check" errors
- [ ] `docker exec pmoves-supabase-db-1 psql -U postgres -d postgres -c "SELECT version, migration_name FROM archon_migrations ORDER BY applied_at;"` lists all 11 migrations (after 008 lands the tracking table)
- [ ] Archon logs show no `migration_required` references after the restart
- [ ] If signing-card mint is attempted, `pmoves/config/signing_identity_cards.yaml` gains a row for `5090-CLAUDE`

## Cross-references

- Source migration files: `pmoves/integrations/archon/migration/0.1.0/001_*.sql` through `011_*.sql`
- Upstream upgrade doc: `pmoves/integrations/archon/migration/0.1.0/DB_UPGRADE_INSTRUCTIONS.md` (the upstream README — slightly out of date, lists only 001–008)
- Plan file: `~/.claude/plans/nested-sniffing-pancake.md` § L1
- Related: `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — L1 RELEASE row will close out this lane

agent_signature (advisory unsigned-local): `ACK::5090-CLAUDE::ARCHON-MIGRATION-RUNBOOK-2026-05-20`
