Run the full pre-deployment preflight gate.

This is the final checkpoint before deploying or pushing changes. It validates environment, submodule integrity, CI runner availability, and overall system readiness.

## Preflight Checks (executed in order)

```
1. env-check               — Cross-platform environment variable validation
2. submodule-integrity      — Git submodule pointer consistency
3. ci-runners-check         — GitHub self-hosted runner availability
4. ci-runners-lockdown      — Runner lane phase policy enforcement
5. flight-check             — Fast readiness scan (host tools, Docker, ports)
6. codex-health-quick       — Core agent service health summary (non-fatal)
```

## Implementation

Execute the following steps:

1. **Run full preflight:**
   ```bash
   make -C pmoves preflight
   ```

   All checks except `codex-health-quick` must pass. The health check is informational (won't block).

2. **If preflight fails, follow the remediation order:**

   **env-check failure:**
   ```bash
   make -C pmoves ensure-env-shared          # Create env.shared from template
   make -C pmoves bootstrap-tier-envs        # Create missing tier files
   make -C pmoves secrets-funnel             # Regenerate from CHIT source
   ```

   **submodule-integrity failure:**
   ```bash
   git submodule update --init               # Re-sync submodule pointers
   ```

   **ci-runners-check failure:**
   ```bash
   make -C pmoves ci-runners-local-cert-up   # Start local runner containers
   ```

   **flight-check failure:**
   ```bash
   make -C pmoves check-tools                # Verify Docker, supabase CLI, Python
   ```

3. **For the full retro diagnostics with boot animation:**
   ```bash
   make -C pmoves flight-check-retro
   ```

## When to Run

- **Before creating a PR** — validates your branch is deployment-ready
- **Before `make up-*`** — catches missing env or broken submodules early
- **After `git pull`** — submodule pointers may have changed
- **In CI/CD** — automated gate before deploy steps

## Related Skills

| Skill | Purpose |
|-------|---------|
| `/deploy:secrets-funnel` | Regenerate tier env files from CHIT source |
| `/deploy:bootstrap-env` | Create missing tier files from examples |
| `/deploy:audit-layers` | Deep static + runtime certification |
| `/deploy:smoke-test` | Post-deployment service validation |

## Notes

- Preflight is lighter than `audit-layers` — it's a quick gate, not a full certification
- `codex-health-quick` requires Agent Zero / core services running (skipped if down)
- For full certification before production, use `/deploy:audit-layers` instead
- Evidence can be captured: `make -C pmoves preflight 2>&1 | tee preflight-evidence.log`
