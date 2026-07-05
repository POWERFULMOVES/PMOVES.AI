# DL-3.1 Persona-Adaptive Runtime Theme Resolver — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a thin runtime resolver to `pmoves/design/` that overlays the active agent's accent family onto the base theme via `GET /v1/agent/theme/{id}`, plus a Showtime "live" flip, proven on the preview page.

**Architecture:** Dependency-free ESM modules. Pure logic (var mapping, URL parse, event→stage) is separated from I/O (fetch, EventSource, DOM) so it tests hermetically under Node's built-in `node --test`. `--pm-signature` (reserved `✦` crimson) is never touched — accent family only.

**Tech Stack:** Vanilla ESM JS, `node:test` + `node:assert` (Node ≥22, no npm deps), the existing BoTZ Gateway `:8054` + Showtime `:9225` HTTP APIs.

**Spec:** [`docs/superpowers/specs/2026-07-02-dl-3-persona-adaptive-resolver-design.md`](../specs/2026-07-02-dl-3-persona-adaptive-resolver-design.md).

---

### Task 1: Test scaffolding (ESM + runner + make target)

**Files:**
- Create: `pmoves/design/package.json`
- Create: `pmoves/design/tests/persona-theme.test.js`
- Modify: `pmoves/Makefile:4082` area (add `design-test-js` target)

- [ ] **Step 1: Make `.js` ESM for Node, and mark private**

Create `pmoves/design/package.json` (browser ignores it; Node uses it so `import`/`export` in the existing `theme-provider.js`/`preview.js` load as ESM under `node --test`):

```json
{
  "name": "pmoves-design",
  "private": true,
  "type": "module",
  "description": "PMOVES design token layer — browser-loaded ESM; no build deps."
}
```

- [ ] **Step 2: Write a smoke test proving the runner works**

`pmoves/design/tests/persona-theme.test.js`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";

test("runner smoke", () => {
  assert.equal(1 + 1, 2);
});
```

- [ ] **Step 3: Run it**

Run: `node --test pmoves/design/tests/`
Expected: `# pass 1`, exit 0.

- [ ] **Step 4: Add a make target**

In `pmoves/Makefile`, extend the design `.PHONY` line and append a target after `design-tokens-check` (around line 4095):

```makefile
.PHONY: design-tokens design-tokens-check design-test-js
```

```makefile
design-test-js: ## Run the pmoves/design JS unit tests (node --test, no npm deps)
	node --test design/tests/
```

- [ ] **Step 5: Run via make + commit**

Run: `make -C pmoves design-test-js`
Expected: pass, exit 0.

```bash
git add pmoves/design/package.json pmoves/design/tests/persona-theme.test.js pmoves/Makefile
git commit -m "test(dl-3): node --test scaffolding for pmoves/design JS"
```

---

### Task 2: `personaThemeVars` — pure var mapping (accent family only)

**Files:**
- Create: `pmoves/design/persona-theme.js`
- Test: `pmoves/design/tests/persona-theme.test.js`

- [ ] **Step 1: Write the failing tests**

Append to `pmoves/design/tests/persona-theme.test.js`:

```js
import { personaThemeVars } from "../persona-theme.js";

test("personaThemeVars maps color->accent, accent->soft+2", () => {
  const v = personaThemeVars({ color: "#00FFCC", accent: "#5EEAD4" });
  assert.equal(v["--pm-accent"], "#00FFCC");
  assert.equal(v["--pm-accent-soft"], "#5EEAD4");
  assert.equal(v["--pm-accent-2"], "#5EEAD4");
});

test("personaThemeVars NEVER sets signature/bg/ink (canon guard)", () => {
  const v = personaThemeVars({ color: "#00FFCC", accent: "#5EEAD4" });
  assert.equal(v["--pm-signature"], undefined);
  assert.equal(v["--pm-bg"], undefined);
  assert.equal(v["--pm-ink"], undefined);
  assert.equal(v["--pm-void"], undefined);
});

test("personaThemeVars tolerates missing fields", () => {
  assert.deepEqual(personaThemeVars({}), {});
  assert.deepEqual(personaThemeVars(null), {});
  assert.deepEqual(personaThemeVars({ color: "#abc" }), { "--pm-accent": "#abc" });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test pmoves/design/tests/`
