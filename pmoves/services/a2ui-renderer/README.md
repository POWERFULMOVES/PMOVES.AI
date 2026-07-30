# a2ui-renderer

Remotion-based animation engine for the creator pipeline. Renders
A2UI message streams (comfy.collab.*.v1 NATS subjects) as on-brand
video segments via the `pmoves-ui` shell surface.

## Port

- Default: **8107**
- Compose service: `a2ui-renderer`
- Profile: `agents` (rendering work is GPU-light; runs on z890 or 5090)

## Quick start

```bash
make -C pmoves up-a2ui-renderer
curl -s http://localhost:8107/healthz
```

## Inputs

- `comfy.collab.prompt.v1` — design intent (style, motion language)
- `comfy.collab.progress.v1` — render progress updates
- `comfy.collab.artifact.v1` — final artifact notification

## Outputs

- `artifact_id` written back via `nats_event_bus` publish on
  `comfy.collab.artifact.v1` with `actor_kind=service`,
  `actor=a2ui-renderer`.

## See also

- `pmoves/services/a2ui-renderer/src/` — renderer source
- `pmoves/docs/AGENTS/AGNOTE4482.md` — coordination gateway
- `pmoves/contracts/topics.json` — topic schema registry
