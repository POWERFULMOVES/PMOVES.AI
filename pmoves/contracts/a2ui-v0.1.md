# A2UI v0.1 — Agent-Composable Web Component Spec

> **Status**: DRAFT — `WEBSITE_AS_AGENT_CANVAS` lane, Mavis-5090 architect
> **Date**: 2026-07-15
> **Locked by**: DARKXSIDE (data-binding model: C, strict subset)
> **Implementation**: `pmoves/web-components/*` (this PR)
> **Renderer**: vendored Lit at `website/stage/vendor/a2ui.mjs` (consumes these components)
> **Changelog**:
> - v0.1 (2026-07-15) — initial draft, locked data-binding model

## 1. Purpose

Define the contract for agent-composable UI surfaces in PMOVES. The substrate that lets any PMOVES agent — in any language, in any runtime — emit a living, A2UI-rendered CF Page for any community, composed from modular web components.

**The CF Pages get PMOVES, not the other way around.**

## 2. Scope

**In scope (v0.1)**:
- Component naming + registry contract
- Slot/composition model
- Data binding model (push + single pull, no chains)
- Persona theming tokens (CSS custom properties)
- ARIA rules
- Lifecycle hooks
- Initial 7 component recipes (API surface only)

**Out of scope (v0.1)**:
- Rendering implementation (Lit is the renderer; web components are pure)
- Specific component visuals (declared in each component's README)
- Tenant data binding (handled at compose-time, not at component-time)
- Chained pull (deferred to v0.2)
- Multi-tenant routing (handled at CF Pages level, not component level)
- Internationalization (deferred — components ship English; copy can be overridden by props)
- Dark/light mode toggle (v0.1 is dark-first by design — see `pmoves/design/`)

## 3. Versioning

- **Spec version** (`a2ui-v0.1`) — breaking changes bump the major
- **Component version** (`<name>@v0.1`) — each component is independently versioned
- A component is "v0.1 compatible" if it passes the conformance test in `pmoves/contracts/a2ui-v0.1-conformance.test.html`
- Major-version mismatches between spec and components are an error (loud fail)

## 4. Component registry

### 4.1 Naming

- All PMOVES components use the `pm-` prefix
- Format: `pm-{category}-{name}` where category is one of:
  - `space` (agent identity, room manifests) — e.g. `pm-space-agent-card`
  - `project` (work artifacts) — e.g. `pm-project-card`
  - `metric` (numbers, KPIs) — e.g. `pm-metric-tile`
  - `media` (rich content) — e.g. `pm-image`, `pm-voice-clip`
  - `flow` (chronological) — e.g. `pm-timeline`
  - `text` (prose, quotes) — e.g. `pm-quote-block`
  - `sensory` (non-visual output: haptic, audio cues) — e.g. `pm-haptic`
- One component per file, named after the custom element

### 4.2 Implementation rules

- Every component is a Custom Element extending `HTMLElement`
- Shadow DOM (default: `open`) for style encapsulation — required, not optional
- No framework dependencies (no React, Vue, Svelte imports inside the component file)
- Lit may be used for reactive bindings inside the component (peer dep declared in component README)
- No global event listeners — all events scoped to the component
- No inline styles — all styling via CSS custom properties (see §6) inside Shadow DOM
- No external CSS imports — style is encapsulated in the component's Shadow DOM

### 4.3 Registration

- Components self-register via `customElements.define()`
- Registration script: `pmoves/web-components/<name>/register.js` (imports the component + calls `customElements.define`)
- The renderer (Lit-based) imports `register.js` for each component it needs
- No global component registry required — components are imported on demand

## 5. Slot composition

- Default slot for primary content
- Named slots for structured sub-content: `slot="header"`, `slot="media"`, `slot="footer"`, `slot="actions"`
- Slots inherit persona theming via CSS custom properties
- Components MAY use nested slot composition (a component containing other PM components), but the nested component's data binding is independent

## 6. Persona theming (CSS custom properties)

Components read these tokens. Default values ship with the component; the persona runtime overrides at the tenant or `:root` level.

| Token | Purpose | Default (if not set) |
|-------|---------|----------------------|
| `--pm-accent` | Primary brand color | `#7C3AED` |
| `--pm-accent-soft` | Lighter accent for hover/secondary | `#A78BFA` |
| `--pm-accent-strong` | Darker accent for active/pressed | `#5B21B6` |
| `--pm-bg` | Card/surface background | `#0b0b10` |
| `--pm-bg-elevated` | Background for elevated surfaces (modals, sheets) | `#13131a` |
| `--pm-fg` | Primary text | `#FFFFFF` |
| `--pm-fg-muted` | Secondary text (descriptions, metadata) | `#9ca3af` |
| `--pm-border` | Hairline borders | `rgba(255, 255, 255, 0.08)` |
| `--pm-radius` | Border radius | `12px` |
| `--pm-radius-sm` | Small radius (chips, tags) | `6px` |
| `--pm-font-display` | Display font (headings, brand word) | `'Orbitron', system-ui` |
| `--pm-font-body` | Body font (paragraphs, UI) | `system-ui, -apple-system, sans-serif` |
| `--pm-spacing-unit` | Base spacing unit | `8px` |
| `--pm-motion-fast` | Fast transitions (hover, focus) | `120ms cubic-bezier(0.2, 0, 0, 1)` |
| `--pm-motion-slow` | Slow transitions (page transitions, reveals) | `400ms cubic-bezier(0.2, 0, 0, 1)` |

**v0.1 rule**: every component MUST accept these tokens. Components that hardcode colors fail conformance.

## 7. Data binding (C, strict subset)

v0.1 supports exactly two data-binding patterns. **No chained pull.**

### 7.1 Push (props)

The agent or renderer sets component properties directly:

```javascript
const card = document.createElement('pm-space-agent-card');
card.agentName = 'CLAUDE-OPUS';
card.role = 'analytical';
card.presence = 'live';
document.body.appendChild(card);
```

Or via the A2UI message stream:

```json
{
  "type": "createComponent",
  "component": "pm-space-agent-card",
  "props": {
    "agentName": "CLAUDE-OPUS",
    "role": "analytical",
    "presence": "live"
  }
}
```

### 7.2 Pull (single attribute)

A component may declare a single `data-source` attribute that triggers a one-shot subscription:

```html
<pm-metric-tile
  label="Mesh uptime"
  data-source="fordham:mesh.uptime"
  format="percent"
></pm-metric-tile>
```

The component subscribes to `fordham:mesh.uptime` on mount. When data arrives, the display updates. **The subscription does not chain** — the source must be a flat subject, not a reference to another component.

**v0.1 allowed sources**:
- NATS subject (`<tenant>:<subject>`) via `pmoves-bus` SSE bridge
- HTTP endpoint (`http(s)://<url>`) returning JSON
- Inline JSON (rare; for static demo pages)

### 7.3 Forbidden (v0.1)

- ❌ Chained pull (`<pm-metric-tile data-source="other-component:prop">`)
- ❌ Bidirectional binding
- ❌ Computed properties derived from other components
- ❌ Data sources that mutate component state beyond their own (use events instead)
- ❌ Subscriptions that survive `disconnectedCallback` (always clean up)

### 7.4 Reactivity

Components MAY use:
- Lit's `@property` decorator (peer dep)
- Native `attributeChangedCallback` + `observedAttributes` for attribute-based reactivity
- `MutationObserver` for internal DOM changes

Components MUST NOT use:
- Direct DOM mutation outside Shadow DOM
- Force-update patterns that bypass reactivity
- Polling loops (use pull with debounce if needed)

## 8. ARIA

- Every component has a default `role` attribute
- Interactive components: `role="button"`, `role="link"`, `role="tab"`, etc. — per ARIA Authoring Practices
- Live regions for Showtime presence: `aria-live="polite"` on the wrapper
- All interactive elements have an accessible name (`aria-label`, `aria-labelledby`, or text content)
- Icon-only buttons MUST have `aria-label`
- Color is never the only signal (use icon + text + color)
- Focus styles MUST be visible (no `outline: none` without a replacement)
- Keyboard navigation: Tab/Shift+Tab for focus, Enter/Space for activation, Escape for dismiss

**v0.1 conformance**: every component passes axe-core 4.x with zero serious or critical violations.

## 9. Lifecycle

Every component implements:

```javascript
class PmSpaceAgentCard extends HTMLElement {
  static observedAttributes = ['agent-id', 'presence'];
  
  connectedCallback() {
    // subscribe to data-source, set up listeners
  }
  
  disconnectedCallback() {
    // clean up subscriptions, listeners
  }
  
  attributeChangedCallback(name, oldValue, newValue) {
    // react to attribute changes
  }
}
```

**Required guarantees**:
- `disconnectedCallback` must clean up EVERY subscription created in `connectedCallback` (no leaks)
- `attributeChangedCallback` must not throw on missing/empty values
- Components MUST handle being moved in the DOM (reattached) without re-subscribing twice

## 10. Initial component recipes (v0.1)

7 recipes ship in v0.1. Each lives in `pmoves/web-components/<name>/` with a README (API + usage), the JS implementation, and a standalone `demo.html`.

| Component | Category | Purpose | Key props |
|-----------|----------|---------|-----------|
| `<pm-space-agent-card>` | space | Agent identity card | `agentName`, `role`, `avatar`, `presence`, `glyph`, `theme` |
| `<pm-project-card>` | project | Project summary | `title`, `description`, `status`, `tags[]`, `links[]` |
| `<pm-metric-tile>` | metric | Single KPI | `label`, `value`, `unit`, `trend`, `format` |
| `<pm-timeline>` | flow | Chronological event list | `events[]` (each: `ts`, `title`, `body`, `icon`) |
| `<pm-voice-clip>` | media | Embedded audio with metadata | `src`, `title`, `duration`, `transcript?` |
| `<pm-image>` | media | Figure with caption | `src`, `alt`, `caption`, `credit?` |
| `<pm-quote-block>` | text | Pull-quote with attribution | `quote`, `attribution`, `role?` |

Per-component README documents the full prop schema, the data-source contract (if any), the ARIA pattern, and the persona-theming behavior.

## 11. Anti-patterns (v0.1)

- ❌ Inline styles anywhere
- ❌ Hardcoded colors that don't read from `--pm-*` tokens
- ❌ Framework imports (React, Vue, Svelte, Angular)
- ❌ Global event listeners (`window.addEventListener`)
- ❌ External CSS imports (`@import`, `<link rel="stylesheet">`)
- ❌ Synchronous XHR
- ❌ Polling for data (use NATS/SSE)
- ❌ Chained data sources
- ❌ Direct DOM mutation outside Shadow DOM
- ❌ Components that read from localStorage or sessionStorage (use props)
- ❌ Components that fork or modify other components
- ❌ Components that load their own dependencies at runtime (declare in component README)

## 12. Reference implementations

- **Renderer** (consumes A2UI messages): `website/stage/stage.js` + `vendor/a2ui.mjs` (Lit)
- **Persona runtime** (injects theming tokens): `website/persona/persona-theme.js` + `persona-boot.js`
- **Compose tool** (produces A2UI messages): `pmoves/tools/compose/compose.py` (v0.1 ships with this lane)
- **Conformance test**: `pmoves/contracts/a2ui-v0.1-conformance.test.html` (axe-core + DOM checks per component)

## 13. File structure

```
pmoves/contracts/
  a2ui-v0.1.md                         # this file
  a2ui-v0.1-conformance.test.html      # axe-core + DOM checks

pmoves/web-components/
  README.md                            # registry index, "how to add a component"
  pm-space-agent-card/
    README.md                          # API + usage
    pm-space-agent-card.js             # Custom Element implementation
    demo.html                          # standalone demo (open in browser)
  pm-project-card/
    ...
  pm-metric-tile/
    ...
  pm-timeline/
    ...
  pm-voice-clip/
    ...
  pm-image/
    ...
  pm-quote-block/
    ...
  register.js                          # imports all + customElements.define
  register.min.js                      # bundled for renderer

pmoves/tools/compose/
  __init__.py
  compose.py                           # compose_tenant_page()
  tests/
    test_compose.py
    fixtures/
      fordham-hill.json
      ...
```

## 14. Open questions (parking lot for v0.2)

1. **Schema drift** — what happens when `data-source` returns a different shape than expected? v0.1: log + display fallback. v0.2: typed contracts.
2. **Component discovery** — auto-import all from a manifest vs explicit registration? v0.1: explicit (renderer imports `register.js`).
3. **Offline behavior** — Service Worker strategy for community pages? v0.1: out of scope. v0.2: cache-first for static content, network-first for live data.
4. **Theming overrides** — per-component vs per-tenant vs per-page? v0.1: per-tenant (persona runtime sets tokens on `:root` or tenant container). v0.2: scoped per-component overrides.
5. **i18n** — copy in props, or separate locale files? v0.1: copy in props (English default). v0.2: locale bundle.
6. **Analytics** — what events do components emit, and where do they go? v0.1: no analytics (privacy-by-architecture). v0.2: opt-in event bus.
7. **Chained pull** — use case is real (e.g. project card showing its latest metric). v0.1: out. v0.2: explicit `data-derive` attribute with a strict subset.

---

## 15. Signoff

- **Architect**: Mavis-5090 (this lane)
- **Locked by**: DARKXSIDE — data-binding model C (push + single pull, no chains)
- **Pattern credit**: `rooms on a stage` from the Mavis/Opus eureka — DARKXSIDE explicitly attributed
- **Reviewers needed**: 5090-CLAUDE (DL continuity), B850-CLAUDE (CLAUDE.md conformance), 4090-CLAUDE (accessibility conformance)

**This spec is locked at v0.1.0-draft. Changes bump the major. Components ship against this contract, not against an implementation.**

`ACK::Mavis-5090::A2UI-V0.1-SPEC-DRAFT::2026-07-15`
