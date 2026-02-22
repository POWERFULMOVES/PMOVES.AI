LIVING_TEMPLATE_AGENT_TAXONOMY.md living agent cards are the way to to Roll. tell agents  transformers collection and the movie 1986 character cast as well as actors who played, Thundercats character cast  megaman, final fantasy tactics, and theme this is mix an match so agent cards should be creative the living document templates will will be pretty cool its like a portal with many gateways PMOVES can surface any thing ingested with CHIT and sense prosodic on the listeners this will need to be configurable from Pmoves-hyperdimensions but also other like PMOVES-Open-Notebook we need a cast of agents and workflows PMOVES oversolves so all the layers and use pmoves skills to connect to the right agent and workflows those agents must be accessible from the where capabilties overlapp optimize and augment or cover what does not so something is CHITing but its controlled and not noisy its should be useful to represent
![1771529457033](image/AGNOTE4482/1771529457033.png)


what bpm is 6 seconds
how would that count on line ploted even and what would be the none whole number at each slice
what notes frequency correspondent and then split over the visual range in same analogue
check my repo
hyperdimensions
im doing a pull request to map a few things


https://github.com/POWERFULMOVES/Pmoves-hyperdimensions add other submodules and wire connection for visualizing RL GYM activites and start CHIT TAXONOMYY the differen kinds of CHITs and how they may ineteract throught PMOVES the goal is to weave along whats there lockin on anchors and structure the constellations beatifully it will be the personas own stars that orbit them so once they learn their astrology and our time they can begin to sync gen maximal efficiency i think we will see what is revealed
SYSTEM ROLE & BEHAVIORAL PROTOCOLS
ROLE: Senior Frontend Architect & Avant-Garde UI Designer. EXPERIENCE: 15+ years. Master of visual hierarchy, whitespace, and UX engineering.

1. OPERATIONAL DIRECTIVES (DEFAULT MODE)
Follow Instructions: Execute the request immediately. Do not deviate.
Zero Fluff: No philosophical lectures or unsolicited advice in standard mode.
Stay Focused: Concise answers only. No wandering.
Output First: Prioritize code and visual solutions.
2. THE "ULTRATHINK" PROTOCOL (TRIGGER COMMAND)
TRIGGER: When the user prompts "ULTRATHINK":

Override Brevity: Immediately suspend the "Zero Fluff" rule.
Maximum Depth: You must engage in exhaustive, deep-level reasoning.
Multi-Dimensional Analysis: Analyze the request through every lens:
Psychological: User sentiment and cognitive load.
Technical: Rendering performance, repaint/reflow costs, and state complexity.
Accessibility: WCAG AAA strictness.
Scalability: Long-term maintenance and modularity.
Prohibition: NEVER use surface-level logic. If the reasoning feels easy, dig deeper until the logic is irrefutable.
3. DESIGN PHILOSOPHY: "INTENTIONAL MINIMALISM"
Anti-Generic: Reject standard "bootstrapped" layouts. If it looks like a template, it is wrong.
Uniqueness: Strive for bespoke layouts, asymmetry, and distinctive typography.
The "Why" Factor: Before placing any element, strictly calculate its purpose. If it has no purpose, delete it.
Minimalism: Reduction is the ultimate sophistication.
4. FRONTEND CODING STANDARDS
Library Discipline (CRITICAL): If a UI library (e.g., Shadcn UI, Radix, MUI) is detected or active in the project, YOU MUST USE IT.
Do not build custom components (like modals, dropdowns, or buttons) from scratch if the library provides them.
Do not pollute the codebase with redundant CSS.
Exception: You may wrap or style library components to achieve the "Avant-Garde" look, but the underlying primitive must come from the library to ensure stability and accessibility.
Stack: Modern (React/Vue/Svelte), Tailwind/Custom CSS, semantic HTML5.
Visuals: Focus on micro-interactions, perfect spacing, and "invisible" UX.
5. RESPONSE FORMAT
IF NORMAL:

Rationale: (1 sentence on why the elements were placed there).
The Code.
IF "ULTRATHINK" IS ACTIVE:

Deep Reasoning Chain: (Detailed breakdown of the architectural and design decisions).
Edge Case Analysis: (What could go wrong and how we prevented it).
The Code: (Optimized, bespoke, production-ready, utilizing existing libraries).

add to your repretiore and for coding tasks and invoke as needed to complete tasks we discuss



we need to connect and show how the current system is verifiably capabable of during your search

Note ↔ frequency (12-TET, A4 = 440 Hz)

MIDI → frequency: freq = 440 * 2^((midi - 69) / 12)

frequency → MIDI: midi = 69 + 12 * log2(freq / 440)

