# PMOVES All‑in‑One **v10** (supersedes v5–v9.1)

Drop this `docs/` folder into your repo at `pmoves/docs/` and run a single Codex task to install everything.

## 🔧 1) Append Codex tasks
Append `pmoves/docs/CODEX_TASKS_ALL_IN_ONE.toml` to your root `codex.toml` (or copy its tasks into your file).

## 🗄️ 2) Database schema & RPCs
```bash
# One‑shot install (or run via pmoves_all_install below)
codex run db_all_in_one SUPABASE_DB_URL=postgres://USER:PASSWORD@HOST:PORT/DB
```
This provisions:
- Base chat/notebook tables with RLS
- Multimodal `content_blocks` + append‑only `message_views` (locked/visible/z/rotation)
- Groups (`view_groups`, `view_group_members`) + Action log (`view_group_actions`)
- Named `snapshots` (+ tags / position), snapshot ticks & snapshot views RPCs
- Group RPCs: **translate**, **z_set**, **lock**, **visible**, **set_archetype_variant**, **align**, **distribute**, **equalize**, **rotate**, **scale**
- `oembed_cache`

## ☁️ 3) Edge functions
```bash
codex run functions_install_all
codex run functions_deploy_all
```
Configure env in Supabase:
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `JELLYFIN_SERVER_URL`, `JELLYFIN_API_KEY`, `JELLYFIN_TTL_SEC`
- `YOUTUBE_API_KEY`, `OEMBED_TTL_SEC` (optional)

Installed endpoints:
- `jellyfin_sign` → `{"token","expires_at"}`
- `jellyfin_hls_proxy?k=playlist&itemId=...` → rewritten `.m3u8` (segments proxied via the same function)
- `youtube_oembed_cache?videoId=...` → cached oEmbed
- `yt_chapters_ingest?videoId=...&messageId=...` → parses YT description → `content_blocks.meta.chapters`

## 🖥️ 4) UI runtime & examples
```bash
codex run ui_install_runtime
```
- Skin system (`SkinProvider`, `ComicBubble` procedural + SVG9)
- Notebook UI: SelectionCanvas, MultiViewEditor, toolbar, baseline guides, groups manager/history, snapshots browser, **SnapshotBookmarksPro (drag‑drop + tags)**, realtime scrubber
- Media (`MediaEmbed`, `MediaBubble`) + YouTube chapters overlay
- Example skin & demo pages (copy to `ui/app/pages/`)

Add a Supabase client at `ui/app/lib/supabase.ts` if you don’t already have one.

## 🤖 5) n8n + scripts
```bash
codex run n8n_install_all
codex run scripts_install
```
- n8n: YouTube ingest webhook, Jellyfin webhook, YouTube channel poll (cron)
- Scripts: seed demo data, **export storyboard** (Puppeteer or Playwright), YouTube channel ingest worker

## 🚀 One button to install everything
```bash
# Requires SUPABASE_DB_URL in the environment for the first step
codex run pmoves_all_install SUPABASE_DB_URL=postgres://USER:PASSWORD@HOST:PORT/DB
```

## 🧪 Quick start
1. Seed sample data:
   ```bash
   codex run scripts_install
   SUPABASE_URL=... SUPABASE_ANON_KEY=... THREAD_ID=<uuid> USER_ID=<uuid> node scripts/seed_demo_variety.mjs
   ```
2. Run your dev server; open demo pages (e.g., `/media-demo`).

## 🔒 Notes
- This is a full append‑only, **replayable** design. All group ops write new `message_views` and log to `view_group_actions`.
- For a production‑grade Jellyfin HLS proxy, treat this as a scaffold: add auth checks and sign sub‑requests.
- You can extend CHIT geometry as a **control knob** by sampling seeds/archetypes from `chat_messages.cgp` and storing in `message_views` for deterministic replays.