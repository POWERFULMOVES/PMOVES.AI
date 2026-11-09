# Supabase image currency — kong + studio (L2, low-risk slice)

**Node:** z890 · **Date:** 2026-08-19 · **Lane:** L2 from the 2026-08-18 lane board
**Change class:** `compose:` (image pins only)

---

## Drift, measured against the submodule (not assumed)

Compared `pmoves/docker-compose.yml` against upstream
`PMOVES-supabase/docker/docker-compose.yml` + `docker-compose.logs.yml`:

| service | upstream | pmoves | verdict |
|---|---|---|---|
| supabase-kong | `kong/kong:3.9.3` | `kong/kong:3.9.1` | **bump (this PR)** |
| supabase-studio | `2026.08.03-sha-022b374` | `2026.06.03-sha-0bca601` | **bump (this PR)** |
| supabase-db | `postgres:17.6.1.136` | `postgres:17.6.1.108` | deferred — data tier |
| supabase-analytics | `logflare:1.43.1` | `logflare:1.30.3` | deferred — 13 minor versions |
| supabase-vector | `vector:0.53.0-alpine` | `vector:0.28.1-alpine` | deferred — ~25 releases |
| supabase-gotrue | `gotrue:v2.189.0` | `gotrue:v2.191.0` | **DO NOT TOUCH — ours is NEWER** |
| rest / realtime / storage / imgproxy / meta / edge-functions / pooler | — | — | already match |

### The gotrue trap

PMOVES runs **v2.191.0**; upstream pins **v2.189.0**. "Syncing to upstream" would be a
**downgrade of the auth service**. Any bulk-bump tooling that assumes upstream-is-newer
would silently regress it. Left alone deliberately.

## Why only kong + studio in this slice

Split by blast radius, not convenience:

- **kong 3.9.1 -> 3.9.3** — patch. Kong is the REST gateway; it was crash-looping until
  2026-08-18 (#2593) and is now `healthy, restarts=0` through a host restart. A patch bump
  is low risk and this is the component we most recently proved out.
- **studio** — the dashboard UI. No data path, no other service depends on it.

Deferred, each needing its own window and verification:

- **db `17.6.1.108 -> .136`** — the data tier. A postgres image bump on a live volume is
  not a "currency" change; it needs a backup/verify window of its own.
- **analytics/logflare `1.30.3 -> 1.43.1`** — 13 minor versions. Logflare owns the
  `_analytics` schema inside the `_supabase` database; a jump that size can carry schema
  migrations. Verify against a snapshot first.
- **vector `0.28.1 -> 0.53.0`** — ~25 releases. NOTE: `vector.yml` is **live-mounted from
  the submodule**, so the config is already written for upstream's newer vector while the
  binary is old. Static analysis of that config shows only long-stable component types
  (`docker_logs`, `remap`, `route`, `filter`), which is why it runs healthy despite the
  gap — so this is **currency/CVE hygiene, not a live breakage**. Bump it deliberately,
  not as a drive-by.

## Verification for this slice

```bash
make -C pmoves compose-split           # regenerate overlays from the canonical file
make -C pmoves up-supabase
docker ps --filter name=supabase-kong --format '{{.Status}}'     # healthy, low restart count
docker ps --filter name=supabase-studio --format '{{.Status}}'
# REST still routes (the thing #2593 fixed):
#   401 without an apikey, 403 with anon on the restricted root
```

Rollback is a one-line revert of each pin plus `up-supabase`.

## Related

- Lane board: `AGNOTE4482PHI.t1.md` (2026-08-18, L2)
- Kong router-flavor fix that made the gateway boot: #2593
- Build-lineage audit establishing that all Supabase images are pulled upstream (zero
  `build:` stanzas), so a pin bump is a genuine upstream upgrade rather than a local rebuild
