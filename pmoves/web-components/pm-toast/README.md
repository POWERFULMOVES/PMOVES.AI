# `<pm-toast>` — v0.2

Notification toast. ARIA `role="status"` with `aria-live="polite"`. Variants: `success`, `error`, `warning`, `info`. Auto-dismiss with timeout.

> **Spec**: [A2UI v0.2 ballot §4.3](../../../contracts/a2ui-v0.2-ballot.md#43-pm-event-slots-event-emission)
> **Use case**: feedback for `on-vote-cast` and similar event wires (e.g. `<pm-ballot on-vote-cast="t:show">`).

## Usage

```html
<!-- Static placement -->
<pm-toast id="t" position="bottom-right" timeout="4000"></pm-toast>

<!-- Show programmatically -->
<script type="module">
  const t = document.getElementById('t');
  t.show('Vote cast!', 'success');
</script>
```

### Event wire (the v0.2 way)

```html
<pm-toast id="t"></pm-toast>
<pm-ballot on-vote-cast="t:show"></pm-ballot>
```

When the ballot fires `vote-cast`, the renderer finds the toast with id `t` and calls `.show()` on it (passing the event payload as the message).

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `variant` | `"success"` \| `"error"` \| `"warning"` \| `"info"` | `"info"` | Visual style + ARIA semantics. |
| `timeout` | number (ms) | `5000` | Auto-dismiss delay. `0` = no auto-dismiss. |
| `position` | `"top-right"` \| `"top-left"` \| `"bottom-right"` \| `"bottom-left"` \| `"top"` \| `"bottom"` | `"bottom-right"` | Screen position. |

## Methods

| Method | Description |
|--------|-------------|
| `show(message, variant?, duration?)` | Display the toast with given text. Variant + duration are optional. |
| `hide()` | Dismiss immediately. |

## ARIA

- `role="status"` + `aria-live="polite"` on host (announced to screen readers, non-interrupting)
- Inner `.body` uses `role="alert"` (for assertive content; ok in v0.2 because `aria-live=polite` on host takes precedence)
- Close button: `aria-label="Dismiss notification"`

## Demo

```bash
python -m http.server 8765 --directory pmoves/web-components/pm-toast
# open http://localhost:8765/demo.html
```
