# Flute Prosodic Sidecar Architecture

> **Canonical location:** [`pmoves/docs/infrastructure/FLUTE_PROSODIC_ARCHITECTURE.md`](infrastructure/FLUTE_PROSODIC_ARCHITECTURE.md)
>
> This copy lives at `pmoves/docs/` for convenience — GitHub links and cross-repo references can use either path.
> For TAC tree details, see [`pmoves/docs/TAC/TAC_FLUTE.md`](TAC/TAC_FLUTE.md).

<!-- CROSS-REF: This is a convenience copy. The canonical version is in infrastructure/. -->

---

> **See also:** [02_GEOMETRY_BUS.md](PMOVESCHIT/02_GEOMETRY_BUS.md) — Flute uses the GEOMETRY BUS for shape-encoded voice transport.

**Version:** 1.1
**Last Updated:** February 2026
**Related PR:** #332 (Pipecat Integration)

---

## Overview

The Flute Prosodic Sidecar is a text-to-speech optimization layer that achieves sub-100ms Time-To-First-Speech (TTFS) while maintaining natural human-like prosody. It works alongside TTS engines to chunk text at natural breath boundaries rather than waiting for complete sentence synthesis.

---

## Design Philosophy

Traditional TTS systems wait until the entire text is processed before returning audio. This creates unacceptable latency for conversational AI. The prosodic sidecar solves this by:

1. **Ultra-low TTFS**: First chunk is minimal (2 words) for immediate audio start
2. **Natural breaks**: Subsequent chunks follow prosodic boundaries
3. **Breath planning**: Forced breath points every ~10 syllables prevent run-on speech
4. **Position awareness**: Each chunk knows its position for intonation modeling

---

## Boundary Type System

The sidecar uses a 4-tier boundary hierarchy based on cognitive linguistics research:

| Boundary | Value | Pause (ms) | Breath Prob | Triggers |
|----------|-------|------------|-------------|----------|
| `SENTENCE` | 4 | 350 | 35% | `.` `!` `?` |
| `CLAUSE` | 3 | 180 | 15% | `,` `;` `:` `-` `—` |
| `PHRASE` | 2 | 100 | 0% | Before conjunctions |
| `BREATH` | 1 | 130 | 90% | Every ~10 syllables |
| `NONE` | 0 | 0 | 0% | Continuous speech |

### Detection Priority

1. **Sentence endings** (highest priority): Period, exclamation, question
2. **Phrase boundaries**: Before connectors (and, but, however, therefore, etc.)
3. **Clause boundaries**: Commas, semicolons, colons, dashes
4. **Continuous speech**: No punctuation, crossfade only

---

## ProsodicChunk Data Structure

```python
@dataclass
class ProsodicChunk:
    text: str                      # Text content to synthesize
    boundary_before: BoundaryType  # Boundary preceding this chunk
    boundary_after: BoundaryType   # Boundary following this chunk
    is_first: bool                 # Ultra-low TTFS target
    is_final: bool                 # Last chunk in utterance
    position_ratio: float          # [0.0=start, 1.0=end]
    estimated_syllables: int       # For breath planning

    @property
    def pause_after(self) -> float:
        """Get pause duration in milliseconds."""

    @property
    def can_breath_after(self) -> bool:
        """Whether breath sounds are allowed."""

    @property
    def breath_probability_after(self) -> float:
        """Probability of breath sound insertion."""
```

---

## BPM-Prosodic Bridge

> **OPEN ITEM from TAC_FLUTE.md — now resolved.**
>
> This section connects the prosodic boundary system to BPM encoding for CHIT attribution.
> Reference: [`AGNOTE4482.BEATS.md`](AGENTS/AGNOTE4482.BEATS.md) for `buildTimeline()` and `musicMapping.ts`.

### Boundary → BPM Mapping

Each prosodic boundary type maps to a musical tempo value, creating an attributable rhythm signature:

| Boundary | BPM | Musical Feel | Rationale |
|----------|-----|-------------|-----------|
| `SENTENCE` | 60 | Largo/Slow | Full pause — breath, reflection |
| `CLAUSE` | 90 | Andante/Walking | Comma pause — moderate separation |
| `PHRASE` | 120 | Allegro/Uptempo | Quick connector pause |
| `BREATH` | 80 | Adagio/Breath | Forced breath — slightly slower than clause |
| `NONE` | 150 | Presto/Continuous | No pause — rapid flow |

### ProsodicChunk → BPM Timeline Conversion

Using `buildTimeline()` from `musicMapping.ts`:

```typescript
import { buildTimeline, type BuildTimelineOpts } from './musicMapping';

function prosodicChunksToBpmTimeline(chunks: ProsodicChunk[]): TimelinePoint[] {
  // Each chunk becomes a timeline segment at its boundary BPM
  const segments = chunks.map((chunk, i) => {
    const boundaryBpm = BOUNDARY_BPM_MAP[chunk.boundary_after];
    const durationSec = chunk.estimated_syllables * 0.15; // ~150ms per syllable

    return buildTimeline({
      durationSec,
      slices: chunk.estimated_syllables,
      bpm: boundaryBpm,
      rootMidi: 60 + Math.floor(chunk.position_ratio * 12), // pitch rises with position
      scale: 'pentatonicMajor',
      notesPerBeat: 1,
      mode: 'step',
      plotHeightPx: 240,
    });
  });

  return segments.flat();
}
```

