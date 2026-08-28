# a2ui-renderer

Remotion-based animation engine for the creator pipeline. Renders **A2UI
Animation v1** specs to MP4 / GIF / WebM, uploads the result to MinIO, and
publishes completion events to NATS.

> **Which "A2UI" is this?** Three distinct schemas share the `a2ui` prefix in
> this repo. This service consumes **A2UI Animation v1** only
> (`pmoves/contracts/a2ui-animation-schema.json`) — a scene/element timeline
> keyed on `version`, `animation`, and `scenes[].elements[]`.
>
> It does **not** consume the A2UI Protocol (`beginRendering` / `surfaceUpdate`)
> that `a2ui-nats-bridge` publishes, and it does not render `pm-*` components
> (`pmoves/contracts/a2ui-v0.1.md`). See
> `pmoves/docs/audit/A2UI_INTEGRATION_AUDIT_2026-08-14.md` § F1.

## Port

- Default: **8107**
- Compose service: `a2ui-renderer`
- Profiles: `agents`, `media`, `docs` (rendering work is GPU-light; runs on z890 or 5090)

## Quick start

```bash
make -C pmoves up-a2ui-renderer
curl -s http://localhost:8107/healthz
```

## Inputs

**HTTP only. This service subscribes to no NATS subjects.**

| Route | Guards |
|---|---|
| `POST /render` | `renderLimiter` + `requireAuth` (JWT) |
| `POST /render/chart` | `renderLimiter` + `requireAuth` (JWT) |
| `POST /render/provenance` | `renderLimiter` + `requireAuth` (JWT) |
| `GET /healthz` | none |
| `GET /metrics` | none |

`POST /render` takes an A2UI Animation v1 spec and rejects it unless `version`,
`animation`, and `scenes` are all present.

### Text layout

Text and heading elements may opt into deterministic layout with
`text_layout.engine: "pretext"` (`@chenglou/pretext`), which enables measured
line-breaking, `shrinkWrap`, `maxLines` overflow detection, locale, and
`debugBoxes`. Without that opt-in, browser layout is used. Usage is exported on
`/metrics` as `pretext_elements`, `bounded_text_elements`, and the set of
engines in play.

> Note: this deterministic path exists only here, in the video renderer. The
> HTML5 stage surface does not use it, so the same string can wrap differently
> in the two places. Tracked as § F3 of the integration audit.

## Outputs

Published to NATS after a successful render:

| Subject | Emitted by | Registered in `topics.json` |
|---|---|---|
| `a2ui.render.completed.v1` | all three render routes | yes |
| `ingest.file.added.v1` | all three render routes | — |
| `agent.graphiti.signed.v1` | `/render` and `/render/provenance` | — |

Rendered artifacts are uploaded to MinIO; the object reference travels on
`ingest.file.added.v1`.

## See also

- `pmoves/services/a2ui-renderer/src/` — renderer source
- `pmoves/contracts/a2ui-animation-schema.json` — the schema this service consumes
- `pmoves/docs/audit/A2UI_INTEGRATION_AUDIT_2026-08-14.md` — integration audit
- `pmoves/docs/AGENTS/AGNOTE4482.md` — coordination gateway
- `pmoves/contracts/topics.json` — topic schema registry
