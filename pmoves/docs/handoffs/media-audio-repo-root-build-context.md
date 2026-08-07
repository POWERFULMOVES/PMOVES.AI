# media-audio — repo-root build context + validated envelope

**Lane:** 4090-claude (field) · **Date:** 2026-08-04 · **Branch:** `fix/service-build-context-envelope`

## Why this touches `pmoves/docker-compose*.yml`

`media-audio` publishes to the registered NATS topic `analysis.audio.v1`, but it was
built with `build: ./services/media-audio` — a service-directory context. That context
physically excludes two things the service needs:

- `pmoves/services/common/` — the `events.envelope()` helper that validates a payload
  and wraps it in the common envelope (`id/topic/ts/version/source`)
- `pmoves/contracts/` — `topics.json` plus the schemas it points at

The consequence is visible in the code that was on `main`. `_maybe_publish` carried this
comment:

> `The build context is ./services/media-audio so the schema file is not in the image;`
> `enforce its one hard invariant inline rather than poison consumers with a bad payload.`

So the service hand-rolled a partial contract check (`emotions` is a list) and published a
**bare payload** with no envelope. It imported nothing from `services.common` — it could not.
Every other producer on the bus emits an envelope; this one did not.

This is not fixable inside the service directory. The build context is the defect.

## Change

| File | Change |
|---|---|
| `pmoves/docker-compose.yml` | `build: ./services/media-audio` → `context: ..` + `dockerfile: pmoves/services/media-audio/Dockerfile` |
| `pmoves/docker-compose.media.yml` | same |
| `pmoves/services/media-audio/Dockerfile` | repo-root-relative `COPY` paths; add `pmoves/services/common/` and `pmoves/contracts/` |
| `pmoves/services/media-audio/server.py` | `_maybe_publish` emits a validated envelope |

The `context: ..` + `dockerfile: pmoves/services/<name>/Dockerfile` form is **not new** —
it is the shape `ffmpeg-whisper` already uses in `docker-compose.yml`. This aligns
`media-audio` with the existing convention rather than inventing one.

## Behaviour

`_maybe_publish` now follows the #1814 discipline:

- payload validated against `schemas/analysis/audio.v1.schema.json` before publish
- schema-invalid → logged and **dropped**, never published (the old `emotions` guarantee
  is preserved, now enforced by the real schema instead of a hand-rolled check)
- unregistered subject → distinct warning; `MEDIA_AUDIO_SUBJECT` is env-overridable, so
  pointing it at an unregistered topic is a config fault, not a bad payload
- validator unavailable → **visible warning**, never a silent downgrade to unvalidated publishing

`events.envelope()` is used rather than `events.publish()` on purpose: `events` resolves its
own module-level `NATS_URL` with an empty-string default, which would connect to nowhere
whenever `NATS_URL` is unset, while this service carries a real default.

Payload is coerced through `json.loads(json.dumps(result, default=str))` **before**
validation, so what is validated is exactly what goes on the wire — validating the raw dict
would validate datetimes as objects while shipping them as strings.

## Verification

```
envelope('analysis.audio.v1', <valid>)      -> id/payload/source/topic/ts/version
envelope('analysis.audio.v1', {no emotions}) -> ValidationError  (dropped)
envelope('not.a.registered.topic.v1', ...)   -> KeyError         (config fault)
```

`pmoves/tests/hardening/test_docker_hardening.py` is unchanged by this work: baseline and
post-change runs are both `5 failed, 22 passed, 4 skipped, 284 errors`. Those errors are
pre-existing and Windows-specific — the suite opens files without `encoding='utf-8'` and
dies on `charmap` (`byte 0x8f`). Worth its own lane; it means the hardening suite provides
no coverage on Windows nodes.

## Related, not fixed here

- `ffmpeg-whisper` compose is already correct (`context: ..`), but its **CI matrix** entry in
  `self-hosted-builds.yml` / `self-hosted-builds-hardened.yml` uses
  `context: ./pmoves/services/ffmpeg-whisper`, which cannot satisfy its `COPY pmoves/...`
  paths. That service cannot build in CI, and no image is published under that name.
- `media-audio` is in **no** CI matrix. `build-gpu` is disabled (`if: ${{ false }}`) with its
  own TODO, so there is no GPU lane to add it to without re-enabling that job.
## Guard behaviour (recorded so it is not re-investigated)

`pmoves/docker-compose.yml` edits are **not** blocked, while `pmoves/docker-compose.media.yml`
edits are. That asymmetry is intentional, not a guard defect: `docker-compose.yml` is listed
under `chitSafePaths:` in `.claude/hooks/damage-control/patterns.yaml` (line ~967) with the
comment *"This allows Edit tool to modify compose env vars for service configuration fixes."*
`docker-compose.media.yml` is not on that list, so it stays behind the Known Road.

Consequence worth knowing: only the `docker-compose.media.yml` half of this change appears in
`known-roads.jsonl`. The `docker-compose.yml` half is unrecorded because it was never a bypass.
Do not read the missing trail line as a skipped guard.
