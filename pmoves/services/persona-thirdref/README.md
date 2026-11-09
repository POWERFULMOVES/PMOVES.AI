# persona-thirdref

Third-reference persona grounding consumer. Subscribes
`persona.consumption.recorded.v1`, joins the consumed item against the
Supabase enrichment columns (`resonance_domain`, `resonance_secondary`,
`persona_signal`, `curriculum_track` on `pmoves_core.youtube_videos`), and
emits `shape.trace.recorded.v1` (`interaction_type: media`) onto the
geometry bus. At `PERSONA_THIRDREF_PROFILE_THRESHOLD` events per identity it
also publishes `shape.profile.updated.v1` with the normalized
resonance-domain histogram — the enrichment moment.

## The three references

Persona grounding now has three sources: authored configuration (first),
observed interaction telemetry (second), and **what is actually consumed of
the shared library** (third). Consumption is gravitational signal in the
three-body sense — every listen and every watch is an orbit measurement.
When human and idents converge on the same resonance domains, the swarm
moves from plain group toward bound collective (Levin's boundness
spectrum): shared consumption is the homogeneity that lets resonance bind.

## Producers

- Agent side: `python3 -m pmoves.tools.persona_consumption --agent <id>
  --kind youtube_video --item <video_id>`
- Human side: Jellyfin playback events (the jellyfin-bridge lane emits
  `persona.consumption.recorded.v1` with `source: jellyfin`)
- HTTP (token-gated, when `PERSONA_THIRDREF_TOKEN` is set):
  `POST /v1/record` with `X-Thirdref-Token`

## Env

| Variable | Default | Purpose |
|---|---|---|
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | bus |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` | — | enrichment join |
| `PERSONA_THIRDREF_TOKEN` | (empty = HTTP off) | record endpoint auth |
| `PERSONA_THIRDREF_PROFILE_THRESHOLD` | 10 | events per profile update |

Degradation is deliberate: no Supabase → caller domains only; no NATS →
log-only mode; no token → HTTP disabled. The service never blocks the bus.

## Tests

```bash
python3 -m pytest pmoves/services/persona-thirdref/tests/ -q
```
