# `<pm-project-card>` — v0.1

Project summary card. Title + description + status badge + tags + action links. The "what is this community building" surface.

> **Spec**: [A2UI v0.1 §10](../../../contracts/a2ui-v0.1.md#10-initial-component-recipes-v01)
> **Conformance**: Shadow DOM `open`, reads `--pm-*` tokens, ARIA `role="article"`, passes axe-core 4.x.

## Usage

```html
<pm-project-card
  title="Mesh pilot: Fordham Hill"
  description="50-family mesh + private AI. Voice that goes through walls."
  status="live"
  tags='["mesh", "voice", "tenancy"]'
  links='[{"label":"Capability brief","href":"#brief"},{"label":"Discord","href":"#discord"}]'
></pm-project-card>
```

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `title` | string | `""` | Project title (required-ish; falls back to "Untitled project"). |
| `description` | string | `""` | Project description, 1-3 sentences. |
| `status` | `"live"` \| `"rehearsal"` \| `"planned"` \| `"archived"` | `"planned"` | Status badge text and color. |
| `tags` | JSON array of strings | `[]` | Tag chips. |
| `links` | JSON array of `{label, href}` | `[]` | Action links. External links get `target="_blank" rel="noopener noreferrer"`. |

## A2UI message (compose tool)

```json
{
  "type": "createComponent",
  "component": "pm-project-card",
  "props": {
    "title": "Mesh pilot: Fordham Hill",
    "description": "50-family mesh + private AI.",
    "status": "live",
    "tags": ["mesh", "voice", "tenancy"],
    "links": [
      { "label": "Brief", "href": "#brief" }
    ]
  }
}
```

## ARIA

- `role="article"` on the outer card
- `aria-label="Project: <title>"`
- Status badge has `aria-label="Status: <status>"`
- Links use `<a>` (semantic) — no `role="button"` overrides
- Tags wrapped in `aria-label="Tags"` group

## Anti-patterns avoided

- ✅ No framework
- ✅ No inline styles
- ✅ All links use native `<a>` (not fake buttons)
- ✅ External links always get `rel="noopener noreferrer"`
- ✅ XSS-safe: tags and links JSON-parsed and string-escaped
- ✅ Status doesn't drive color alone (also drives text label + ARIA announcement)

## Demo

```bash
python -m http.server 8765 --directory pmoves/web-components/pm-project-card
# open http://localhost:8765/demo.html
```
