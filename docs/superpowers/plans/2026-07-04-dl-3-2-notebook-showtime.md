# DL-3.2 — Notebook Showtime mount + `/health/all` poll fallback — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mount the DL-3 persona resolver + Showtime "live" flip into the Notebook UI (`pmoves/ui`), add the `/health/all` poll fallback to `watchShowtime` (spec D4), and open the two service CORS allow-lists to Notebook's real origin (`:4482`).

**Architecture:** The DL-3 design engine (`pmoves/design/*.js`, plain browser ESM) is the canonical source but is **not importable** across the `pmoves/ui ↔ pmoves/design` boundary (Next standalone `outputFileTracingRoot` is pinned to the ui dir). Following the DL-2 precedent (tokens were inlined), we **vendor** the four design `.js` files into `pmoves/ui/lib/persona/` and guard drift with a `design-vendor-check` make target (mirrors `design-tokens-check`). A single `"use client"` controller component drives the accent overlay + live flip; a small pill renders the live state.

**Tech Stack:** Next.js 16 (App Router) / React 19 / TypeScript / Tailwind / Jest (`next/jest`, jsdom) for Notebook; `node:test` for the design engine; FastAPI (showtime-api, botz-gateway) for CORS.

**Decisions baked in (flagged for review):**
- **D-a Vendor, not import** the design `.js` into Notebook (`lib/persona/*.js`), verbatim, guarded by a byte-diff `design-vendor-check`. Rationale: Next standalone tracing can't reach `../design`; DL-2 set the inline precedent; canonical source stays `pmoves/design`.
- **D-b CORS in code defaults**: add `http://localhost:4482` (+ `:3001`) to `SHOWTIME_CORS_ORIGINS` (`showtime-api/app.py:211`) and `BOTZ_GATEWAY_CORS_ORIGINS` (`botz-gateway/main.py:173`) defaults. `botz-gateway` is 4090's W1 lane — PR will CC 4090 (extends their #1956).
- **D-c Poll fallback** lives in `pmoves/design/showtime-live.js` (canonical), re-vendored into Notebook. Polls `GET /health/all` on SSE error/absence.

---

### Task 1: `/health/all` poll fallback in `watchShowtime` (design engine, canonical)

**Files:**
- Modify: `pmoves/design/showtime-live.js`
- Test: `pmoves/design/tests/showtime-live.test.js`

Spec D4: when SSE errors or `EventSource` is unavailable, poll `GET {gw}/health/all` → `{state ∈ preflight|hold|showtime}` → `stageFromShowtimeEvent` → `onState`. Injectable `fetchImpl`, `setIntervalImpl`/`clearIntervalImpl` (or accept an interval + expose the timer) for hermetic tests. Poll stops on `close()`. Default poll interval 5000ms; `opts.pollMs` overrides; `opts.poll === false` disables.

- [ ] **Step 1 — failing tests** (`tests/showtime-live.test.js`): (a) with a StubES that `.fail()`s, a poll fires against `{gw}/health/all` and maps `{state:"showtime"}` → `onState("live")`; (b) when `EventSourceImpl` is null/undefined, poll still runs; (c) `handle.close()` clears the poll timer (no further fetch). Use an injected `fetchImpl` returning `{ok:true,json:async()=>({state})}` and an injected timer (e.g. `opts.setIntervalImpl`/`clearIntervalImpl` capturing the callback so the test can invoke it synchronously).
- [ ] **Step 2** — run `node --test pmoves/design/tests/showtime-live.test.js`; expect FAIL.
- [ ] **Step 3 — implement**: add poll wiring to `watchShowtime` (start poll on `onerror`/no-ES; a single `pollTick` that `await fetchImpl(gw+"/health/all")` → `onState(stageFromShowtimeEvent(json))`; guard against overlapping ticks; `close()` also `clearInterval`s). Keep existing SSE named-event + `onmessage` + `onError` behavior intact.
- [ ] **Step 4** — run tests; expect PASS (existing 6 + new ~3).
- [ ] **Step 5** — `make -C pmoves design-test-js` (full design suite green) + `make -C pmoves design-tokens-check` (zero drift). Commit.

