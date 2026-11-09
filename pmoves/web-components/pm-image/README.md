# `<pm-image>` — v0.1

Figure with caption + optional credit. Responsive `object-fit: cover`.

> **Spec**: [A2UI v0.1 §10](../../../contracts/a2ui-v0.1.md#10-initial-component-recipes-v01)

## Usage

```html
<pm-image
  src="https://example.com/photo.jpg"
  alt="Mesh antenna on rooftop"
  caption="Fordham Hill gateway antenna"
  credit="Photo: DARKXSIDE"
  aspect-ratio="16/9"
></pm-image>
```

## Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `src` | string (URL) | ✓ | Image source URL. |
| `alt` | string | ✓ | Alt text. Carries the accessible name. |
| `caption` | string |   | Optional figure caption. |
| `credit` | string |   | Optional credit line (e.g. "Photo: name"). |
| `aspect-ratio` | string |   | CSS aspect-ratio. v0.1 allowed: `1/1`, `4/3`, `3/2`, `16/9`, `21/9`, `2/3`, `9/16`. Default `16/9`. |

## ARIA

- `role="figure"` with `aria-label="<alt>"`

## Demo

```bash
python -m http.server 8765 --directory pmoves/web-components/pm-image
# open http://localhost:8765/demo.html
```
