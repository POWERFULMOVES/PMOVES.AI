# Unified Design Language — Follow-on Lanes (open call to claim)

**Author:** 5090-CLAUDE (Opus 4.8, 1M) · 2026-06-16
**Parent:** spec `docs/superpowers/specs/2026-06-15-pmoves-unified-design-language.md` (DL-0), plan `docs/superpowers/plans/2026-06-16-dl-1-design-token-layer.md` (DL-1)
**Status of DL-1:** in build (delivery subagent) on `feat/dl-1-unified-design-tokens`. This doc tees up the rest so any node can claim a lane without waiting on me.

> Claim a lane by adding a CLAIM entry to `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` first (per the collision-avoidance protocol), then branch `feat/dl-<n>-<slug>`. Credit the W1 theme lane (4090-claude, PRs #1065/#1101) in any file that reads `agent_signatures.yaml`. Coordinate with the owners noted below.

## The engine (context for any picker-upper)

- **Registry (source of truth):** `pmoves/config/agent_signatures.yaml` — per-persona `glyph/color/accent/voice`. Read-only / additive-only.
- **DL-1 output (this branch):** `pmoves/design/` — `generate.py` (uv) → `build/tokens.<theme>.css` + `tokens.ts`; `theme-provider.js`; `preview.html`. Tokens: `--pm-bg/-surface/-ink/-accent/-accent-soft/-accent-2/-signature/-radius/-font-*`. Themes: `pmoves-armor` (default, cool) + `darkxside-skin` (warm `✦` crimson).
- **4090-owned (need sign-off to modify):** `agent_terminal_theme.py`, `botz_cli.py`, their tests, `botz-gateway/main.py` W1 routes (`/v1/agent/theme/{id}`, `/v1/agent/whoami`).

## Lanes

### DL-1b — CHIT tour re-skin  ·  effort S–M  ·  suggested owner: 5090 or whoever holds the tour
- **Where:** the held tour worktree `.claude/worktrees/chit-visual-tour-p1a` (branch `worktree-chit-visual-tour-p1a`), files `website/chit-tour/`.
- **Do:** import `pmoves/design/build/tokens.pmoves-armor.css` (or vendor a copy under `website/chit-tour/`), drop the AI-default teal `#4f98a3`/amber `#b39458`, map existing styles to `--pm-*`, apply motif kit (shard nodes already D3; add hex dividers; `✦` section markers). Keep CSP-clean (self-host, no CDN/inline — the tour already self-hosts fonts).
- **Gate:** absorbs/closes **PR #1697** (VISUAL_TOUR.md draft). DARKXSIDE visual sign-off (this was the original hold reason).
- **Depends on:** DL-1 merged (tokens.css exists).

### DL-2 — Roll tokens to Notebook + A2UI + CF site  ·  effort S (each)  ·  owner: TBD
- **Notebook (`pmoves/ui`):** re-point `app/globals.css` + `tailwind.config.ts` at the generated tokens (hues already near-identical: cata-cyan ≈ armor). Smallest diff.
- **A2UI renderer:** set `ProvenancePalette` default ← `pmoves/design/build/tokens.ts` 7-key mapping (`background/panel/panelAlt/accent/accentSoft/ink/muted`). DarkxsidePortal already `#E11D48` ✓. Coordinate with PMOVES-Creator (owns Remotion/motion).
- **CF site (`website/`):** swap `--c-*` → `--pm-*`, unify radius/fonts. Public on merge — respect hardened `_headers` CSP (no CDN/inline; self-host fonts). This is the token-swap only; the A2UI rebuild is DL-4.

### DL-3 — Persona-adaptive runtime + Showtime live skin  ·  effort M  ·  owner: coordinate w/ 4090 (W1 gateway)
- Extend `pmoves/design/theme-provider.js` `setPersona(id)` to resolve via BoTZ Gateway `GET /v1/agent/theme/{id}` + `/v1/agent/whoami` (additive consumer; do not modify the routes). Active signature drives the whole skin (DARKXSIDE→crimson, 4090→teal).
- **Live mode:** subscribe to Showtime `showtime.all_green.v1` / `:9225/sse/events` to flip surfaces to "live" skin. Wire the prosodic timing layer (HTML5 Vibration + BPM + chakra + 6-sec flute, per `AGNOTE4482FLUTE.md` cymatic-visualizer gap) — this is the "portal/time-machine" experience from the North Star.
- **Adjacent:** the `AGNOTE4482FLUTE.md` cymatic-visualizer + chakra-color-axis is the same surface — fold together.

### DL-4 — CF site rebuilt from A2UI components (demonstrative) + optional light theme  ·  effort L  ·  owner: TBD
- Rebuild `website/` from A2UI's component catalog (Lit `web_core` + PMOVES custom components via the `componentRegistry` hook) so the site IS a live demo of the platform + theme engine. Needs a CSP relaxation on `/` or a subpath block (mirror `/hyperdim/*` precedent, PR #1672).
- Optional: add a real **light** theme (Model C) for marketing — `light-dark()` over the same token names.
- **Do not grab here:** the A2UI Remotion hologram viewport is a **SPARK lane** (claim separately).

## Coordination summary
- **4090:** invited to pair-review DL-1 (W1 lane owner). DL-3 touches their gateway as an additive consumer — give them the heads-up before DL-3.
- **PMOVES-Creator submodule:** owns Remotion/motion — coordinate on DL-2 (A2UI palette) + DL-4.
- **SPARK:** A2UI Remotion hologram viewport scaling (per `AGNOTE_CONVERGENCE_CHECKLIST_2026-05-16.md`) — separate lane.
- **Launch reality:** platform is pre-launch (launch gate FAIL 12/45); design-language work is launch-relevant but does not unblock infra gates — keep scope clean, don't imply launch-readiness.
