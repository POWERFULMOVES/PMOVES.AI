# `<pm-metric-tile>` — v0.1

Single KPI tile: label + value + unit + trend. The reference implementation of the **A2UI v0.1 single data-source pull** pattern (§7.2). Every community page that shows live data uses this.

> **Spec**: [A2UI v0.1 §7.2, §10](../../../contracts/a2ui-v0.1.md#72-pull-single-attribute)
> **Conformance**: Shadow DOM `open`, reads `--pm-*` tokens, no chained pull, ARIA `role="meter"`, passes axe-core 4.x.

## Usage

### Static

```html
<pm-metric-tile
  label="Mesh uptime"
  value="99.4"
  unit="%"
  trend="up"
  format="percent"
></pm-metric-tile>
```

### Live (NATS)

```html
<pm-metric-tile
  label="Mesh uptime"
  data-source="fordham:mesh.uptime"
  format="percent"
></pm-metric-tile>
```

### Live (HTTP)

```html
<pm-metric-tile
  label="Active sessions"
  data-source="https://api.pmoves.ai/tenants/fordham/sessions/count"
></pm-metric-tile>
```

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `label` | string | `""` | Metric label (displayed above the value). |
| `value` | string | `""` | The metric value. Rendered via `format` template. Empty → em-dash. |
| `unit` | string | `""` | Display unit. If `format` is set, behavior changes (see Format). |
| `trend` | `"up"` \| `"down"` \| `"flat"` | `"flat"` | Trend arrow + color. Up=green, down=red, flat=muted. |
| `format` | `"plain"` \| `"percent"` \| `"currency"` \| `"duration"` | `"plain"` | Formatting template. |
| `data-source` | string | `null` | Pull a single subject. NATS `<tenant>:<subject>` or HTTP URL. |

## Format

| `format` | Rendered value | `unit` example |
|----------|----------------|----------------|
| `plain` | `value` + (optional `unit`) | `150 ms` |
| `percent` | `value` (unit defaults to `%`) | `99.4%` |
| `currency` | (optional `unit` prefix) + `value` | `$150` |
| `duration` | `value` + (optional `unit`, defaults to `ms`) | `150 ms` |

## Data source schema

The data source must return JSON shaped:

```json
{ "value": "99.4", "trend": "up", "unit": "%", "format": "percent" }
```

All fields optional except `value`. Unknown fields are ignored.

## Loading states

The component announces state via `aria-live="polite"`:

| State | Announcement | When |
|-------|--------------|------|
| `idle` | (silent) | No data-source attribute |
| `loading` | "Loading…" | Source attribute set, no data yet |
| `live` | (silent) | First data received |
| `error` | "Source unavailable" | Fetch failed or EventSource errored |

## ARIA

- `role="meter"` (semantic for a single-value metric)
- `aria-label="<label>: <formatted value>"`
- Trend icon has `aria-label="trending up|down|flat"`
- State announcement via `aria-live="polite"`

## Anti-patterns avoided

- ✅ No chained pull — single `data-source` only
- ✅ No framework
- ✅ No polling loops (EventSource is push-based, fetch is one-shot)
- ✅ Subscriptions cleaned up in `disconnectedCallback`
- ✅ Graceful degradation: bad data → `error` state, no exception
- ✅ Tabular numbers (`font-variant-numeric: tabular-nums`) so values don't jitter

## Demo

```bash
python -m http.server 8765 --directory pmoves/web-components/pm-metric-tile
# open http://localhost:8765/demo.html
```

The demo includes a static tile, a "live NATS" tile (will show "Source unavailable" without a running bridge), and a HTTP-poll tile with a mock endpoint URL.

## See also

- [A2UI v0.1 spec §7.2 (pull pattern)](../../../contracts/a2ui-v0.1.md#72-pull-single-attribute)
- `<pm-space-agent-card>` (also uses `data-source` for presence)
- `pmoves/tools/compose/compose.py` (compose tool produces A2UI messages for this component)
