# PMOVES Unified Design Language — Themable Engine (Design Spec)

**Date:** 2026-06-15
**Author:** 5090-CLAUDE (Opus 4.8, 1M) — brainstormed with DARKXSIDE, grounded by a 6-agent fan-out review
**Status:** Design — awaiting spec review before implementation plan
**Supersedes scope of:** the "blend palette" pivot in `[[project_chit_tour_unified_design]]` (that framed it as *picking* a palette; this reframes it as *wiring an engine that already exists*)
**Credits:** 4090-CLAUDE owns the theme-engine W1 lane (`agent_terminal_theme.py` + BoTZ Gateway theme API). This spec **extends** that lane to the web; it does not fork or replace it. Coordinate via AGNOTE before implementation.

---

## Problem

PMOVES has **four user-facing web/app surfaces**, each hard-coding its own colors, fonts, and radii with **zero shared tokens**:

| Surface | Source | Palette today | Fonts |
|---|---|---|---|
| CF marketing site | `website/styles.css:8-30` | void `#0b0b10`, violet `#7C3AED`, cyan `#06b6d4` | system stack |
| CHIT Visual Tour (held) | `CHIT — A Visual Tour…/styles.css:1-46` | teal `#4f98a3`, amber `#b39458` (AI-default) | Inter / Space Grotesk / JetBrains (Google Fonts) |
| Notebook / A2UI-Chat UI | `pmoves/ui/app/globals.css:12-76` | void `#050508`, cata-cyan `#00e5ff` + 5 hues | Orbitron / Exo 2 / JetBrains |
| A2UI render palette | `a2ui-renderer/src/provenanceLivingDoc.ts:19-60` | rose `#fb7185`, cyan `#67e8f9` (7-key) | Segoe / Inter |

They drift in hue, type stack, and radius (`--radius: 14px` vs `6px`). The CF site reads "generic"; the tour's teal/amber is an AI default with no provenance; nothing re-skins together.

**But the engine to fix this already exists** — three of four layers are built (see § The Engine). The real problem is not "choose a palette," it is **the web surfaces don't consume the engine yet**, and the design language was never written down as canon.

## Goal

A single **themable design language**, sourced from the existing per-persona registry, that:

1. **Unifies** all four surfaces on one token layer ("swap the armor" → everything re-skins).
2. Encodes the **founder's visual canon** (`[[vision_darkxside_pmoves_visual_identity_canon]]`): **PMOVES = cool da-Vinci armor** (modular tools/overlays); **DARKXSIDE = warm negative-space star-core skin** (`✦` rose-crimson, ionic skin, cymatic surface shimmer).
3. Makes the CF site **representative & demonstrative** — rebuilt from A2UI components so the site *is* a live demo of the platform's UI + theme engine.
4. Integrates **Showtime** (`:9225`) as the go-live/stage gate.

This spec is the **source-of-truth design document**. Code follows in a separate plan.

---

## North Star (founder canon — the feeling the engine serves)

