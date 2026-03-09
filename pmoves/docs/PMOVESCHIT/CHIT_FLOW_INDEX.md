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

## CHIT-FLOW-005: Operation Dock.Tier Git.Flare Parity
- Scope: local-first image validation, GHCR credential reuse, and targeted workflow dispatch with runner gates.
- Entry commands:
  - `make -C pmoves ghcr-bootstrap-secrets GH_SECRET_ENV=Dev GH_REPO=CATACLYSMSTUDIOS-INC/PMOVES.AI`
  - `make -C pmoves ghcr-prepublish-supaserch`
  - `make -C pmoves ci-runners-check-strict`
  - `make -C pmoves ghcr-dispatch-supaserch GHCR_DISPATCH_REF=<branch> GHCR_NAMESPACE=cataclysmstudios-inc`
- Output: targeted GHCR matrix runs only after local proof, plus auditable credential/bootstrap pathway.
- Related runbook:
  - `pmoves/docs/AGENTS/OPERATION_DOCK_TIER_GIT_FLARE_PARITY.md`

## CHIT-FLOW-006: PR Review Learnings -> FlOO$ -> Graphiti
- Scope: keep PR queue actionable and machine-traceable by chaining monitor output into CHIT and Graphiti handoff context.
- Entry commands:
  - `make -C pmoves pr-monitor`
  - `make -C pmoves pr-monitor-chit-packet`
  - `make -C pmoves floos-pr-monitor-validate`
  - `make -C pmoves floos-pr-monitor-resolve`
  - `make -C pmoves floos-pr-monitor-run-dry`
  - `make -C pmoves chit-flow-pr-monitor-strict`
- Output:
  - `pmoves/docs/logs/pr_monitor_latest.json`
  - `pmoves/docs/logs/pr_monitor_learnings_latest.md`
  - `pmoves/docs/logs/pr_monitor_learnings_latest.cgp.json`
  - FlOO$ pairing: `pr-monitor-graphiti-chit` in `pmoves/configs/skill-pairings.yaml`

## CHIT-FLOW-007: Codex MCP + PMOVES Integration Parity
- Scope: keep Codex MCP wiring and Agent Zero MCP runtime map aligned with production topology.
- Entry commands:
  - `make -C pmoves a0-mcp-seed`
  - `cat pmoves/data/agent-zero/runtime/mcp/servers.env`
  - `make -C pmoves archon-mcp-smoke`
  - `make -C pmoves codex-health-quick`
- Output:
  - Refreshed MCP server map for Agent Zero runtime
  - Verified Archon MCP bridge reachability
  - Fast Codex health evidence for core PMOVES services