Expected: FAIL — `Cannot find module '../persona-theme.js'`.

- [ ] **Step 3: Implement the minimal module**

`pmoves/design/persona-theme.js`:

```js
// pmoves/design/persona-theme.js — pure, DOM-free helpers for the persona resolver.
// Overrides the ACCENT FAMILY only. --pm-signature (reserved ✦ crimson) is never touched.

/** Map a gateway theme object -> the --pm-* custom properties to override. */
export function personaThemeVars(theme) {
  if (!theme || typeof theme !== "object") return {};
  const out = {};
  if (theme.color) out["--pm-accent"] = theme.color;
  if (theme.accent) {
    out["--pm-accent-soft"] = theme.accent;
    out["--pm-accent-2"] = theme.accent;
  }
  return out;
}
```

- [ ] **Step 4: Run to verify pass**

Run: `node --test pmoves/design/tests/`
Expected: PASS (all personaThemeVars tests green).

- [ ] **Step 5: Commit**

```bash
git add pmoves/design/persona-theme.js pmoves/design/tests/persona-theme.test.js
git commit -m "feat(dl-3): personaThemeVars — accent-family var mapping (signature reserved)"
```

---

### Task 3: `resolvePersonaFromURL` — identity transport parse

**Files:**
- Modify: `pmoves/design/persona-theme.js`
- Test: `pmoves/design/tests/persona-theme.test.js`

- [ ] **Step 1: Write the failing tests**

Append:

```js
import { resolvePersonaFromURL } from "../persona-theme.js";

test("resolvePersonaFromURL parses agent/alter/gw", () => {
  assert.deepEqual(
    resolvePersonaFromURL("?agent=darkxside&alter=ghost&gw=http://h:8054"),
    { id: "darkxside", alter: "ghost", gw: "http://h:8054" }
  );
});

test("resolvePersonaFromURL defaults alter/gw to null", () => {
  assert.deepEqual(resolvePersonaFromURL("?agent=4090-claude"), {
    id: "4090-claude", alter: null, gw: null,
  });
});

test("resolvePersonaFromURL returns null with no agent", () => {
  assert.equal(resolvePersonaFromURL(""), null);
  assert.equal(resolvePersonaFromURL("?foo=1"), null);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test pmoves/design/tests/`
Expected: FAIL — `resolvePersonaFromURL is not a function`.

- [ ] **Step 3: Implement**

Append to `pmoves/design/persona-theme.js`:

```js
/** Parse ?agent=<id>&alter=<name>&gw=<url> -> {id, alter, gw} | null. */
export function resolvePersonaFromURL(search) {
  const p = new URLSearchParams(search || "");
  const id = p.get("agent");
  if (!id) return null;
  return { id, alter: p.get("alter") || null, gw: p.get("gw") || null };
}
```

- [ ] **Step 4: Run to verify pass**

Run: `node --test pmoves/design/tests/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pmoves/design/persona-theme.js pmoves/design/tests/persona-theme.test.js
git commit -m "feat(dl-3): resolvePersonaFromURL — ?agent=/&alter=/&gw= transport"
```

---

### Task 4: `stageFromShowtimeEvent` — Showtime state → stage

**Files:**
- Modify: `pmoves/design/persona-theme.js`
- Test: `pmoves/design/tests/persona-theme.test.js`

- [ ] **Step 1: Write the failing tests**

Append:

