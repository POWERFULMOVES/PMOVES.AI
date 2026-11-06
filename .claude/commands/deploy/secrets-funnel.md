Regenerate all tier env files from CHIT source through the canonical secrets pipeline.

Tier env files (`env.tier-*`, `.env.generated`, `env.shared.generated`) are generated. Never edit them directly. Which make target regenerates them depends on where this node's CHIT bundle came from, so decide that first.

## Step 0 — Decide which funnel this node uses

```bash
make -C pmoves chit-provenance-check
```

Read-only: it never pulls or writes and prints key names only, so it is safe in an agent transcript. It reports whether the bundle at `CHIT_EXPORT_PATH` is CI-pulled (a `<bundle>.provenance` stamp with `source=ci`, written by `secrets-pull`) and whether a pullable producer artifact is still alive.

| Bundle state | Run | Why |
|---|---|---|
| Local export, or no bundle (Pattern A producer node) | `make -C pmoves secrets-funnel` | Re-exports `env.shared` into the bundle, then materializes tiers |
| CI-pulled, producer artifact still alive (Pattern B consumer) | `make -C pmoves secrets-funnel-from-prod` | `secrets-pull` + `secrets-funnel-sync-from-bundle`, then refreshes `local.env` and force-hydrates `env.shared` |
| CI-pulled, artifact expired (Pattern B consumer) | `make -C pmoves secrets-funnel-sync-from-bundle` | Regenerates tiers from the bundle already installed; skips `chit-export` |

**Do not run `secrets-funnel` on a node that holds a CI-pulled bundle.** Its `secrets-funnel-sync` step depends on `chit-export`, and `chit-export` writes the same path `secrets-pull` installs to. A local export is a strict subset of the CI bundle: prod-only keys never live in `env.shared`. The guard in `pmoves/mk/codex.mk` (`chit-export`, via `scripts/chit_export_guarded.sh`) now refuses to overwrite a CI-pulled bundle, so the plain funnel fails on such a node rather than silently dropping keys. `CHIT_EXPORT_FORCE=1` overrides that guard; do not set it to make the funnel pass.

The producer workflow `sync-secrets-local.yml` uploads with a one-day retention. `secrets-pull` only works if a producer ran within that window. Past it, use `secrets-funnel-sync-from-bundle` against the bundle you already have, or ask the operator to dispatch a producer run.

Full pattern: `pmoves/docs/operations/SECRETS_DISTRIBUTION_PATTERNS.md` § Pattern B, including its warning "Do not run `make -C pmoves secrets-funnel` on a node that just pulled a bundle."

## Pipeline Order of Operations (`secrets-funnel`, Pattern A)

The recipe in `pmoves/mk/codex.mk`, in order:

```
1. env-shared-repair          — Collapse raw multi-line PEM/SSH values that break compose env-file parsing
2. secrets-local-hydrate      — Overlay real API keys from local.env into env.shared (FORCE=1 overwrites stale)
3. secrets-runtime-hydrate    — Pull runtime-emitted labels (Supabase/container) into env.shared
4. secrets-ensure-generated   — Recover live secrets from running containers, then mint only what is absent
                                (must precede the sync: the export seals env.shared into the bundle)
5. secrets-derive-nats-url    — Re-derive NATS_URL from the NATS user/password (before the bundle is sealed)
6. secrets-funnel-sync        — Prerequisites chit-manifest-sync, then chit-export (guarded);
                                then secrets_sync.py generate writes the tier env files
7. secrets-nats-promote       — Mirror env.shared's NATS keys into each env.tier-* that declares them
8. credential_urlencoder.py   — URL-encode credentials embedded in URLs (must run after the sync)
9. secrets-audit              — Secrets hardening audit (CHIT paths, sync workflow, export hygiene)
10. tooling-audit             — Tools/scripts overlap audit
11. supabase-boot-user        — Only when SECRETS_FUNNEL_BOOT_USER=1
```

## Implementation

Execute the following steps:

1. **Run Step 0**, then the funnel target it selects:
   ```bash
   make -C pmoves chit-provenance-check
   make -C pmoves secrets-funnel                     # Pattern A only
   ```

2. **Verify tier files were generated:**
   ```bash
   ls -la pmoves/env.tier-* pmoves/.env.generated pmoves/env.shared.generated 2>/dev/null
   ```

   You should see files for: `env.tier-agent`, `env.tier-api`, `env.tier-data`, `env.tier-llm`, `env.tier-media`, `env.tier-worker`.

3. **Populate the UI tier.** No funnel variant writes `env.tier-ui`:
   ```bash
   make -C pmoves supa-env-fix-tier-ui
   ```
   It fills the empty Supabase key fields in `env.tier-ui` from `env.tier-supabase`. When skipped, pmoves-ui `/api/health` returns 503 with `database: Unauthorized` (measured on node 5090, 2026-11-06). Recreate the UI afterwards from a shell that does not export those keys; see `pmoves/docs/operations/COMPLETE_BRING_UP_RUNBOOK.md` Phase 3 step 6.

4. **If secrets-funnel fails on a missing CHIT bundle (Pattern A, first run):**
   ```bash
   make -C pmoves chit-export
   make -C pmoves secrets-funnel
   ```
   If `chit-export` refuses because the bundle is CI-pulled, this node is Pattern B. Go back to Step 0.

5. **If the funnel warns about missing secrets:**
   - Non-fatal warnings (e.g., `SERVICE_PASSWORD_ADMIN`) mean those keys aren't in your CHIT bundle yet
   - Pattern A: add them to `env.shared` first, then re-run the funnel
   - Pattern B: they must arrive in the CI bundle; do not add prod-only keys locally
   - Fatal errors mean required keys for production services are missing — fix before deploying

## When to Run This

- **Before any `make up-*` target** — ensures services get fresh env
- **After editing `.example` files** — propagates new keys through the pipeline
- **After `git pull`** — picks up new manifest entries from upstream
- **After rotating secrets** — updates all tier files from single source

## What NOT to Do

- Never edit `env.tier-*` files directly (header says "Auto-generated by pmoves.tools.secrets_sync")
- Never run `docker compose up` directly (bypasses COMPOSE_ENV_FILES injection)
- Never copy secrets between tier files manually (use the manifest's `targets` to route keys)
- Never run `secrets-funnel` on a node holding a CI-pulled bundle (see Step 0)

## Notes

- The CHIT bundle lives at `CHIT_EXPORT_PATH` (user-scoped, outside the repo): `%APPDATA%\pmoves\chit\env.cgp.json` on Windows, `${XDG_CONFIG_HOME:-~/.config}/pmoves/chit/env.cgp.json` elsewhere
- `--allow-missing` is passed by default (`SECRETS_ALLOW_MISSING ?= 1` in `pmoves/mk/codex.mk`) so the funnel doesn't fail on optional keys
- The manifest at `pmoves/chit/secrets_manifest_v2.yaml` is the source of truth for key routing
