# `<pm-haptic>` — v0.1

HTML5 Web Vibration API wrapper. Triggers `navigator.vibrate()` patterns for tactile feedback synced to events (BPM, button presses, alerts, etc). For users without vibration hardware, a small visual indicator flashes in the same rhythm.

> **Spec**: [A2UI v0.1 §10](../../../contracts/a2ui-v0.1.md#10-initial-component-recipes-v01)
> **Plugs into**: `pmoves/tools/bpm_encoder.py` (BPM → haptic pulses)

## Usage

### One-shot pattern

```html
<pm-haptic id="alert" pattern="200,100,200"></pm-haptic>
<button onclick="document.getElementById('alert').pulse()">Alert</button>
```

### Auto-derive from BPM

```html
<pm-haptic bpm="120"></pm-haptic>
<button onclick="document.getElementById('h').startLoop()">Start loop</button>
```

The component computes a 4-pulse pattern: 100ms on, then `gap = max(20, 60000/bpm - 100)ms` off, repeated. At 120 BPM that's 100ms on, 400ms off, 100ms on, 400ms off, ...

### Live BPM via data-source

```html
<!-- NATS subject -->
<pm-haptic data-source="fordham:track.bpm"></pm-haptic>

<!-- HTTP endpoint returning { "bpm": 142 } -->
<pm-haptic data-source="https://api.pmoves.ai/tenants/fordham/track/bpm"></pm-haptic>
```

The component subscribes on mount. On each BPM update, it recomputes the pattern. Per A2UI v0.1 §7.2: single subscribe, no chained pull.

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `pattern` | string (CSV of ms) | `""` | Explicit vibration pattern (e.g. `"100,50,100,50,100"`). Overrides `bpm` if both are set. |
| `bpm` | number | `null` | Auto-derive pattern from BPM. Period = 60000/bpm ms. |
| `data-source` | string | `null` | Subscribe to a BPM feed (NATS subject or HTTP URL). |
| `enabled` | `"true"` \| `"false"` | `"true"` | Master switch. False = no vibration, no visual. |
| `respect-reduced-motion` | `"true"` \| `"false"` | `"true"` | If true, checks `prefers-reduced-motion` and skips vibration when set. Visual indicator still fires. |

## Methods

| Method | Description |
|--------|-------------|
| `pulse()` | Trigger one vibration with the current pattern. No-op if `enabled=false` or device unsupported. |
| `startLoop()` | Start a recurring pulse at the current BPM. Calls `pulse()` once per beat. |
| `_stopLoop()` | Stop the loop. (Private API; v0.2 will add a public `stopLoop()` if peer agents request it.) |

## ARIA

- `aria-hidden="true"` on the host (decorative output — vibration is invisible)
- Listens to `prefers-reduced-motion` media query and respects it by default
- No content; nothing for screen readers to read

## Theming

- The visual indicator uses `--pm-accent` (defaults to `#7C3AED`)
- No structural CSS custom properties beyond the accent token

## Anti-patterns avoided

- ✅ No framework
- ✅ No inline styles
- ✅ No global listeners (listeners are scoped to the host's media query)
- ✅ No chained pull — single `data-source` only
- ✅ No lingering vibration on disconnect (`navigator.vibrate(0)` in `disconnectedCallback`)
- ✅ `prefers-reduced-motion` respected by default

## Browser support

| Browser | Vibration | Notes |
|---------|-----------|-------|
| Chrome (Android) | ✓ | Full support |
| Safari (iOS) | ✗ | iOS doesn't expose `navigator.vibrate` (returns undefined). Component gracefully no-ops. |
| Firefox (Android) | ✓ | Full support |
| Chrome (Desktop) | ✗ | Most desktop browsers don't expose vibration. Visual indicator still fires. |

## Demo

```bash
python -m http.server 8765 --directory pmoves/web-components/pm-haptic
# open http://localhost:8765/demo.html
```

The demo includes three haptic instances: a one-shot pattern, a BPM-driven loop, and a custom-pattern input. The BPM slider restarts the loop in real time. On desktop, you'll see the visual indicator but not feel vibration.
