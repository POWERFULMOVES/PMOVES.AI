# `<pm-timeline>` — v0.1

Chronological event list. The "what happened, in order" surface.

> **Spec**: [A2UI v0.1 §10](../../../contracts/a2ui-v0.1.md#10-initial-component-recipes-v01)

## Usage

```html
<pm-timeline events='[
  {"ts": "2026-07-15T10:00:00Z", "title": "Mesh came up", "body": "...", "icon": "◆"}
]'></pm-timeline>
```

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `events` | JSON array of `{ts, title, body, icon?}` | `[]` | The events. `ts` is ISO 8601; component renders relative ("2h ago"). |
| `empty-message` | string | `"No events yet"` | Shown when `events` is empty. |

## ARIA

- `role="list"` on the outer
- Each event: `role="listitem"`, `aria-posinset`, `aria-setsize`
- Dots/connectors are `aria-hidden="true"` (decorative)

## Demo

```bash
python -m http.server 8765 --directory pmoves/web-components/pm-timeline
# open http://localhost:8765/demo.html
```
