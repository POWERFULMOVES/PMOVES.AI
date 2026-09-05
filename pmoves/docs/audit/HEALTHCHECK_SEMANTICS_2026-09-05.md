# Healthcheck semantics audit — 2026-09-05

**Finding: the compose fleet is 91% instrumented and 92% of that instrumentation
asserts nothing.** Coverage is not the defect. Meaning is.

Measured on `pmoves/docker-compose.yml` at `55bd6a2c3`, by parsing the file as
YAML — see *Method* for why that matters.

## Numbers

| | |
|---|---:|
| services | 110 |
| declare a healthcheck | 100 (91%) |
| declare none | 10 (9%) |
| **of the 100 — liveness-only** | **92 (92%)** |
| assert a real value | 8 |
| distinct probe shapes | 53 |
| most-copied single shape | **28×** |

"Liveness-only" means the probe establishes that a socket answered on a health
path and nothing further. "Asserts a real value" means it exercises something
that breaks when the service is broken: `pg_isready`, `redis-cli PING`,
`kong health`, `postgrest --ready`, a `fetch()` that throws on non-200.

## Why 28 identical copies is the signal

The dominant shape is:

```
["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://<host>:<port>/healthz', timeout=5)"]
```

reused verbatim across 28 services that share nothing but a template. **A probe
that travels by copy-paste cannot be validating anything specific to where it
landed** — what it checks is identical everywhere, so it is checking the
template, not the service.

`/healthz` fails when the process is dead. Docker already knows that from the
PID. The probe therefore adds no information over `restart: unless-stopped`
while licensing `condition: service_healthy` for dependents.

## The clearest case, now fixed

`supabase-studio` shipped:

```yaml
test: ["CMD-SHELL", "node -e 'process.exit(0)' || exit 1"]
```

This names no host, no port and no route. It **cannot fail** while the `node`
binary exists, and it reported `service_healthy` to dependents on a dead Studio.
Its own comment stated the intent — *"We rely on container being started
successfully"* — which is the fact Docker already has.

The stated reason for substituting it ("Next.js 16 binds to container hostname,
not localhost") is stale: `HOSTNAME=0.0.0.0` is pinned three lines above, so the
bind it worked around no longer happens. Verified against the running container:

```
docker exec pmoves-supabase-studio-1 node -e "fetch('http://localhost:3000/api/platform/profile')..."
  -> localhost status 200
  -> 127.0.0.1 status 200
```

Replaced with the vendored upstream probe
(`PMOVES-supabase/docker/docker-compose.yml:17-23`), which throws on non-200.

## The standard this argues for

From 5090-CLAUDE's §3 recommendation on #2935, which generalises past Cipher:

> satisfy "must not fail quietly" with an authenticated `store.recall`
> round-trip at mount time, not a health endpoint. The health of the process
> says nothing; the round-trip of a real value says everything.

Corroborated from the other end the same day: `pmoves-cipher-api-1` is `Up
(healthy)` while its MCP mount returns `AUTH_HEADER_REJECTED` (401). A liveness
probe calls that green.

## Method — and a correction to this audit's own first pass

The first pass counted services with a regex over two-space YAML keys. It
reported **261 services, 62% with no healthcheck, 68% liveness-only**. All three
were wrong: the regex matched `networks:` and `volumes:` entries as services.

It returned a plausible number, so nothing flagged it. Parsing the file as YAML
— asserting the structure instead of pattern-matching the text — produced the
figures above. The audit's own first pass was the defect it documents, one level
up.

## Not decided here

- **Whether to gate on this.** A ratchet refusing a healthcheck that cannot fail
  is implementable, but it is a policy call and belongs to the operator, not to
  this audit.
- **Converting the 92.** Each conversion needs per-service knowledge of what
  "working" means for that service; it is not a sweep.
- **The 10 with none.** Absence claims nothing and is more honest than
  decoration. Whether they need probes is a separate question from whether the
  existing ones mean anything.