### Task 2: Vendor design engine into Notebook + `design-vendor-check`

**Files:**
- Create: `pmoves/ui/lib/persona/persona-theme.js`, `persona-resolver.js`, `theme-provider.js`, `showtime-live.js` (verbatim copies of `pmoves/design/*.js`)
- Create: `pmoves/ui/lib/persona/index.d.ts` (ambient types for the 4 modules so TS strict passes)
- Create: `pmoves/ui/lib/persona/README.md` (one line: "Vendored from pmoves/design — DO NOT edit; run `make -C pmoves design-vendor` to resync. Guarded by design-vendor-check.")
- Modify: `pmoves/Makefile` (add `design-vendor` copy target + `design-vendor-check` byte-diff target)

- [ ] **Step 1** — copy the four files verbatim into `lib/persona/`; add `index.d.ts` declaring the exported signatures (`setPersona`, `clearPersona`, `applyPersonaThemeToRoot`, `resolvePersonaFromURL`, `alterOptions`, `personaThemeVars`, `stageFromShowtimeEvent`, `watchShowtime`, `applyStage`, `fetchAgentTheme`, `agentThemeURL`).
- [ ] **Step 2** — add Makefile targets: `design-vendor` (`cp pmoves/design/{four}.js pmoves/ui/lib/persona/`), `design-vendor-check` (diff each pair, non-zero on drift with a "run make design-vendor" message). Mirror `design-tokens-check` style (`pmoves/Makefile:4087-4093`).
- [ ] **Step 3** — run `make -C pmoves design-vendor-check`; expect PASS (just-copied = identical). Commit.

### Task 3: Notebook env config + `PersonaStageController` client component

**Files:**
- Modify: `pmoves/ui/config/index.ts` (add `NEXT_PUBLIC_BOTZ_GATEWAY_URL` default `http://localhost:8054`, `NEXT_PUBLIC_SHOWTIME_URL` default `http://localhost:9225`)
- Create: `pmoves/ui/components/PersonaStageController.tsx` (`"use client"`)
- Test: `pmoves/ui/components/PersonaStageController.test.tsx`

Controller: on mount (`useEffect`) resolve `resolvePersonaFromURL(location.search)`; if id, `setPersona(id,{alter,gw:botzUrl})`; start `watchShowtime({gw:showtimeUrl, onState:(s)=>{applyStage(s); setLive(s==="live")}, onError:()=>{}})`; return cleanup `handle.close()`. Exposes live state via a render-prop/context or simply sets `data-stage` (pill reads attribute). Keep it dependency-injectable: accept optional `fetchImpl`/`EventSourceImpl` props defaulting to globals, so Jest can drive it.

- [ ] **Step 1 — failing test** (`PersonaStageController.test.tsx`, jsdom): render with an injected `EventSourceImpl` stub + `fetchImpl`; assert (a) a persona in `?agent=x` triggers a theme fetch and `document.documentElement.style` gets `--pm-accent`; (b) emitting a `showtime.all_green.v1` frame sets `document.documentElement.dataset.stage === "live"`; (c) unmount calls the ES `close()`.
- [ ] **Step 2** — `npm test -- PersonaStageController` (from `pmoves/ui`); expect FAIL.
- [ ] **Step 3 — implement** the component + config additions.
- [ ] **Step 4** — run test; expect PASS. Commit.

### Task 4: Live-stage CSS + `LiveStageBadge`

**Files:**
- Modify: `pmoves/ui/app/globals.css` (add `:root[data-stage="live"]` block intensifying `--pm-signature` glow, per D4 — never recolor)
- Create: `pmoves/ui/components/LiveStageBadge.tsx`
- Test: `pmoves/ui/components/LiveStageBadge.test.tsx`

