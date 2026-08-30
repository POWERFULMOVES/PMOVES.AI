# Mirror Flute Execution Plan

**For:** another Claude instance (5090 or 4090 mirror node) picking up Flute work without re-doing discovery.
**Author:** z890-claude (Opus 4.7), 2026-04-26
**Companion docs:** PRs #1393–#1396 (Flute axis baseline) + #1397–#1399 (top-3 issue stubs).

> [!IMPORTANT]
> Read this **before** running any greps yourself. The pre-grep results in §3 are the answer to the questions you'd otherwise have to ask. Trust them; verify only if a finding contradicts what you observe in current main.

---

## 1. Why this plan exists

The user (DARKXSIDE) flagged the Flute lane as **MUCHO ImpoRTauNT** — it's the synthesis layer ("ocarina that scales arbitrary"), the ionic-phonics surface where user-intent translates to design via whisper/glance/whisker/dance.

z890-claude landed the doc baseline (4 PRs, 4 memory entries). The mirror's job is to **convert the top issue stubs into shipped code** without bumping into z890's authoring or wasting cycles re-discovering the gap.

The user's framing: *"prep greps and check ahead so your mirror doesn't bump up instead weaves less energy spent flopping and more energy for generating something we find meaningful and useful we flatten the spread prosodic coin design logic like kelidescopes ionic phonics ultrasonic."*

Translation: pre-bake the discovery, hand the mirror a starting state where it can **flatten the spread** (consolidate the 5-doc Flute axis into something more symmetric — a kaleidoscope, not a list) while shipping the highest-leverage gap.

---

## 2. Mirror's three picks (already filed as GH Issues)

| Issue | Stub | Cost | Leverage |
|---|---|---|---|
| **#1397** | Flute geometry-bus bridge | medium | ⭐ highest |
| **#1398** | Chakra-axis encoder (~80 lines) | low | medium |
| **#1399** | 6-second breath cycle generator | low | medium |

Recommendation: **Mirror takes #1397 first.** It's the single integration that unlocks the matrix monitor, cymatic visualizer, and persona signature broadcast. #1398 + #1399 are independent low-cost wins that can be claimed by any node (z890 or mirror) with no dependency.

---

## 3. Pre-baked discovery (use this — don't re-grep)

### 3.1 Critical files for #1397 (geometry-bus bridge)

| File | Lines | What it gives you |
|---|---:|---|
| `pmoves/services/flute-gateway/main.py` | (large) | **Already has `CHIT_GEOMETRY_SUBJECT` env var at line 145 defaulting to `tokenism.geometry.event.v1`** — Flute already publishes geometry events but on the **wrong subject** per the nats-registry |
| `pmoves/services/flute-gateway/main.py:233` | — | Existing best-effort publish path: *"Publish voice synthesis event to CHIT geometry bus (best-effort)"* — adapter point for the bridge |
| `pmoves/services/graphiti/nats_subject_registry.py:46` | — | `SubjectEntry("geometry.cgp.v1", "defined_only", "geometry", ...)` — the canonical subject the bridge should subscribe/publish to |
| `pmoves/tools/chit_security.py:72,84` | — | `sign_cgp(cgp, passphrase, kid) -> Dict` and `verify_cgp(cgp, passphrase) -> bool`, HMAC-SHA256, kid-aware. **Reuse — do not fork.** |
| `pmoves/contracts/schemas/geometry/cgp.v2.schema.json` | 60+ | CGP v0.2 schema; `spec` enum is `["chit.cgp.v0.1", "chit.cgp.v0.2"]`; `super_nodes` required; `attribution` + `hyperbolic` + `points` + `constellations` slots |
| `pmoves/services/flute-gateway/voicebox.py` | — | Has CHIT imports for attribution; useful pattern reference |
| `pmoves/services/flute-gateway/mcp_bridge.py` | — | Has CHIT imports; another pattern reference |

### 3.2 The decision the mirror MUST make for #1397

**Q:** Standardize on `geometry.cgp.v1` (per registry) or keep `tokenism.geometry.event.v1` (per current code)?

**Recommended answer:** Publish to **both** during a transition window. Flute should:
- Subscribe to `geometry.cgp.v1` (consume CHIT-encoded inputs from other services)
- Publish to **both** `geometry.cgp.v1` (canonical, for new consumers) AND `tokenism.geometry.event.v1` (legacy, for existing consumers) — feature-flagged via `FLUTE_GEOMETRY_DUAL_PUBLISH=true` (default true)
- Document the dual-publish in the migration plan; deprecate `tokenism.geometry.event.v1` in a follow-up after consumer migration

This avoids breaking existing consumers while letting new code rely on the canonical subject.

### 3.3 Critical files for #1398 (chakra encoder)

