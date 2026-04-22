# Fix Runner Restart Loop

## Problem Analysis (2026-04-21)

**Symptom:** All three local-cert runners (`gha-runner-ai-lab`, `gha-runner-vps`, `gha-runner-hotfix`) stuck in restart loop with exit code 2.

**Root Cause:** Runner state persistence conflict

1. **Volume mount persistence**: Containers mount `$HOME/.config/pmoves` → `/root/.config/pmoves`
2. **State leak**: GitHub runner stores configuration in `/root/.config/pmoves` or `/tmp/runner/_work`
3. **Container recreation**: `docker_rm()` removes container but mounted volume preserves runner state
4. **Configuration failure**: New container tries to configure already-configured runner → error

**Error Pattern:**
```
Cannot configure the runner because it is already configured.
An error occurred: Value cannot be null. (Parameter 'configuredSettings')
Runner reusage is disabled
```

## Solution Options

### Option 1: Enable Runner Reuse (RECOMMENDED)
Add environment variable to allow runner state reuse:

```python
# In local_cert_runners.py docker_run() function
env["RUNNER_ALLOW_RUNNER_REUSE"] = "true"
```

**Pros:**
- Preserves runner authentication across container restarts
- Faster startup (no re-registration needed)
- Aligns with GitHub Actions runner best practices

**Cons:**
- Runner state may become stale if registration expires

### Option 2: Clean State on Startup
Add cleanup step before container start:

```python
# In local_cert_runners.py cmd_up() function
def _cleanup_runner_state(container_name: str) -> None:
    """Remove runner configuration from persistent volume."""
    from pmoves.tools._secrets_common import host_config_dir
    config_dir = host_config_dir()
    runner_config = config_dir / ".runner"  # or wherever runner stores state
    if runner_config.exists():
        shutil.rmtree(runner_config, ignore_errors=True)
```

**Pros:**
- Guaranteed clean state each run
- No stale configuration issues

**Cons:**
- Loses runner authentication (must re-register each time)
- Slower startup

### Option 3: Unique Container Names
Generate unique container names per run:

```python
import uuid
container_name = f"gha-runner-{lane.lane}-{uuid.uuid4().hex[:8]}"
```

**Pros:**
- No configuration conflicts

**Cons:**
- Breaks `docker_rm()` logic (doesn't know previous container name)
- Accumulates stopped containers over time

## Recommended Fix

**Implement Option 1 (Enable Runner Reuse)** as the primary solution with Option 2 as fallback.

### Changes to `pmoves/tools/local_cert_runners.py`

```python
def docker_run(
    repo: str, image: str, lane: RunnerLane, token: str,
    *, is_pat: bool = True, auth_mode: str = "pat",
) -> None:
    # ... existing code ...

    # Add runner reuse flag BEFORE creating container
    env["RUNNER_ALLOW_RUNNER_REUSE"] = "true"  # ← ADD THIS LINE

    env["REPO_URL"] = f"https://github.com/{repo}"
    env["RUNNER_NAME"] = lane.runner_name
    env["LABELS"] = lane.labels
    env["RUNNER_WORKDIR"] = "/tmp/runner/_work"
```

### Fallback Cleanup (if reuse fails)

```python
def cmd_up(repo: str, image: str, lanes: tuple[RunnerLane, ...]) -> int:
    require_tool("docker")
    for lane in lanes:
        # Clean up old runner state if it exists
        from pmoves.tools._secrets_common import host_config_dir
        config_dir = host_config_dir()
        runner_state = config_dir / f".{lane.lane}-runner-state"
        if runner_state.exists():
            shutil.rmtree(runner_state, ignore_errors=True)

        token, is_pat, auth_mode = access_token(repo, lane.lane)
        docker_rm(lane.container_name)
        docker_run(repo, image, lane, token, is_pat=is_pat, auth_mode=auth_mode)
        # ... rest of function ...
```

## Implementation Steps

1. Update `local_cert_runners.py` to add `RUNNER_ALLOW_RUNNER_REUSE=true`
2. Restart all runners: `python pmoves/tools/local_cert_runners.py down && python pmoves/tools/local_cert_runners.py up`
3. Verify runners stay running: `docker ps --filter "name=gha-runner"`
4. Check runner registration: `gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners --jq '.runners[] | select(.name | startswith("pmoves-")) | {name, status}'`

## Testing Checklist

- [ ] Runners start successfully without restart loop
- [ ] Runners register with GitHub (status: "online")
- [ ] Runners can pick up jobs (test workflow dispatch)
- [ ] Container restart preserves runner state (no re-registration)
- [ ] Multiple `up/down` cycles work correctly

## Related Documentation

- GitHub Actions Runner Docs: https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners
- AGNOTE4482.md - Runner authentication cascade (Phase 9G)
- pmoves/docs/operations/GHA_RUNNER_RUNBOOK.md - Runner operations guide
