# Merge Playbook — Geometry Packs + Health/Finance + External Integration

_Last updated: 2025-10-19_

This playbook outlines how to merge the `feat/geometry-pack-smoke` branch (new folder structure + CHIT EvoSwarm + Wger/Firefly docs, schemas, flows) with other in-flight branches (e.g., `feature/jellyfin-backfill-automation`, `feat/integrations-wger-firefly`, and recent `codex/*`).

## 0) Inventory and Branch Strategy
- Target: `main` (fast-forward preferred).
- Integration branch: create `merge/integrations-rollup-2025-10-19` off `main`.
- Bring in branches in this order to minimize conflicts:
  1. `feat/geometry-pack-smoke` (this branch)
  2. external integration branch (provide exact name/commit) — if it touches services/docs, merge after geometry
  3. `feature/jellyfin-backfill-automation` (publisher scripts, Supabase artifacts)
  4. `codex/*` maintenance/test branches

Rationale: folder structure and docs redirects land first, then specific integrations adapt to the new paths.

## 1) Path Mapping & Compatibility
- Keep redirects in `pmoves/docs/*.md` pointing to `pmoves/docs/PMOVES.AI PLANS/*`.
- Python import shims present for underscore/hyphen modules:
  - `pmoves/services/publisher_discord/*` → forwards to `publisher-discord`
  - `pmoves/services/pmoves_yt/*` → forwards to `pmoves-yt`
- Services docs index updated under `pmoves/docs/services/`.

Action: if the external integration adds new services, create matching docs under `pmoves/docs/services/<service>/README.md` and link from the index.

## 2) Merge Procedure (commands)
```bash
# Create rollup branch
git checkout main && git pull --rebase
git checkout -b merge/integrations-rollup-2025-10-19

# 1) Merge geometry packs branch
git merge --no-ff origin/feat/geometry-pack-smoke

# 2) Merge the external integration branch (provide name)
# Example: git merge --no-ff origin/feat/integrations-wger-firefly

# 3) Merge jellyfin backfill automation
git merge --no-ff origin/feature/jellyfin-backfill-automation

# 4) Merge codex maintenance PRs
# Example: for bunched codex/* branches, prefer merging main after they’re in
```

Conflict hotspots to expect:
- `README.md`, `folders.md`, services docs index
- publisher-discord main formatting tweaks
- pmoves-yt requirements / tests
- Supabase migrations ordering (ensure idempotence)

## 3) Conflict Resolution Rules
- Prefer the new folder structure and docs redirects.
- Keep both enhancements when conflict is in logic; otherwise prefer the more recent tested behavior (see failing tests on both branches).
- For migrations:
  - Keep geometry tables and compat alters from 2025-10-18 files.
  - If the other branch adds migrations on same objects, ensure `IF NOT EXISTS` guards and additive indexes; re-run `make supabase-bootstrap` locally.

## 4) Validation Matrix
Run locally from repo root:
- Contracts/links
  - `make chit-contract-check`
  - topics schema path validation script (already used in PR)
  - services docs link check (rg based)
- DB migrations
  - `make supabase-bootstrap` (CLI) or apply via compose Postgres as documented
  - Verify `geometry_parameter_packs`, `geometry_swarm_runs`, `health_*`, `finance_*`
- Services
  - `pytest` per service in separate venvs (publisher, pmoves-yt, publisher-discord)
  - Optional: pmoves-yt emit CGP and confirm gateway v2 persists constellation meta with pack_id
- n8n
  - Ensure `N8N_API_KEY` set; import or update flows; run manual executions for Wger/Firefly

## 5) Release Notes & Migration
- New docs:
  - Service index under `pmoves/docs/services/` plus per-service READMEs
  - Redirect stubs under `pmoves/docs/*.md` (backwards compatibility)
- Env changes:
  - `DISCORD_PUBLISH_PREFIX` (publisher-discord)
  - `YT_RATE_LIMIT` read at call-time in pmoves-yt
  - `SUPA_REST_URL` available to n8n compose; flows rely on Supabase service key
- Data model:
  - Added health_*, finance_* tables with dev RLS; geometry packs tables & compat columns

## 6) Rollback Plan
- If rollup branch fails CI:
  - Re-merge without the external integration to isolate issues.
  - Back out contentious migrations (keep compat alters), retest.

## 7) Owner Checklist
- [ ] Confirm external integration branch name/commit SHA
- [ ] Merge rollup branch and resolve conflicts
- [ ] Run validation matrix
- [ ] Post PR with this playbook linked; request reviewers @PowerfulMoves @codex

