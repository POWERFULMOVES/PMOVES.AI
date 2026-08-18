# Supabase Kong crash-loop (3,924 restarts) — two independent config faults

**Node:** z890 · **Found:** 2026-08-18 while enabling self-hosted Supabase MCP access
**Impact:** Kong is the REST gateway on `:8000`. While it is down, the self-hosted
`pmoves-supabase` MCP (PostgREST via Kong) is non-functional, as is every
`/rest/v1`, `/auth/v1`, `/storage/v1` route.

## Fault 1 — `DASHBOARD_PASSWORD` never existed (FIXED)

Kong templates `PMOVES-supabase/docker/volumes/api/kong.yml` -> `/usr/local/kong/kong.yml`,
substituting `password: '$DASHBOARD_PASSWORD'`. Kong then refused the config:

```
in 'basicauth_credentials': in 'password': length must be at least 1
```

Traced end to end: the key was **absent from `env.shared` and every tier env file**, so
compose passed `DASHBOARD_PASSWORD=` (empty). The CHIT vault held only 6 labels and this
was not one of them, so `secrets-funnel` could not materialise it — **and it was not even
listed in the funnel's `Missing secrets (non-fatal)` warning**, so nothing ever flagged it.
That silence is why this ran for **3,924 restarts** unnoticed.

Fixed via the Known Road `make -C pmoves secrets-rotate KEY=DASHBOARD_PASSWORD LEN=32`
(mints a value when none is supplied), then `make -C pmoves up-supabase`. Verified: the
container now receives a non-empty value and Kong got past basic-auth validation.

> **Trap for the next agent:** `secrets-rotate` chains into `secrets-funnel`, which
> **hangs** at its `secrets-audit` / `tooling-audit` steps (6-7 of 7). Steps 1-5 —
> including the rotation itself and `secrets-funnel-sync` — complete first. The hang is
> downstream of the write, so the rotation lands even if you interrupt. Do not conclude
> the rotate failed because the make never returned. Track the audit hang separately.

## Fault 2 — declarative config uses expressions-router syntax the container cannot parse

With the password fixed, Kong still refused to boot:

```
in 'services': - in entry 8 of 'services': in 'routes': - in entry 1 of 'routes':
  in 'expression': unknown field
  in '@entity': - must set one of 'methods','hosts','headers','paths','snis' when 'protocols' is 'https'
```

Entry 8 is `rest-v1-openapi` -> route `rest-v1-openapi-root`:

```yaml
routes:
  - name: rest-v1-openapi-root
    strip_path: true
    expression: 'http.path == "/rest/v1/"'
```

`expression:` is Kong's **expressions router** syntax. It requires
`KONG_ROUTER_FLAVOR=expressions`; under the default traditional router it is an unknown
field and the **entire declarative file fails to parse**, so Kong never starts — one route
takes down all 21 services.

**This is upstream drift, not a PMOVES defect.** The route arrives from upstream Supabase
commit `9777f051d6 feat(self-hosted): restrict rest root anon (#45462)`, and upstream's own
`PMOVES-supabase/docker/docker-compose.yml:95` sets `KONG_ROUTER_FLAVOR: expressions`
alongside it. PMOVES defines its **own** `supabase-kong` service in
`pmoves/docker-compose.yml` and **did not carry that env var over**, so the config file
(tracked by the submodule, updated by upstream) outran the service definition.

Counts confirm the route is the outlier, not the norm: **1 route uses `expression`, 20 use
`paths`.**

**Fix:** add `KONG_ROUTER_FLAVOR=expressions` to the PMOVES `supabase-kong` environment,
matching upstream.

### Why not rewrite the route to `paths:` instead

`http.path == "/rest/v1/"` is an **exact** match; `paths: ["/rest/v1/"]` is a **prefix**
match. Swapping them would apply the restricted-anon treatment to *all* REST traffic
rather than only the OpenAPI root — a silent auth-scope change. An anchored regex
(`~/rest/v1/$`) would be equivalent, but diverging from upstream on a security-relevant
route invites the next upstream sync to re-break it. Matching upstream's env var is the
smaller, more durable change.

### Related drift worth tracking (NOT changed here)

