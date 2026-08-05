# Edge runbook — Traefik + sso-auth

Operator reference for `up-edge` / `down-edge` / `edge-health` / `edge-preflight`.

The edge is what makes every app **one app**: Traefik terminates TLS, calls `sso-auth`
to verify the session, and injects `Remote-User` into the upstream request so the app
does not ask for a second login.

> **Status 2026-08-05:** the overlays (`docker-compose.traefik.yml`,
> `docker-compose.sso.yml`) have existed since #2221, but no make target started them,
> so the edge had **never run**. These targets close that gap. Read "Known gaps" before
> expecting single sign-on to work end to end.

## Targets

| Target | Does |
|---|---|
| `make -C pmoves edge-preflight` | Checks prerequisites. Starts nothing. Safe any time. |
| `make -C pmoves up-edge` | Runs preflight, then starts Traefik + sso-auth. |
| `make -C pmoves down-edge` | Stops both. |
| `make -C pmoves edge-health` | Reports containers, published ports, and which routers actually carry forward-auth. |

Both overlays start **together** deliberately: the `auth.pmoves.ai` router is declared
on the Traefik container but points at `sso-auth@docker`, so Traefik alone is an edge
whose own login route 404s.

## Prerequisites

### Secrets

Sourced through the CHIT secrets pipeline — never hand-edit `env.shared`.

| Variable | Needed by | If missing |
|---|---|---|
| `CLOUDFLARE_DNS_API_TOKEN` | Traefik ACME DNS-01 (`certresolver=cf`) | Traefik starts, **certificate issuance fails**; browsers get a TLS error |
| `SSO_FORWARD_AUTH_SECRET` | `sso-auth` + apps validating proof-of-proxy | Header trust never engages; apps fall back to their own login |
| `SUPABASE_JWT_SECRET` / `JWT_SECRET` | `sso-auth` session verification | `/auth/verify` cannot validate sessions |
| `ACME_EMAIL` | ACME registration | Defaults to `ops@pmoves.ai` |

### Networks

`docker-compose.sso.yml` declares three **external** networks. Compose fails with
network-not-found before starting anything if any is missing.

- `pmoves_external` — `internal: false`. **Created automatically** by `edge-preflight`.
- `pmoves_app`, `pmoves_api` — **must already exist**; bring the core stack up first
  (`make -C pmoves up`).

`edge-preflight` deliberately does **not** create `pmoves_app` / `pmoves_api`. Both are
`internal: true` in the core stack (`docker-compose.yml:5364,5373`). Creating them here
with a plain bridge would make them **non-internal**, and the core stack would then
attach to a network that no longer blocks egress — turning a loud error into a quiet
security regression.

### Ports

Traefik publishes **80 and 443 directly on the host**. It owns them; nothing else may.

`edge-preflight` probes them OS-aware — `ss` where available, else `netstat`, matching
both `LISTEN` (Linux/BSD) and `LISTENING` (Windows). If neither tool exists it warns and
continues rather than blocking a legitimate bring-up.

The probe is **skipped** when a `pmoves-traefik` container is already running, so
`up-edge` stays idempotent — a rerun to pick up config changes must not be blocked by
its own listener.

### Config

`config/traefik/dynamic.yml` must exist. It defines `pmoves-forward-auth` (the
ForwardAuth middleware) and `pmoves-auth-redirect` (401 → login). Preflight fails
without it, because Traefik would start and silently protect nothing.

## Run

```bash
make -C pmoves edge-preflight     # optional; up-edge runs it anyway
make -C pmoves up-edge
make -C pmoves edge-health
```

Healthy `edge-health` shows both containers up, Traefik holding 80/443 with a non-empty
binding list, and at least one router under "Routers attached to pmoves-forward-auth".

An **empty `[]` binding list** means the publish silently no-oped. On Windows that is
the same-subnet ghost-adapter pattern — see
[`SAME_SUBNET_GHOST_PATTERN.md`](./SAME_SUBNET_GHOST_PATTERN.md).

## Rollback

```bash
make -C pmoves down-edge
```

Stops both containers and releases 80/443. Apps keep working on their own auth and
host ports; nothing else depends on the edge running. The ACME certificate cache
survives in the `traefik-acme` volume, so a later `up-edge` does not re-request certs
and will not hit Let's Encrypt rate limits.

To roll back further, `docker volume rm <project>_traefik-acme` — but only if
certificates are actually the problem, since it forces fresh issuance.

## Known gaps

Bringing the edge up is necessary but **not sufficient** for single sign-on.

1. **Stale containers carry no middleware labels.** `docker-compose.external.yml:45,85,192`
   set `pmoves-forward-auth@file` on the health/wealth/notebook routers, but containers
   created before those labels landed are still running without them (`pmoves-firefly`
   created 2026-07-21, `pmoves-wger*` 2026-07-25; #2221 merged 2026-07-25). **Recreate
   the labeled services after `up-edge`** or Traefik comes up and still protects nothing.
   `edge-health` calls this out explicitly.
2. **Most services have no edge presence.** Only `persona`, `chit-tour`, `external` and
   `sso` carry `traefik.enable`. n8n, Supabase Studio, MinIO, Grafana, Neo4j, RustDesk
   and TTS Studio are reachable by host port and bypass the edge entirely.
3. **Apps with their own login double-prompt** if put behind forward-auth without
   disabling native auth. The durable pattern is the one wger already uses: **no host
   `ports:`, reachable only through Traefik** — which is also what stops `Remote-User`
   being spoofed by connecting directly.
4. **Jellyfin is deliberately not behind forward-auth** (`external.yml:210-212`) — it
   uses its own OIDC plugin, because forward-auth would guard the `/oidc/*` callback
   the login itself needs, and would break non-browser clients that cannot do an
   interactive redirect.
5. **`sso-auth` is single-tenant.** It supports exactly one OIDC client
   (`oidc.py:77-80`, hardcoded to Jellyfin) and emits no role, group, or tenant claim.
   Identity today is one tier: "has a valid GoTrue session."

## Troubleshooting

| Symptom | Cause |
|---|---|
| `network pmoves_app not found` | Core stack not up. `make -C pmoves up` first. |
| Traefik up, browser TLS error | `CLOUDFLARE_DNS_API_TOKEN` missing/invalid — DNS-01 cannot complete. |
| App still shows its own login | Its router has no `pmoves-forward-auth` middleware, or the container predates the label. Check `edge-health`, then recreate it. |
| `edge-health` shows ports `[]` | Publish silently no-oped — ghost adapter on Windows. |
| Logged in but app says anonymous | `SSO_FORWARD_AUTH_SECRET` unset, so the app rejects the injected header. |