### Voice Pitch Contour Mapping

The `freqToY()` function from `musicMapping.ts` maps directly to voice pitch contours:

| Prosodic Position | MIDI Range | Frequency Range | Voice Effect |
|-------------------|-----------|-----------------|-------------|
| Start (0.0) | 60-64 (C4-E4) | 262-330 Hz | Neutral/rising |
| Mid (0.5) | 64-67 (E4-G4) | 330-392 Hz | Peak energy |
| End (1.0) | 67-72 (G4-C5) | 392-523 Hz | Falling/conclusive |

### NATS Integration

BPM-encoded prosodic events publish to:

**`tokenism.prosodic.bpm.v1`**
```json
{
  "spec": "chit.cgp.v0.2",
  "summary": "Prosodic BPM timeline for voice attribution",
  "created_at": "2026-02-20T12:00:00Z",
  "super_nodes": [{
    "id": "flute:prosodic:<utterance_id>",
    "label": "voice_prosodic",
    "constellations": [{
      "id": "prosodic.bpm.<utterance_id>",
      "summary": "BPM-encoded prosodic timeline",
      "spectrum": [0.8, 0.6, 0.4],
      "points": [
        {
          "id": "chunk:0",
          "modality": "voice",
          "proj": 1.0,
          "conf": 0.95,
          "summary": "SENTENCE boundary @ 60 BPM",
          "ref_id": "voice_persona_id"
        }
      ],
      "meta": {
        "namespace": "pmoves.voice.prosodic",
        "bpm_timeline": [60, 120, 90, 60],
        "boundary_sequence": ["SENTENCE", "PHRASE", "CLAUSE", "SENTENCE"]
      }
    }]
  }],
  "meta": {
    "source": "tokenism.prosodic.bpm.v1",
    "voice_persona_id": "af_sky",
    "tags": ["prosodic", "bpm", "voice-attribution"]
  }
}
```

---

## CHIT Voice Attribution Integration

The prosodic sidecar integrates with CHIT for voice attribution:

```
Text Input → Prosodic Parser → CGP Geometry Event
                ↓
        ProsodicChunk[]
                ↓
        TTS Engine(s)
                ↓
        Audio Output + NATS Event
                ↓
        tokenism.geometry.event.v1
                ↓ (BPM-enriched)
        tokenism.prosodic.bpm.v1
```

Each synthesized audio segment can be attributed via:
- `voice_persona_id`: Which voice persona spoke
- `chunk_position`: Where in the utterance
- `boundary_type`: What kind of pause followed
- `cgp_packet_id`: Link to CHIT geometry packet
- `bpm_value`: Tempo encoding for the boundary (NEW)

---

## Configuration

### Environment Variables

```bash
# Prosodic parsing defaults
PROSODIC_FIRST_CHUNK_WORDS=2     # Words in first chunk (TTFS optimization)
PROSODIC_MAX_SYLLABLES=10        # Max syllables before forced breath
PROSODIC_MIN_WORDS_PER_CHUNK=2   # Minimum words before natural break

# BPM encoding
PROSODIC_BPM_PUBLISH=false       # Enable BPM timeline publishing
PROSODIC_BPM_SCALE=pentatonicMajor  # Musical scale for encoding

# Audio stitching
BREATH_SOUND_PATH=/assets/breath.wav
CROSSFADE_MS=20                  # Crossfade duration between chunks
```

---

## Related Documentation

- `.claude/context/flute-gateway.md` - Flute API reference
- `pmoves/docs/context/PMOVES Multimodal Communication Layer (Flute) – Architecture & Roadmap.md` - Full architecture
- `.claude/context/nats-subjects.md` - Voice NATS subjects (`voice.tts.*`)
- `.claude/context/geometry-nats-subjects.md` - GEOMETRY BUS subjects
- `pmoves/docs/AGENTS/AGNOTE4482.BEATS.md` - BPM/frequency math and `musicMapping.ts`
- `pmoves/docs/TAC/TAC_FLUTE.md` - TAC tree for Flute Gateway
- `.claude/commands/chit/bpm.md` - `/chit:bpm` tool specification

---

## Module Structure

```
pmoves/services/flute-gateway/prosodic/
├── __init__.py           # Module exports
├── types.py              # BoundaryType, ProsodicChunk, PauseConfig
├── boundary_detector.py  # detect_boundary(), find_chunk_points()
├── syllable_counter.py   # estimate_syllables()
├── prosodic_parser.py    # parse_prosodic() main function
├── audio_processor.py    # Audio stitching and breath insertion
└── bpm_encoder.py        # BPM timeline encoding (NEW)
```

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->