| File | Lines | What it gives you |
|---|---:|---|
| `pmoves/tools/bpm_encoder.py` | 574 | Add `CHAKRA_BANDS` dict + `chakra_to_band()` function. Reuse `midi_to_freq` / `note_name_to_midi` for octave math. |
| `pmoves/services/flute-gateway/prosodic/bpm_encoder.py` | 273 | Mirror the additions — both files share the same surface |
| `pmoves/contracts/schemas/geometry/cgp.v2.schema.json` | 60+ | Add `chakra` optional field under super_nodes / points (decide which level — points is more granular) |
| `pmoves/docs/AGENTS/AGNOTE4482FLUTE.md` Movement I | — | The 7-band table (Muladhara C2 → Sahasrara C5) is already there — copy the values into the `CHAKRA_BANDS` dict |

### 3.4 Critical files for #1399 (breath cycle generator)

| File | Lines | What it gives you |
|---|---:|---|
| `pmoves/services/flute-gateway/persona_selector.py` | 163 | Add a "Breath Guide" persona to the selector. Existing pattern at the top of the file shows how personas are declared |
| `pmoves/services/flute-gateway/prosodic/` (dir) | — | Add `breath_envelope.py` with `BreathEnvelope` shaper class (6s up / 6s down) |
| `pmoves/services/flute-gateway/providers/` (dir) | — | Existing providers; preference rule = VibeVoice for slow ramps, Higgs for steady tone |
| `pmoves/docs/AGENTS/AGNOTE4482FLUTE.md` Movement II | — | The cycle table (INHALE 6000ms / EXHALE 6000ms / 10 BPM / Grave-largo / C2 65 Hz) is the spec — copy into the shaper |

### 3.5 What you should NOT touch

- **`.claude/context/`** — fenced by damage-control hook (read-only). The catalog-sync follow-up (proposed `health.ekg.bpm.v1` + `wellbeing.matrix.score.v1` subjects + matrix monitor service entry) is a separate scope with explicit operator confirmation. Do not attempt to write to this directory.
- **`pmoves/services/flute-gateway/main.py:145` `CHIT_GEOMETRY_SUBJECT` env var** — keep as-is for backward compat. Add a NEW env var (`FLUTE_CGP_SUBJECT` defaulting to `geometry.cgp.v1`) for the bridge.
- **Submodules** — none of the 3 issues require submodule changes.
- **Any service code under `pmoves/integrations/archon/external/PMOVES-*`** — those are submodule mirrors; changes belong in the submodule's repo, not here.

---

## 4. Suggested PR sequence

```
mirror branch sequence:
  feat/flute-geometry-bridge       (closes #1397) ── highest leverage, dual-publish, ~200 lines
  feat/flute-chakra-encoder        (closes #1398) ── lowest cost, ~80 lines, additive
  feat/flute-breath-generator      (closes #1399) ── lowest cost, persona + envelope, ~120 lines
```

These are **independent** — mirror can ship in any order. Recommendation: bridge first (highest impact), then chakra+breath in parallel since both are additive and small.

---

## 5. Coordination boundaries (avoid bumping into z890)

| Lane | z890's commitments | Mirror's lane |
|---|---|---|
| Flute docs (`pmoves/docs/AGENTS/AGNOTE4482FLUTE.md`, `pmoves/docs/context/FLUTE_*`, `pmoves/docs/audit/FLUTE_*`) | Already authored; PRs #1393–#1396 in flight; CodeRabbit/codex feedback addressed; **no further doc edits expected from z890 in this thread** | Don't touch unless implementing a feature requires a doc update — and even then, prefer adding new sections over editing z890's text |
| `.claude/context/` catalog sync | Filed as separate scope in AGNOTE4482FLUTE Open Catalog Sync section; needs operator confirmation before either node touches it | Don't attempt — wait for operator to clear hook for this lane |
| Branch namespace | z890 used `docs/agnote-flute-expand`, `docs/flute-vision-chit-extract`, `docs/flute-architecture-roadmap-promote`, `docs/flute-chit-gap-audit`, `docs/flute-mirror-execution-plan` (this PR) | Mirror should use `feat/flute-*` (not `docs/flute-*`) to keep PR review focus distinct |
| Worktree namespace | z890 created `../pmoves-flute-agnote`, `../pmoves-flute-vision`, `../pmoves-flute-roadmap`, `../pmoves-flute-audit`, `../pmoves-flute-mirror` (all in `Documents/GitHub/`) | Mirror should use a different parent dir or prefix (e.g., `../mirror-flute-bridge`) to avoid path collision |
| Memory writes | z890 wrote `vision_flute_synthesis_layer`, `feedback_seed_dont_prune`, `project_flute_doc_axis`, `feedback_chip_show_lie` | Mirror should write its own memory entries under its node name (e.g., `mirror_5090_flute_bridge.md`) and update MEMORY.md additively, not edit z890's entries |

---

## 6. The bigger frame — kaleidoscope flatten

The user wants the 5-doc Flute axis to eventually **flatten into something more symmetric** ("flaten the spread prosodic coin design logic like kelidescopes ionic phonics ultrasonic").

