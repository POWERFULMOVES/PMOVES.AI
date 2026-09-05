# Healthcheck semantics audit — 2026-09-05

One probe in the compose file could not fail. Fixing it turned up a shape
problem behind it, and three defects in how this audit itself measured.

Re-runnable: `python pmoves/tools/healthcheck_semantics.py`.

## What is counted

| | |
|---|---:|
| services | 110 |
| declare a healthcheck | 100 |
| declare none | 10 |
| explicitly disabled | 1 (`invidious-companion`, `disable: true`) |
| distinct command shapes | 52 |
| **most-reused single shape** | **28×** |

That is arithmetic over the parsed file, and it holds. Nothing below claims more.

## The 28-way collision

```
["CMD", "python3", "-c",
 "import urllib.request; urllib.request.urlopen('http://<host>:<port>/healthz', timeout=5)"]
```

Byte-identical across 28 services after normalising host, port and env
interpolation. **A probe reused verbatim across services that share nothing but
a template is checking the template.** `/healthz` answering proves the process is
listening — which Docker already knows from the PID — while licensing
`condition: service_healthy` for everything downstream.

Whether that is *adequate* for a given service is a judgement about that
service. This audit does not make it; see *Corrections* for what happened when
an earlier pass tried.

## The one that could not fail — fixed here

`supabase-studio` shipped:

```yaml
test: ["CMD-SHELL", "node -e 'process.exit(0)' || exit 1"]
```

No host, no port, no route. It cannot fail while the `node` binary exists, and
it reported `service_healthy` to dependents on a dead Studio. Its own comment
stated the intent — *"We rely on container being started successfully"* — which
is what `restart: unless-stopped` already provides.

The reason given for replacing upstream's probe ("Next.js 16 binds to container
hostname, not localhost") is **stale**: `HOSTNAME=0.0.0.0` is pinned three lines
above. Verified against the running container rather than argued:

```
docker exec pmoves-supabase-studio-1 node -e "fetch('http://localhost:3000/api/platform/profile')..."
  -> localhost status 200 / 127.0.0.1 status 200
```

Restored to the vendored upstream probe
(`PMOVES-supabase/docker/docker-compose.yml:17-23`), which throws on non-200.

## The compose gate validates less than its name suggests

`make -C pmoves compose-yaml-check` asserts that all 57 tracked compose files
**parse**. Its docstring says exactly that, and it exists for a good reason: it
replaced a step whose body ended in `|| echo 'Compose validation skipped'` and
therefore could not fail.

Parsing is not conformance. Measured on a fixture:

| | `retries: "not-a-number"`, `test: ["WRONG-VERB", …]` |
|---|---|
| `compose_yaml_validate.py` | **clean, rc=0** |
| `docker compose config` | **rc=1** — `failed to cast to expected type: strconv.Atoi` |

Docker's own tool is the Compose Specification authority. **It cannot run in CI
here**: compose declares `env_file: env.shared` per service, and that file is a
secret absent from a fresh checkout, so `docker compose config` exits 1 with
"env file ... not found" before it validates anything.

The parse-only gate is therefore the most that runs without secrets, and that is
a sound call. The gap is the label: the step satisfies a required check named
`docker-build-validation`, and a reader of the checks list sees compose
validated when what was validated is that the YAML is well-formed.

Worth deciding (not decided here): whether a stub env permits spec validation in
CI, or whether the check should be renamed to what it does.

## Corrections — this audit measured wrong three times

**Pass 1** counted services with a regex over two-space YAML keys: *261
services, 62% with no healthcheck*. Both wrong — it matched `networks:` and
`volumes:` entries. It returned a plausible number, so nothing flagged it.

**Pass 2** parsed as YAML (correct for counting) but classified probe *meaning*
with a second regex over command text, and published **"92 of 100 are
liveness-only"**. That figure is **withdrawn**. A regex is a way to find
candidates, not a way to decide whether one qualifies. The structural screen
that replaced it had false positives both ways: of 13 probes naming neither port
nor path, several (`pg_isready`, `kong health`, `imgproxy health`) are *more*
meaningful than an HTTP liveness probe, not less.

**Pass 3** modelled the Compose Specification in pydantic before that was cut.
Validating compose structure is Docker's job, and a second schema here would be
a second opinion about what a compose file is. The tool now imports
`compose_yaml_validate.ComposeLoader` rather than carrying its own parser, so it
and the gate cannot disagree about what parses — which matters, because
`yaml.safe_load` fails on two tracked files that use Compose's `!reset` and
`!override` tags.

Each pass produced a number that looked like a measurement. That is the failure
the audit documents in the probes themselves, three times, one level up.

## Not decided here

- **A ratchet gating on this.** Implementable; it is a policy call.
- **Converting the reused probes.** Each needs per-service knowledge of what
  "working" means. Not a sweep.
- **The 10 with no healthcheck.** Absence claims nothing, which is more honest
  than decoration.
