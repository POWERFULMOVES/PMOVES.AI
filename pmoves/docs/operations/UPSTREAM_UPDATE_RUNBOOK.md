# Upstream Submodule Update Runbook

Operational guide for the automated submodule update pipeline that keeps PMOVES.AI
synchronized with upstream changes in core submodules.

## Tracked Submodules

| Submodule | Path | Branch | Expected Cadence | Risk Level |
|-----------|------|--------|------------------|------------|
| PMOVES-Agent-Zero | `PMOVES-Agent-Zero` | `PMOVES.AI-Edition-Hardened` | Frequent (weekly) | High — orchestration core, MCP API surface |
| PMOVES-Archon | `PMOVES-Archon` | `PMOVES.AI-Edition-Hardened` | Moderate (biweekly) | Medium — agent forms, Supabase integration |
| PMOVES-n8n | `PMOVES-n8n` | `PMOVES.AI-Edition-Hardened` | Monthly releases | Low-Medium — workflow engine, node updates |
| PMOVES-supabase | `PMOVES-supabase` | `PMOVES.AI-Edition-Hardened` | Quarterly | High — database schema, auth, RLS policies |

## How the Pipeline Works

### Automated Detection (Weekly)

The `submodule-update-check` workflow runs every Sunday at 06:00 UTC:

1. Checks out the main branch with all submodules initialized
2. For each tracked submodule, fetches the latest commit on its tracking branch
3. Compares the current gitlink SHA against the upstream HEAD
4. If new commits are found, creates a PR with:
   - Updated gitlink pointer
   - `upstream-update` label
   - Commit log of the last 5 upstream changes
   - Review checklist for breaking changes

### Smoke Test Gate

When a PR with the `upstream-update` label is opened or updated, the
`submodule-smoke` workflow automatically:

1. Identifies which submodules have changed gitlinks
2. Verifies submodule checkout integrity
3. Runs `make -C pmoves verify-all` (bring-up, preflight, smoke tests)
4. Checks health endpoints for affected services
5. Posts results as a PR comment

### Manual Trigger

To check a specific submodule on demand:

```
gh workflow run submodule-update-check.yml \
  --field submodules="PMOVES-Agent-Zero" \
  --field dry_run=false
```

Dry-run mode (detect only, no PR):

```
gh workflow run submodule-update-check.yml \
  --field dry_run=true
```

## Reviewing Update PRs

### Always Check

1. **NATS Subject Compatibility**
   - Search the upstream diff for changes to NATS publish/subscribe subjects
   - Any renamed or removed subjects will break inter-service communication
   - Cross-reference against `pmoves/configs/nats-subjects.yaml` or `.claude/context/nats-subjects.md`

2. **API Schema Changes**
   - Check for modified endpoint paths, request/response shapes, or removed endpoints
   - Agent Zero: `/mcp/*` endpoints, `/healthz`
   - Archon: `/healthz`, form management endpoints
   - n8n: webhook endpoints, workflow execution API
   - Supabase: PostgREST schema, RLS policy changes, migration files

3. **Configuration Format**
   - New or changed environment variables (check upstream `.env.example` or `.env.defaults`)
   - Docker compose override changes (ports, volumes, healthchecks)
   - If new env vars are required, add them to `pmoves/bootstrap/registry.json` and
     `pmoves/tools/brand_defaults.py` before merging

4. **Docker Healthcheck**
   - Verify the service healthcheck endpoint still works at the same path
   - Check for changed ports or startup dependencies

5. **Python/Node Dependency Changes**
   - Review `requirements.txt` / `package.json` diffs for:
     - Removed packages (will break imports)
     - Major version bumps (potential API changes)
     - New system dependencies (gcc, ffmpeg, etc.)

### Per-Submodule Specifics

**Agent Zero:**
- Check `agent_zero/mcp/` for MCP tool registration changes
- Verify `instruments/` folder for new or removed agent instruments
- Review `models/` for default model configuration changes
- Watch for changes to the subordinate agent spawn mechanism

**Archon:**
- Check Supabase migration files in `supabase/migrations/`
- Verify form schema definitions have not changed shape
- Review persona service for prompt template changes