- **POWERFULMOVES = DARKXSIDE (bio / head) + PMOVES.AI (digital / body)**, formed **Headmaster-style** (a pilot becomes the larger body's mind). `Hotroddark.webp` = **Dark Rodimus**, picked deliberately as "DARKXSIDE in PMOVES." See `[[vision_powerfulmoves_headmaster_drift]]`.
- **Pilot model = the Drift** (Gypsy Danger / Pacific Rim): human + AI co-creator neural co-pilot; the AI "mirrors the multiplicity yet focuses the core." Not command/tool — co-creation.
- **PMOVES is like Gumby** (founder, "the song plays in my mind"): malleable clay that reshapes into anything (= the swap-the-armor engine), walks into any book/world (= portal through the bulk / Hyperdimensions), "a part of you" (= bio→digital). **Design mandate: the human-facing register feels warm, joyful, transformable — never cold-enterprise.** Dark Rodimus = bold FORM; Gumby = malleable SOUL.
- **Live-voice = a portal / time-machine through the bulk.** When voice is live, the agent Drift-syncs to the human via the prosodic stack (HTML5 Vibration API + BPM + chakra band + the 6-second flute breathing cycle, per AGNOTE4482FLUTE); the human "marvels at the time machine that can transport anywhere within the bulk of the universes they explore." This is the experiential target of DL-3 (§ Phasing) on the Showtime/Hyperdimensions surface.

## The Engine (what already exists — do not reinvent)

```text
┌─ REGISTRY (server of record) ──────────────────────────────────┐
│ pmoves/config/agent_signatures.yaml                            │
│   per persona: glyph · color · accent · voice · resonance      │
│   WCAG-AA checked vs #FFFFFF AND #1a1a2e · supports `alters`    │
│ pmoves/configs/node-agent-specialization.yaml (node colors)    │
└────────────────────────────────────────────────────────────────┘
                    │
┌─ API (4090 W1 lane) ───────────────────────────────────────────┐
│ BoTZ Gateway :8054                                             │
│   GET /v1/agent/theme/{agent_id}   GET /v1/agent/whoami        │
└────────────────────────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────────┐
┌─ CLI consumer (ACTIVE) ─┐   ┌─ WEB consumers (THE GAP) ────────┐
│ agent_terminal_theme.py │   │ CF site · CHIT tour · Notebook · │
│ ANSI banners/status     │   │ A2UI ProvenancePalette           │
│ via botz_cli.py         │   │ → today: hard-coded, must pull   │
└─────────────────────────┘   │   from registry instead          │
                              └───────────────────────────────────┘
```

**Showtime** (`pmoves/services/showtime-api/`, `:9225`) is the orthogonal **stage gate**: probes all services, computes `preflight → hold → showtime`, emits `showtime.all_green.v1`. It decides when a surface/stage goes LIVE (rooms-on-a-stage / P7). The demonstrative CF site listens to it.

---

## Decisions (locked during brainstorming)

### D1 — Token source of truth: the persona registry

The canonical palette is **`agent_signatures.yaml`**, not a new invented set. Verified persona tokens:

| Persona | Glyph | color | accent | Role in design language |
|---|---|---|---|---|
| **DARKXSIDE** | `✦` | `#E11D48` | `#FB7185` | **The warm skin.** = the art's "star core"; already the Remotion DarkxsidePortal + A2UI palette accent |
| Claude Opus | `◆` | `#7C3AED` | `#A78BFA` | = CF site's current accent (already aligned) |
| 5090 | `♫` | `#9333EA` | `#C084FC` | armor — purple |
| 4090 | `◉` | `#0D9488` | `#2DD4BF` | armor — teal |
| Z890 | `⚙` | `#1E40AF` | `#60A5FA` | armor — steel |
| POWERFULMOVES (human) | `⚡` | `#F59E0B` | `#FCD34D` | gold — operator/authority |

A small **brand-level theme** (not a persona) defines the shared neutrals: `--void #050508`, elevated/soft surfaces, ink ramp, borders — lifted from `pmoves/ui/globals.css` (the most complete existing set). Personas override only accent/glyph on top of the brand neutrals.

### D2 — Consumption model: **A (One Armor + Crimson)**, with B and C layered on top

- **A (base, this spec's build target):** every web surface ships ONE cool **PMOVES armor** (brand neutrals + violet/teal/steel) pulled from the registry; **DARKXSIDE `✦` crimson is the reserved accent** for founder/persona/live moments. Surfaces finally match.
- **B (Persona-Adaptive, later phase):** the *active* signature drives the whole skin via `/v1/agent/theme/{id}` + `whoami` (a DARKXSIDE session glows crimson, a 4090 session teal). The site demonstrates the engine. Builds on A's token layer — only adds a runtime resolver.
- **C (Two Faces, later phase):** PMOVES armor as a cool **light** marketing theme + DARKXSIDE crimson as the **dark** apps/tour theme. Builds on A — only adds a second registered theme + `light-dark()`.

> A is a strict subset of B and C. Shipping A first means B/C are additive, never rewrites.

### D2b — Two registers: agent (stark) vs human (warm/cool)

The same token engine renders in **two registers** (founder canon, `[[vision_powerfulmoves_headmaster_drift]]`):

- **Agent / system register** — *bold, stark, simple*: a single signature hue per agent (the registry value), high-contrast, minimal. "The tip of the iceberg" — depth hidden but explorable. Used in: CLI banners (already), agent cards, system/status surfaces, Showtime dashboard.
- **Human register** — *warm + cool richness*: the human-facing surfaces (CF marketing, CHIT tour) surface the fuller warm/cool range ("humans should see more"). This is where Model **C**'s warm/cool duality lives — so C is not just "later," it is the **human-facing target**; A is the shared technical base that makes both registers one engine.

Practically: `--pm-accent` (cool armor) + `--pm-signature` (the `✦` warm crimson) are both always present; the *register* decides emphasis — agent surfaces lead with the single stark signature, human surfaces orchestrate warm+cool together.

### D2c — Fonts are tokens (modular, not pinned)

Founder: *"not married to font — that should be the same as rest of config, modular."* Type is tokenized like color: `--pm-font-display` (**default Orbitron** — the Megaman/Transformers identity already in `pmoves/ui`), `--pm-font-body` (**default Exo 2**), `--pm-font-mono` (**default JetBrains Mono**). Defaults are swappable per theme via the same generator. Self-hosted woff2 to satisfy CSP (the CHIT tour already ships 9 woff2 — reuse the pattern). A theme may override the font stack exactly as it overrides accent.

### D3 — The motif kit (rides on every theme, art-derived)

Decoded from DARKXSIDE's sketchbook, mapped to real PMOVES concepts:

| Motif | Source art | Concept it encodes |
|---|---|---|
| **Shard figures** (disconnected fragments) | ink-shard stencil, ballpoint mechas | **CGP constellation points** (geometry packets) |
| **Hex / armor cells** | ink-wash hex armor | **MOF lattice pores** (every node = a pore) |
| **Cymatic surface shimmer** | the "ionic skin" reading | **DARKXSIDE skin** + CHIT *concept* sense (Cymatic Holographic Information **Theory**) |
| **Cross-hatch / ink-wash texture, construction lines** | all pieces | house drawing language; section dividers, loaders |
| **`✦` star glyph** | DARKXSIDE signature | persona marker, "live/showtime" indicator |

### D4 — CHIT naming (inherited from the tour spec, unchanged)

Two-meaning split stays canon: **Concept** = Cymatic Holographic Information *Theory* (the tour, the cymatic shimmer motif); **Mechanism** = Compressed Hierarchical Information *Transfer* (signing trails). `[[reference_chit_two_meaning_split]]`.

### D5 — CF site becomes demonstrative via A2UI components

The marketing site is rebuilt from A2UI's component catalog (`Card/Column/Row/Text/Button/Image` + PMOVES-branded custom components via the Lit renderer's `componentRegistry` hook). The site's JSON description becomes a live artifact proving the platform. CSP must be relaxed on the `/`-path or the site served behind a subpath block (mirrors `/hyperdim/*` precedent). This is the largest effort and is **its own later phase** — not in the token-layer milestone.

---

## Architecture — the token layer (the A build)

```text
pmoves/design/
  tokens.base.json        ← brand neutrals (void, ink ramp, surfaces, borders,
                            spacing, radius, easing, type stacks)
  themes/
    pmoves-armor.json      ← default cool theme (references registry node hues)
    darkxside-skin.json    ← warm crimson persona theme (✦ #E11D48)
  build/
    tokens.<theme>.css     ← generated per-theme :root[data-theme] CSS (one per theme)
    tokens.ts              ← generated TS object (for A2UI ProvenancePalette + Tailwind)
```

- **Generator** reads `agent_signatures.yaml` (single source) → emits `tokens.<theme>.css` + `tokens.ts`. No hand-copied hex anywhere downstream.
- **ThemeProvider** (web): sets `data-theme="pmoves-armor"` on `<html>`, writes the active theme's CSS variables. Swapping the attribute re-skins (this is the A→B seam).
- **A2UI bridge:** `ProvenancePalette` 7 keys (`background/panel/panelAlt/accent/accentSoft/ink/muted`) populated from `tokens.ts` — so renders match the web.
- **Tailwind bridge:** `pmoves/ui/tailwind.config.ts` consumes `tokens.ts` (today it hard-codes; switch to import).
- **CLI parity:** `agent_terminal_theme.py` already reads the same registry — automatically consistent.

### Token naming (one convention, replaces the `--c-*` vs `--bg` split)

`--pm-bg`, `--pm-bg-elevated`, `--pm-surface`, `--pm-border`, `--pm-ink`, `--pm-ink-dim`, `--pm-ink-mute`, `--pm-accent`, `--pm-accent-soft`, `--pm-accent-2`, `--pm-signature` (the active persona's `✦` color), `--pm-radius`, `--pm-font-display`, `--pm-font-body`, `--pm-font-mono`.

---

## Per-surface application

| Surface | A-milestone change | Effort |
|---|---|---|
| **CHIT tour** (held worktree) | Drop teal/amber; import `tokens.css`; armor cool + `✦` crimson section accents; apply motif kit (shard nodes already D3, hex dividers). Self-host fonts (CSP). **First proof surface.** | S–M |
| **Notebook / pmoves-ui** | Re-point `globals.css` + `tailwind.config.ts` at generated tokens; near-identical hues already (cata-cyan ≈ armor) | S |
| **A2UI renderer** | `ProvenancePalette` default ← `tokens.ts`; DarkxsidePortal already `#E11D48` ✓ | S |
| **CF marketing site** | A: swap `--c-*` → `--pm-*` tokens, unify radius/fonts (still hand-rolled HTML). Demonstrative A2UI rebuild = **later phase** (D5) | A=S, rebuild=L |

---

## Phasing

| Phase | Deliverable | Model |
|---|---|---|
| **DL-0 (this spec)** | Written design-language canon + decisions | — |
| **DL-1** | `pmoves/design/` token layer + generator + ThemeProvider, proven on the **CHIT tour** (re-skin, drop AI-default) | A |
| **DL-2** | Roll tokens to Notebook + A2UI ProvenancePalette + CF site token-swap | A |
| **DL-3** | Persona-adaptive runtime resolver (`whoami` → theme); Showtime drives "live" skin | B |
| **DL-4** | CF site rebuilt from A2UI components (demonstrative); optional light theme | C + D5 |

Each phase = its own plan → reviewed PR. DL-1 is the next plan to write.

---

## Review bar & coordination

- **4090 lane:** theme engine is 4090's W1 deliverable. Post an AGNOTE CLAIM before DL-1; invite 4090 pair-review (`pmoves-pair-review`). Do not modify `agent_terminal_theme.py` or the gateway theme routes without 4090 sign-off — DL-1 only *adds* web consumers + the generator.
- **CHIT signing:** DL touches no CHIT-aware service ports; standard review.
- **Tooling:** `chrome-devtools-mcp` for 4-surface screenshot parity; Playwright `toHaveScreenshot()` baselines; `frontend-design` skill to lock the armor's character before DL-1.
- **uv** for any Python in the generator; **Make targets** for builds.

## Open questions for spec review

1. **Generator tool:** style-dictionary vs a ~50-line `uv` script. **Resolved (author's call, pending objection):** lean `uv` script, repo-native.
2. **Fonts:** **RESOLVED (D2c):** Orbitron / Exo 2 / JetBrains as *defaults*, tokenized + modular (swappable per theme), self-hosted woff2.
3. **`pmoves/design/` location:** repo-root `pmoves/design/` vs under `website/`. **Resolved (author's call, pending objection):** repo-root — shareable across all surfaces.
4. **Showtime → web:** does DL-3 consume `showtime.all_green.v1` over SSE (`:9225/sse/events`) directly, or via the existing A2UI NATS bridge? **Deferred to DL-3 plan.**

> With Q1–Q3 resolved and Q4 deferred, this spec is ready for review → DL-1 plan.