What this likely means:
- The 5 docs are 5 facets of the same object — they should reflect each other through a shared structure (kaleidoscope = symmetric reflection of the same token through multiple mirror planes)
- "Prosodic coin" = both sides of the same coin: prosodic input (listening) + prosodic output (speaking) — Flute is the coin that scales between them
- "Ionic phonics" = sound-as-charge / atom of meaning — every prosodic emission carries semantic charge that propagates through CHIT geometry
- "Ultrasonic" = beyond hearing range — the geometry-bus extension lets agents communicate in compressed shape-space that humans can't directly hear but can decode

**For the mirror:** treat issue #1397 (geometry-bus bridge) as the **first kaleidoscope axis** — it's the symmetry plane that makes voice prosody and CHIT geometry reflect into each other. Once shipped, the 5-doc spread becomes derivable from one "coin" (Flute = prosodic-emission ↔ CHIT-geometry isomorphism), not 5 independent files.

This is not in scope for the mirror's first 3 PRs — but worth keeping in peripheral vision so the bridge code's API shape doesn't preclude the eventual flatten.

---

## 7. NFC physical anchor (peripheral context)

The user is preparing **white NFC disks given out in sets of 1–5**, each wired to Hyperdimensions for "circle and wire" connection patterns. This pairs with:
- The 5-band BPM table (SENTENCE/BREATH/CLAUSE/PHRASE/NONE)
- The 7-chakra band proposed in #1398 (ironically a 7-set, not a 1-5)
- The Hyperdimensions cymatic visualizer hook (issue stub 13 in audit doc)

**For the mirror:** be aware that future issues will likely include:
- `pmoves/services/nfc-bridge/` — reads NFC tag UID, looks up identity in Supabase, fires Hyperdimensions scene preset
- New NATS subject `physical.nfc.tap.v1` for tag-tap events
- Hyperdimensions scene presets keyed by chakra band or BPM band

Don't prematurely build for this — but if the mirror's chakra encoder adds a `chakra_id` field to CGP, make sure that field is shaped to also accept NFC-tag-derived identities later (e.g., as a string, not an enum-int).

---

## 8. Verification before claiming any of the 3 PRs done

Per `feedback_verification_before_completion` (existing memory rule): before posting any "done" claim, run:

| PR | Verification command |
|---|---|
| #1397 bridge | `python -c "from pmoves.services.flute_gateway.geometry_bridge import GeometryBridge; b = GeometryBridge(); print(b.encode_packet({...}))"` AND publish a test packet, observe `geometry.cgp.v1` consumer (graphiti) ingests it without HMAC error |
| #1398 chakra | `pytest pmoves/tools/tests/test_bpm_encoder.py -k chakra` — assert all 7 bands return correct freq/BPM/prosodic-affinity |
| #1399 breath | `pytest pmoves/services/flute-gateway/tests/test_breath_envelope.py` — assert 12s cycle period, 6s ramp shape, persona-selector returns "Breath Guide" |

Don't claim done before evidence. Keep the test outputs in the PR description.

---

## 9. If you (the mirror) get stuck

- **CGP schema ambiguity:** `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md` (499 lines) is the math reference; consult before extending the schema
- **HMAC signing failure:** check `CHIT_PASSPHRASE` env var is set in your shell; the dev pattern is to run unsigned with a stderr warning (acceptable in feature-flag-gated dev mode, not in production)
- **Subject conflict:** if `tokenism.geometry.event.v1` consumers panic on receiving CGP v0.2 packets, that's the dual-publish migration cost — surface back to operator, don't silently downgrade

---

## 10. Final checklist before the mirror starts

- [ ] Read this whole file (you're doing it now)
- [ ] Read `pmoves/docs/audit/FLUTE_CHIT_GAP_2026-04-26.md` (the audit baseline)
- [ ] Read `pmoves/docs/AGENTS/AGNOTE4482FLUTE.md` Movements I, II, III (the seed-derived spec)
- [ ] Read `pmoves/services/flute-gateway/main.py` lines 140–250 (existing geometry-bus hooks)
- [ ] Read `pmoves/tools/chit_security.py` (HMAC sign/verify surface)
- [ ] Confirm GH Issues #1397, #1398, #1399 are still open and not claimed by another node
- [ ] Pick one issue to start; create branch `feat/flute-<issue-slug>` off `origin/main`
- [ ] Use a new worktree under `../mirror-flute-<slug>` (or your node's preferred parent dir)
- [ ] Ship; verify; PR with the verification commands' output

`★ Mirror Insight ─────────────────────────────────`
The point of this plan is symmetry: z890 already did the discovery, so you don't re-grep the same files. The energy you save on flopping is the energy you spend generating. Plant where z890 watered. The seed is in `AGNOTE4482FLUTE.md`. The roots are in `bpm_encoder.py`. Make the kaleidoscope turn one click.
`──────────────────────────────────────────────────`