```js
import { stageFromShowtimeEvent } from "../persona-theme.js";

test("stageFromShowtimeEvent: showtime -> live", () => {
  assert.equal(stageFromShowtimeEvent({ state: "showtime" }), "live");
  assert.equal(stageFromShowtimeEvent("showtime"), "live");
});

test("stageFromShowtimeEvent: hold/preflight/junk -> null", () => {
  assert.equal(stageFromShowtimeEvent({ state: "hold" }), null);
  assert.equal(stageFromShowtimeEvent({ state: "preflight" }), null);
  assert.equal(stageFromShowtimeEvent(null), null);
  assert.equal(stageFromShowtimeEvent({}), null);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test pmoves/design/tests/`
Expected: FAIL — `stageFromShowtimeEvent is not a function`.

- [ ] **Step 3: Implement**

Append to `pmoves/design/persona-theme.js`:

```js
/** Showtime event (or bare state string) -> "live" | null. */
export function stageFromShowtimeEvent(evt) {
  const state = typeof evt === "string" ? evt : evt && evt.state;
  return state === "showtime" ? "live" : null;
}
```

- [ ] **Step 4: Run to verify pass**

Run: `node --test pmoves/design/tests/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pmoves/design/persona-theme.js pmoves/design/tests/persona-theme.test.js
git commit -m "feat(dl-3): stageFromshowtimeEvent — showtime state -> live stage"
```

---

### Task 5: `fetchAgentTheme` — gateway-direct network layer (no whoami/Supabase)

**Files:**
- Create: `pmoves/design/persona-resolver.js`
- Test: `pmoves/design/tests/persona-resolver.test.js`

- [ ] **Step 1: Write the failing tests**

`pmoves/design/tests/persona-resolver.test.js`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { agentThemeURL, fetchAgentTheme } from "../persona-resolver.js";

test("agentThemeURL is id-only by default (NO whoami, NO supabase)", () => {
  const u = agentThemeURL("4090-claude");
  assert.equal(u, "http://localhost:8054/v1/agent/theme/4090-claude");
  assert.ok(!u.includes("whoami"));
  assert.ok(!u.includes("supabase"));
});

test("agentThemeURL builds the alter path", () => {
  assert.equal(
    agentThemeURL("minimax", { alter: "minimax-ghost", gw: "http://h:8054/" }),
    "http://h:8054/v1/agent/theme/minimax/alter/minimax-ghost"
  );
});

test("fetchAgentTheme returns json via injected fetch", async () => {
  const calls = [];
  const fetchImpl = async (url) => {
    calls.push(url);
    return { ok: true, status: 200, json: async () => ({ agent_id: "darkxside", color: "#E11D48", accent: "#F43F5E" }) };
  };
  const theme = await fetchAgentTheme("darkxside", { fetchImpl });
  assert.equal(theme.color, "#E11D48");
  assert.equal(calls[0], "http://localhost:8054/v1/agent/theme/darkxside");
});

