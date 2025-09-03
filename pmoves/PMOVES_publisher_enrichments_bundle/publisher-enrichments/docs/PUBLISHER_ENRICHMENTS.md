# Publisher Enrichments
Adds three capabilities to the publisher worker:
1) **Discord rich embeds** for published items (`PUBLISHER_NOTIFY_DISCORD_WEBHOOK`)
2) **Jellyfin refresh** of the matched item (fallback to library refresh) on publish
3) **Supabase audit log** (`publisher_audit` table) for notifications/refresh/errors

## New SQL
Run `supabase/sql/004_publisher_audit.sql` against your Supabase DB.

## .env
```
PUBLISHER_NOTIFY_DISCORD_WEBHOOK=
PUBLISHER_REFRESH_ON_PUBLISH=true
PUBLISHER_EMBED_COVER=true
```
