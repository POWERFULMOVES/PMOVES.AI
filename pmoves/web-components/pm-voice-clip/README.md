# `<pm-voice-clip>` — v0.1

Embedded audio with metadata. Optional collapsible transcript.

> **Spec**: [A2UI v0.1 §10](../../../contracts/a2ui-v0.1.md#10-initial-component-recipes-v01)

## Usage

```html
<pm-voice-clip
  title="DARKXSIDE: why mesh, why now"
  speaker="DARKXSIDE"
  duration="2:14"
  src="https://example.com/clip.mp3"
  transcript="When the cell tower goes down..."
></pm-voice-clip>
```

## Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `src` | string (URL) | ✓ | Audio source URL. |
| `title` | string | ✓ | Clip title. |
| `speaker` | string |   | Optional speaker name. |
| `duration` | string |   | Optional duration label (e.g. "2:14"). |
| `transcript` | string |   | Optional transcript text. Renders collapsible. |

## ARIA

- `role="region"` with `aria-label="Voice clip: <title>"`
- Native `<audio controls>` for playback (browser-native a11y)
- `<details>` for transcript (native a11y)

## Demo

```bash
python -m http.server 8765 --directory pmoves/web-components/pm-voice-clip
# open http://localhost:8765/demo.html
```