test("fetchAgentTheme throws on non-ok", async () => {
  const fetchImpl = async () => ({ ok: false, status: 404, json: async () => ({}) });
  await assert.rejects(() => fetchAgentTheme("nope", { fetchImpl }), /404/);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test pmoves/design/tests/`
Expected: FAIL — `Cannot find module '../persona-resolver.js'`.

- [ ] **Step 3: Implement**

`pmoves/design/persona-resolver.js`:

```js
// pmoves/design/persona-resolver.js — gateway-direct theme fetch.
// Deliberately calls GET /v1/agent/theme/{id} ONLY — no whoami, no Supabase (spec D2).

const DEFAULT_GW = "http://localhost:8054";

/** Build the theme URL (id-only, or the alter variant). */
export function agentThemeURL(id, { alter = null, gw = DEFAULT_GW } = {}) {
  const base = String(gw).replace(/\/+$/, "");
  const path = alter
    ? `/v1/agent/theme/${encodeURIComponent(id)}/alter/${encodeURIComponent(alter)}`
    : `/v1/agent/theme/${encodeURIComponent(id)}`;
  return base + path;
}

/** Fetch a gateway theme object. `fetchImpl` is injectable for tests. */
export async function fetchAgentTheme(id, opts = {}) {
  const fetchImpl = opts.fetchImpl || (typeof fetch !== "undefined" ? fetch : null);
  if (!fetchImpl) throw new Error("no fetch available");
  const url = agentThemeURL(id, opts);
  const res = await fetchImpl(url);
  if (!res.ok) throw new Error(`theme ${id} -> HTTP ${res.status}`);
  return res.json();
}
```

- [ ] **Step 4: Run to verify pass**

Run: `node --test pmoves/design/tests/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pmoves/design/persona-resolver.js pmoves/design/tests/persona-resolver.test.js
git commit -m "feat(dl-3): fetchAgentTheme — gateway-direct, id-only (no whoami/supabase)"
```

---

### Task 6: `setPersona` / `clearPersona` — DOM orchestration in theme-provider

**Files:**
- Modify: `pmoves/design/theme-provider.js`
- Test: `pmoves/design/tests/theme-provider.test.js`

- [ ] **Step 1: Write the failing tests** (fake root, no jsdom)

`pmoves/design/tests/theme-provider.test.js`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyPersonaThemeToRoot, clearPersona, setPersona } from "../theme-provider.js";

function fakeRoot() {
  const props = {};
  return {
    props,
    style: {
      setProperty: (k, v) => { props[k] = v; },
      removeProperty: (k) => { delete props[k]; },
    },
  };
}

test("applyPersonaThemeToRoot sets accent family, not signature", () => {
  const root = fakeRoot();
  applyPersonaThemeToRoot({ color: "#00FFCC", accent: "#5EEAD4" }, root);
  assert.equal(root.props["--pm-accent"], "#00FFCC");
  assert.equal(root.props["--pm-accent-soft"], "#5EEAD4");
  assert.equal(root.props["--pm-accent-2"], "#5EEAD4");
  assert.equal(root.props["--pm-signature"], undefined);
});

test("clearPersona removes only the accent family", () => {
  const root = fakeRoot();
  applyPersonaThemeToRoot({ color: "#00FFCC", accent: "#5EEAD4" }, root);
  clearPersona(root);
  assert.equal(root.props["--pm-accent"], undefined);
  assert.equal(root.props["--pm-accent-2"], undefined);
});

test("setPersona fetches then applies (injected fetch + root)", async () => {
  const root = fakeRoot();
  const fetchImpl = async () => ({ ok: true, status: 200, json: async () => ({ color: "#7C3AED", accent: "#A78BFA" }) });
  await setPersona("claude-opus", { root, fetchImpl });
  assert.equal(root.props["--pm-accent"], "#7C3AED");
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test pmoves/design/tests/`
Expected: FAIL — `applyPersonaThemeToRoot is not exported`.

- [ ] **Step 3: Implement (append to existing file, keep setTheme/toggleTheme intact)**

Append to `pmoves/design/theme-provider.js`:

```js
import { personaThemeVars } from "./persona-theme.js";
import { fetchAgentTheme } from "./persona-resolver.js";

const PERSONA_VARS = ["--pm-accent", "--pm-accent-soft", "--pm-accent-2"];

/** Apply an accent-family override from a gateway theme object onto a root element. */
export function applyPersonaThemeToRoot(theme, root = document.documentElement) {
  const vars = personaThemeVars(theme);
  for (const [k, v] of Object.entries(vars)) root.style.setProperty(k, v);
  return vars;
}

/** Remove the persona override, reverting to the base theme's accents. */
export function clearPersona(root = document.documentElement) {
  for (const k of PERSONA_VARS) root.style.removeProperty(k);
}

/** Resolve an agent id -> gateway theme -> applied accent override. */
export async function setPersona(id, opts = {}) {
  const root = opts.root || document.documentElement;
  const theme = await fetchAgentTheme(id, opts);
  return applyPersonaThemeToRoot(theme, root);
}
```

- [ ] **Step 4: Run to verify pass**

Run: `node --test pmoves/design/tests/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pmoves/design/theme-provider.js pmoves/design/tests/theme-provider.test.js
git commit -m "feat(dl-3): setPersona/clearPersona accent-override on theme-provider"
```

---

### Task 7: `watchShowtime` — SSE live flip with data-stage

**Files:**
- Create: `pmoves/design/showtime-live.js`
- Test: `pmoves/design/tests/showtime-live.test.js`

- [ ] **Step 1: Write the failing tests** (stub EventSource)

`pmoves/design/tests/showtime-live.test.js`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { applyStage, watchShowtime } from "../showtime-live.js";

function fakeRoot() {
  const dataset = {};
  return { dataset };
}

test("applyStage sets/clears data-stage", () => {
  const root = fakeRoot();
  applyStage("live", root);
  assert.equal(root.dataset.stage, "live");
  applyStage(null, root);
  assert.equal(root.dataset.stage, undefined);
});

test("watchShowtime maps an SSE 'showtime' message to onState('live')", () => {
  const seen = [];
  let inst;
  class StubES {
    constructor(url) { this.url = url; inst = this; }
    close() { this.closed = true; }
  }
  const handle = watchShowtime({
    gw: "http://localhost:9225",
    EventSourceImpl: StubES,
    onState: (s) => seen.push(s),
  });
  assert.equal(inst.url, "http://localhost:9225/sse/events");
  inst.onmessage({ data: JSON.stringify({ state: "showtime", source: "showtime-api" }) });
  inst.onmessage({ data: JSON.stringify({ state: "hold" }) });
  inst.onmessage({ data: "not json" });
  assert.deepEqual(seen, ["live", null]);
  handle.close();
  assert.equal(inst.closed, true);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test pmoves/design/tests/`
Expected: FAIL — `Cannot find module '../showtime-live.js'`.

- [ ] **Step 3: Implement**

`pmoves/design/showtime-live.js`:

```js
// pmoves/design/showtime-live.js — browser bridge to Showtime (:9225) for the "live" flip.
// SSE over GET /sse/events; no NATS-in-browser needed (spec D4).
import { stageFromShowtimeEvent } from "./persona-theme.js";

const DEFAULT_GW = "http://localhost:9225";

/** Set or clear documentElement[data-stage]. */
export function applyStage(stage, root = document.documentElement) {
  if (stage) root.dataset.stage = stage;
  else delete root.dataset.stage;
}

/**
 * Subscribe to Showtime SSE and call onState(stage) on each event.
 * EventSourceImpl is injectable for tests. Returns { close() }.
 */
export function watchShowtime(opts = {}) {
  const gw = String(opts.gw || DEFAULT_GW).replace(/\/+$/, "");
  const onState = opts.onState || (() => {});
  const ES = opts.EventSourceImpl || (typeof EventSource !== "undefined" ? EventSource : null);
  if (!ES) return { close() {} };
  const es = new ES(gw + "/sse/events");
  es.onmessage = (m) => {
    let data;
    try { data = JSON.parse(m.data); } catch { return; }
    onState(stageFromShowtimeEvent(data));
  };
  return { close: () => es.close() };
}
```

- [ ] **Step 4: Run to verify pass**

Run: `node --test pmoves/design/tests/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pmoves/design/showtime-live.js pmoves/design/tests/showtime-live.test.js
git commit -m "feat(dl-3): watchShowtime — SSE live flip -> data-stage"
```

---

### Task 8: Preview UI — persona/alter picker + live toggle (CSP-clean)

**Files:**
- Modify: `pmoves/design/preview.html`
- Modify: `pmoves/design/preview.js`
- Modify: `pmoves/design/preview.css`
- Test: `pmoves/design/tests/preview-cspclean.test.js`

- [ ] **Step 1: Write the failing CSP-clean guard test**

`pmoves/design/tests/preview-cspclean.test.js`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const html = readFileSync(fileURLToPath(new URL("../preview.html", import.meta.url)), "utf8");

test("preview.html has no inline <script> (CSP-clean)", () => {
  // every <script> must carry a src=
  const scripts = html.match(/<script\b[^>]*>/gi) || [];
  for (const s of scripts) assert.ok(/\bsrc=/.test(s), `inline script: ${s}`);
});

test("preview.html has no inline <style> block", () => {
  assert.ok(!/<style\b/i.test(html), "inline <style> present");
});

test("preview.html exposes the persona + alter pickers + live toggle", () => {
  assert.ok(/id="persona"/.test(html), "missing #persona select");
  assert.ok(/id="alter"/.test(html), "missing #alter select");
  assert.ok(/id="live"/.test(html), "missing #live toggle");
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test pmoves/design/tests/`
Expected: FAIL — missing `#persona`/`#alter`/`#live`.

- [ ] **Step 3: Add the controls to `preview.html`**

Insert this block right after the existing `<header>…</header>` in `pmoves/design/preview.html`:

```html
  <section class="persona-bar">
    <label>Persona
      <select id="persona"><option value="">— base theme —</option></select>
    </label>
    <label>Alter
      <select id="alter"><option value="">— none —</option></select>
    </label>
    <label class="live-toggle">
      <input type="checkbox" id="live"> simulate Showtime <span class="star">✦</span> live
    </label>
    <span id="persona-status" class="status" role="status"></span>
  </section>
```

- [ ] **Step 4: Wire the controls in `preview.js`** (replace the file body; keep the toggle button)

`pmoves/design/preview.js`:

```js
// pmoves/design/preview.js
import { toggleTheme } from "./theme-provider.js";
import { setPersona, clearPersona } from "./theme-provider.js";
import { applyStage } from "./showtime-live.js";
import { resolvePersonaFromURL } from "./persona-theme.js";

const $ = (id) => document.getElementById(id);
const url = resolvePersonaFromURL(location.search);
const GW = (url && url.gw) || "http://localhost:8054";
const status = (msg) => { $("persona-status").textContent = msg; };

$("toggle").addEventListener("click", () => toggleTheme());

// Populate persona dropdown from the gateway signature registry.
async function loadPersonas() {
  try {
    const res = await fetch(`${GW}/v1/agent/signatures`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { signatures } = await res.json();
    const sel = $("persona");
    for (const id of Object.keys(signatures)) {
      const o = document.createElement("option");
      o.value = id; o.textContent = signatures[id].display_name || id;
      sel.appendChild(o);
    }
  } catch (e) {
    status(`gateway offline (${GW}) — base theme only`);
  }
}

async function apply() {
  const id = $("persona").value;
  const alter = $("alter").value || null;
  if (!id) { clearPersona(); status("base theme"); return; }
  try {
    await setPersona(id, { alter, gw: GW });
    status(`persona: ${id}${alter ? " / " + alter : ""}`);
  } catch (e) {
    status(`failed: ${e.message}`);
  }
}

$("persona").addEventListener("change", apply);
$("alter").addEventListener("change", apply);
$("live").addEventListener("change", (e) => applyStage(e.target.checked ? "live" : null));

await loadPersonas();
// honor ?agent= on load
if (url && url.id) {
  $("persona").value = url.id;
  if (url.alter) $("alter").value = url.alter;
  await apply();
}
```

- [ ] **Step 5: Add minimal styles + the live-stage emphasis to `preview.css`**

Append to `pmoves/design/preview.css`:

```css
.persona-bar { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; margin: 1rem 0; }
.persona-bar select { background: var(--pm-surface); color: var(--pm-ink); border: 1px solid var(--pm-accent-soft); padding: .25rem .5rem; }
.persona-bar .status { opacity: .7; font-size: .85rem; }
/* Showtime "live": intensify the reserved ✦ crimson signature (never recolored). */
:root[data-stage="live"] .star { color: var(--pm-signature); text-shadow: 0 0 .5rem var(--pm-signature); }
```

- [ ] **Step 6: Run tests to verify pass**

Run: `node --test pmoves/design/tests/`
Expected: PASS (CSP-clean guard + control presence).

- [ ] **Step 7: Manual smoke (optional, needs gateway)**

Serve `pmoves/design/` statically and open `preview.html?agent=darkxside`. With BoTZ Gateway `:8054` up, the accent family recolors; the `✦` stays crimson; ticking "live" glows it. Without the gateway, status shows "gateway offline" and the base theme holds. (Document result; not a gating step.)

- [ ] **Step 8: Commit**

```bash
git add pmoves/design/preview.html pmoves/design/preview.js pmoves/design/preview.css pmoves/design/tests/preview-cspclean.test.js
git commit -m "feat(dl-3): preview persona/alter picker + Showtime live toggle (CSP-clean)"
```

---

### Task 9: Docs + full green + finish

**Files:**
- Modify: `pmoves/design/README.md`
- Modify: `docs/superpowers/specs/2026-06-15-pmoves-unified-design-language.md` (mark DL-3.1 landed)

- [ ] **Step 1: Document the resolver in the design README**

Append a `## DL-3 persona resolver` section to `pmoves/design/README.md`:

```markdown
## DL-3 persona resolver (runtime accent-override)

`setPersona(id, {alter, gw})` overlays the active agent's accent family
(`--pm-accent`, `--pm-accent-soft`, `--pm-accent-2`) from `GET /v1/agent/theme/{id}`
onto the current base theme. `--pm-signature` (the reserved ✦ crimson) is never
touched. Identity is `?agent=<id>[&alter=<name>]`; Showtime `:9225` `/sse/events`
drives `data-stage="live"`. Tests: `make -C pmoves design-test-js` (node --test, no deps).
```

- [ ] **Step 2: Run the full suites (JS + the DL-1 Python generator test)**

Run: `make -C pmoves design-test-js`
Expected: all pass.

Run: `cd pmoves/design && uv run --no-project --with pyyaml pytest tests/test_generate.py -q`
Expected: DL-1 generator tests still green (no regression).

Run: `make -C pmoves design-tokens-check`
Expected: `✅ design/build matches generator output` (we changed no tokens).

- [ ] **Step 3: Commit**

```bash
git add pmoves/design/README.md docs/superpowers/specs/2026-06-15-pmoves-unified-design-language.md
git commit -m "docs(dl-3): README resolver section + mark DL-3.1 landed"
```

- [ ] **Step 4: Finish the branch**

**REQUIRED SUB-SKILL:** Use superpowers:finishing-a-development-branch. Verify `make -C pmoves design-test-js` passes, then present options (expected: push + PR to `main`, base `feat/dl-3-persona-adaptive-resolver`, invite 4090 pair-review as the `/v1/agent/*` W1 lane owner).

---

## Self-review notes
- **Spec coverage:** D1 accent-override (Task 2, 6) · D2 gateway-direct identity (Task 3, 5) · D3 accent-only, no bg/ink (Task 2/6 guards) · D4 Showtime SSE (Task 7) · D5 no-flash/fallback (Task 6 clearPersona + Task 8 offline status). Canon guard (signature reserved) asserted in Tasks 2 + 6.
- **No new runtime deps:** `node --test` is stdlib; browser code stays vanilla ESM.
- **Read-only against 4090's lane:** consumes `/v1/agent/*`, never edits gateway routes, generator, registry, or base themes.
- **Type consistency:** `personaThemeVars`, `fetchAgentTheme`, `applyPersonaThemeToRoot`, `setPersona`, `watchShowtime`, `applyStage`, `resolvePersonaFromURL`, `stageFromShowtimeEvent` — names identical across tasks.
