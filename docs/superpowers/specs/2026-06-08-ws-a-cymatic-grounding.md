# WS-A Cymatic Grounding (addendum)

**Date:** 2026-06-08 · **Author:** 4090-claude · **Status:** implemented (PR pending)
**Extends:** `docs/superpowers/specs/2026-06-03-ws-a-audio-grounding-design.md`

## Why

Cymatics — Chladni figures, vibrating water, "every frequency has its own
geometry" (ref: *Sonic Architecture | Cymatics Decoded*, BassForge, 2026-05-05)
— is the **artistic statement of the WS-A thesis**: audio frequency content maps
to geometric structure. WS-A already does this scientifically (librosa + CLAP →
CGP geometry on a Poincaré **disk** — itself the "radial harmonics / circles"
the cymatics tradition draws). This addendum adds three deterministic features
that make the sound→geometry mapping richer and **visible**.

## Principle: tool can tool, model can model

The cymatics tradition makes claims (528 Hz "DNA repair," etc.) we do **not**
encode as truth. But the underlying signal facts are deterministic and real. We
**detect** a 528 Hz peak with an FFT and **tag** it as a culturally-named
frequency; we make **no** health/esoteric claim. The science grounds the magic;
the magic motivates the science. Any interpretation is left to the model tier
(CLAP/AST), never asserted by the tool tier.

## Features (implemented in `pmoves/tools/cymatic.py`)

### 1. Harmonicity / symmetry — "more harmony = more symmetry"
`harmonicity_symmetry(y, sr) -> dict`:
- `harmonic_ratio` [0,1] — harmonic energy fraction (librosa HPSS)
- `tonality` [0,1] — `1 - spectral_flatness` (noise→0, tonal→1)
- `n_fold` ∈ {2,3,4,6,12} — dominant rotational self-similarity of the 12 pitch
  classes (chord/scale symmetry, via circular chroma autocorrelation)
- `rotational_symmetry` [0,1] — strength of that fold
- `symmetry` [0,1] — composite

### 2. Named-frequency detection (scientific, no claims)
`named_frequency_tags(y, sr, tol_cents=60, top_k=6) -> list[{name,target_hz,peak_hz,magnitude}]`:
- Hann-windowed rFFT magnitude; for each entry in `NAMED_FREQUENCIES` (schumann
  7.83, gamma 40, a432, solfeggio set, …), report the in-band peak if ≥ 5% of
  the spectral max. Detection only — names are cultural labels.

### 3. Cymatic glyph — the visual bridge (→ Z890 / website)
`cymatic_glyph(n_fold, m_radial, dominant_hz, size=256) -> {svg, n_fold, m_radial, dominant_hz}`:
- Deterministic Chladni nodal pattern of a **circular** membrane mode: `n_fold`
  nodal diameters + `m_radial` nodal circles — the radial-harmonic look. Pure
  geometry (no deps), `currentColor` so the site theme drives the stroke.
- `glyph_params_from_features(feat)` derives `(n_fold, m_radial, dominant_hz)`
  from the analyzer features (n_fold from rotational symmetry; m_radial from
  onset density; dominant_hz from the top named frequency or spectral centroid).

## Integration

- `analyze_beats.librosa_features_from_array` now returns `feat["cymatic"]`
  (graceful `{}` on failure) → flows into the CGP `point.meta` via the existing
  `beats_to_cgp` path. No schema change required (meta is open).
- The glyph is a **standalone** deterministic function: the website (Z890) calls
  `cymatic_glyph(**glyph_params_from_features(point.meta.cymatic))` to render the
  audio's geometry — 4090 forges signal→geometry, Z890 paints it.

## Validation

`pmoves/tools/tests/test_cymatic.py` — 10 deterministic tests: symmetry ranges,
harmonic-vs-noise tonality, 528 Hz / a432 detection, silence→empty, glyph SVG
structure (n nodal diameters + m+1 circles) + determinism + degenerate clamps,
reproducibility. No new dependencies (librosa + numpy already in WS-A).

## Future (model tier)

The CLAP/AST semantic layer can **interpret** the cymatic geometry (e.g.,
"this track's 5-fold symmetry + 528 Hz energy reads as meditative") — the model
models; the tool only measures. Possible next: true Bessel circular-membrane
modes for the glyph; per-beat glyph animation for the live A2UI surface.
