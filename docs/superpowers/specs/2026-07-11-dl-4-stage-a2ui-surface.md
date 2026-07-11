# DL-4 — `/stage/`: the A2UI-Rendered Stage Surface (Design Spec)

**Phase:** DL-4 of the [Unified Design Language](2026-06-15-pmoves-unified-design-language.md) (final phase; DL-1…DL-3 shipped).
**Author:** 5090-CLAUDE (Fable 5) · 2026-07-11
**Status:** design — decisions locked with DARKXSIDE 2026-07-11; 4.1 plan to follow.

---

## Problem

The CF site is a hand-written static page. It *describes* the platform but demonstrates none of it. Meanwhile the platform's own UI protocol — A2UI (`PMOVES-A2UI/renderers/lit`, `@a2ui/lit`, `<a2ui-root>` + component registry) — is exactly a machine for rendering UI surfaces from declarative component JSON, the same way agents paint UIs. DL-0 named the end state: *the site IS a live demo of the platform + theme engine*.

## Decisions (locked with DARKXSIDE, 2026-07-11)

### D1 — Land at `/stage/`, not on `/`
New surface at `pmoves.ai/stage/`, mirroring the `/hyperdim/*` and `/chit-tour/*` per-route precedent (own CSP block, own directory, additive). The hardened <50 KB marketing page stays untouched; `/stage/` earns promotion to `/` later or doesn't. No root-CSP loosening.

### D2 — The surface is rendered by the real A2UI Lit renderer
Vendor a **built** `@a2ui/lit` bundle under `website/stage/vendor/` (same committed-vendor pattern as the tour's D3/Three — no CDN, no build step at deploy). The page mounts `<a2ui-root>` and feeds it **surface JSON** (A2UI component messages). This is the demonstrative core: a static file and a live agent message are the *same schema* rendered by the *same code*.

### D3 — Content starts with rooms-on-a-stage; North Star is a spawnable UI
- **4.1 ships rooms-on-a-stage:** the PUBLIC room catalog (Demo Room, Fordham Community, ToKenism Exchange — exactly the `isPublicRoom()` set) as cards on a literal stage, with room lifecycle framing (rehearsal → live → review → archive) and each room's glyph/accent from its manifest theme.
- **Operator North Star (recorded verbatim intent):** the stage should *eventually show all of it — it's a spawnable UI*. Persona switcher, Showtime live state, and the tour/beats exhibits join in later slices; ultimately agents spawn surfaces onto the stage over the A2UI protocol. Start with the recommended core.

### D4 — Data: build-time bake, loopback-only live enrichment
The site is static CF Pages — no server. A generator (`make -C pmoves stage-data`) reads `pmoves/config/rooms/` and emits `website/stage/data/public-rooms.json`, applying the SAME visibility rules as `pmoves/ui/lib/rooms.ts` `isPublicRoom()` (exclude `private`/`unlisted`/`owner_only`/`exclude_from_public_catalog`). Committed output + a drift-gate check (pattern: `design-tokens-check`). Live enrichment (Showtime state, persona resolution) reuses the DL-3.3 loopback-only machinery already vendored at `website/persona/` — public visitors see the baked stage; on-net visitors see it come alive.

### D5 — Theming: tokens in, signature reserved
The stage chrome consumes `--pm-*` (vendored `tokens.pmoves-armor.css`); room cards use their manifest `accent_color`. The reserved ✦ `--pm-signature` crimson stays the founder mark only (DL-3 D1 canon guard). Persona `?agent=` accents flow through the existing boot module.

### D6 — Light theme: DEFERRED
Dark-first like every shipped surface. Model C (`light-dark()` over the same token names) is a small follow-up once tokens gain light variants — out of DL-4 scope by operator decision.

## Architecture (4.1)

```text
pmoves/config/rooms/*.json ──(make stage-data: isPublicRoom rules)──► website/stage/data/public-rooms.json
                                                                             │
website/stage/index.html ── <a2ui-root> + vendored @a2ui/lit ◄── surface JSON (stage layout + room cards)
        │                                                            │
        ├── tokens.pmoves-armor.css (vendored)                       └── room accents from manifest theme
        └── /persona/ boot (existing, DL-3.3) — ?agent= accents + Showtime data-stage flips (loopback-only)
```

New units: `website/stage/` (index.html, stage.css, surface JSON, `vendor/a2ui-lit.*.js`, `data/public-rooms.json`), a `stage-data` generator + drift check in `pmoves/` tooling, one `_headers` block for `/stage/*`.

## CSP posture (`/stage/*` block)

- `script-src 'self'` — bundle vendored; no CDN, no eval. Verify at build that the `@a2ui/lit` production bundle needs neither (Lit itself does not).
- Styles: Lit uses constructable stylesheets (`adoptedStyleSheets`) in shadow roots, which CSP `style-src` does not block in modern browsers. Target `style-src-elem 'self'`; if renderer fallbacks inject inline styles at runtime, narrow to `style-src-attr 'unsafe-inline'` exactly like `/chit-tour/*` — measured, not assumed.
- `connect-src 'self'` + the loopback gateway origins (same list as `/` after DL-3.3).

## Phasing

| Slice | Deliverable |
|---|---|
| **DL-4.1 (next plan)** | `/stage/` live: vendored renderer, baked public-rooms surface, stage chrome on tokens, CSP block, drift-gated data bake. |
| DL-4.2 | Persona switcher panel + Showtime live-state visual (preflight/hold/showtime) on the stage — reuses DL-3 engine wholesale. |
| DL-4.3 | Exhibits: fold the CHIT tour (**resumes held PR #2076** — visual sign-off happens here) + hyperdim/beats embeds in as stage exhibits. |
| DL-4.4 | **Spawnable stage:** agent-pushed surfaces over the A2UI protocol via the A2UI NATS Bridge (:9224) — on-net only, additive consumer; static and live surfaces share the schema by construction (D2). |

## Non-goals / guardrails
- No change to `/` (marketing page) or its CSP.
- No light theme (D6 — deferred).
- No CDN assets anywhere; everything vendored (site-wide invariant).
- SPARK owns the A2UI Remotion hologram viewport — not touched here. PMOVES-Creator coordinates on any A2UI custom-component additions.
- 4.4's NATS bridge consumption is additive; no modification to the bridge service.

## Open questions (for 4.1 plan review)
1. Bundle production: build `@a2ui/lit` once in the submodule (`npm ci && build`) and commit the artifact, or add a small pinned build script in `pmoves/` tooling? (lean: build once + commit, exactly like the tour vendored D3/Three; record the source commit in a `vendor/README`.)
2. Does the standard component catalog (card/column/button/…) suffice for room cards, or do we register one `pmoves-room-card` custom component? (lean: try standard catalog first; custom component only if the layout fights us.)
3. `stage-data` generator language: Python beside `design/generate.py` (uv, matches token generator) or Node beside the UI's `rooms.ts`? (lean: Python in `pmoves/design/` family — same toolchain as the existing generator + drift gate.)
