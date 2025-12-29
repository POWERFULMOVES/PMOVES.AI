# Flute Prosodic Sidecar Architecture

**Version:** 1.0
**Last Updated:** December 2025
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

## Phrase Starters

The following words trigger `PHRASE` boundaries when they appear after a word:

```
Conjunctions:     and, but, or, so, yet, nor
Subordinating:    because, although, though, while, when, if, then, unless, until, whereas
Transitions:      however, therefore, thus, hence, consequently
Sequencing:       first, second, third, finally, next, lastly
Connectors:       meanwhile, furthermore, moreover, instead, otherwise
Questions:        what, where, why, how (when mid-sentence)
```

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

## Parsing Algorithm

### Step 1: First Chunk (Ultra-low TTFS)

```python
# Extract minimal first chunk (default: 2 words)
n_first = min(first_chunk_words, len(words))
first_text = " ".join(words[:n_first])
first_boundary = detect_boundary(words[n_first - 1], words[n_first])
```

The first chunk is intentionally small to enable immediate audio playback while subsequent chunks are processed in parallel.

### Step 2: Remaining Chunks

For each remaining word:

```python
# Decision tree for chunk breaks:
1. SENTENCE boundary? → Always break
2. CLAUSE boundary + enough words? → Break
3. PHRASE boundary + enough words? → Break
4. >10 syllables without natural break? → Force BREATH break
5. Otherwise → Continue accumulating
```

### Step 3: Syllable-Based Breath Forcing

When no natural boundary occurs for `max_syllables_before_breath` (default: 10), force a `BREATH` boundary:

```python
if syllables_since_break >= max_syllables_before_breath:
    if boundary == BoundaryType.NONE:
        boundary = BoundaryType.BREATH  # 130ms pause, 90% breath probability
    should_break = True
```

---

## Syllable Estimation

The sidecar uses a vowel-based heuristic for English syllable counting:

```python
def estimate_syllables(word: str) -> int:
    """Count syllables using vowel cluster method.

    Rules:
    1. Count vowel sequences (a, e, i, o, u, y)
    2. Don't count trailing silent 'e'
    3. Minimum 1 syllable per word

    Examples:
        "hello" → 2 (he-llo)
        "beautiful" → 4 (beau-ti-ful)
        "the" → 1 (minimum)
    """
```

---

## Audio Stitching

### Pause Insertion

After each chunk, silence is inserted based on boundary type:

```
SENTENCE: 350ms silence (natural sentence pause)
CLAUSE:   180ms silence (comma pause)
PHRASE:   100ms silence (short connector pause)
BREATH:   130ms silence (breath point)
NONE:     0ms (crossfade only)
```

### Breath Sound Integration

At boundaries with `can_breath=True`, breath sounds may be inserted:

```python
if chunk.can_breath_after:
    if random.random() < chunk.breath_probability_after:
        audio = insert_breath_sound(audio, position=chunk_end)
```

Breath probability is highest at forced breath points (90%) and moderate at sentence boundaries (35%).

---

## TTFS Optimization Strategy

### Target: <160ms Time-To-First-Speech

```
┌─────────────────────────────────────────────────────────────┐
│                    Timeline (0ms → 500ms)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [0ms] Text arrives                                         │
│   │                                                         │
│  [10ms] Prosodic parsing → First chunk (2 words)           │
│   │                                                         │
│  [30ms] TTS request sent for first chunk                   │
│   │                                                         │
│  [120ms] First audio chunk returned                        │
│   │                                                         │
│  [160ms] Audio playback begins ← TTFS TARGET               │
│   │                                                         │
│  [200ms] Second chunk TTS completes (overlapped)           │
│   │                                                         │
│  [350ms] First pause ends, second audio plays              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Optimization Techniques

1. **Parallel TTS requests**: Send chunk N+1 while chunk N is playing
2. **Pre-fetched silence**: Generate pause audio ahead of time
3. **Streaming response**: Begin WebSocket audio push immediately
4. **Minimal first chunk**: 2 words = fastest possible TTFS

---

## Configuration

### Environment Variables

```bash
# Prosodic parsing defaults
PROSODIC_FIRST_CHUNK_WORDS=2     # Words in first chunk (TTFS optimization)
PROSODIC_MAX_SYLLABLES=10        # Max syllables before forced breath
PROSODIC_MIN_WORDS_PER_CHUNK=2   # Minimum words before natural break

# Audio stitching
BREATH_SOUND_PATH=/assets/breath.wav
CROSSFADE_MS=20                  # Crossfade duration between chunks
```

### API Parameters

```python
POST /v1/voice/synthesize/prosodic
{
    "text": "Hello, this is a test sentence.",
    "voice": "default",
    "format": "wav",
    "prosodic_config": {
        "first_chunk_words": 2,
        "max_syllables_before_breath": 10,
        "min_words_per_chunk": 2,
        "enable_breath_sounds": true
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
```

Each synthesized audio segment can be attributed via:
- `voice_persona_id`: Which voice persona spoke
- `chunk_position`: Where in the utterance
- `boundary_type`: What kind of pause followed
- `cgp_packet_id`: Link to CHIT geometry packet

---

## Provider Comparison Matrix

| Provider | TTFS | Quality | Streaming | Breath Sounds |
|----------|------|---------|-----------|---------------|
| Ultimate-TTS | ~200ms | High | Yes | Manual |
| VibeVoice | ~100ms | Medium | Yes | Built-in |
| Whisper (STT) | N/A | High | Yes | N/A |
| ElevenLabs | ~150ms | Very High | Yes | Built-in |

---

## Example Output

Input: `"Hello, world! This is a test of the prosodic parser."`

```
Prosodic Analysis (4 chunks):
  [1] "Hello, world!" → SENTENCE (350ms) [FIRST]
  [2] "This is" → NONE (0ms)
  [3] "a test of" → PHRASE (100ms)
  [4] "the prosodic parser." → SENTENCE (350ms) [FINAL]
```

Audio timeline:
```
[0-150ms]   "Hello, world!" plays
[150-500ms] 350ms pause (sentence boundary)
[500-600ms] "This is" plays
[600-680ms] "a test of" plays (crossfade)
[680-780ms] 100ms pause (phrase boundary)
[780-950ms] "the prosodic parser." plays
[950-1300ms] 350ms pause (utterance end)
```

---

## Related Documentation

- `.claude/context/flute-gateway.md` - Flute API reference
- `pmoves/docs/context/PMOVES Multimodal Communication Layer (Flute) – Architecture & Roadmap.md` - Full architecture
- `.claude/context/nats-subjects.md` - Voice NATS subjects (`voice.tts.*`)
- `.claude/context/voice-personas.md` - Voice persona system

---

## Module Structure

```
pmoves/services/flute-gateway/prosodic/
├── __init__.py           # Module exports
├── types.py              # BoundaryType, ProsodicChunk, PauseConfig
├── boundary_detector.py  # detect_boundary(), find_chunk_points()
├── syllable_counter.py   # estimate_syllables()
├── prosodic_parser.py    # parse_prosodic() main function
└── audio_processor.py    # Audio stitching and breath insertion
```

---

## Future Enhancements

- **Emotion-aware pausing**: Longer pauses for sad/thoughtful content
- **Speaker turn detection**: Different prosody at speaker boundaries
- **Language-specific rules**: French liaison, German compound words
- **Intonation modeling**: Use `position_ratio` for rising/falling pitch
