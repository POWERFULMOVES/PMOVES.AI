# /chit:bpm — Prosodic BPM Encoding Tool

Encode prosodic chunks as BPM timeline events for CHIT attribution.

## Purpose

Bridges the Flute prosodic parser output with the CHIT Geometry Bus by converting `ProsodicChunk[]` into BPM-encoded CGP v0.2 packets, then publishing to `tokenism.prosodic.bpm.v1`.

## Input

- **ProsodicChunk[]** from Flute Gateway's prosodic parser
- Each chunk contains: `text`, `boundary_before`, `boundary_after`, `position_ratio`, `estimated_syllables`

## BPM Mapping

| Boundary Type | BPM | Musical Tempo | MIDI Root Offset |
|---------------|-----|--------------|-----------------|
| SENTENCE | 60 | Largo | +0 (C4) |
| CLAUSE | 90 | Andante | +4 (E4) |
| PHRASE | 120 | Allegro | +7 (G4) |
| BREATH | 80 | Adagio | +2 (D4) |
| NONE | 150 | Presto | +12 (C5) |

## Output

CGP v0.2 packet with `bpm_timeline` field:

```json
{
  "spec": "chit.cgp.v0.2",
  "summary": "Prosodic BPM timeline for voice attribution",
  "created_at": "ISO-8601",
  "super_nodes": [{
    "id": "flute:prosodic:<utterance_id>",
    "label": "voice_prosodic",
    "constellations": [{
      "id": "prosodic.bpm.<utterance_id>",
      "summary": "BPM-encoded prosodic timeline",
      "spectrum": [0.8, 0.6, 0.4],
      "points": [
        {
          "id": "chunk:<index>",
          "modality": "voice",
          "proj": 1.0,
          "conf": 0.95,
          "summary": "<BOUNDARY> boundary @ <BPM> BPM"
        }
      ],
      "meta": {
        "namespace": "pmoves.voice.prosodic",
        "bpm_timeline": [60, 120, 90, 60],
        "boundary_sequence": ["SENTENCE", "PHRASE", "CLAUSE", "SENTENCE"],
        "total_syllables": 42,
        "duration_estimate_ms": 6300
      }
    }]
  }],
  "meta": {
    "source": "tokenism.prosodic.bpm.v1",
    "voice_persona_id": "<persona>",
    "tags": ["prosodic", "bpm", "voice-attribution"]
  }
}
```

## NATS Subject

**Publish to:** `tokenism.prosodic.bpm.v1`

## Dependencies

- `musicMapping.ts` from `PMOVES-ToKenism-Multi/integrations/contracts/chit/`
- Flute Gateway prosodic parser (`/v1/voice/analyze/prosodic`)
- NATS client for publishing

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROSODIC_BPM_PUBLISH` | `false` | Enable BPM timeline publishing |
| `PROSODIC_BPM_SCALE` | `pentatonicMajor` | Musical scale for encoding |
| `CHIT_VOICE_ATTRIBUTION` | `false` | Must also be enabled |

## Usage

```bash
# Analyze text prosodically and encode as BPM timeline
/chit:bpm "Hello, this is a test of the prosodic parser."

# With custom scale
/chit:bpm --scale minor "A somber message with careful pacing."
```

## Related

- [`pmoves/docs/FLUTE_PROSODIC_ARCHITECTURE.md`](../../pmoves/docs/FLUTE_PROSODIC_ARCHITECTURE.md) — Full prosodic architecture
- [`pmoves/docs/AGENTS/AGNOTE4482.BEATS.md`](../../pmoves/docs/AGENTS/AGNOTE4482.BEATS.md) — BPM math reference
- [`pmoves/docs/TAC/TAC_TOKENISM.md`](../../pmoves/docs/TAC/TAC_TOKENISM.md) — ToKenism TAC tree
- `.claude/context/geometry-nats-subjects.md` — GEOMETRY BUS catalog

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->