**n8n:**
- Check for custom node changes in `packages/nodes-base/`
- Verify credential type definitions are compatible
- Review workflow execution engine changes

**Supabase:**
- **Highest risk** — database schema changes can break all dependent services
- Always review `migrations/` directory for new SQL files
- Check `docker/` for compose changes, new containers, or removed services
- Verify `kong/` configuration for API gateway route changes
- Test GoTrue (auth) configuration changes locally before merging

## Rollback Procedure

If a merged submodule update causes issues:

### Quick Rollback (Revert Gitlink)

```bash
# Identify the merge commit
git log --oneline -5

# Revert the gitlink bump commit
git revert <merge-commit-sha>

# Reinitialize submodules to the reverted state
git submodule update --init --recursive

# Redeploy affected services
make -C pmoves up
```

### Targeted Rollback (Single Submodule)

```bash
# Pin to a known-good commit
cd PMOVES-Agent-Zero
git checkout <known-good-sha>
cd ..

# Stage and commit
git add PMOVES-Agent-Zero
git commit -m "fix(submodules): rollback PMOVES-Agent-Zero to <known-good-sha>"

# Redeploy
make -C pmoves up-agent-zero
```

### Full Recovery

If multiple submodules are affected:

```bash
# Reset all submodules to the state at a known-good main commit
git checkout <known-good-main-sha> -- .gitmodules
git submodule sync
git submodule update --init --recursive

# Stage everything
git add .gitmodules PMOVES-Agent-Zero PMOVES-Archon PMOVES-n8n PMOVES-supabase
git commit -m "fix(submodules): rollback all to known-good state"

# Full redeploy
make -C pmoves up
make -C pmoves verify-all
```

## Manual Update Procedure

For cases where the automated pipeline is not running or you need immediate updates:

```bash
# Update a single submodule to latest upstream
git submodule update --remote PMOVES-Agent-Zero

# Verify the diff
cd PMOVES-Agent-Zero
git log --oneline -5
cd ..

# Stage and commit
git add PMOVES-Agent-Zero
git commit -m "chore(submodules): bump PMOVES-Agent-Zero to latest"

# Push and create PR
git push origin feature/manual-bump-agent-zero
gh pr create \
  --title "chore(submodules): bump PMOVES-Agent-Zero to latest" \
  --body "Manual submodule bump. Review upstream changelog before merging." \
  --label "upstream-update"
```

## Adding a New Tracked Submodule

1. Verify the submodule exists in `.gitmodules` with the correct branch
2. Add a new entry to the `TRACKED_SUBMODULES` env var in
   `.github/workflows/submodule-update-check.yml`:
   ```
   NewSubmodule:path/to/submodule:branch-name
   ```
3. If the submodule has a health endpoint, add it to the `health_map` in
   `.github/workflows/submodule-smoke.yml`
4. Update the table at the top of this document

## NATS Event

When updates are detected, the workflow publishes (best-effort):

- **Subject:** `ops.submodule.update.detected.v1`
- **Payload:** `{"workflow": "submodule-update-check", "updated": <count>, "timestamp": "<ISO8601>"}`

This can be consumed by monitoring or notification services (e.g., Publisher-Discord)
to alert the team about pending update PRs.

## Troubleshooting

### Workflow fails with "could not fetch origin/branch"

The submodule remote URL may have changed or the branch may have been renamed.
Check `.gitmodules` for the correct URL and branch, then verify with:

```bash
cd PMOVES-Agent-Zero
git remote -v
git ls-remote origin
```

### PR creation fails with "label does not exist"

The `upstream-update` label must exist in the GitHub repository. Create it manually:

```bash
gh label create upstream-update --description "Automated upstream submodule update" --color "0E8A16"
```

### Smoke tests fail but submodule update is valid

If the failure is pre-existing (not caused by the update), document it in the PR
comment and merge with `--admin` if appropriate. Always verify the failure is
unrelated by checking the smoke test output against the previous main branch state.

### Submodule has merge conflicts

This typically means local hardened-branch changes conflict with upstream. Resolution:

1. Check out the submodule's hardened branch
2. Rebase or merge upstream changes
3. Push the resolved hardened branch
4. Re-run the update check workflow
