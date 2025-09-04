# PMOVES • Publisher Enrichments Smoke Test
This verifies the enriched publisher:
- Writes a **content.published.v1** event
- Posts a **Discord** rich embed (audited)
- Records **audit** rows (notify/refresh/errors) in Supabase

## Pre-reqs
- `supabase-db` + `postgrest` running and reachable at `$SUPA_REST_URL` (default `http://localhost:3000`)
- `publisher` service running with env:
  - `PUBLISHER_NOTIFY_DISCORD_WEBHOOK` (optional but recommended)
  - `PUBLISHER_REFRESH_ON_PUBLISH=true`
  - `PUBLISHER_EMBED_COVER=true`
- Migration applied: `004_publisher_audit.sql`

## Run
```bash
# optional overrides
export SUPA_REST_URL="http://localhost:3000"
export JELLYFIN_TEST_TITLE="DARKXSIDE – Test Release (Smoke)"   # change to an existing Jellyfin item title for a sure match

bash smoketest_publisher_enrich.sh
```

## Expected
- Script prints created `studio_board` row ID
- Waits for publisher to process and then prints:
  - latest `published_events` for the studio_id
  - `publisher_audit` rows (should include `notify.discord` and `jellyfin.refresh` if configured)
- Marks **PASS** if at least one audit row exists and an event exists for the `studio_id`.
