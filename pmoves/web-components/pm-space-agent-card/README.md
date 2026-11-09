# `<pm-space-agent-card>` — v0.1

Agent identity card. Avatar (or brand glyph) + name + role + live presence signal. The most-used surface in the v0.1 registry — every community page that lists agents uses this.

> **Spec**: [A2UI v0.1 §10](../../../contracts/a2ui-v0.1.md#10-initial-component-recipes-v01)
> **Conformance**: passes axe-core 4.x (no serious/critical), reads `--pm-*` tokens, Shadow DOM `open`.

## Usage

### HTML

```html
<pm-space-agent-card
  agent-name="CLAUDE-OPUS"
  role="analytical"
  glyph="◆"
  presence="live"
  theme="armor"
></pm-space-agent-card>
```

### JavaScript

```javascript
const card = document.createElement('pm-space-agent-card');
card.agentName = 'CLAUDE-OPUS';
card.role = 'analytical';
card.glyph = '◆';
card.presence = 'live';
document.body.appendChild(card);
```

### A2UI message (from compose tool)

```json
{
  "type": "createComponent",
  "component": "pm-space-agent-card",
  "props": {
    "agentName": "CLAUDE-OPUS",
    "role": "analytical",
    "glyph": "◆",
    "presence": "live",
    "theme": "armor"
  }
}
```

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `agent-name` | string | `""` | Display name. Falls back to "Unnamed agent" if empty. |
| `role` | string | `""` | Optional role label (e.g., "analytical", "creative", "ops"). |
| `avatar` | string (URL) | `null` | Optional image URL. If present, replaces the glyph. |
| `presence` | `"live"` \| `"rehearsal"` \| `"offline"` | `"offline"` | Live presence signal. Live region announced. |
| `glyph` | string | `"◆"` | Brand glyph shown when no avatar. Unicode-safe. |
| `theme` | string | `"armor"` | Reserved for future theme variants. v0.1 reads CSS custom properties; theme is metadata only. |
| `data-source` | string | `null` | Pull a single subject for live presence updates. See §"Data source" below. |

## Data source (v0.1)

The `data-source` attribute subscribes to a single subject for live presence updates. Per A2UI v0.1 §7.2, **no chained pull**.

**Allowed shapes**:
- **NATS subject** (via pmoves-bus SSE bridge): `"<tenant>:<subject>"` — e.g. `"fordham:agents.opus.presence"`
- **HTTP endpoint**: `"http(s)://<url>"` — returns JSON `{ "presence": "live|rehearsal|offline" }`

**Example (NATS)**:
```html
<pm-space-agent-card
  agent-name="CLAUDE-OPUS"
  role="analytical"
  data-source="fordham:agents.opus.presence"
></pm-space-agent-card>
```

**Example (HTTP)**:
```html
<pm-space-agent-card
  agent-name="DARKXSIDE"
  role="operator"
  data-source="https://api.pmoves.ai/tenants/fordham/agents/darkxside/presence"
></pm-space-agent-card>
```

**Offline / malformed data**: per spec §13.3 v0.1, the component logs the error and keeps the current `presence` value (graceful degradation). No exceptions are thrown.

## ARIA

- Outer: `role="article"`, `aria-label="Agent card: <name>"`
- Presence: `aria-live="polite"` so screen readers announce status changes
- Avatar: empty `alt=""` (decorative — the name carries the accessible name)
- No icon-only buttons

## Persona theming

Reads all 15 tokens from the [A2UI v0.1 spec §6](../../../contracts/a2ui-v0.1.md#6-persona-theming-css-custom-properties). Concrete defaults:

- Background: `var(--pm-bg, #0b0b10)`
- Border: `var(--pm-border, rgba(255, 255, 255, 0.08))`
- Name color: `var(--pm-fg, #FFFFFF)` in `var(--pm-font-display, 'Orbitron', system-ui)`
- Role color: `var(--pm-fg-muted, #9ca3af)`
- Glyph color: `var(--pm-accent, #7C3AED)` (presence variant: `--pm-accent-soft` for rehearsal, `--pm-fg-muted` for offline)

## Lifecycle

- `connectedCallback` — renders Shadow DOM, subscribes to `data-source` if present
- `disconnectedCallback` — closes the EventSource / cancels HTTP polling. **No leak guarantee.**
- `attributeChangedCallback` — re-renders on prop change. Subscriptions are reset only when `data-source` itself changes.

## Anti-patterns avoided

- ✅ No framework (plain Web Component)
- ✅ No inline styles (all in Shadow DOM via CSS custom properties)
- ✅ No global event listeners
- ✅ No chained pull
- ✅ XSS-safe: all prop values escaped before insertion
- ✅ No localStorage / sessionStorage reads
- ✅ Subscriptions cleaned up in `disconnectedCallback`

## Demo

Open `demo.html` in a browser to see three live cards (armor, darkxside, skin themes) with simulated presence. Or run:

```bash
# from repo root
python -m http.server 8765 --directory pmoves/web-components/pm-space-agent-card
# then open http://localhost:8765/demo.html
```

## See also

- [A2UI v0.1 spec](../../../contracts/a2ui-v0.1.md)
- `<pm-project-card>` (next in registry)
- `<pm-metric-tile>` (data-source pattern reference)
