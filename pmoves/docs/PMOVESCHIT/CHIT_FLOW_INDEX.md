# CHIT Flow Index

This file is the operator list of active CHIT-adjacent flows, ordered for production execution.

## CHIT-FLOW-001: CI Recovery (PR Lane)
- Scope: unblock CI regressions without merging.
- Entry commands:
  - `gh pr checks <pr>`
  - `gh run view <run_id> --job <job_id> --log`
  - `git worktree add ...`
- Output: atomic commits per PR and rerun checks.
- Current references:
  - `#677` `fix/silent-failure-hardening`
  - `#678` `fix/ci-pytest-conftest-collision`
  - `#681` `fix/ci-self-hosted-hardening`

## CHIT-FLOW-002: Production Runtime Audit
- Scope: validate stack, networking, migrations, and health in production mode.
- Entry commands:
  - `make -C pmoves supa-start`
  - `make -C pmoves supabase-bootstrap`
  - `SUPABASE_RUNTIME=cli make -C pmoves up`
  - `make -C pmoves smoke`
  - `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu`
- Output: update `pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md` and evidence logs.

## CHIT-FLOW-003: Credential and CHIT Portability
- Scope: secrets sync, CHIT export, and runtime hydration before bring-up.
- Entry commands:
  - `make -C pmoves secrets-runtime-hydrate`
  - `make -C pmoves chit-export`
  - `make -C pmoves secrets-funnel-sync`
- Output: updated CHIT manifests and validated environment parity.

## CHIT-FLOW-004: Geometry Bus + Discord Intake
- Scope: event intake from Discord/content drops into PMOVES ingestion.
- Related docs:
  - `pmoves/docs/PMOVESCHIT/02_GEOMETRY_BUS.md`
  - `pmoves/docs/PMOVESCHIT/03_EVO_SWARM.md`
  - `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md`
- Output: channel monitor and downstream ingestion events visible in audit trails.

## CHIT-FLOW-005: GHCR Targeted Matrix + Auth Hardening
- Scope: fix GHCR push authorization failures and validate one integration image at a time.
- Entry commands:
  - `gh workflow run integrations-ghcr.yml --ref <branch> -f integration=supaserch -f push_to_dockerhub=false`
  - `gh run view <run_id> --json status,conclusion,jobs`
  - `gh run view <run_id> --log-failed`
- Operator pattern:
  - Prefer PAT-first GHCR login (`GHCR_TOKEN` or `GH_PAT_PUBLISH`) with workflow-token fallback.
  - Keep matrix selection output minimal (`["supaserch"]` style names only); resolve metadata inside the build job.
  - Use resolve/build split (`resolve-matrix` -> `build-publish`) so dispatch selectors can run one image instead of full matrix.
  - If GitHub annotates `Skip output ... may contain secret`, treat as a matrix-output redaction issue and reduce output payload.
- Reference docs:
  - https://docs.github.com/actions/using-jobs/using-a-matrix-for-your-jobs
  - https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions#jobsjob_idoutputs
  - https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions#jobsjob_idstrategy
- Output: deterministic single-image validation path for GHCR ACL/ownership troubleshooting.
