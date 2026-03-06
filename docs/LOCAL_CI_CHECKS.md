# Local CI Checks

Run these workflows before opening a pull request so GitHub Actions and the Codex/Copilot reviewers only have to evaluate the diff, not chase failed automation.

## 1. Python Service Tests

The CI workflow installs the publisher, pmoves-yt, and publisher-discord requirements and runs their unit suites. Mirror that locally:

```bash
cd pmoves
python -m venv .venv && source .venv/bin/activate       # or reuse an existing env
python -m pip install -U pip
python -m pip install -r services/publisher/requirements.txt \
                       -r services/publisher-discord/requirements.txt \
                       -r services/pmoves-yt/requirements.txt \
                       pytest
pytest -q services/publisher/tests \
        services/pmoves-yt/tests \
        services/publisher-discord/tests
```

Tip: run per-service in separate virtualenvs if resolver conflicts occur. The repo includes underscore import shims so tests can import `pmoves.services.pmoves_yt` and `pmoves.services.publisher_discord` reliably.

`services/pmoves-yt/requirements.txt` now bundles `pytest-asyncio` because the playlist rate-limit test (`tests/test_rate_limit.py`) executes `async def` coroutines. Make sure you reinstall the requirements file (or `pip install pytest-asyncio`) locally before rerunning the CI mirror commands above.

Keep the virtualenv around so re-runs before each push are quick (`pytest …`).

## 2. CHIT Contract Check

This grep-based smoke ensures the geometry schema, endpoints, events, and env flags stay present. We ship a helper script and Makefile target so the workflow logic is easy to mirror:

```bash
sudo apt-get install ripgrep   # once per machine (Linux) – macOS: brew install ripgrep
cd pmoves
make chit-contract-check       # wraps ../scripts/check_chit_contract.sh
```

If the command exits non-zero, inspect the missing asset and update the offending file or adjust the workflow allowlist before pushing.

## 3. Jellyfin Credential Check (self-hosted stacks)

Confirm that the local Jellyfin instance is reachable, branded, and exposes the
expected libraries:

```bash
cd pmoves
JELLYFIN_URL=http://localhost:8096 \           # override as needed
JELLYFIN_API_KEY=your-token \                 # required
JELLYFIN_USER_ID=<optional-user-id> \         # validates enumeration when set
make jellyfin-verify
```

The command calls `scripts/check_jellyfin_credentials.py` and raises actionable
errors when the API key is invalid, the user cannot enumerate libraries, or the
server name does not match the default PMOVES branding.

## 4. SQL Policy Lint

Prevents accidental `USING true` policies or `GRANT … TO anon` statements outside the approved files.

```bash
bash -c "set -euo pipefail
shopt -s nullglob
files=(pmoves/supabase/sql/*.sql pmoves/supabase/migrations/*.sql)
allowlist=(
  'pmoves/supabase/sql/006_media_analysis.sql'
  'pmoves/supabase/migrations/2025-09-08_geometry_bus_rls.sql'
  'pmoves/supabase/migrations/2025-09-09_pmoves_yt_jobs.sql'
  'pmoves/supabase/migrations/2025-09-10_media_analysis_rls.sql'
  'pmoves/supabase/migrations/2025-10-18_geometry_swarm.sql'
  'pmoves/supabase/migrations/2025-10-18_health_finance.sql'
)
echo \"Scanning \${#files[@]} SQL files for 'USING true' or 'to anon'...\"
bad=0
for f in \"\${files[@]}\"; do
  if printf '%s\n' \"\${allowlist[@]}\" | grep -Fxq \"$f\"; then
    echo \"Skipping allowlisted policy file: $f\"
    continue
  fi
  if grep -Eqi '\\bUSING\\s*\\(?\\s*true\\s*\\)?' \"$f\"; then
    echo \"Unsafe blanket policy in: $f\"; bad=1
  fi
  if grep -Eqi 'to\\s+anon\\b' \"$f\"; then
    echo \"Policy grants to anon found in: $f\"; bad=1
  fi
done
if [ \"$bad\" -ne 0 ]; then
  echo \"Found unsafe policy patterns. See pmoves/docs/SUPABASE_RLS_CHECKLIST.md\" >&2
  exit 1
fi
echo \"No unsafe patterns found.\""
```

## 5. Env Preflight (Windows parity)

The workflow runs on `windows-latest` with PowerShell 7. On Windows or WSL:

```powershell
cd pmoves
pwsh -NoProfile -File scripts/env_check.ps1 -Quick
```

The script validates required binaries (`git`, `python`, `docker`, etc.), checks .env coverage, and lists port collisions. For Linux/macOS, run `scripts/env_check.sh -q` for parity.

## 6. Integration Contract Gate (pmoves-integrations)

Validate the contract template and any opted-in integration overlay before PR:

```bash
cd pmoves
make integration-contract-check-baseline
./integrations/tools/validate-integration.sh integrations/_template/pmoves-integrations --strict-hooks
```

For a concrete integration overlay under review:

```bash
cd pmoves
INTEGRATION_PATH=integrations/<integration-name> make integration-contract-check-strict
```

For submodule-managed overlays (current blocker: `integrations/archon`), run:

```bash
python pmoves/tools/integration_contract_check.py pmoves/integrations/archon --strict-hooks
```

## 7. Self-Hosted Runner Lane Check (production CI)

Before dispatching workflow jobs that require self-hosted labels, verify the lanes are online:

```bash
cd pmoves
make ci-runners-check
make ci-runners-check-strict
python pmoves/tools/ci_runner_check.py --discover-workflow-groups
```

Expected required groups:
- `self-hosted,vps` (core build/test lanes)
- `self-hosted,ai-lab,gpu` (GPU build lanes)