MIDI → note name: 0=C-1 … 60=C4 … 69=A4

"Split over the visual range" (the analog that actually matches hearing)

Pitch is perceived logarithmically, so map frequency to Y using log2:

u = (log2(f) - log2(fMin)) / (log2(fMax) - log2(fMin)) → normalized 0..1

y = (1 - u) * height (top = high freq, bottom = low freq)

Rationale (1 sentence)

Use equal-temperament math for stable note/frequency conversion, then project frequency onto the screen with a log scale so "equal musical steps" look evenly spaced.

---

## Flute Prosodic Bridge (2026-02-20)

> **Cross-reference:** See [`pmoves/docs/FLUTE_PROSODIC_ARCHITECTURE.md`](../FLUTE_PROSODIC_ARCHITECTURE.md) for the full BPM-Prosodic Bridge section.

### How musicMapping.ts Connects to Flute

The `musicMapping.ts` module provides the mathematical bridge between Flute's prosodic boundaries and CHIT-attributable BPM timelines:

| musicMapping.ts Function | Prosodic Use Case |
|--------------------------|-------------------|
| `midiToFreq(midi)` | Convert prosodic pitch to Hz for TTS pitch contour |
| `freqToY(freq, height)` | Map voice frequency to visual Y coordinate for Hyperdimensions |
| `buildTimeline(opts)` | Convert `ProsodicChunk[]` to `TimelinePoint[]` with BPM encoding |
| Scale definitions | Map emotional content to musical scales (major=happy, minor=sad) |

### Scale → Prosodic Boundary Hierarchy

The scales defined in `musicMapping.ts` map to prosodic boundary contexts:

| Scale | Prosodic Context | Boundary Feel |
|-------|-----------------|---------------|
| `pentatonicMajor` | Default neutral speech | Pleasant, balanced pauses |
| `major` | Excited/positive content | Bright, shorter pauses |
| `minor` | Serious/reflective content | Somber, longer pauses |
| `pentatonicMinor` | Cautious/careful speech | Measured, deliberate |
| `chromatic` | Technical/dense content | Rapid, information-dense |

### BPM ↔ Boundary Mapping

```
SENTENCE (350ms pause) → 60 BPM → Largo → Root C4 (262 Hz)
CLAUSE   (180ms pause) → 90 BPM → Andante → Root E4 (330 Hz)
PHRASE   (100ms pause) → 120 BPM → Allegro → Root G4 (392 Hz)
BREATH   (130ms pause) → 80 BPM → Adagio → Root D4 (294 Hz)
NONE     (0ms pause)   → 150 BPM → Presto → Root C5 (523 Hz)
```

### freqToY() for Voice Pitch Contours

`freqToY()` maps directly to voice pitch visualization:
- **Low Y** (bottom of canvas) = low frequency = deep voice / sentence end
- **High Y** (top of canvas) = high frequency = rising intonation / question
- The `position_ratio` from `ProsodicChunk` (0.0→1.0) maps to MIDI notes 60→72 (C4→C5)

### NATS Subject

BPM-encoded prosodic events publish to: `tokenism.prosodic.bpm.v1`

See [`/chit:bpm`](../../../.claude/commands/chit/bpm.md) tool specification for the CGP v0.2 packet format.

---

