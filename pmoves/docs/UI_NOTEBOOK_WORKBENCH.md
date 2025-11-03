# Notebook Workbench Guide
_Last updated: 2025-11-02_

The Notebook Workbench surfaces Supabase conversation threads inside the PMOVES operator UI so editors can manage message layouts, view groups, and snapshots without leaving the console. Use this guide to wire the environment, validate access, and capture smoke evidence.

## Prerequisites

- Supabase CLI stack running locally (`make supa-start`) or a remote Supabase project populated with the PMOVES schema.
- `chat_messages`, `content_blocks`, `message_views`, `view_groups`, and snapshot RPCs (`rpc_snapshot_ticks`, `rpc_snapshot_views`) available in the target database.
- Local `.env.local` (or exported vars) supplying:
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  - Optional: `NEXT_PUBLIC_SUPABASE_REST_URL` when the REST hostname differs from the base URL.
- A thread ID you can use for smoke verification. Use `select id from chat_messages order by created_at desc limit 1;` if you need a fresh value.

## Bring-up Steps

1. Install UI dependencies:
   ```bash
   cd pmoves/ui
   npm install
   ```
2. Sync environment configuration: `make env-setup` (repo root) refreshes `.env`, `.env.local`, and `pmoves/env.shared`.
3. Launch the dev server: `npm run dev` and navigate to `http://localhost:3000/notebook-workbench`.
4. Paste a thread ID into the **Thread ID** input to hydrate the workbench. The canvas, groups panel, snapshots, and scrubber update in realtime as Supabase changes land.

## Smoketest Workflow

Use the consolidated smoketest target whenever you touch workbench code:

```bash
make -C pmoves notebook-workbench-smoke ARGS="--thread=<thread_uuid>"
```

What it does:

1. Runs ESLint via `npm --prefix ui run lint` to ensure the Next.js bundle compiles cleanly.
2. Executes `node scripts/notebook_workbench_smoke.mjs` while sourcing `env.shared`, `.env`, and `.env.local`. The script checks for the required Supabase environment variables and optionally fetches `chat_messages` for the supplied thread ID to confirm REST access.

Exit codes are non-zero on failure, which keeps CI-style executions honest. Capture the console output in PR evidence when reporting validation for notebook UI changes.

### Script arguments

`notebook_workbench_smoke.mjs` accepts the following flags:

- `--thread=<uuid>` – queries `chat_messages` over REST and prints the number of rows returned.
- `--limit=<n>` – optional, defaults to `1`. Controls how many rows to request when a thread ID is provided.

Environment variables can be used instead of flags (`NOTEBOOK_SMOKE_THREAD_ID`, `NOTEBOOK_SMOKE_LIMIT`). Flags take precedence over env values.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `SUPABASE_URL is not configured` | Run `make env-setup` and confirm `.env.local` includes `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`. The smoketest reads the same variables. |
| Workbench shows empty canvas | Verify the thread has at least one `content_block`. Use `insert into content_blocks` with a placeholder block or select a thread with conversation history. |
| No snapshot ticks appear | Ensure the RPCs from `docs/ops/sql/03_snapshots_and_rpcs.sql` have been applied. Run `codex run db_all_in_one` or re-run the migrations bundle. |
| Realtime updates fail | Confirm `supabase start` is running (or Realtime is enabled on hosted Supabase) and that your anon key has Realtime access to the `public` schema. |
| `401 Unauthorized` during smoketest fetch | Check that `NEXT_PUBLIC_SUPABASE_ANON_KEY` matches the project’s anon key and that Row Level Security policies allow the anon role to select from `chat_messages`. |

## Related References

- `pmoves/ui/runtime/notebook/` – canvas, group, and snapshot components shared by the workbench.
- `pmoves/ui/runtime/skin/` – comic-pop skin renderer and tokens.
- `pmoves/ui/app/notebook-workbench/page.tsx` – full page implementation.
- `pmoves/ui/README.md` – quick start and command reference for the UI bundle.
- `pmoves/docs/SMOKETESTS.md` – master smoke checklist (updated with the workbench entry).