If strict mode fails, bring the runner(s) online first. Otherwise GHCR and hardened build workflows will queue indefinitely.

## 8. GHCR Local-First Prepublish Gate (Production Matrix)

Before dispatching `integrations-ghcr.yml`, optionally bootstrap GHCR auth secrets (when rotation/refresh is needed), then run the local gate so non-VPS operators can validate production image Dockerfile/context correctness locally.

If GHCR auth secrets need rotation/bootstrap from existing credentials in `env.shared`:

```bash
cd pmoves
make ghcr-bootstrap-secrets GH_SECRET_ENV=Dev GH_REPO=<org>/<repo>
```

Then run the local prepublish gate for all in-repo production images:

```bash
cd pmoves
make ghcr-prepublish-inrepo
```

Optional: include external integration repos from the matrix as part of local validation:

```bash
cd pmoves
make ghcr-prepublish-all
```

Use the targeted SupaSerch gate when triaging one image:

```bash
cd pmoves
make ghcr-prepublish-supaserch
```

Then dispatch the full production matrix build:

```bash
cd pmoves
make ghcr-dispatch-all GHCR_DISPATCH_REF=<branch> GHCR_NAMESPACE=<org-namespace>
```

Or dispatch a targeted integration lane:

```bash
cd pmoves
make ghcr-dispatch-supaserch GHCR_DISPATCH_REF=<branch> GHCR_NAMESPACE=<org-namespace>
```

## 9. Submodule Production Deterministic Gate

Before final production promotion PRs, run the submodule-first deterministic chain:

```bash
cd pmoves
make submodule-layer-validate-all-strict
make submodule-layer-validate-strict
make submodule-branch-policy-check
make submodule-integrity-strict
make submodule-docs-audit-strict
make integration-contract-check-baseline
make tooling-audit-strict
make secrets-audit
make ci-runners-lockdown-strict
SUPABASE_RUNTIME=compose make supa-runtime-guard
make smoke-prod
GPU_SMOKE_STRICT=true make smoke-gpu
```

Use the per-submodule matrix in:

`pmoves/docs/integrations/SUBMODULE_PRODUCTION_RELEASE_CHECKLIST.md`

## 10. Python Images Toolchain Canary (weekly + manual)

Production Python image toolchain pins are intentionally exact for reproducibility. Weekly canary checks for new `setuptools`/`wheel` releases, validates build+Trivy across the managed image set (`supaserch`, `deepresearch`, `pmoves-yt`, `archon`), and opens a bump PR only when every candidate passes.

Manual dispatch:

```bash
gh workflow run python-images-toolchain-canary.yml \
  --repo POWERFULMOVES/PMOVES.AI \
  --ref PMOVES.AI-Edition-Hardened
```

Manual dispatch with explicit versions:

```bash
gh workflow run python-images-toolchain-canary.yml \
  --repo POWERFULMOVES/PMOVES.AI \
  --ref PMOVES.AI-Edition-Hardened \
  -f setuptools_version=82.0.0 \
  -f wheel_version=0.46.3 \
  -f open_pr=true
```

Local parity:

```bash
docker buildx build --platform linux/amd64 \
  -f pmoves/services/supaserch/Dockerfile \
  -t local/pmoves-supaserch:toolchain-canary \
  pmoves/services --load

docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.57.1 image --severity HIGH,CRITICAL \
  --ignore-unfixed --format table --exit-code 1 \
  local/pmoves-supaserch:toolchain-canary
```

Runbook: `docs/hardening/PYTHON_IMAGES_TOOLCHAIN_CANARY.md`

## 11. UI Topology Smoke (4482 + branded overlays)

When release work touches service wiring, compose topology, or branded integrations, run the UI topology gate so backend bring-up and UI routing stay in sync:

```bash
cd pmoves
make ui-topology-smoke
make ui-topology-smoke-all
```

Notes:
- `ui-topology-smoke` defaults to the core profile (`PMOVES UI`, `Agent Zero UI`, `Archon UI`, `Open Notebook UI`, and service detail routes that commonly regressed to 404s).
- `ui-topology-smoke-all` adds external surfaces (`Firefly`, `Wger`, `Jellyfin`, `Jellyfin AI dashboard/API`, and Open Notebook API).
- To avoid hard failures for intentionally-down optional surfaces during local iteration, use:

```bash
cd pmoves
UI_TOPOLOGY_ALLOW_MISSING=true make ui-topology-smoke-all
```

## Checklists

Copy these bullets into PR descriptions (or tick the template boxes) after each local run:

- [ ] `pytest` suites (publisher, pmoves-yt, publisher-discord)
- [ ] CHIT contract grep
- [ ] Jellyfin credential check (when the publisher is in play)
- [ ] SQL policy lint
- [ ] Env preflight (`scripts/env_check.ps1 -Quick` or `env_check.sh -q`)
- [ ] Integration contract check (`make integration-contract-check-strict`; plus `INTEGRATION_PATH=...` when onboarding/updating an opted-in integration)
- [ ] Discord embed smoke (`make demo-content-published`) when validating multimedia metadata
- [ ] Self-hosted runner lane check (`make ci-runners-check-strict`) before GHCR/self-hosted dispatches
- [ ] GHCR local-first prepublish gate (`make ghcr-prepublish-inrepo`) before production GHCR dispatch
- [ ] Python images toolchain canary dispatch/review (`python-images-toolchain-canary.yml`) when bumping Docker toolchain pins
- [ ] UI topology smoke (`make ui-topology-smoke`; plus `make ui-topology-smoke-all` for external-stack release validation)
- [ ] Submodule deterministic gate (`make submodule-layer-validate-all-strict` through `make smoke-prod`, plus `make submodule-branch-policy-check`)

If any check is intentionally skipped (e.g., doc-only change), note the reason in the PR “Testing” section.