- [ ] **Step 1 — failing test**: `LiveStageBadge` renders nothing (or `hidden`) when not live, and a "LIVE" pill when `data-stage="live"` / `live` prop true. Pattern after `GraphitiStatusBadge.tsx`.
- [ ] **Step 2** — `npm test -- LiveStageBadge`; expect FAIL.
- [ ] **Step 3 — implement** badge + the `:root[data-stage="live"] { }` CSS (glow on the signature mark; keep `--pm-signature` value unchanged — intensify only).
- [ ] **Step 4** — run test; expect PASS. Commit.

### Task 5: Mount into Notebook

**Files:**
- Modify: `pmoves/ui/components/NotebookWorkbenchView.tsx` (render `<PersonaStageController/>` near the existing effect ~lines 63-71; render `<LiveStageBadge/>` in the header near `GraphitiStatusBadge` ~line 204)
- Test: extend/add a `NotebookWorkbenchView` test if one exists; else a light smoke test that the controller + badge mount without error.

- [ ] **Step 1 — failing/smoke test**: rendering `NotebookWorkbenchView` includes the controller and badge (mock the design modules or inject stubs) without throwing.
- [ ] **Step 2** — run; expect FAIL (not yet mounted).
- [ ] **Step 3 — implement** the mount.
- [ ] **Step 4** — `npm test` (full Notebook Jest suite green). Commit.

### Task 6: CORS allow-list — add Notebook origin to both services

**Files:**
- Modify: `pmoves/services/showtime-api/app.py:211` default → `http://localhost:3000,http://localhost:3001,http://localhost:4482,http://localhost:9225`
- Modify: `pmoves/services/botz-gateway/main.py:173` default → same
- Test: extend `pmoves/services/botz-gateway/test_cors.py` (assert `:4482` echoed on preflight + GET); add/extend a showtime CORS test if one exists, else add `pmoves/services/showtime-api/test_cors.py` mirroring the botz one.

- [ ] **Step 1 — failing test**: assert a request from `http://localhost:4482` gets `access-control-allow-origin: http://localhost:4482` on both services; an unlisted origin does not.
- [ ] **Step 2** — run pytest; expect FAIL (4482 not yet listed).
- [ ] **Step 3 — implement** the two default changes.
- [ ] **Step 4** — `python -m pytest pmoves/services/botz-gateway/test_cors.py pmoves/services/showtime-api/test_cors.py -q`; expect PASS. Commit.

### Task 7: Docs + spec note

**Files:**
- Modify: `pmoves/design/README.md` (note the `/health/all` poll fallback + the Notebook vendor + `design-vendor-check`)
- Modify: `docs/superpowers/specs/2026-06-15-pmoves-unified-design-language.md` (italic "DL-3.2 landed 2026-07-04 — Notebook adoption + Showtime live" after the phasing table)
- Modify: `pmoves/ui/README.md` if it documents theme wiring

- [ ] **Step 1** — apply doc edits. **Step 2** — `make -C pmoves docs-reconcile-check` if applicable. Commit.

---

## Self-review notes
- **Spec coverage:** D4 SSE + `/health/all` poll (T1), D3 `--pm-*` override in Notebook (T3/T4), D2 `?agent=` transport reused via `resolvePersonaFromURL` (T3), canon guard preserved (vendored code unchanged; CSS intensifies never recolors — T4). ✓
- **Drift:** vendored copies guarded by `design-vendor-check` (T2). ✓
- **Type consistency:** controller calls `setPersona`/`watchShowtime`/`applyStage`/`resolvePersonaFromURL` — names verified against `theme-provider.js:33`, `showtime-live.js:23/13`, `persona-theme.js:17`. ✓
- **No live-service dependency at test time:** all tests inject `fetchImpl`/`EventSourceImpl`. ✓
