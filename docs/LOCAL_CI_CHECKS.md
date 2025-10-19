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

Tip: run per-service in separate virtualenvs if resolver conflicts occur. The repo includes underscore import shims so tests can import `pmoves.services.pmoves_yt` and `pmoves.services.publisher_discord` reliably.
```

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

## Checklists

Copy these bullets into PR descriptions (or tick the template boxes) after each local run:

- [ ] `pytest` suites (publisher, pmoves-yt, publisher-discord)
- [ ] CHIT contract grep
- [ ] Jellyfin credential check (when the publisher is in play)
- [ ] SQL policy lint
- [ ] Env preflight (`scripts/env_check.ps1 -Quick` or `env_check.sh -q`)
- [ ] Discord embed smoke (`make demo-content-published`) when validating multimedia metadata

If any check is intentionally skipped (e.g., doc-only change), note the reason in the PR “Testing” section.
