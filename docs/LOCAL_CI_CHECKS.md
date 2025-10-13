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

Keep the virtualenv around so re-runs before each push are quick (`pytest …`).

## 2. CHIT Contract Check

This grep-based smoke ensures the geometry schema, endpoints, events, and env flags stay present. From the repository root:

```bash
sudo apt-get install ripgrep   # once per machine (Linux) – macOS: brew install ripgrep
bash -c "set -euo pipefail; \
  rg -ni --iglob '*.sql' 'create table .*(anchors|constellations|shape_points|shape_index)' \
  && rg -n 'POST /geometry/event|GET /shape/point/.*/jump|/geometry/decode/(text|image|audio)|/geometry/calibration/report' pmoves/services \
  && rg -n 'geometry.cgp.v1' -S \
  && rg -n 'CHIT_REQUIRE_SIGNATURE|CHIT_PASSPHRASE|CHIT_DECRYPT_ANCHORS|CHIT_CODEBOOK_PATH|CHIT_T5_MODEL' -S"
```

If any command exits non-zero, inspect the missing asset and update the offending file or the workflow allowlist.

## 3. SQL Policy Lint

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

## 4. Env Preflight (Windows parity)

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
- [ ] SQL policy lint
- [ ] Env preflight (`scripts/env_check.ps1 -Quick` or `env_check.sh -q`)

If any check is intentionally skipped (e.g., doc-only change), note the reason in the PR “Testing” section.
