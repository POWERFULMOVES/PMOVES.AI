# DL-3 — Persona-Adaptive Runtime Theme Resolver (Design Spec)

**Phase:** DL-3 (Model B) of the [Unified Design Language](2026-06-15-pmoves-unified-design-language.md).
**Author:** 5090-CLAUDE (Opus 4.8) · 2026-07-02
**Status:** design — approved shape, plan to follow.
**Builds on:** DL-1 (`pmoves/design/` token layer, merged #1827) + DL-2 (tokens rolled to Notebook/A2UI/CF, merged #1866).

---

## Problem

DL-1 shipped two pre-built base themes (`pmoves-armor` cool, `darkxside-skin` warm) selected by `data-theme`. But the persona registry (`pmoves/config/agent_signatures.yaml`) holds **20 agents + 6 alters**, each with its own accent hex. Today a 4090 session and a DARKXSIDE session render identically (armor violet) unless one of the two hand-built themes is selected. The engine can't yet let the **active signature drive the skin** — the Model B promise ("a DARKXSIDE session glows crimson, a 4090 session teal").

## Goal

A **thin runtime resolver** that, given an active agent id, overlays that agent's accent onto the current base theme — no per-agent CSS, no build artifacts. Prove it on the isolated `pmoves/design` preview (slice 1); Notebook is the first real surface (slice 2). Showtime (`:9225`) drives a "live" emphasis when a stage goes green.

## Decisions (locked during brainstorming, 2026-07-02)

### D1 — Resolution model: **runtime accent-override**, not pre-built per-agent CSS
The base theme (armor/skin) still ships as pre-built CSS via `data-theme` — it carries `bg`/`bg-tint`/`surface`/`void` deltas worth pre-generating. On top of it, `setPersona(id)` overlays **only the accent family** from `GET /v1/agent/theme/{id}`:

| Overridden at runtime (accent family only) | Left untouched |
|---|---|
| `--pm-accent` ← `color` | **`--pm-signature` — reserved `✦` crimson, NEVER overridden** |
| `--pm-accent-soft` ← `accent` | `--pm-bg`, `--pm-bg-tint`, `--pm-surface`, `--pm-void`, `--pm-void-elevated` |
| `--pm-accent-2` ← `accent` | `--pm-ink`, typography, spacing, motif geometry |

This handles all 20 agents **and** all 6 alters (`GET /v1/agent/theme/{id}/alter/{name}`) with zero build output. Rationale: the agent×alter identity space is combinatorially hostile to pre-built CSS; the gateway already returns raw hex (`botz-gateway/main.py:612-621`).

**Canon guard (decided 2026-07-02):** `--pm-signature` is the reserved DARKXSIDE `✦` crimson (`#E11D48`) and is **never** touched by the resolver — a 4090 session "glows teal" through the accent family while the `✦` stays the constant founder mark. Model B ("active signature drives the skin") is honored via the accent family only. Honors `[[vision_darkxside_pmoves_visual_identity_canon]]`.

### D2 — Identity transport: **URL query param**, gateway-direct
The browser has **no** existing identity mechanism (no cookie, no injected global — `whoami` is CLI/hostname-oriented and needs a Supabase-registered `instance_id`). DL-3 introduces the lightest transport: **`?agent=<id>`** (and optional `&alter=<name>`) read on load → call `GET /v1/agent/theme/{id}` **directly**. This deliberately **skips `whoami`/Supabase** — the gateway (`:8054`) is the only dependency.

> This also keeps DL-3 clear of the parked Supabase host-reachability work (YT gap #3): no Supabase round-trip in the web path.

`whoami` remains the *server/CLI* identity path; a future slice may add an env-injected global (`NEXT_PUBLIC_PMOVES_AGENT`) or an operator picker writing localStorage. Not in slice 1.

### D3 — Resolve at the layer each surface consumes
Preview + Notebook consume `--pm-*` directly → override `--pm-*`. The CF site consumes a `--c-*` brand layer derived from `--pm-*`, and its `prefers-color-scheme: light` block sets `--c-bg`/`--c-ink` **directly** — so a `--pm-*`-only override cannot reach CF backgrounds in light mode. **DL-3 overrides accent/signature only** (never `--pm-void`/`--pm-ink`), which flows safely through every surface. CF/A2UI get surface-specific resolvers in a later slice, not slice 1.

### D4 — Showtime "live" skin: SSE with poll fallback
Browsers reach Showtime over HTTP, no NATS needed:
- **`GET /sse/events`** (`text/event-stream`) carries `showtime.all_green.v1` = `{"state":"showtime","source":"showtime-api"}` — the live-edge flip.
- **`GET /health/all`** returns `{state ∈ preflight|hold|showtime}` — a coarse poll fallback.

When state is `showtime`, the resolver adds a `data-stage="live"` attribute that intensifies the `✦` signature (glow/emphasis) — the "live" moment. `preflight`/`hold` = normal. This answers the parent spec's open question Q4: the A2UI NATS bridge is **not** required.

### D5 — Fallback & no-flash
No `?agent=` → keep the base theme's default accent (no override, no fetch). Gateway 404/unreachable → log once, keep base accent (never blank). The override is applied via `documentElement.style.setProperty` after the base CSS is already linked, so there is no flash-of-wrong-accent for the base theme; the persona accent settles on first paint after fetch.

## Architecture

```text
?agent=darkxside[&alter=…]        GET /v1/agent/theme/{id}[/alter/{name}]  ->  {color,accent,glyph}
        │                                          │
        ▼                                          ▼
theme-provider.js  setPersona(id, {alter})  ──►  style.setProperty('--pm-accent', color)
        │                                        style.setProperty('--pm-accent-soft', accent)
        │                                        style.setProperty('--pm-accent-2', accent)
        │                                        // --pm-signature untouched (reserved ✦ crimson)
Showtime  GET /sse/events ── showtime.all_green.v1 ──►  documentElement.dataset.stage = 'live'
                                                         (intensifies the reserved ✦; poll /health/all fallback)
```

New/changed units:
- **`pmoves/design/theme-provider.js`** — add `setPersona(id, opts)`, `clearPersona()`, `applyPersonaTheme(themeObj)` (pure, testable: object → `--pm-*` map), `resolvePersonaFromURL()`. Keep `setTheme`/`toggleTheme` unchanged.
- **`pmoves/design/showtime-live.js`** (new) — `watchShowtime({onState})` using `EventSource('/sse/events')` with `/health/all` poll fallback; sets `data-stage`.
- **`pmoves/design/persona-resolver.js`** (new) — the thin fetch layer (`fetchAgentTheme(id, alter)`), gateway base URL configurable (default `http://localhost:8054`).
- **`pmoves/design/preview.html` / `preview.js`** — add a persona `<select>` (populated from `GET /v1/agent/signatures`) + an alter `<select>` + a "stage: live" simulate toggle; CSP-clean (external module only).
- Tests: `pmoves/design/tests/` — pure-function tests for `applyPersonaTheme` (object→property map), `resolvePersonaFromURL` (query parsing), Showtime state→`data-stage` mapping. Network-boundary functions are injected (fetch/EventSource passed in) so tests stay hermetic.

## Testing

TDD, hermetic (no live gateway needed):
1. `applyPersonaTheme({color,accent})` sets exactly `--pm-accent/-soft/-2` and touches **no** `--pm-signature`, background, or ink var (guards D1 canon + D3).
2. `resolvePersonaFromURL('?agent=x&alter=y')` → `{id:'x', alter:'y'}`; empty → `null` (guards D5 no-fetch default).
3. `stageFromShowtimeEvent({state:'showtime'})` → `'live'`; `hold`/`preflight` → `null`.
4. `fetchAgentTheme` calls the injected fetch with the id-only URL (guards D2: no whoami/Supabase).
5. CSP-clean assertion on `preview.html` (no inline `<script>`/`<style>`) — extend DL-1's existing preview guard if present.

## Phasing (DL-3 sub-slices)

| Slice | Deliverable |
|---|---|
| **DL-3.1 (this plan)** | Resolver + Showtime watcher + preview persona/alter picker + live-flip, proven on `pmoves/design/preview`. Hermetic tests. |
| DL-3.2 | Notebook (`pmoves/ui`) adoption — `setPersona` on app shell, `?agent=` honored, Showtime SSE (origin already in CORS). |
| DL-3.3 | CF (`--c-*` layer) + A2UI (`ProvenancePalette` object patch) surface-specific resolvers. |

## Non-goals / guardrails
- No change to `agent_signatures.yaml`, the generator, or the two base themes (registry read-only, DL-1 contract intact).
- No `whoami`/Supabase dependency in the web path (D2).
- No override of background/ink tokens (D3) — **accent family only**; `--pm-signature` (reserved `✦` crimson) is never touched (D1 canon guard).
- No Model C `light-dark()` work (that's DL-4); DL-3 must not regress CF's existing `prefers-color-scheme: light` block.
- CSP-clean preserved (external module scripts only).
- 4090 owns the CLI theme lane + `/v1/agent/*` routes (W1); DL-3 is **read-only** against those routes — invite 4090 pair-review.

## Open questions for review
1. `--pm-accent-2`: source from `accent` (softer, current lean) or `color` (bolder second accent)?
2. Slice-1 gateway base URL: hardcode `localhost:8054` default + allow `?gw=` override for testing, or read a `<meta>` config? (lean: default + `?gw=` override.)
3. Should the persona picker in the preview also demo an **alter** dropdown in slice 1, or defer alters to 3.2? (lean: include — it's the same code path and proves the second axis.)
