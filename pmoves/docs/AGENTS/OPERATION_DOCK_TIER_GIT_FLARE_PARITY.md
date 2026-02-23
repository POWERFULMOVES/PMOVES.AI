# OPERATION DOCK.TIER GIT.FLARE PARITY

This runbook defines the local-to-cloud release lane for PMOVES integrations with local-first certification before publish.

## Objective
- Keep one through-line from local dev to production publish.
- Reuse existing credentials for rotation/bootstrap instead of creating ad-hoc secrets.
- Require local image/build proof before dispatching self-hosted GHCR workflows.

## Lifecycle Schedule (CLI -> Cloud)

| Phase | Trigger | Primary Agent | Supporting Agents | Commands | Exit Criteria |
| --- | --- | --- | --- | --- | --- |
| 0. Credential Bootstrap | New runner/repo env or auth failure (401/403) | Codex | Archon (ops), Claude (review) | `make -C pmoves ghcr-bootstrap-secrets GH_SECRET_ENV=Dev GH_REPO=CATACLYSMSTUDIOS-INC/PMOVES.AI` | `GHCR_USERNAME` + `GHCR_TOKEN` present in target GitHub environment |
| 1. Local Runtime Bring-up | Branch ready for validation | Codex | Agent Zero | `SUPABASE_RUNTIME=cli make -C pmoves up` | Core services healthy (`make -C pmoves smoke`) |
| 2. Local Build Gate | Before any publish dispatch | Codex | SupaSerch worker | `make -C pmoves ghcr-prepublish-supaserch` | Local SupaSerch image builds successfully |
| 3. Runner Lane Gate | Before workflow dispatch | Codex | Archon | `make -C pmoves ci-runners-check-strict` | Required self-hosted lanes online |
| 4. Targeted Matrix Dispatch | Local gate + runner gate pass | Codex | GitHub Actions | `make -C pmoves ghcr-dispatch-supaserch GHCR_DISPATCH_REF=<branch>` | Selected integration workflow started successfully |
| 5. Release Audit Closeout | Workflow complete | Claude | Codex, Archon | PR comment + `docs/AGENT_TRAIL.md` graphiti entry | Checks green and handoff documented |

## Agent Availability and Responsibilities
- `Codex`: implementation, local gates, command parity, make/compose path consistency.
- `Claude`: PR review remediation, audit narrative, release readiness checks.
- `Archon`: runtime orchestration health, lane visibility, endpoint status.
- `Agent Zero`: operator interaction surface (health endpoints, user-facing status).
- `Channel Monitor`: ingest/approval feedback signal for new content review loops.

## Credential Reuse Policy
- Preferred source order for GHCR bootstrap:
1. `GHCR_TOKEN`
2. `GH_PAT_PUBLISH`
3. `gh auth token` (interactive fallback)
- Username source order:
1. `GHCR_USERNAME`
2. `GITHUB_ACTOR`
3. `gh api user -q .login`

## Required Evidence Before Publish
- Local build proof: `make -C pmoves ghcr-prepublish-supaserch`
- Runner lane proof: `make -C pmoves ci-runners-check-strict`
- Dispatch record: workflow URL or run id for `integrations-ghcr.yml`
- Doc parity: update `pmoves/docs/NEXT_STEPS.md` and `pmoves/docs/PMOVES.AI PLANS/ROADMAP.md` timestamps when the lane changes.
