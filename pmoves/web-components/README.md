# PMOVES Web Components — A2UI v0.1 registry

The library of agent-composable UI surfaces. Per [A2UI v0.1 spec](../contracts/a2ui-v0.1.md).

> **Pattern**: every component is a plain Web Component (Custom Element + Shadow DOM). No framework. Lit is fine for the renderer; the components themselves don't import it.
> **Pattern credit**: `rooms on a stage` from the Mavis/Opus eureka — DARKXSIDE attributed the lineage and assigned Mavis-5090 the architectural leadership role.
> **CHIT trail**: `ACK::Mavis-5090::WEBSITE-AS-AGENT-CANVAS-CLAIM::2026-07-15`

## Initial registry (v0.1)

| Component | Category | Status | File |
|-----------|----------|--------|------|
| `<pm-space-agent-card>` | space | shipped | [`pm-space-agent-card/`](./pm-space-agent-card/) |
| `<pm-project-card>` | project | shipped | [`pm-project-card/`](./pm-project-card/) |
| `<pm-metric-tile>` | metric | shipped | [`pm-metric-tile/`](./pm-metric-tile/) |
| `<pm-timeline>` | flow | **planned (v0.1)** | (TBD) |
| `<pm-voice-clip>` | media | **planned (v0.1)** | (TBD) |
| `<pm-image>` | media | **planned (v0.1)** | (TBD) |
| `<pm-quote-block>` | text | **planned (v0.1)** | (TBD) |

The first 3 ship in this lane (Mavis-5090). The remaining 4 follow as small follow-up lanes.

## How to use

### From HTML (browser)

```html
<script type="module" src="/pmoves/web-components/register.js"></script>

<pm-space-agent-card
  agent-name="CLAUDE-OPUS"
  role="analytical"
  glyph="◆"
  presence="live"
></pm-space-agent-card>
```

### From a Python agent (via the compose tool)

```python
from pmoves.tools.compose import compose_tenant_page

cfg = {
    "tenant": {"id": "fordham-hill", "name": "Fordham Hill", "theme": "armor"},
    "components": [
        {"component": "pm-space-agent-card", "props": {"agentName": "DARKXSIDE"}},
        {"component": "pm-metric-tile", "props": {"label": "Uptime", "value": "99.4", "unit": "%"}},
    ],
}

page = compose_tenant_page(cfg)
# page["messages"] is the A2UI message stream the Lit renderer consumes
```

See [`pmoves/tools/compose/`](../tools/compose/) for the full compose tool.

### From the A2UI renderer (Lit)

The renderer at `website/stage/stage.js` consumes the message stream:

```javascript
import { startA2ui } from '/stage/stage.js';
startA2ui('/stage/data/<tenant>.json');  // fetches the composed page
```

## How to add a new component

1. Create `pm-space-<your-name>/` with the standard structure:
   - `<name>.js` — the Custom Element implementation
   - `README.md` — API documentation
   - `demo.html` — standalone demo
2. Conform to the [A2UI v0.1 spec](../contracts/a2ui-v0.1.md) — every checkbox in §11
3. Register the component in `pm-space-<your-name>/register.js`
4. Add the component to `pmoves/contracts/COMPONENT_SCHEMAS` (in `compose.py`)
5. Add the component to `SUPPORTED_COMPONENTS` (in `compose.py`)
6. Run the conformance test (`pmoves/contracts/a2ui-v0.1-conformance.test.html` in a browser)
7. Add tests in `pmoves/tools/compose/tests/`

## Conformance

Every component in this registry passes:

1. **Axe-core 4.x** with zero serious/critical violations (`pmoves/contracts/a2ui-v0.1-conformance.test.html`)
2. **Token check** — no hardcoded colors; all from `--pm-*` CSS custom properties
3. **Lifecycle check** — `disconnectedCallback` cleans up every subscription created in `connectedCallback`
4. **XSS check** — all prop values are HTML-escaped before insertion
5. **Anti-pattern check** — no framework imports, no inline styles, no global listeners, no chained pull

## See also

- [A2UI v0.1 spec](../contracts/a2ui-v0.1.md) — the contract
- [Compose tool](../tools/compose/) — Python-side message production
- `website/stage/` — Lit renderer (consumes these components)
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — AGNOTE trail
