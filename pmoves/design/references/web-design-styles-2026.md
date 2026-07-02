# Web design-style vocabulary (2026) — a preset naming layer for the theme engine

**Status:** reference / inspiration input for the [Unified Design Language spec](../../../docs/superpowers/specs/2026-06-15-pmoves-unified-design-language.md).
**Not normative.** This is an external taxonomy captured to give the theme engine a *shared naming language* for theme intents. It does not define tokens — the token source of truth remains [`pmoves/config/agent_signatures.yaml`](../../config/agent_signatures.yaml) consumed by [the DL-1 token layer](../README.md).

## Source

- **Video:** "The ONLY 6 Web Design Styles that Matter (2026)" — https://www.youtube.com/watch?v=N1Cl5cYmegE
- **Creator:** Self-Made Web Designer / Chris Misterek (@chrismisterek)
- Captured 2026-07-02 via authenticated transcript (486 segments). Full raw capture archived out-of-repo (session scratchpad).

The value here is **not** the beginner framing (it's a freelance-client-work overview). It's that six named archetypes give us a compact, memorable vocabulary for *theme presets* — the exact thing a swappable token engine wants when someone says "make this surface feel like X."

---

## The six archetypes

Each is a famous-person mnemonic → a design register → concrete signals → the client phrase that flags it.

| Archetype | Register | Signals | Flag phrase |
|-----------|----------|---------|-------------|
| **Steve Jobs** | Systematic minimalism | Skinny sans, systemic spacing/type, generous white space | "I just want something clean" |
| **Jensen Huang** | Buttoned-up precision | Strict grid, no full-width bleed, function > form (SaaS/AI, investor-facing) | "Look put-together / serious" |
| **Drew Barrymore** | Warm & approachable | Bounce animations, rounded corners, warm/natural palette, candid photography | "Feel down-to-earth" |
| **Zendaya** | Editorial cool | Swiss/modular layouts, ultra-minimal, cinematic imagery, unconventional layout | "Show our taste" |
| **Virgil Abloh** | One unforgettable element | *One* standout font/color/3D object, repeated tastefully — "contrast, not bigness" | "That's sick" |
| **Christopher Nolan** | Wow-factor motion | Morphs, novel hero scroll, interaction nearly everywhere (Spline/Unicorn Studio) | "I want a wow factor" |

### Two principles worth adopting verbatim
- **"Perfection is achieved… when there's nothing left to take away."** (Saint-Exupéry, via the Steve Jobs style) — the discipline behind DL's structural base tokens.
- **"The point is contrast, not bigness."** (Virgil Abloh style) — a signature element earns attention by standing out, not by shouting. Directly relevant to how `--pm-signature` / `--pm-accent` should be *reserved*, not spread.

### Real reference sites named
Apple · Melrose AI · Fruitful · Still Agency · Obsidian Assembly · Active Theory.

---

## Mapping to the PMOVES theme engine

The [DL spec's founder canon](../../../docs/superpowers/specs/2026-06-15-pmoves-unified-design-language.md) already frames two registers — **DARKXSIDE** (warm negative-space star-core) and **PMOVES** (cool modular da Vinci armor) — served by *one* engine with swappable skins. These six archetypes slot into that model rather than competing with it:

- **`darkxside-skin`** (warm crimson) ≈ **Drew Barrymore** warmth + **Steve Jobs** white-space, with the **✦ star-core as the single Virgil-Abloh signature element** repeated tastefully. The canon's "one element repeated" and the video's "contrast, not bigness" are the same idea.
- **`pmoves-armor`** (cool violet, default) ≈ **Jensen Huang** grid discipline + **Zendaya** modular/editorial layout — armor panels as modular blocks, function-forward.
- **Motion tier** (A2UI / Remotion, cymatic shimmer) ≈ the **Christopher Nolan** register — reserved for showtime surfaces, not everywhere. Maps to the spec's D3 motif kit.

**Implication for phasing, not a new requirement:** if the engine ever exposes named intents beyond the two skins, this six-word vocabulary is a good candidate label set. Steve-Jobs *structure* underneath, warm↔cool skin on top, Nolan motion gated to showtime — the same "nothing left to take away" restraint applied to tokens.

## Where this does NOT apply
- It does not add or rename any `--pm-*` token.
- It does not change the registry contract or the `pmoves-armor` / `darkxside-skin` themes.
- Accessibility (AA contrast, from DL-2) and CSP-cleanliness still bound every choice; the "Nolan" register especially must not regress motion-reduction or contrast.
