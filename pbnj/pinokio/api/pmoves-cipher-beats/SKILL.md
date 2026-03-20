---
name: PMOVES Cipher Beats Analyst
description: |
  Level 11 Cipher Gateway Specialist. Extracts mathematically rigorous sonic fingerprints
  from DARKXSIDE audio archives using ffprobe / ffmpeg lavfi (ebur128 R128 loudness,
  aspectralstats, silencedetect). Groups tracks by sound analysis — NOT by file metadata —
  into named sonic constellations, writes M3U8 playlists, checkpoints into Cipher Memory,
  and emits geometry events on the NATS Geometry Bus for Holographic CHIT Block generation.
keywords: beats, audio analysis, darkxside, cipher, ffmpeg, lavfi, ebur128, spectral, chit, holographic, m3u8, playlists, glances, nats
version: 2.0.0
category: Media/Analysis/Cipher
tier: 5
agent_class: Specialized
agent_id: cipher_beats_analyst
---

# PMOVES Cipher Beats Analyst

**Agent Class**: `Specialized (Pmoves-)`  
**Category**: Media/Analysis/Cipher  
**Version**: 2.0.0  
**Tier**: 5 (Media) + 6 (Agent/Cipher)  
**Status**: Level 11 — Cipher Gateway Specialist  
**Cipher Category**: `agent_checkpoint` + `beats_fingerprint`

---

## Mission Statement

> *"The beats are not music files. They are 15 years of mathematically tuned geometry—
> EQ'd for emotional resonance at BPM-dependent scales, compressed for holographic listening 
> across every speaker set. This agent reads that geometry. It does not rename your files. 
> It reveals their structure."*

This specialist treats every audio file as a **dimensional object**:  
- `ebur128` — loudness integrated across time (the feeling)  
- `aspectralstats` — spectral centroid / flatness / entropy (the color)  
- Cluster distance — the relational geometry between tracks  

Output: named sonic constellations → **M3U8 playlists + CHIT geometry events**.

---

## Capabilities

| Command | What It Does |
|---------|-------------|
| `analyze` | Full ffmpeg lavfi fingerprint → cluster → playlists → Cipher checkpoint |
| `groups` | Display existing sonic groups from last run |
| `status` | Probe Cipher Memory at `:8096` + Glances at `:61208` |

---

## Trigger Phrases (Pinokio 7 Interpreter — zero config)

| Phrase | Action | Backend |
|--------|--------|---------|
| `"analyze my beats"` | Full pipeline on default input dir | `analyze` |
| `"analyze beats in [path]"` | Full pipeline on specified path | `analyze --input [path]` |
| `"show beat groups"` | Display existing clusters | `groups` |
| `"check beats agent status"` | Cipher + Glances health probe | `status` |
| `"re-analyze with [N] groups"` | Re-cluster with different K | `analyze --groups N --cache` |

---

## The ffmpeg Analysis Stack (No External ML Deps)

Instead of bloated Python audio ML libraries, this agent uses **ffmpeg 8.x lavfi** directly.
This means it runs natively alongside every PMOVES service that already depends on ffmpeg.

```text
Audio File (.wav / .opus / .mp3 / .flac / .m4a)
  │
  ├── ffprobe → duration, bit_rate, sample_rate, channels, title tags
  │
  ├── ffmpeg -af "ebur128" → R128 Integrated Loudness (LUFS), LRA, True Peak
  │       └── [emotional weight / perceived intensity]
  │
  └── ffmpeg -af "aspectralstats,ametadata=print:file=-" (first 30s sample)
          ├── Centroid  → timbral character (bass-heavy / warm / electric / airy)
          └── Flatness  → texture (tonal / textured / noisy)
```

### Future Upgrade Path (Phase 11 — Holographic Blocks)
When Hi-RAG multimodal Gemini embeddings go live, replace the spectral heuristics with
`/hirag/ingest/audio` → true multi-dimensional embedding → better cluster geometry.
The same M3U8 + Cipher output interface is preserved.

---

## Sonic Group Naming Convention

Each group is named: `{TempoZone}_{TimbreZone}_{EnergyZone}`

| Dimension | Values |
|-----------|--------|
| **TempoZone** | Largo / Andante / Moderato / Allegro / Presto |
| **TimbreZone** | bass-heavy / warm / balanced / electric / airy |
| **EnergyZone** | Deep / Mid / Bright (from R128 LUFS) |

