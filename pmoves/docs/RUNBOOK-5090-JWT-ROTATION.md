# 5090 Node: JWT Secret Rotation + Runtime Secrets Hydration Runbook

> **Status**: v1 (operator-actionable, addresses B850-CLAUDE P1/P2/P3 of 2026-09-28 on PR #3213).
> **Tool**: `pmoves/tools/jwt_rotate.py` (companion). Wraps the upstream Supabase self-hosted
> `pmoves-supabase/docker/utils/generate-keys.sh` algorithm with a backup-first, enumerate-all
> consumers, verify-after-rotate contract.
> **Cross-fork map**: PMOVES-BoTZ, PMOVES-Archon, PMOVES-supabase -- see "Cross-fork context" below.

## Cwd pin (resolves P1.3 from B850)

Every command below runs from the PMOVES.AI repo root. Resolve it once at the top:

```bash
cd "$(git rev-parse --show-toplevel)"
```

Do not run from `pmoves/` or anywhere else -- step 2 needs the root (for `pmoves/tools/`), step 4
needs `pmoves/env.tier-supabase`, and the recreate commands need the compose files at the root
`docker-compose*.yml` set.

The `jwt_rotate.py` script defaults to cwd as the repo root. Override with `--repo-root` if
the cwd is wrong.

## Phase 0: Tool sanity check

```bash
# The script must load + show its 5 subcommands.
python pmoves/tools/jwt_rotate.py --help
# Expect: {backup, rotate, enumerate, verify, rollback}
```

If the script is missing, this runbook is out of date with the slice. See
`pmoves/docs/AGENTS/jwt_rotate_v1_LEARNINGS.md` for the slice trail.

## Phase 1: Hydrate runtime secrets from owning containers

Same as v0 -- no change. The hydrate tool replaces placeholder values in `env.shared` with
the real credentials already baked into running containers.

```bash
# 1. Supabase stack must be running (hydrate reads container env)
docker compose up -d supabase-db supabase-kong supabase-gotrue supabase-postgrest

# 2. Generate the Supabase status snapshot
make supa-status

# 3. Preview what would be hydrated (no writes)
python pmoves/tools/runtime_secrets_hydrate.py --dry-run

# 4. Apply
python pmoves/tools/runtime_secrets_hydrate.py
```

## Phase 2: BACKUP before any edit (resolves P1.1 from B850)

The v0 runbook overwrote `env.tier-supabase` with no backup. The new contract is: every
edit is preceded by a timestamped backup. The script enforces this in `rotate`; the
operator can also call `backup` standalone.

```bash
# 5. Back up env.tier-supabase (timestamped, .bak.<UTC-ISO>)
python pmoves/tools/jwt_rotate.py backup
# Expect: backup written: pmoves/env.tier-supabase.bak.2026-10-11T14-22-00Z
```

The backup file is at `pmoves/env.tier-supabase.bak.<UTC-ISO>`. It carries the SAME
permission (0600) as the live file. Rollback = `python pmoves/tools/jwt_rotate.py
rollback <backup_file>`.

## Phase 3: Rotate (mirrors pmoves-supabase generate-keys.sh)

```bash
# 6. Preview the new keys (no file writes)
python pmoves/tools/jwt_rotate.py rotate --dry-run
# Expect: JSON with JWT_SECRET, ANON_KEY, SERVICE_ROLE_KEY

# 7. Apply the rotation. The script backs up env.tier-supabase first
#    (a fresh backup even if Phase 2 ran) and writes the new values in place.
python pmoves/tools/jwt_rotate.py rotate
# Expect: 13 canonical Supabase consumers listed for recreate.
```

The `rotate` command:
1. Generates a new 30-byte base64 JWT secret (mirrors `gen_base64 30`).
2. Mints new `anon` and `service_role` HS256 JWTs (mirrors the upstream `gen_token`).
3. Updates `JWT_SECRET`, `SUPABASE_JWT_SECRET`, `ANON_KEY`, `SUPABASE_ANON_KEY`,
   `SERVICE_ROLE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_SERVICE_KEY` in
   `env.tier-supabase`.
4. Enumerates the consumers and prints a list for the operator to act on in Phase 4.

## Phase 4: Recreate ALL consumers (resolves P1.2 from B850)

The v0 recreated 4 services. The new runbook recreates 13 canonical Supabase services + every
PMOVES service that reads `env.shared` (the latter picks up the new keys on the next
`docker compose up` because the env_file is re-read on container start).

```bash
# 8. Enumerate the full consumer set (operator-actionable list)
python pmoves/tools/jwt_rotate.py enumerate
# Expect: 50+ services (13 Supabase + ~40 PMOVES). The rotate command already
# prints the Supabase subset; this command prints the full set as JSON.

# 9. Recreate the 13 canonical Supabase consumers. Compose's --no-deps
#    keeps the dependent services (Postgres, etc.) running while the
#    13 containers restart with the new env_file.
docker compose -p pmoves up -d --force-recreate --no-deps \
  supabase-kong supabase-postgrest supabase-gotrue supabase-realtime \
  supabase-storage supabase-edge-functions supabase-studio supabase-meta \
  supabase-pooler supabase-analytics supabase-imgproxy supabase-vector \
  supabase-db

# 10. Recreate the PMOVES consumers that read env.shared.
docker compose -p pmoves up -d --force-recreate --no-deps \
  pmoves-ui agent-zero botz-gateway cipher-api p7-room-orchestrator \
  hi-rag-gateway model-registry supaserch tokenism-simulator wealth-mcp
# (The exact list comes from the enumerate output. The script enumerates
#  the file's listed services; the operator runs the recreate command
#  for the services they want to roll.)
```

## Phase 5: Verify (uses GET, the correct probe method)

```bash
# 11. Read the new + old keys from the rotated env file
NEW_ANON=$(grep '^ANON_KEY=' pmoves/env.tier-supabase | cut -d= -f2-)
OLD_ANON=$(grep '^ANON_KEY=' pmoves/env.tier-supabase.bak.<ISO> | cut -d= -f2-)

# 12. Probe /rest/v1/ with both keys (GET -- the right method for a HEAD-style probe)
python pmoves/tools/jwt_rotate.py verify \
  --base-url http://127.0.0.1:8000 \
  --new-anon "$NEW_ANON" \
  --old-anon "$OLD_ANON"
# Expect: new_key.status == 200, old_key.status == 401
```

## Phase 6: Rollback (resolves P1.1 fully)

If anything breaks, the operator restores from the backup the script took in Phase 2/3.

```bash
# 13. List available backups
ls -la pmoves/env.tier-supabase.bak.* 2>/dev/null

# 14. Roll back to a specific backup
python pmoves/tools/jwt_rotate.py rollback pmoves/env.tier-supabase.bak.2026-10-11T14-22-00Z
# Expect: pre-rollback snapshot: pmoves/env.tier-supabase.bak.<NEW-ISO>
#         rolled back: pmoves/env.tier-supabase <- pmoves/env.tier-supabase.bak.<OLD-ISO>
```

The rollback command takes a snapshot of the CURRENT state BEFORE restoring from the
named backup, so a failed rollback can itself be rolled back.

## Acceptance criteria

| Check | Command | Expected |
|---|---|---|
| New anon key works | `python pmoves/tools/jwt_rotate.py verify ...` | `new_key.status == 200` |
| Old anon key rejected | same | `old_key.status == 401` |
| `/api/health` healthy | `curl -s http://127.0.0.1:<ui-port>/api/health` | `database: healthy` |
| All 13 Supabase containers up | `docker compose -p pmoves ps supabase-*` | all `running` |
| Hydrate dry-run | `python pmoves/tools/runtime_secrets_hydrate.py --dry-run` | 0 placeholders |
| All consumers enumerate | `python pmoves/tools/jwt_rotate.py enumerate \| jq length` | `>= 50` (13 Supabase + ~40 PMOVES) |
| Backup exists | `ls pmoves/env.tier-supabase.bak.*` | at least 1 file |

## Cross-fork context (the "map out to one" piece)

This runbook is one of three JWT surfaces in the PMOVES mesh. They do NOT share a
JWT secret; each has its own scope. The "map to one" is the PATTERN (backup +
enumerate + verify), not the SECRET.

| Surface | Repo | JWT scope | Where the secret lives | This runbook covers? |
|---|---|---|---|---|
| **PMOVES-AI** (PostgREST/Supabase) | `POWERFULMOVES/PMOVES.AI` | Supabase PostgREST | `pmoves/env.tier-supabase` | **YES -- this runbook** |
| **PMOVES-BoTZ** (Mavis-gateway) | `POWERFULMOVES/PMOVES-BoTZ` | Mavis gateway JWT | `core/docker-compose/env.shared` | NO -- separate scope, see BoTZ docs |
| **PMOVES-Archon** (its own auth) | `POWERFULMOVES/PMOVES-Archon` | None -- does not use Supabase JWTs | n/a | n/a |
| **PMOVES-supabase** (canonical tools) | `POWERFULMOVES/PMOVES-supabase` (submodule) | Submodule of PMOVES-AI; canonical `generate-keys.sh` lives here | the canonical algorithm | n/a -- the algorithm source |

`grep -r JWT_SECRET` confirms the BoTZ and Archon distinction:
- BoTZ: 8 hits, all in `core/docker-compose/env.shared` and docs. BoTZ's JWT is the
  Mavis-gateway JWT; it does not gate PostgREST.
- Archon: 0 hits. Archon does not use Supabase JWTs at all.
- pmoves-supabase: 207 hits. The canonical Supabase self-hosted algorithm.

**Conflict check**: rotating this runbook's secret does NOT affect BoTZ or Archon.
A BoTZ rotation is a separate operator task in BoTZ's docs.

## Warnings

- Rotation invalidates all existing sessions and tokens. Plan a maintenance window.
- The new keys are printed to stdout. The script does NOT write the new values to
  `/tmp` files. If you redirect the output, use `umask 077` and `mktemp`.
- The new service_role key grants full PostgREST access. Treat it like the
  database root password.
- Do not run `rotate` more than once in the same second -- the backup dedup
  (`.1`, `.2`, ...) handles this, but the operator should still avoid it.

## Provenance

- Method: `pmoves-supabase/docker/utils/generate-keys.sh` (upstream Supabase
  self-hosted, Apache 2.0, Inder Singh). The PMOVES wrapper is original.
- PR that supersedes the v0 draft: PR TBD on branch
  `fix/5090-jwt-rotation-runbook-rollback`.
- B850 review trail: PR #3213 thread, 2026-09-28 15:02 + 15:36 UTC.
- AGNOTE row: `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (this slice).
- LEARNINGS file: `pmoves/docs/AGENTS/jwt_rotate_v1_LEARNINGS.md`.
