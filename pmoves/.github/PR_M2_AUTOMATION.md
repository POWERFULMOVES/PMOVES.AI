# feat(m2): Finish M2 Automation Loop

## Summary
- Implements Supabase → Agent Zero → Discord automation (M2) with n8n flows and validation helpers.
- Aligns environment variables for n8n and services; adds Discord ping scripts and Jellyfin deep-link embeds.
- Adds Windows-friendly bootstrap, venv helpers, and an n8n Docker runner.

## Changes
- Env alignment
  - `.env(.example/.local)`: adds `SUPABASE_REST_URL` (alias for CLI), `DISCORD_WEBHOOK_USERNAME`, `AGENT_ZERO_BASE_URL`, and notes for `/rest/v1` when using Supabase CLI.
- Make targets
  - `discord-ping`, `demo-content-published`, `up-n8n`, `m2-preflight`, `seed-approval`, `seed-approval-ps`
  - Evidence helpers: `evidence-stamp`, `evidence-log` (+ PowerShell variants)
  - Local venv: `venv`, `venv-min`; Windows prerequisites: `win-bootstrap`
- Services
  - `publisher-discord`: richer `content.published.v1` embeds (thumbnail, duration, artifact URI, tags), and Jellyfin deep links (when `jellyfin_item_id` + base URL available).
  - Port: publisher-discord now maps `8094:8092` to avoid conflicts with `pdf-ingest`.
- Docs
  - `N8N_SETUP.md`, `N8N_CHECKLIST.md` (wiki-friendly), `M2_VALIDATION_GUIDE.md`
  - `SUPABASE_DISCORD_AUTOMATION.md` references the n8n guide and seed helpers
  - `LOCAL_DEV.md` updated with n8n runner, Windows bootstrap, venv instructions
  - Index updated (`README_DOCS_INDEX.md`) and codex bundle referenced

## Validation
- Health: `make m2-preflight` (Agent Zero + publisher-discord OK; Discord ping optional)
- n8n: import flows, bind env vars, activate poller then echo publisher
- Seed: `make seed-approval TITLE="Demo" URL="s3://outputs/demo/example.png"`
- Discord: embed received; optional `make demo-content-published` and `make n8n-webhook-demo`
- Evidence: CSV log at `pmoves/docs/evidence/log.csv` with stamped screenshots

## Notes
- Supabase CLI requires `/rest/v1` on REST URL; `.env.local` and `N8N_SETUP.md` call this out.
- Use `host.docker.internal` for n8n to reach Supabase CLI on Windows/macOS.
- Jellyfin deep links require `JELLYFIN_URL` (or `jellyfin_base_url` in payload) + `jellyfin_item_id`.

## Codex: Network Access, Web Search, Docker MCP
- A full Codex config bundle with profiles is included: `pmoves/docs/codex_full_config_bundle/README-Codex-MCP-Full.md` and `config.toml`.
  - Profiles:
    - `web-auto`: network ON, workspace-write sandbox, auto-approve
    - `full-send`: network ON, no sandbox (break-glass)
    - `mcp-only`: auto-approve; writes scoped to MCP paths
    - `dev`: local model via Ollama (optional)
  - Web search: `[tools] web_search = true`
  - Docker MCP gateway: configured under `[mcp_servers.MCP_DOCKER]` using `docker mcp gateway run`
  - Windows config path: `C:\Users\<user>\.codex\config.toml`

## Roadmap Links
- NEXT_STEPS: Finish the M2 Automation Loop (n8n + Supabase + Agent Zero + Discord)
- ROADMAP: M2 — Creator & Publishing

