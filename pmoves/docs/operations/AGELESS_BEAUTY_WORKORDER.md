# Ageless Beauty — PMOVES Edition Workorder

> **Lane:** feat/ageless-beauty-edition · **Operator:** elder (elder-melchor) · **CLAIM:** 2026-09-10
> **Contribution context:** elder contributes a nutritional interactive database + conformant base team (agents) to the practice of a nurse practitioner expanding her own practice ("Ageless Beauty"). The edition assists patients in getting a good beat on nutrition, exercise, and other PMOVES capabilities they can tune. The practitioner is also a minister — the edition must carry resonant medical + bio + spirituality surfaces. She likes Ratchet & Clank, Mega Man 2, The Twilight Zone — homage branding, never IP assets.

## What ships (in dependency order)

1. **Room manifest** `pmoves/config/rooms/ageless-beauty.room.practice.json`
   - Room: Ageless Beauty practice — hybrid (patient-facing + practitioner control)
   - Panels: nutrition database (custom), care-team console (custom), devotion/reflection (custom)
   - Apps: nutritional database (interactive), exercise "good beat" tracker (HR-zone aware), reflection/spiritual journal
   - Persona: minister-aware; voice = warm, measured; glyph ♱/✦
   - Skill bindings (approval-gated where patient-facing): nutrition-lookup, meal-plan-draft, exercise-tune, devotion-prompt, referral-draft (NP review required)
   - service_refs: nats, notebook (mirrored writeback), nutritional-db (new), cipher (memory, per-agent)
   - Policies: memory.chit_handoff=true; publish allowlist scoped to room + care channels

2. **Nutritional interactive database** `pmoves/services/nutritional-db/` (new service)
   - Data: Open Food Facts / USDA FoodData Central (both open-licensed) — fork-friendly, no proprietary feeds
   - Contract: REST :8107 — /search, /food/:id, /meal/analyze (macro/micro per patient profile), /interaction-check (supplement × medication caution flags, INFO-level only — decision support, NOT diagnosis; NP reviews all flags)
   - Conformant base team (the "conformant" in elder's contribution): personon-navigator agent (greets, collects goals), nutrition-analyst agent (database queries), care-coordinator agent (summarizes for NP review) — dsh-style, a2a-able later; v1 = skill-driven agents in the room
   - Deployment: CPU-only, no VRAM (kokoro-class), compose profile "wellness"

3. **Spiritual/medical resonance** `pmoves/services/nutritional-db/reflections/`
   - Curated reflection prompts (minister-reviewed by the practitioner herself), scripture/meditation references tagged by theme (strength, rest, gratitude, stewardship-of-body)
   - NO generative theology: prompts are curated content the practitioner edits; the system never generates doctrine

4. **Mobile app branding** (separate follow-up lane after room+DB land)
   - PMOVES mobile launcher skin: ageless-beauty (steel blue / energy gold — Mega Man 2 homage palette, already staged as Hermes skin)
   - Iconography language: bolt/energy-tank motifs (homage), Twilight-Zone-style intro cards for daily check-ins ("Submitted for your approval: today's nutrition beat…") — text homage only
   - Ratchet & Clank nod: the care-team console's "gadget" grid layout; wrench-glyph for the NP's tool palette

5. **Hermes instance for her seat** (operator provisioned, separate from this PR)
   - Profile `pmoves-hermes-ageless` with skin ageless-beauty, STT on, TTS = kokoro warm voice, memory scoped to practice, approvals = manual for anything patient-facing

## Compliance line (non-negotiable)
- Decision SUPPORT, not diagnosis: every clinical-adjacent output carries "review with your practitioner" framing; referral/meal-plan drafts require NP approval in the room contract.
- Data: patient data stays on her instance (no fleet telemetry of PHI); NATS events carry counts/ids only.
- Licensing: food data open-license; game inspirations are stylistic homage (palette, layout, phrasing) — no trademarked assets, sprites, or music.

## Verification (per Known Roads)
- Room manifest: schema-conform to ROOM_MANIFEST_CONTRACT.md; once public,
  `make -C pmoves stage-data-check` bakes website/stage/data from manifests
  and fails on drift (unlisted rooms are not baked — contract check only)
- nutritional-db: unit tests + live /search + /meal/analyze against USDA sandbox; compose healthcheck :8107/healthz
- Skins: already live on elder-melchor (pmoves active; ageless-beauty listed)

## Out of scope (this lane)
- Mobile app CODE (branding spec only here; app lane follows)
- Actual minister content (practitioner curates; we ship the empty shelving + format)
