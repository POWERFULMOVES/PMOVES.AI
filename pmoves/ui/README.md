# PMOVES Operator Console UI

This package contains the Next.js front end that surfaces ingestion workflows, video review tooling, and integration runbooks for PMOVES operators. In addition to the services dashboard, it now ships the Notebook Workbench experience for inspecting and arranging Supabase notebook threads.

## Development quickstart

```bash
npm install
# If port 3000 is free: 
npm run dev
# If Invidious is bound to 3000, use an alternate port:
npm run dev:3001
```

The development server runs on [http://localhost:3000](http://localhost:3000) (or [http://localhost:3001](http://localhost:3001) when using `dev:3001`). Any changes under `app/`, `components/`, or `lib/` trigger automatic reloads.

### Quick Links on the landing page
The home page renders a “Quick Links” grid to common dashboards when available:

- Agent Zero (8080), Archon health (8091), Hi‑RAG Geometry (GPU), TensorZero UI (4000), TensorZero Gateway (3030), Jellyfin (8096), Open Notebook (8503), and Supabase Studio (65433).

Override any link with:

```
NEXT_PUBLIC_AGENT_ZERO_URL
NEXT_PUBLIC_ARCHON_URL
NEXT_PUBLIC_TENSORZERO_UI
NEXT_PUBLIC_TENSORZERO_GATEWAY
NEXT_PUBLIC_JELLYFIN_URL
NEXT_PUBLIC_OPEN_NOTEBOOK_URL
NEXT_PUBLIC_SUPABASE_STUDIO_URL
```

The Hi‑RAG Geometry link respects `HIRAG_V2_GPU_HOST_PORT`.

## Services dashboard workflow

The dashboard includes a **Services** section under `/dashboard/services` that highlights the external integrations bundled with PMOVES:

- Open Notebook
- PMOVES.YT
- Jellyfin
- Wger
- Firefly

Use the pills at the top of the ingestion, video, and services pages to move between dashboards. Each service card links to a dedicated page (for example `/dashboard/services/open-notebook`) that renders the markdown runbook from `pmoves/docs/services/<service>/README.md` via a shared Markdown renderer.

## Notebook Workbench quick start

1. **Start core services** so the UI has data to read:
   ```bash
   make -C pmoves up up-agents
   make -C pmoves up-tensorzero up-external-wger up-external-firefly up-external-jellyfin
   docker start cataclysm-open-notebook cataclysm-open-notebook-surrealdb  # or `make -C pmoves notebook-up`
   make -C pmoves up-n8n  # optional: automation canvas
   ```
   Ensure Supabase CLI is running (`make -C pmoves supa-status`) because the workbench relies on Supabase Realtime and REST.

2. **Install dependencies** (once per checkout):
   ```bash
   cd pmoves/ui
   npm install
   ```

3. **Load environment variables** so the client can talk to Supabase:
   - Run `make env-setup` from the repo root to refresh `.env`, `.env.local`, and `pmoves/env.shared`.
   - Ensure the following keys are present (either in `.env.local` or exported before you start the dev server):
     - `NEXT_PUBLIC_SUPABASE_URL`
     - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
     - `NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT` – reproducible JWT managed by `make supabase-boot-user` (invoked automatically by `make first-run`); keeps the UI authenticated as the branded operator instead of the anon role.
     - Optional UI links (see above) to surface external dashboards on the home page.
     - Optional but recommended: `NEXT_PUBLIC_SUPABASE_REST_URL` (falls back to `<SUPABASE_URL>/rest/v1`).
   - Server components/read routes also honour `SUPABASE_BOOT_USER_JWT`; set it alongside the `NEXT_PUBLIC_…` value so API routes inherit the same session.

4. **Start the dev server**:
   ```bash
   npm run dev
   ```
   Visit [http://localhost:4482/notebook-workbench](http://localhost:4482/notebook-workbench) to open the workbench UI.

5. **Connect to a thread**: paste a `thread_id` from `chat_messages` into the Thread ID input. The page subscribes to Supabase realtime channels and renders message views, group membership, and snapshot data for that thread.

## Notebook Workbench features

| Area | Purpose |
| --- | --- |
| Canvas editor | Drag, resize, align, lock, and persist `message_views` for the active message. Uses the comic-pop skin tokens so layouts match the published notebook experience. |
| Group manager | Creates `view_groups`, manages members, and lets you pull group selections directly into the canvas. |
| Snapshot tooling | Browse ticks from `rpc_snapshot_ticks`, drag-sort bookmarks, and persist snapshot layouts back into Supabase. |
| Scrubber | Listens for Realtime updates on `message_views` / `view_group_actions` and lets you scrub through snapshot history. |

Configurations live in `pmoves/ui/runtime/*` and can be imported by other pages through `@/runtime/notebook` and `@/runtime/skin`.

## Smoke test

Run the bundled smoketest after refreshing dependencies or changing workbench code:

```bash
make -C pmoves notebook-workbench-smoke [ARGS="--thread=<uuid>"]
```

The target performs two checks:

1. `npm --prefix ui run lint` to ensure the Next bundle still passes ESLint.
2. `node scripts/notebook_workbench_smoke.mjs` to validate Supabase environment variables and, when a thread ID is supplied, confirm the REST endpoint returns data.

See `pmoves/docs/UI_NOTEBOOK_WORKBENCH.md` for additional workflows (seeding demo threads, interpreting the Realtime events, and sharing evidence).

## Testing

Run the full suite before publishing changes:

```bash
npm run lint
npm run typecheck
npm run test
npm run test:e2e
npm run smoke:upload-events
```

The Jest coverage exercises the services index/detail routes and Notebook Workbench helpers. The Playwright run boots the dev server and validates that the integration list, markdown pages, and workbench surface load successfully.

### Upload events diagnostics

The dashboard uses Supabase Realtime to keep the upload history fresh. The `UploadEventsTable` component now emits structured metrics for:

- Fetch success/error counts with duration tracking.
- Row removal (manual deletes) and smoke-clear cycles.
- Skipped fetches when an owner ID is unavailable.

The metrics helper writes to the browser console (`[metric] uploadEvents.…`) so keep the DevTools console open during ingest troubleshooting. The dedicated Jest spec `__tests__/upload-events-table.test.tsx` exercises all flows, while `npm run smoke:upload-events` runs only that suite for quick validation after UI or Supabase schema changes.

## Related PMOVES UIs

| UI | Default URL | How to start |
| --- | --- | --- |
| Supabase Studio | http://127.0.0.1:65433 | `make -C pmoves supa-start`
| TensorZero Playground | http://localhost:4000 | `make -C pmoves up-tensorzero`
| Firefly Finance | http://localhost:8082 | `make -C pmoves up-external-firefly`
| Wger Coach Portal | http://localhost:8000 | `make -C pmoves up-external-wger`
| Jellyfin Media Hub | http://localhost:8096 | `make -C pmoves up-external-jellyfin`
| Open Notebook UI | http://localhost:8503 | `docker start cataclysm-open-notebook` or `make -C pmoves notebook-up`
| n8n Automation Canvas | http://localhost:5678 | `make -C pmoves up-n8n`

Additional headless services surfaced via the console:

- Agent Zero (MCP): UI wrapper at `/dashboard/agent-zero` (reads `NEXT_PUBLIC_AGENT_ZERO_URL`, default `http://localhost:8080`). Start with `make -C pmoves up-agents`. The native Agent Zero UI runs in the upstream container; the console uses `NEXT_PUBLIC_AGENT_ZERO_UI_URL` (default `http://localhost:8081`) for the “Open native UI” link when available.
- Archon (MCP): UI wrapper at `/dashboard/archon` (reads `NEXT_PUBLIC_ARCHON_URL`, default `http://localhost:8091`). Start with `make -C pmoves up-agents`. When using your fork via `up-agents-integrations`, the Archon front-end is exposed on `http://localhost:3737` and the console uses `NEXT_PUBLIC_ARCHON_UI_URL` to link to it (default `http://localhost:3737`).

Health endpoints used for badges can be customized:

- `NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH` (default `/healthz`, fallbacks to `/api/health` then `/`).
- `NEXT_PUBLIC_ARCHON_HEALTH_PATH` (default `/healthz`, fallbacks to `/api/health` then `/`).
- `NEXT_PUBLIC_PMOVES_YT_BASE_URL` (default `http://localhost:8091`) – PMOVES.YT base used by the yt‑dlp status tile.

Link to the consolidated rundown in `pmoves/docs/LOCAL_DEV.md` for more context on ports and dependent Make targets.

## Useful scripts

- `npm run dev` – start the Next.js dev server.
- `npm run lint` – run ESLint with the repository configuration.
- `npm run build` / `npm run start` – production build + launch. Remember to export Supabase env vars before running these commands.

For Playwright or Jest targets, refer to the scripts and configuration in `package.json`. End-to-end coverage is optional for the workbench in this iteration; rely on the smoketest target above for quick validation.
