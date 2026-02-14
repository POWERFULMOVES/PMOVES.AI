# Production Audit Prep — 2026-02-14

## Scope

This prep pass focused on:

1. Cleaning submodule working trees for parent pointer updates.
2. Finalizing Codex parity updates across focus submodules.
3. Running available runtime validation commands and capturing blockers.
4. Preparing a push-ready set of repo-level updates for audit review.

## Completed Changes

- `PMOVES-Agent-Zero`
  - Synced upstream release `v0.9.8` via merge.
  - Added Codex home.
  - Key commits:
    - `a8fac57` `merge: sync upstream agent0ai/agent-zero v0.9.8`
    - `3b01fd4` `docs(codex): add codex operator home`

- `PMOVES-Pipecat`
  - Added Codex home on hardened branch.
  - Key commit:
    - `4335b8d5` `docs(codex): add codex home`

- `PMOVES-Creator`
  - Added Codex home on hardened branch.
  - Key commit:
    - `c67eaf40` `docs(codex): add codex home`

- `PMOVES-Wealth`
  - Added Codex home on hardened branch.
  - Removed duplicate lowercase `readme.md` to resolve Windows case-collision dirty state.
  - Key commits:
    - `ba3963ada2` `docs(codex): add codex home`
    - `2228425b6c` `chore(repo): remove duplicate lowercase readme for windows`

- Codex parity report updated:
  - `pmoves/docs/AGENTS/CODEX_SUBMODULE_INTEGRATION_AUDIT.md`
  - Focus coverage is now **8/8**.

## Validation Evidence

- `make -C pmoves codex-config && make -C pmoves codex-home && make -C pmoves codex-audit && make -C pmoves codex-health-quick`
  - Result: completed.
  - Health quick:
    - `ok`: `agent-zero`, `supaserch`
    - `--`: `archon`, `hirag-v2`, `flute-gateway`, `evo-controller`, `botz-gateway`

- `make -C pmoves smoke`
  - Result: failed.
  - Reason: `No rule to make target 'smoke'`.

- `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu` (PowerShell invocation)
  - Result: failed.
  - Reason: PowerShell treats inline env assignment as a command (`GPU_SMOKE_STRICT=true` not recognized). Also `smoke-gpu` target is not present in current Makefile.

- `make -C pmoves verify-all`
  - Result: exits without running full chain.
  - Reason: target recipe currently prints a quoted command chain and does not execute as expected in this environment.

- `make -C pmoves agents-headless-smoke`
  - Result: failed.
  - Reason: `Bash/Service/CreateInstance/E_ACCESSDENIED` while invoking bash-dependent sub-targets.

- `pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/scripts/smoke.ps1`
  - Result: partial pass then failed.
  - Progress: Qdrant, Meilisearch, Neo4j UI, Presign checks passed.
  - Reason: render-webhook health check (`http://localhost:8085/healthz`) was connection refused.

- `make -C pmoves gpu-rerank-evidence`
  - Result: failed.
  - Reason: command syntax error in this shell path before evidence capture completed.

## Audit Blockers (Current)

1. Makefile/docs mismatch for smoke targets (`smoke`, `smoke-gpu`).
2. `verify-all` recipe execution behavior needs correction in this shell path.
3. Bash/WSL permission issue blocks several smoke targets from PowerShell.
4. Not all required services are up (`render-webhook` currently failing health), so end-to-end runtime gates cannot be fully exercised yet.

## Recommended Next Remediation Before Production Audit

1. Add/restore canonical smoke aliases (`smoke`, `smoke-gpu`) or update docs to current target set.
2. Fix `verify-all` recipe quoting/execution so chained checks run reliably.
3. Resolve local Bash/WSL `E_ACCESSDENIED` (or provide PowerShell-native smoke wrappers).
4. Bring up full stack and rerun:
   - `make -C pmoves verify-all`
   - `make -C pmoves agents-headless-smoke`
   - `make -C pmoves codex-health-quick`

## CI Hardening Updates (2026-02-14)

Additional production-audit fixes were applied on branch `pr/hardened-ghcr-standardize` (PR #623):

1. GHCR auth standardized across active self-hosted build workflows:
   - `.github/workflows/integrations-ghcr.yml`
   - `.github/workflows/build-images.yml`
   - `.github/workflows/self-hosted-builds.yml`
   - `.github/workflows/self-hosted-builds-hardened.yml`
   - Uses `GHCR_USERNAME` + (`GHCR_TOKEN` or `GH_PAT_PUBLISH`) with fallback to `github.token`.
2. Workflow parser blockers resolved:
   - `codeql.yml`: moved `paths-ignore` under `on.push` and `on.pull_request`.
   - `sync-secrets-local.yml`: removed inline `${{` parse hazard and fixed secret summary variable reference bug.
3. Added operator docs:
   - `docs/GITHUB_APP_LOCAL_SETUP.md`
   - Updated GHCR/PAT guidance in `docs/SECRETS_ONBOARDING.md` and `pmoves/docs/CI_IMAGES.md`.

### Remaining CI audit checks to confirm before merge

1. Validate new queued runs on PR #623:
   - `CodeQL Advanced`
   - `Build and publish integration images to GHCR`
2. If GHCR still reports `denied: denied`, rotate PAT and verify:
   - `GHCR_USERNAME` matches PAT owner.
   - PAT scopes include `read:packages` + `write:packages` (+ `repo` for private clone flows).
3. Self-hosted runner capacity/availability:
   - Repository runner inventory currently reports only `pmoves-ai-lab-runner` and `status=offline`.
   - While offline, PR checks that target self-hosted labels remain `queued` and cannot validate merged fixes.