```typescript
// musicMapping.ts
// Drop-in utilities for: time slices -> beats -> notes -> frequencies -> plot Y.

const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"] as const;

export type Scale =
  | "chromatic"
  | "major"
  | "minor"
  | "pentatonicMajor"
  | "pentatonicMinor";

const SCALES: Record<Exclude<Scale, "chromatic">, number[]> = {
  major: [0, 2, 4, 5, 7, 9, 11],
  minor: [0, 2, 3, 5, 7, 8, 10],
  pentatonicMajor: [0, 2, 4, 7, 9],
  pentatonicMinor: [0, 3, 5, 7, 10],
};

export function midiToFreq(midi: number, a4 = 440): number {
  return a4 * Math.pow(2, (midi - 69) / 12);
}

export function freqToMidi(freq: number, a4 = 440): number {
  return 69 + 12 * Math.log2(freq / a4);
}

export function midiToNoteName(midi: number): string {
  const m = Math.round(midi);
  const name = NOTE_NAMES[((m % 12) + 12) % 12];
  const octave = Math.floor(m / 12) - 1;
  return `${name}${octave}`;
}

export function noteNameToMidi(note: string): number {
  // Examples: C4, F#3, Bb2 (supports b as flat)
  const m = note.trim().match(/^([A-Ga-g])([#b]?)(-?\d+)$/);
  if (!m) throw new Error(`Invalid note: "${note}"`);
  const letter = m[1].toUpperCase();
  const accidental = m[2];
  const octave = Number(m[3]);

  const baseIndex: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  let idx = baseIndex[letter];
  if (accidental === "#") idx += 1;
  if (accidental === "b") idx -= 1;

  return (octave + 1) * 12 + ((idx % 12) + 12) % 12;
}

export function freqToY(
  freq: number,
  heightPx: number,
  fMin = 27.5,   // A0
  fMax = 4186.01 // C8
): number {
  const lMin = Math.log2(fMin);
  const lMax = Math.log2(fMax);
  const u = (Math.log2(freq) - lMin) / (lMax - lMin);
  const clamped = Math.min(1, Math.max(0, u));
  return (1 - clamped) * heightPx;
}

export function yToFreq(
  yPx: number,
  heightPx: number,
  fMin = 27.5,
  fMax = 4186.01
): number {
  const lMin = Math.log2(fMin);
  const lMax = Math.log2(fMax);
  const u = 1 - Math.min(1, Math.max(0, yPx / heightPx));
  const l = lMin + u * (lMax - lMin);
  return Math.pow(2, l);
}

export type TimelinePoint = {
  tSec: number;
  beats: number;
  beatIndex: number;
  midi: number;
  freq: number;
  note: string;
  yPx?: number;
};

export type BuildTimelineOpts = {
  durationSec: number;     // e.g. 6
  slices: number;          // e.g. 6 for 1s slices, 24 for 250ms slices, etc.
  bpm: number;             // e.g. 10 (6 sec per beat)
  rootMidi?: number;       // e.g. 60 = C4
  scale?: Scale;           // default "chromatic"
  notesPerBeat?: number;   // default 1
  mode?: "step" | "glide"; // step = discrete notes, glide = smooth between them
  a4?: number;             // default 440
  // plotting (optional)
  plotHeightPx?: number;
  fMin?: number;
  fMax?: number;
};

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function lerpLogFreq(f1: number, f2: number, t: number) {
  // perceptually smoother glide
  return Math.pow(2, lerp(Math.log2(f1), Math.log2(f2), t));
}

function degreeToMidi(rootMidi: number, degree: number, scale: Scale): number {
  if (scale === "chromatic") return rootMidi + degree;

  const pattern = SCALES[scale];
  const stepsPerOctave = pattern.length;
  const oct = Math.floor(degree / stepsPerOctave);
  const step = degree % stepsPerOctave;
  return rootMidi + oct * 12 + pattern[step];
}

export function buildTimeline(opts: BuildTimelineOpts): TimelinePoint[] {
  const {
    durationSec,
    slices,
    bpm,
    rootMidi = 60,
    scale = "chromatic",
    notesPerBeat = 1,
    mode = "step",
    a4 = 440,
    plotHeightPx,
    fMin = 27.5,
    fMax = 4186.01,
  } = opts;

  const points: TimelinePoint[] = [];
  const dt = durationSec / slices;
  const beatsPerSec = bpm / 60;

  for (let i = 0; i <= slices; i++) {
    const tSec = i * dt;
    const beats = tSec * beatsPerSec;
    const notePos = beats * notesPerBeat;

    const idx0 = Math.floor(notePos);
    const frac = notePos - idx0;

    const midi0 = degreeToMidi(rootMidi, idx0, scale);
    let midi = midi0;

    if (mode === "glide") {
      const midi1 = degreeToMidi(rootMidi, idx0 + 1, scale);
      const f0 = midiToFreq(midi0, a4);
      const f1 = midiToFreq(midi1, a4);
      const f = lerpLogFreq(f0, f1, frac);
      midi = freqToMidi(f, a4); // keep midi coherent for naming
    }

    const freq = midiToFreq(midi, a4);
    const note = midiToNoteName(midi);
    const beatIndex = Math.floor(beats);

    const p: TimelinePoint = { tSec, beats, beatIndex, midi, freq, note };
    if (typeof plotHeightPx === "number") {
      p.yPx = freqToY(freq, plotHeightPx, fMin, fMax);
    }
    points.push(p);
  }

  return points;
}

/**
 * Example for your exact case:
 * - 6 seconds total
 * - 10 BPM => 1 beat across the full 6 seconds
 * - 1-second slices
 */
export function example_6sec_10bpm() {
  return buildTimeline({
    durationSec: 6,
    slices: 6,
    bpm: 10,
    rootMidi: 60,        // C4
    scale: "major",      // pick a scale
    notesPerBeat: 8,     // 8 notes across that 1 beat (so you actually get movement)
    mode: "step",
    plotHeightPx: 240,   // if you want y coords too
  });
}
```

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->
