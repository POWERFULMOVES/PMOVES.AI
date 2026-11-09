# Holographic Music Video — Recipe v1 (darkxside corpus)

- Date: 2026-09-16 · Status: DRAFT, pre-calibration · Author: A0 (crush-spark dispatch; Mavis wire was dark)
- Vision anchor (operator): "holographic music video songs beats art 3d designs"
- Corpus: `pmoves/data/beats/soundcloud/darkxside/` (86 tracks, BPM embedded in some filenames)
- Tempo classes: playlist names under `pmoves/data/beats/playlists/` (e.g. `Allegro_balanced_Bright_*`)

## 0. Ground truth vs assumptions

Verified (dispatch + fleet context):

- ComfyUI H3 live at `http://localhost:8189` **on the GB10 host**; V3 chain rendered a 119s piece; double-slit colors video at 36s.
- Corpus and playlist dirs are NOT mounted in the authoring container (checked; empty) — run calibration/render steps from GB10.

Assumptions (calibrate before first burn):

- `Shaelamix1loudLONG 183bpm` = 183 BPM, extended arrangement ("LONG"), loud master.
- i2v cost scales ~linearly with frame count; no hard per-frame timing measured yet.

## 1. Beat pick

**Track: `Shaelamix1loudLONG 183bpm`**

| Criterion | Fit |
|---|---|
| Tempo | 183 BPM is the fastest explicit filename tag sampled → densest BPM-cut grid (beat = 328 ms); half-time pocket (656 ms) reads as heavy sway |
| Energy | "1loud" + LONG arrangement → sustained drops that carry strobe/bloom peaks without dead air |
| Palette | `Allegro_balanced_Bright_*` class neighbors → bright/iridescent material pairs with holographic chromatic dispersion (double-slit precedent) |
| 3D fit | Loud sustained bed keeps orbit-cam lattice/fracture scenes alive between cuts |

Runner-up: an `Allegro_balanced_Bright_*` track at 140–160 BPM if the LONG arrangement proves hard to cut below 2:00.

Pre-lock QC (on GB10): run `librosa.beat.beat_track` on the WAV; if measured tempo drifts ±3 BPM from 183, re-derive the grid from the measured value.

## 2. Beat-synced visual plan

Grid @ 183 BPM, 4/4: beat 0.3279 s · bar 1.3115 s · 4-bar phrase 5.246 s · scene (2 phrases) 10.49 s · 8 scenes = 83.9 s (1:24).

Cut rules:

- Intro/outro: hold one phrase per shot (calm).
- Mid energy: hard cut every 2 bars (2.62 s).
- Drops (S3/S4/S6/S7): cut per bar (1.31 s) plus 656 ms (2-beat) strobe inserts.
- Downbeat flash frames (white/prism) only on the first beat of drop phrases.

| # | Scene | Start | Energy | Visual |
|---|---|---|---|---|
| 1 | Void | 0:00.0 | low | black chamber, single laser line, drifting dust |
| 2 | Ignition | 0:10.5 | build | first drop: volumetric hologram blooms from the line |
| 3 | Lattice | 0:21.0 | high | wireframe holographic cathedral, slow orbit cam |
| 4 | Diffraction | 0:31.5 | high | double-slit homage: beam splits into RGB spectrum fans |
| 5 | Pulse chamber | 0:42.0 | half-time | strobing glass solids locked to the 656 ms pocket |
| 6 | Bloom cascade | 0:52.5 | peak | particle caustics, holographic petals shattering |
| 7 | Fracture | 1:03.0 | peak | glitch shatter, fastest cuts (per-bar + inserts) |
| 8 | Dissolve | 1:13.4 | tail | return to void, prism logo card, fade |

Arc: void → bloom → peak fracture → void. Every scene boundary lands on a phrase boundary (t = 2k × 5.246 s).

## 3. ComfyUI workflow skeleton

Stage A — text2image keyframes (12 images: 8 scene anchors + 4 strobe inserts):

- SDXL/Flux class @ 1920×1080 (or 1280×720 proxy → upscale if VRAM-tight); fixed seed per scene.
- Style token block: `iridescent holographic, volumetric light, chromatic dispersion, glass refraction, dark background, cyan-magenta-gold spectrum, 3d render, octane`
- Coherence: same style block everywhere + IPAdapter reference anchored on the S2 keyframe.

Stage B — image2video segments (16 segments = 2 per scene, 1 phrase each):

- Per segment: keyframe → 64 frames @ 12 fps (5.33 s raw, trimmed to the 5.246 s grid), Wan2.1/SVD-class i2v on GB10.
- Scene phrase B reuses the anchor keyframe with an alternate motion prompt (cheap variation).
- Motion prompt = scene verb (orbit / strobe / shatter / bloom) + style block; denoise 0.5–0.7 to hold keyframe identity.
- RIFE/VFI ×2 → 24 fps (≈128 frames per segment).
- Node chain: `LoadImage → i2v → RIFE → VideoCombine`; queue via POST `/prompt` (API-format JSON), poll `/history`.

Stage C — BPM-cut assembly (ffmpeg on host):

1. `ffprobe` each segment; trim/pad to exact 5.246 s multiples (bar-locked grid).
2. Concat: hard cuts on drops; 2-frame (83 ms) `xfade` everywhere else.
3. Insert the 4 strobe frames at downbeats of S4/S7.
4. Mux the Shaelamix WAV (`loudnorm`), export 1080p24 H.264 CRF 18 + poster keyframe.

## 4. Render budget on GB10

| Item | Count | Unit cost | Total |
|---|---|---|---|
| Keyframes | 12 | ~3–8 s (SDXL, assumed) | ~1–2 min |
| i2v segments | 16 × 64f | **calibrate: 1 test segment** | 16 × t_seg |
| RIFE + encode | 16 | ~10–20 s (assumed) | ~4–6 min |
| Assembly | 1 pass | CPU-bound | <5 min |

Mandatory calibration run: render S5 as a single 64-frame segment first, measure t_seg, then extrapolate:

- total_i2v ≈ 16 × t_seg → t_seg 10 min ⇒ ~2.7 h; t_seg 20 min ⇒ ~5.3 h (book an overnight slot worst case).
- Sanity envelope: target 84 s sits between the 36 s and 119 s precedents; 16 discrete segments cost more than one contiguous run of equal length, so expect the upper band until measured.

Budget savers, in order: (1) 12 segments — S1/S8 drop to 1 phrase; (2) 48f @ 12 fps with 1.5× RIFE; (3) 720p master.

## 5. Open items

- Confirm WAV/stem path + true BPM on GB10 (librosa check) before locking the grid.
- Confirm which i2v checkpoint H3 has loaded (Wan2.1 vs SVD); pick by VRAM headroom.
- Scene 8 logo/card asset: operator-supplied or AI-generated in Stage A.
