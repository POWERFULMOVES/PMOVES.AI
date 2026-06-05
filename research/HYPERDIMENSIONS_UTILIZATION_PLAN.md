# Hyperdimensions: "Proper Utilization" Program — Plan

**Status:** planning (draft for review). Author: 4090-claude, 2026-06-02.
**Trigger:** gallery holograms look identical; "review the dev's video to ensure we map correctly."

## Source-of-truth: the dev's paradigm (Emergent Garden, *Creatures in Higher Dimensions*)
- A surface is `surface(input) → {x,y,z, r,g,b,a}`. Inputs: `u,v` (always) + named params.
- **Params are genes/knobs (genotype); the rendered shape+color is the phenotype.** Distinct genes ⇒ distinct creatures.
- Up to **7 outputs**: `xyz` (shape) + `rgba` (color), each driven by *independent* logic.
- **`t` = time** → surfaces evolve (now auto-played, shipped 2026-06-02).
- **Output conversions** (no code change, set in Outputs): `xyz`→spherical/cylindrical; `rgb`→hsv.
- `math` lib `m` available (matrices, complex) → fractals/chaos.

## Current state (what's live, what's wrong)
- ✅ Live viewer renders; legacy-schema presets load (schema-B shim); presets auto-animate; CTAs deep-link to presets.
- ❌ **Gallery beats_c1/c3/c5 look identical.** Root cause: all three are "Allegro balanced" clusters drawn by the **same toroid formula**; param deltas are subtle; `hue = hz·2π + u` sweeps the *full* rainbow regardless of `hz`. Genotype differs slightly; phenotype barely moves.

## Pipeline (real files)
```text
beats audio → pmoves/tools/beats_to_cgp.py   (track→state_vector: delta/Hz/kappa/A/F; groups→CGP)
            → pmoves/tools/chit_a2ui_bridge.py (CGP → A2UI spec + preset surface.code; inferred_shape)
            → Pmoves-hyperdimensions/saves/*.json  (live Three.js viewer presets)
            → pmoves/services/a2ui-renderer/src/remotion/*.tsx  (Remotion → baked .mp4)
```
CGP semantics (beats_to_cgp.py): `delta`=tempo(0=Largo,1=Presto), `Hz`=centroid(0=bass,1=airy), `kappa`=loudness-LRA→curvature(−1–0), `A`=flatness→tonal-clarity(1=tonal), `F`=coherence→group fitness.

---

## WS2 — CGP→geometry mapping (KEYSTONE; do first)
**Goal:** make each cluster's state vector produce a *visibly distinct* phenotype, per the genotype→phenotype paradigm.

**Design directions (to decide during this WS):**
1. **Amplify, don't whisper.** Map features to *structural* axes, not just amplitude tweaks:
   - `delta` (tempo) → **lobe count / winding** (Largo = few smooth lobes; Presto = many tight lobes) — discrete, highly visible.
   - `kappa` (dynamic range) → **warp depth / spikiness**.
   - `F` (coherence) → **closure/symmetry** (tight group = clean closed surface; loose = broken/scattered).
   - `A` (tonal clarity) → **surface smoothness vs noise** (tonal = smooth; noisy = turbulent/fractal via `m`).
2. **Color as identity, not rainbow.** Replace full-sweep `hue=hz·2π+u` with `Hz`→**base hue** + `A`→**saturation** + `F`→**value/brightness**, so each cluster has a recognizable palette (bass=warm/red, airy=cool/blue).
3. **Shape archetype by dominant feature** (optional): pick toroid vs spherical (coord-conversion) vs knot per the cluster's strongest axis → categorically different silhouettes.

**Steps:**
1. Read `chit_a2ui_bridge.py` surface-code generation + `inferred_shape` logic (where the toroid template lives).
2. Write a **mapping spec** (feature → geometry axis + color channel) as a short doc + a parametric `surface.code` template that *consumes* delta/kappa/Hz/A/F meaningfully.
3. Regenerate beats_c1/c3/c5 (+ a couple more clusters) through the updated bridge.
4. Verify distinctness live (chrome screenshots side-by-side) — they must be obviously different.

**Deliverable:** updated `chit_a2ui_bridge.py` template + regenerated presets. Fork PR (presets) + main PR (bridge).

---

## WS1 — Distinct gallery (depends on WS2; quick interim available)
**Proper:** once WS2 yields distinct beats, the 3 tiles differ naturally — keep the "beats pipeline" theme.
**Interim (no WS2):** point the 3 tiles at 3 already-distinct presets (e.g. a beat + CHIT Manifold + a topology) and adjust the caption. Fast visible win.
**Decision needed:** keep gallery as **beats-only** (requires WS2) or **mixed PMOVES geometry** (interim, ships now)?

**Deliverable:** `website/index.html` gallery iframe srcs (+ caption). Small main PR.

---

## WS3 — Remotion render pipeline (depends on WS2)
**Goal:** bake per-cluster hologram `.mp4`s via `a2ui-renderer` (Remotion) — lightweight, distinct, no live-WebGL/CSP cost.
**Decision needed:** gallery = **live Three.js embeds** (current; interactive) **or baked Remotion videos** (lighter, but static)? Could do both: videos as poster/fallback, live on click.
**Steps:** trace `chit_a2ui_bridge` → A2UI spec → `A2UIComposition.tsx`; confirm geometry reaches the Remotion comp; add a render command/skill; render the WS2 presets.
**Deliverable:** render recipe + gallery `.mp4`s (if we choose baked). Scoped in `pmoves/services/a2ui-renderer` + `skills/remotion-render`.

---

## Dependencies & recommended order
```text
WS2 (mapping) ──► WS1 (gallery uses distinct beats)
              └─► WS3 (render distinct geometry)
```
**WS2 is the keystone.** WS1 has a ship-now interim; WS3 needs the live-vs-baked decision.

## Open questions for DARKXSIDE
1. **Gallery medium:** live Three.js embeds (current) or baked Remotion `.mp4`s?
2. **Gallery content:** beats-only (needs WS2) or mixed (beat + CHIT + topology, ships now)?
3. **Mapping intent:** confirm the feature→visual intent above (e.g. tempo→lobes, centroid→hue, coherence→closure) — this is an artistic call as much as technical.
4. **Scope of regen:** just the 3 gallery clusters, or re-run the whole beats corpus through the new mapping?
