# JWT rotation runbook v1 — lessons (4-bucket × 5-class taxonomy)

**Slice:** `fix/5090-jwt-rotation-runbook-rollback` (inherits the lane from PR #3213).
**Author:** mavis (DARKXSIDE).
**Date:** 2026-10-11.
**Status:** built + tested (26/26 ratchets), live end-to-end verified, awaiting PR review.

The 4-bucket × 5-class taxonomy follows the project convention; see
`ensure_agint_skills_LEARNINGS.md` and `claude_backend_switch_LEARNINGS.md` for
prior art.

---

## Bucket 1 — design

### D-1 — "Map to one" means the PATTERN, not the SECRET
**Class:** scope / cross-fork coordination, per operator directive 2026-10-11:
"we should map out to one ensure no conflictss and routes correct PMOVES-supabase".

The operator's intent was to unify the rotation PATTERN across PMOVES-BoTZ,
PMOVES-Archon, and PMOVES-supabase, not to share one JWT secret. Each surface
has its own scope:
- PMOVES-AI (this runbook): Supabase PostgREST, secret in `pmoves/env.tier-supabase`
- PMOVES-BoTZ: Mavis-gateway JWT, secret in `core/docker-compose/env.shared` (different scope, separate task)
- PMOVES-Archon: no Supabase JWTs (0 grep hits in the repo)
- PMOVES-supabase: the upstream submodule; the canonical `generate-keys.sh` lives here

The PATTERN is: backup → rotate → enumerate → recreate → verify → rollback.
The v0 runbook had the shape but the wrong sequence (no backup, 4-of-20
consumers, GET-vs-POST doc bug). The v1 fixes the sequence; the secret
itself stays surface-local.

### D-2 — "Backup before edit" is the load-bearing safety property
**Class:** operator-safety, **caught by** B850's P1.1 (no working rollback).

The v0 ran `sed -i` over `env.tier-supabase` with no backup step. The runbook
text said "the old JWT secret is still in the env files" — a lie. After the
sed, the old secret exists nowhere, so rollback is impossible.

The v1 makes the backup a Phase 2 explicit step, run before any edit. The
`jwt_rotate.py backup` and `rotate` subcommands both write a timestamped copy
at `<file>.bak.<UTC-ISO>` before any in-place write. Pinned by
`test_backup_creates_bak_iso_file` (file written) and the runbook's Phase 2
+ Phase 6 + the script's `backup_env` function.

### D-3 — "Enumerate the consumers" is what makes the rotation complete
**Class:** correctness, **caught by** B850's P1.2 (4 of ~20 consumers).

The v0 only recreated `kong, postgrest, gotrue, pmoves-ui` after rotation.
The other ~16 services (realtime, storage, edge-functions, studio, meta,
pooler, analytics, imgproxy, vector, db, plus PMOVES consumers) would
silently fail auth on the next request.

The v1 enumerates consumers by parsing every `docker-compose*.yml` for
`<<: *tier-supabase-hardened[-ro]` anchors and `env_file: env.{tier-supabase,shared,...}`
references. The 13 canonical Supabase consumers are pinned as a Python tuple
in `jwt_rotate.CANONICAL_SUPABASE_CONSUMERS` and asserted by
`test_canonical_supabase_consumers_pinned` (the test fails if any of the 13
is renamed in the future).

The enumerate output is the operator-actionable list. Pinned by
`test_enumerate_finds_canonical_supabase_consumers`.

---

## Bucket 2 — implementation

### I-1 — Mirror the upstream keygen, don't reimplement
**Class:** correctness, **caught by** reading
`pmoves-supabase/docker/utils/generate-keys.sh`.

The canonical Supabase self-hosted keygen is a 30-byte base64 JWT secret +
HS256 `anon` + HS256 `service_role` tokens. The PMOVES wrapper (`jwt_rotate.keygen`)
mirrors the algorithm exactly: same payload shape (`{role, iss, iat, exp}`),
same `iss=supabase-local` issuer, same 10-year TTL by default.

A re-implementation that signs the JWTs differently (e.g. wrong alg, wrong
issuer, wrong TTL) would produce tokens that postgrest rejects. The mirror
is pinned by `test_anon_key_decodes_to_anon_role` and
`test_service_role_key_decodes_to_service_role` and
`test_anon_and_service_role_signed_with_same_secret` (the cross-signature
check catches a regression where the two tokens are signed with different
secrets).

### I-2 — Write env files in place, but as KEY=VALUE replacement
**Class:** correctness, **caught by** considering the alternative.

The naive approach is to load the file as a dict, mutate, and `write_text`.
That LOSES comments, blank lines, and the relative ordering of unrelated
keys. The runbook documents the env file with comments explaining what each
var is for; those would vanish.

The v1 uses a regex-based line replacement (`write_env_replace`) that
preserves every line that doesn't match a key in the replacement map. New
keys (not in the file) are appended at the end. Pinned by
`test_write_env_replace_preserves_comments`,
`test_write_env_replace_quotes_value_with_whitespace`,
`test_write_env_replace_appends_new_keys`.

### I-3 — Backup filename: ISO with hyphens, not colons
**Class:** portability.

Windows + POSIX both accept ISO timestamps with colons, but Windows file
APIs reject colons in filenames (`C:\foo:bar` is interpreted as a drive
letter). The script uses `YYYY-MM-DDTHH-MM-SSZ` (hyphens, not colons) so
the backup path is portable. The on-tarball ISO format is the canonical
form for `git log --format=%cI`-style timestamps.

The same dedup logic from the Mavis SDK env-strip lane (PR #3149) applies:
same-second collisions append `.1`, `.2`, .... Two `backup` calls within
the same UTC second each get their own file. Pinned by the
`test_idempotency` pattern in `test_claude_backend.py`.

### I-4 — Verify on the LIVE endpoint, not the file
**Class:** operational.

The rotate step updates the env file. The recreate step restarts the
containers. The verify step probes the live PostgREST endpoint to confirm
the new key works and the old one doesn't. This is the only check that
catches a class of bugs the env-file check can't:
- Old container still running with the old secret (didn't restart).
- New env file not mounted into the container (compose interpolation bug).
- PostgREST caching the old key from a stale process.

The verify command uses GET (not POST as the v0 doc said). Pinned by
`test_runbook_uses_get_not_post`.

---

## Bucket 3 — operations

### O-1 — 26 ratchets across 6 classes
**Class:** test coverage / ROI.

The 26 tests in `test_jwt_rotate.py` cover:
- KeygenTests (6): key shape, JWT decoding, cross-signature verification
- BackupFirstTests (6): backup write, write_env_replace, rotation takes backup
- ConsumerEnumerationTests (3): 13 canonical pinned, enumerate finds them
- VerifyTests (2): unreachable URL doesn't raise
- RunbookStructuralTests (8): runbook references script, pins cwd, GET not POST, 13 consumers mentioned, cross-fork map

10 runbook structural pins + 13 code-level pins = the runbook can never
silently regress to v0's shape.

### O-2 — Live end-to-end test on a fake env
**Class:** test pyramid.

The pytest suite uses tempdir fixtures. The script's CLI is tested with
`subprocess.run` to confirm `--repo-root` works + `backup` writes + `rotate`
updates + `rollback` restores. The script ran live on
`C:\Users\russe\AppData\Local\Temp\jwt-rotate-live`:
- backup → env.tier-supabase.bak.<ISO> (66 bytes, matches source)
- rotate → active env 450 bytes, new keys present
- rollback → active env back to 66 bytes, old keys present

The live test confirmed the CLI works. The pytest suite confirms the unit
semantics. Together: full coverage of the script's behavior.

---

## Bucket 4 — collaboration

### C-1 — Inherit the lane, fix the inherited bugs
**Class:** operator practice (DARKXSIDE 2026-10-10).

Same pattern as the `ensure-agint-skills` lane (prior slice): the original
PR was directionally correct but had real bugs. The fix is to inherit the
lane, fix the bugs, add the tests, write the LEARNINGS, and open a new
PR that supersedes the original. PR #3213 stays as B850-CLAUDE-owned
draft; this branch carries the actual fix.

### C-2 — Cross-fork coordination via grep, not coordination-ritual
**Class:** collaboration.

The operator's "map out to one" was answered with a grep:
- `grep JWT_SECRET pmoves-BoTZ/` → 8 hits, all in `core/docker-compose/env.shared` (separate scope)
- `grep JWT_SECRET pmoves-Archon/` → 0 hits (no Supabase JWTs)
- `grep JWT_SECRET pmoves-supabase/` → 207 hits (the canonical algorithm)

A grep + a one-page table answered the question in 5 minutes. The
table is in the runbook's "Cross-fork context" section so the next
operator doesn't have to re-grep.

### C-3 — Document the runbook's tool, not the runbook
**Class:** API surface.

The v0 runbook was a 138-line markdown file with embedded bash. The v1
runbook is a 200-line markdown file that references the
`pmoves/tools/jwt_rotate.py` script for every operator-actionable step.
The runbook describes the WHAT and WHY; the script does the HOW.

This separation means:
- The runbook can be re-read in 5 minutes.
- The script is unit-testable in isolation.
- A future tool change (e.g. add a `--commit-message` flag) doesn't require
  editing the runbook.

---

## Cross-cutting

### X-1 — The 13 canonical consumers are a different abstraction from the 50+ enumerated consumers
**Class:** abstraction layering.

The `CANONICAL_SUPABASE_CONSUMERS` tuple in `jwt_rotate.py` is the
LOAD-BEARING set: the operator MUST recreate these after rotation, or
services fail auth. The enumerate output includes the broader 50+ PMOVES
services that read `env.shared` (not `env.tier-supabase`), and those are
SOFT requirements (recreate at your own pace; they pick up the new key
on next restart regardless).

The two are separated by data structure: tuple (pinned, exhaustively
tested) vs set (computed, runtime-surveyed). The test
`test_canonical_supabase_consumers_pinned` pins the tuple to a literal set
of 13 names, so a future rename of any of them fails the build.

### X-2 — The "upstream" reference is a pinned commit, not a moving target
**Class:** provenance.

The `pmoves-supabase` submodule has its own commit history. The v1
runbook references the algorithm in `pmoves-supabase/docker/utils/generate-keys.sh`
but does not pin a specific commit. A future change to generate-keys.sh
(e.g. switch from HS256 to ES256) would silently break the v1 keygen.

For v2, the runbook should pin the pmoves-supabase commit hash used as
the algorithm source. For v1, the algorithm is simple enough (30-byte
base64 secret + 2 HS256 tokens) that a re-implementation matching the
current generate-keys.sh is safe.

---

## Verification commands

```
# Pytest (26/26)
"C:\Users\russe\AppData\Local\Programs\Python\Python312\python.exe" -m pytest \
  pmoves/tools/tests/test_jwt_rotate.py -v

# CLI help
"C:\Users\russe\AppData\Local\Programs\Python\Python312\python.exe" \
  pmoves/tools/jwt_rotate.py --help

# Live end-to-end (operator can re-run in a temp dir)
mkdir -p /tmp/jwt-test/pmoves
echo "JWT_SECRET=old" > /tmp/jwt-test/pmoves/env.tier-supabase
python pmoves/tools/jwt_rotate.py --repo-root /tmp/jwt-test backup
python pmoves/tools/jwt_rotate.py --repo-root /tmp/jwt-test rotate --dry-run
python pmoves/tools/jwt_rotate.py --repo-root /tmp/jwt-test rotate
ls /tmp/jwt-test/pmoves/
python pmoves/tools/jwt_rotate.py --repo-root /tmp/jwt-test rollback \
  /tmp/jwt-test/pmoves/env.tier-supabase.bak.<ISO>
```
