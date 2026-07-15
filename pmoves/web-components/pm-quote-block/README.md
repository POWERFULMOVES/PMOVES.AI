# `<pm-quote-block>` — v0.1

Pull-quote with attribution. Optional role/title for the attribution.

> **Spec**: [A2UI v0.1 §10](../../../contracts/a2ui-v0.1.md#10-initial-component-recipes-v01)

## Usage

```html
<pm-quote-block
  quote="When the cell tower goes down, the block goes dark."
  attribution="DARKXSIDE"
  role="Founder, PMOVES.AI"
></pm-quote-block>
```

## Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `quote` | string | ✓ | The quote text. |
| `attribution` | string | ✓ | The person being quoted. |
| `role` | string |   | Optional title/role for the attribution (e.g. "Founder, PMOVES.AI"). |

## ARIA

- `role="figure"` with the blockquote as `<blockquote cite="...">`
- Native `<blockquote>` + `<figcaption>` semantics

## Demo

```bash
python -m http.server 8765 --directory pmoves/web-components/pm-quote-block
# open http://localhost:8765/demo.html
```
