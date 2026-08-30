# Traefik v3.3's Docker provider cannot talk to Docker Engine 29 (2026-08-06)

**Brief for `KNOWN_ROAD=compose:handoff:traefik-docker-provider-api-version-2026-08-06.md`.**

## Symptom

The edge comes up clean — `make up-edge` succeeds, `edge-health` shows both containers
healthy, and 80/443 bind correctly (`0.0.0.0:80`, `0.0.0.0:443`, no ghost-adapter empty
`[]`). But **every route 404s**:

```
curl -H 'Host: auth.pmoves.ai' http://localhost/login   → 301 → https  (entrypoint works)
curl -k -H 'Host: auth.pmoves.ai' https://localhost/login → 404
```

`auth.pmoves.ai` is declared on the Traefik container itself
(`traefik.http.routers.auth.rule=Host(...)`, `service=sso-auth@docker`), so a 404 on
that route means Traefik is not reading container labels **at all** — not that one
app is misconfigured.

The log says so, once a minute, forever:

```
ERR Failed to retrieve information of the docker client and server host
    error="Error response from daemon: " providerName=docker
ERR Provider error, retrying in 12.5s
    error="Error response from daemon: " providerName=docker
```

Note the **empty** error message. That is the whole diagnostic difficulty: there is
nothing after the colon.

## What it is not

Ruled out by measurement, in this order:

| Hypothesis | Test | Result |
|---|---|---|
| Socket not mounted | `docker inspect` mounts | `bind /var/run/docker.sock → /var/run/docker.sock rw=false` — present |
| Socket not visible in container | `docker exec pmoves-traefik ls -la /var/run/docker.sock` | `srw-rw---- root root` — present |
| Permission (non-root Traefik) | `docker exec pmoves-traefik id` | `uid=0(root)` — not it |
| Socket itself broken | `alpine/curl --unix-socket … /version` | **200** |
| Read-only mount rejected | same, with `:ro` | **200** |
| `/info` specifically failing | same, `/info` with `:ro` | **200** |

The socket is fine. Another container reads it happily with the identical mount.

> Trap worth recording: `docker exec … ls -la /var/run/docker.sock` run from Git Bash
> on Windows silently becomes `ls -la C:/Program Files/Git/var/run/docker.sock` and
> reports "No such file or directory". That is MSYS path mangling in the *caller*, not
> a finding about the container. Set `MSYS_NO_PATHCONV=1` or use `//var/run/...`.

## Root cause

Docker Engine dropped support for old API versions. This daemon:

```
Docker Desktop 4.85.0 / Engine 29.6.2
ApiVersion 1.55, MinAPIVersion 1.40
```

Traefik v3.3's Docker provider pins API **v1.24**, below that floor. Reproduced
directly against the socket:

```
/v1.24/version → HTTP 400  {"Platform":{...},"Version":"","ApiVersion":"","Os":"","Arch":""}
/v1.40/version → HTTP 200  Version 29.6.2
/v1.44/version → HTTP 200
/v1.47/version → HTTP 200
```

The 400 carries an empty body, which is exactly how it reaches the log as
`Error response from daemon: ` with nothing after the colon.

## The fix, and the one that does not work

`DOCKER_API_VERSION=1.44` in the container environment — the documented Docker Go
client override — **does not help**. Measured: 7 provider errors in 12 seconds, same
message. Traefik constructs its client with a pinned version and never consults the
env var.

The only thing that works is a version bump. Measured across three tags, 10s each,
identical flags, same socket:

| Image | Provider errors |
|---|---|
| `traefik:v3.4` | 7 |
| `traefik:v3.5` | 6 |
| **`traefik:v3.6`** | **0** |

So: `${TRAEFIK_IMAGE:-traefik:v3.3}` → `traefik:v3.6`, digest-pinned.

## Why this went unnoticed

The edge had no make target until #2411, so Traefik had never been started on this
node. Every `traefik.*` label in the fleet has been inert since the labels were
written. `edge-health` reported "no router uses forward-auth" and that was read as
"the app containers predate the labels" — which is *also* true (they do, see below) —
but it masked the fact that Traefik could not have seen any label regardless.

Two independent faults presenting as one symptom. Fixing only the containers would
have changed nothing.

## Verification

After the bump, from the node:

```
docker logs pmoves-traefik | grep -c "Provider error"        # expect 0
curl -k -H 'Host: auth.pmoves.ai' https://localhost/login    # expect the sso-auth login page, not 404
```

## Related, not fixed here

- The running `pmoves-wger`, `pmoves-firefly`, `pmoves-open-notebook-ext-1` containers
  (created 2026-07-21/25) carry **zero** `traefik.*` labels — they predate #2221/#2419
  and must be recreated before any route reaches them.
- Recreating `wger` also **activates `WGER_ALLOW_REMOTE_USER=True`** and **drops the
  `:8010` host publish** (current `docker-compose.external.yml` has no `ports:` for
  `wger-nginx`, by design). Both are deliberate, and both mean the recreate must not
  happen until `health.pmoves.ai` actually resolves — otherwise the PMOVES-Health
  phone app loses its only path. Sequencing, not a code change.
- Confirmed today that forging `Remote-User` against the live `:8010` port does
  nothing: the only byte difference between a forged and an unforged response is the
  per-request CSRF nonce, identical to the difference between two unforged responses.
  `WGER_ALLOW_REMOTE_USER` is not active on the container that is running now.
