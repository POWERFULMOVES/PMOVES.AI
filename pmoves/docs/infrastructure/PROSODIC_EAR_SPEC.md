# Prosodic Ear — Audio Analysis & BPM Encoding Spec

> The prosodic "mouth" (synthesis) exists in Flute-Gateway. This spec defines the prosodic "ear" — how the system listens to, analyzes, and encodes incoming speech into CHIT-compatible BPM events.

## Problem

Flute-Gateway can **produce** prosodically-aware speech (chunked by boundary type, paused at breath points, crossfaded). But the system cannot yet **listen** to speech and extract prosodic features. This means:

- No feedback loop: we synthesize prosody but can't measure it
- No speaker emotion detection from audio (only text sentiment)
- No BPM encoding from real speech into the CHIT geometry bus
- STT via Whisper returns text only — no pitch, tempo, or energy data

## Architecture

```
Incoming Audio (mic, WebSocket, file upload)
    ↓
[1] Whisper STT → text transcription (existing)
    ↓
[2] Prosodic Analyzer (NEW)
    ├── Pitch contour extraction (f0 via librosa/parselmouth)
    ├── Energy envelope (RMS)
    ├── Tempo estimation (onset detection → BPM)
    ├── Pause detection → boundary type mapping
    └── Speaker emotion (hubert-large via media-audio-analyzer at :8082)
    ↓
[3] BPM Encoder (NEW)
    ├── Map detected boundaries to BoundaryType enum
    ├── Convert tempo to BPM value
    ├── Generate ProsodicTimeline from analysis
    └── Package as CHIT CGP event
    ↓
[4] NATS Publisher
    └── Emit `tokenism.prosodic.bpm.v1` with CGP payload
```

## Component Details

### 2. Prosodic Analyzer

**Input:** Audio bytes (WAV/PCM16, any sample rate)
**Output:** `ProsodicAnalysis` dataclass

```python
@dataclass
class ProsodicAnalysis:
    # Pitch
    f0_contour: list[float]       # Hz values per frame
    f0_mean: float                # Average pitch
    f0_range: tuple[float, float] # (min, max) Hz

    # Energy
    rms_contour: list[float]      # RMS energy per frame
    energy_mean: float

    # Tempo
    estimated_bpm: float          # Beats per minute from onset detection
    onset_times: list[float]      # Seconds

    # Pauses
    pauses: list[PauseEvent]      # Detected silences with duration + position
    boundary_types: list[BoundaryType]  # Mapped from pause durations

    # Emotion (optional, from media-audio-analyzer)
    emotion: str | None           # e.g., "happy", "calm", "angry"
    emotion_confidence: float

    # Duration
    duration_sec: float
    sample_rate: int
```

**Pause → Boundary Mapping:**

| Pause Duration | Boundary Type | Confidence |
|---------------|--------------|------------|
| >300ms | SENTENCE | High |
| 150-300ms | CLAUSE | Medium |
| 80-150ms | PHRASE | Medium |
| 50-80ms | BREATH | Low |
| <50ms | NONE | — |

### 3. BPM Encoder

Maps `ProsodicAnalysis` → CHIT CGP event:

```python
def encode_prosodic_bpm(analysis: ProsodicAnalysis) -> dict:
    return {
        "schema": "chit.cgp.v1.0",
        "type": "prosodic.ear",
        "bpm": analysis.estimated_bpm,
        "pitch_mean_hz": analysis.f0_mean,
        "energy_mean": analysis.energy_mean,
        "boundaries": [
            {"type": b.value, "position_sec": p.position}
            for b, p in zip(analysis.boundary_types, analysis.pauses)
        ],
        "emotion": analysis.emotion,
        "duration_sec": analysis.duration_sec,
    }
```

### 4. NATS Publishing

**Subject:** `tokenism.prosodic.bpm.v1`
**Payload:** CGP v1.0 event with prosodic analysis data

## Dependencies

| Dependency | Purpose | Status |
|-----------|---------|--------|
| `librosa` or `parselmouth` | Pitch/tempo extraction | Not installed in Flute |
| Whisper (port 8078) | STT transcription | Existing |
| Media-Audio-Analyzer (port 8082) | Emotion detection (HuBERT) | Existing |
| NATS (port 4222) | Event publishing | Existing |
| CHIT `sign_cgp()` | CGP signing | Existing |

## Flute-Gateway Integration

### New Endpoint (PROPOSED — not implemented)

```
POST /v1/voice/analyze/prosodic
Content-Type: audio/wav (or multipart/form-data)

Response:
{
    "transcription": "Hello world",
    "bpm": 72.5,
    "pitch_mean_hz": 185.3,
    "energy_mean": 0.045,
    "boundaries": [...],
    "emotion": "calm",
    "emotion_confidence": 0.87,
    "duration_sec": 2.3
}
```

### Existing Endpoint Enhancement

`POST /v1/voice/synthesize/prosodic` — **SHIPPED** (`main.py:1193`). Returns `audio/wav` with the BPM/prosodic timeline in the `X-Prosodic-Chunks` / `X-Prosodic-BPM` / `X-Prosodic-Timeline` response headers. Requires the `ultimate_tts` provider (400 otherwise). The analysis-only endpoint below remains **PROPOSED**.

## Implementation Phases

### Phase A: Analysis Only (MVP)
- Add `librosa` to Flute requirements
- Implement `ProsodicAnalyzer` class
- Expose `/v1/voice/analyze/prosodic` endpoint
- Return analysis as JSON (no NATS yet)

### Phase B: BPM Encoding
- Implement BPM encoder
- Publish to `tokenism.prosodic.bpm.v1` via NATS
- Connect to CHIT geometry bus

### Phase C: Feedback Loop
- Compare synthesis prosody vs analysis prosody
- Auto-tune speaking rate based on feedback
- Emotion-aware engine selection (calm → Kokoro, dramatic → IndexTTS2)

### Phase D: Real-Time Ear
- WebSocket `/v1/voice/stream/analyze`
- Continuous pitch/energy monitoring
- Live BPM dashboard in Hyperdimensions

## NATS Subjects

| Subject | Direction | Payload |
|---------|-----------|---------|
| `tokenism.prosodic.bpm.v1` | Publish | CGP event with BPM + boundaries |
| `voice.ear.analysis.v1` | Publish | Full prosodic analysis result |
| `voice.ear.emotion.v1` | Publish | Emotion detection event |

## Related Files

| File | Purpose |
|------|---------|
| `pmoves/services/flute-gateway/prosodic/` | Existing prosodic parser (synthesis side) |
| `pmoves/docs/infrastructure/FLUTE_PROSODIC_ARCHITECTURE.md` | Synthesis-side architecture |
| `pmoves/configs/tts-engine-capabilities.yaml` | Engine → emotion mapping |
| `.claude/context/voice-personas.md` | Persona → engine assignment |