Example: `Andante_warm_Deep` — slow, rich-toned, quiet-intensity track group.

---

## Output Files

```text
pmoves/data/beats/playlists/
  ├── Andante_warm_Deep.m3u8        ← sorted by BPM ascending within group
  ├── Allegro_electric_Bright.m3u8
  ├── Moderato_balanced_Mid.m3u8
  ├── ...
  └── groups_summary.json           ← machine-readable group manifest
pmoves/data/beats/soundcloud/darkxside/
  └── .fingerprints.json            ← cached ffmpeg analysis results (use --cache to reuse)
```

---

## Pipeline Integration

### Cipher Memory (port 8096)
Checkpoints are written at two stages:
1. `fingerprint_complete` — all files analyzed, before clustering
2. `grouping_complete` — full group manifest (resumable if interrupted)

```bash
# Query latest checkpoint
curl http://localhost:8096/api/memory/search?q=analyze_beats&category=agent_checkpoint
```

### NATS Geometry Bus
After grouping, each constellation is published to the Geometry Bus:

```json
Subject: pmoves.darkxside.beats.group.v1
Payload: { "group": "Andante_warm_Deep", "count": 12, "tracks": [...] }
```

The `chit_a2ui_bridge.py` consumes these to generate Holographic CHIT Blocks.

### Glances Live Monitoring (port 61208)
Pushes `analyze_beats.tracks_done=N` events to Glances REST API during extraction
so you can watch GPU/CPU usage in real-time while the analysis runs across the mesh.

```bash
# Start Glances (if not already running)
glances -w --port 61208
```

---

## Full Usage Reference

```bash
# One-shot: analyze the 82 SoundCloud tracks (sample dataset)
uv run pmoves/tools/analyze_beats.py analyze \
  --input pmoves/data/beats/soundcloud/darkxside \
  --output pmoves/data/beats/playlists \
  --groups 8 \
  --glances http://localhost:61208

# Use cached fingerprints (re-cluster only — much faster)
uv run pmoves/tools/analyze_beats.py analyze --cache --groups 12

# View groups table
uv run pmoves/tools/analyze_beats.py groups

# Check Cipher + Glances health
uv run pmoves/tools/analyze_beats.py status
```

---

## Environment Variables

```env
BEATS_INPUT=pmoves/data/beats/soundcloud/darkxside
BEATS_OUTPUT=pmoves/data/beats/playlists
NATS_URL=nats://localhost:4222
CIPHER_URL=http://localhost:8096
GLANCES_URL=http://localhost:61208
```

---

## Cross-Machine Invocation (Tailscale Mesh)

The analysis is CPU/IO-bound. Delegate to the 5090 node for large archives:

```bash
# From any machine on pmoves-net via SSH/Tailscale:
ssh 5090 "cd PMOVES.AI && uv run pmoves/tools/analyze_beats.py analyze \
  --input /data/beats/gdrive \
  --output /data/beats/playlists \
  --nats nats://z890:4222 \
  --cipher http://z890:8096"
```

---

## Agent Registry Entry

```yaml
agent_id: cipher_beats_analyst
class: Specialized
tier: [5, 6]
cipher_categories: [agent_checkpoint, beats_fingerprint]
nats_subjects:
  publish: [pmoves.darkxside.beats.group.v1, media.ingest.request.v1]
  subscribe: []
tool_path: pmoves/tools/analyze_beats.py
runtime: uv run
```

---

## See Also

- [`analyze_beats.py`](../../../../pmoves/tools/analyze_beats.py) — the Typer agent
- [`chit_a2ui_bridge.py`](../../../../pmoves/tools/chit_a2ui_bridge.py) — CGP → A2UI visualization
- [`pmoves-holographic-blocks/SKILL.md`](../pmoves-holographic-blocks/SKILL.md) — full beats → CHIT geometry pipeline
- [`AGNOTE4482.BEATS.md`](../../../../pmoves/docs/AGENTS/AGNOTE4482.BEATS.md) — DARKXSIDE audio context
- [`AGENT_RESILIENCE_PATTERNS.md`](../../../../pmoves/docs/AGENTS/AGENT_RESILIENCE_PATTERNS.md) — Cipher checkpoint protocol