PMOVES pins `kong/kong:3.9.1`; upstream now ships `3.9.3`. The expressions router exists in
both, so this is not the boot failure — but the version gap is how the config/definition
skew appeared in the first place. Bump deliberately, with its own verification.

## Verify

```bash
make -C pmoves up-supabase
docker inspect pmoves-supabase-kong-1 --format '{{.State.Status}} {{.RestartCount}}'   # running, low
docker logs --tail 5 pmoves-supabase-kong-1                                            # no 'error parsing declarative config'
```
Then confirm the self-hosted MCP path: `/rest/v1` answers through `:8000`.

---

## Fault 3 — new-format API keys aliased to the legacy JWTs (OPERATOR FIX REQUIRED)

With faults 1 and 2 cleared, Kong reached a third refusal:

```
in 'keyauth_credentials':
  - in entry 2 of 'keyauth_credentials': uniqueness violation:
    'keyauth_credentials' entity with key set to 'eyJ...' already declared
```

Upstream's template now declares **two** key slots per consumer — the legacy JWT plus the
newer opaque API key:

```yaml
consumer=anon          keyauth=[{key: $SUPABASE_ANON_KEY},   {key: $SUPABASE_PUBLISHABLE_KEY}]
consumer=service_role  keyauth=[{key: $SUPABASE_SERVICE_KEY},{key: $SUPABASE_SECRET_KEY}]
```

Fingerprinted from the live container (values never printed):

| Variable | sha256[:12] | len |
|---|---|---|
| `SUPABASE_ANON_KEY` | `5a4af33d310d` | 176 |
| `SUPABASE_PUBLISHABLE_KEY` | **`5a4af33d310d`** | 176 |
| `SUPABASE_SERVICE_KEY` | `a68ca943db03` | 187 |
| `SUPABASE_SECRET_KEY` | **`a68ca943db03`** | 187 |

The new keys are **aliased to the legacy JWTs**, so each consumer declares the *same* key
twice. Kong requires `keyauth_credentials.key` to be globally unique, so it rejects the
whole file.

**Upstream's intended state is EMPTY.** `PMOVES-supabase/docker/.env.example:47,49` ships
`SUPABASE_PUBLISHABLE_KEY=` / `SUPABASE_SECRET_KEY=` with no value, and the entrypoint
strips the resulting blank entries before Kong ever sees them:

```sh
# kong-entrypoint.sh:47
sed -i '/^[[:space:]]*- key:[[:space:]]*$/d' "$KONG_DECLARATIVE_CONFIG"
```

Empty -> stripped -> no duplicate. Populated-with-a-duplicate -> not stripped -> refusal.
`pmoves/env.shared.example:177` also ships it empty, so **the repo is correct and the live
`env.shared` has drifted** — someone populated the new-format vars with the legacy values.

### The fix (operator — `env.shared` is zero-access under damage-control)

Clear both keys, then re-funnel and recreate:

```bash
# set SUPABASE_PUBLISHABLE_KEY= and SUPABASE_SECRET_KEY= (empty) in env.shared
make -C pmoves secrets-funnel
make -C pmoves up-supabase
```

Only populate them if you have genuinely migrated to Supabase's opaque key model, in which
case they must be **real `sb_publishable_…` / `sb_secret_…` values** — never copies of the
JWTs. Note the entrypoint keys its asymmetric-auth expressions off these vars
(`kong-entrypoint.sh:15-21`), so a bogus value changes auth behaviour, it does not merely
sit unused.

### Why not patch the template instead

Deleting the second keyauth entries would diverge the fork from upstream on an
**auth-relevant** file, and the next submodule sync would silently re-break it. The
entrypoint already implements the intended escape hatch; the data is what is wrong.

## Status

| Fault | State |
|---|---|
| 1 — `DASHBOARD_PASSWORD` empty | **FIXED** (rotated + funnelled; container receives a non-empty value) |
| 2 — expressions-router syntax unparseable | **FIXED** (`KONG_ROUTER_FLAVOR=expressions`; error class gone from logs) |
| 3 — new API keys aliased to legacy JWTs | **OPEN** — needs the `env.shared` edit above |

Kong will keep crash-looping until fault 3 is cleared. The self-hosted `pmoves-supabase`
MCP stays non-functional until then; the cloud `supabase@claude-plugins-official` plugin is
**not** the substitute — it targets `mcp.supabase.com`, not this stack.
