# GitHub Actions

Check CI/CD workflow status and manage GitHub Actions for PMOVES.AI.

## Usage

```
/github:actions [workflow|run_id]
```

## Arguments

- `workflow` (optional): Workflow name or filename (e.g., `build`, `ci.yml`)
- `run_id` (optional): Specific run ID to inspect

## What This Command Does

1. **List Recent Workflow Runs:**
   ```bash
   gh run list --limit 10
   ```

2. **Check Specific Workflow:**
   ```bash
   gh workflow view <workflow_name>
   gh run list --workflow <workflow_name> --limit 5
   ```

3. **Inspect Run Details:**
   ```bash
   gh run view <run_id>
   gh run view <run_id> --log-failed
   ```

4. **Check PR Checks:**
   ```bash
   gh pr checks <pr_number>
   ```

## Workflow Status Legend

| Status | Meaning | Action |
|--------|---------|--------|
| ✓ Success | All jobs passed | None required |
| ✗ Failure | One or more jobs failed | Investigate logs |
| ○ Pending | Workflow in progress | Wait or check logs |
| ⊘ Cancelled | Manually cancelled | Re-run if needed |
| ⊘ Skipped | Conditions not met | Check workflow triggers |

## PMOVES Workflows

### Build Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `docker-build.yml` | Push to main, PR | Build Docker images |
| `multi-arch-build.yml` | Release | Multi-arch (amd64, arm64) |
| `ghcr-publish.yml` | Tag | Publish to GHCR |

### Test Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `smoke-tests.yml` | PR, Push | Run 75+ smoke tests |
| `functional-tests.yml` | PR | Service integration tests |
| `security-scan.yml` | Weekly, PR | Trivy, CodeQL scans |

### Deployment Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `deploy-staging.yml` | Push to main | Deploy to staging |
| `deploy-prod.yml` | Manual | Production deployment |

## Output Format

```markdown
## GitHub Actions Status

### Recent Runs
| Workflow | Branch | Status | Duration | Triggered |
|----------|--------|--------|----------|-----------|
| ... | ... | ... | ... | ... |

### Failed Runs (Last 24h)
| Run ID | Workflow | Failed Jobs | Error Summary |
|--------|----------|-------------|---------------|
| ... | ... | ... | ... |

### Pending Runs
<List of in-progress workflows>
```

## Example

```bash
# Show recent runs
/github:actions

# Check specific workflow
/github:actions docker-build

# Inspect failed run
/github:actions 12345678

# View failed logs
gh run view 12345678 --log-failed
```

## Common Actions

```bash
# Re-run failed workflow
gh run rerun <run_id>

# Re-run only failed jobs
gh run rerun <run_id> --failed

# Cancel running workflow
gh run cancel <run_id>

# Watch workflow progress
gh run watch <run_id>

# Download artifacts
gh run download <run_id>

# Trigger manual workflow
gh workflow run <workflow_name> --ref main
```

## Debugging Failed Runs

1. **Get failure summary:**
   ```bash
   gh run view <run_id> --json conclusion,jobs --jq '.jobs[] | select(.conclusion == "failure") | {name, conclusion}'
   ```

2. **View failed job logs:**
   ```bash
   gh run view <run_id> --log-failed
   ```

3. **Check environment variables:**
   ```bash
   gh run view <run_id> --json jobs --jq '.jobs[].steps[] | {name, conclusion}'
   ```

4. **Re-run with debug logging:**
   ```bash
   gh run rerun <run_id> --debug
   ```

## Notes

- Requires `gh` CLI authenticated with repo access
- Failed runs should be investigated promptly
- Consider enabling required status checks for protected branches
- PMOVES uses multi-arch builds for amd64 and arm64 compatibility
