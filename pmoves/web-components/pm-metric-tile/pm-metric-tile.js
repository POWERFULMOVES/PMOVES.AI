// <pm-metric-tile> — v0.1
// Single KPI display: label + value + unit + trend arrow.
// Per A2UI v0.1 spec §10. This component is the reference implementation
// of the "single data-source pull" pattern (§7.2).
//
// Spec compliance:
//   - Custom Element extending HTMLElement
//   - Shadow DOM (open)
//   - Reads --pm-* tokens
//   - data-source: NATS subject OR HTTP endpoint
//   - No chained pull (§7.3 forbidden)
//   - Lifecycle cleanup in disconnectedCallback
//
// Usage:
//   <pm-metric-tile
//     label="Mesh uptime"
//     value="99.4"
//     unit="%"
//     trend="up"
//     format="percent"
//     data-source="fordham:mesh.uptime"
//   ></pm-metric-tile>

class PmMetricTile extends HTMLElement {
  static get observedAttributes() {
    return ['label', 'value', 'unit', 'trend', 'format', 'data-source'];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._subscription = null;
    this._loadingState = 'idle'; // 'idle' | 'loading' | 'live' | 'error'
  }

  connectedCallback() {
    // ARIA role + attributes live on the HOST so axe-core (which does not
    // pierce shadow DOM by default) can see them.
    this.setAttribute('role', 'meter');
    this._render();
    this._syncHostAria();
    this._subscribeIfNeeded();
  }

  disconnectedCallback() {
    this._unsubscribe();
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue === newValue) return;
    if (this.isConnected) {
      this._render();
      this._syncHostAria();
      if (name === 'data-source') {
        this._unsubscribe();
        this._subscribeIfNeeded();
      }
    }
  }

  // Mirror the aria-* attrs onto the host (axe-core inspects the host,
  // not the shadow root by default).
  _syncHostAria() {
    const numericValue = parseFloat(this.value);
    const hasNumeric = !Number.isNaN(numericValue);
    const valuenow = hasNumeric ? numericValue : 0;
    const valuemax = hasNumeric ? Math.max(100, numericValue) : 100;
    this.setAttribute('aria-label', `${this.label || 'Metric'}: ${this._formatValue()}`);
    this.setAttribute('aria-valuenow', String(valuenow));
    this.setAttribute('aria-valuemin', '0');
    this.setAttribute('aria-valuemax', String(valuemax));
    this.setAttribute('aria-valuetext', this._formatValue());
  }

  // Property getters/setters
  get label() { return this.getAttribute('label') || ''; }
  set label(v) { this.setAttribute('label', v); }

  get value() { return this.getAttribute('value') ?? ''; }
  set value(v) { this.setAttribute('value', v); }

  get unit() { return this.getAttribute('unit') || ''; }
  set unit(v) { this.setAttribute('unit', v); }

  get trend() { return this.getAttribute('trend') || 'flat'; }
  set trend(v) { this.setAttribute('trend', v); }

  get format() { return this.getAttribute('format') || 'plain'; }
  set format(v) { this.setAttribute('format', v); }

  _formatValue() {
    if (this.value === '' || this.value === null) return '—';
    const v = this.value;
    switch (this.format) {
      case 'percent':
        return `${v}${this.unit || '%'}`;
      case 'currency':
        return `${this.unit || '$'}${v}`;
      case 'duration':
        return `${v} ${this.unit || 'ms'}`;
      case 'plain':
      default:
        return this.unit ? `${v}${this.unit}` : `${v}`;
    }
  }

  _trendIcon() {
    return {
      up: '↑',
      down: '↓',
      flat: '→',
    }[this.trend] || '→';
  }

  _trendLabel() {
    return {
      up: 'trending up',
      down: 'trending down',
      flat: 'flat',
    }[this.trend] || this.trend;
  }

  _render() {
    const stateAnnouncement = {
      loading: 'Loading…',
      error: 'Source unavailable',
      idle: '',
      live: '',
    }[this._loadingState] || '';

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --_trend-color: var(--pm-fg-muted, #9ca3af);
          display: block;
          font-family: var(--pm-font-body, system-ui, -apple-system, sans-serif);
        }
        :host([trend="up"]) { --_trend-color: #34d399; }
        :host([trend="down"]) { --_trend-color: #f87171; }
        :host([trend="flat"]) { --_trend-color: var(--pm-fg-muted, #9ca3af); }

        .tile {
          padding: calc(var(--pm-spacing-unit, 8px) * 2);
          background: var(--pm-bg, #0b0b10);
          border: 1px solid var(--pm-border, rgba(255, 255, 255, 0.08));
          border-radius: var(--pm-radius, 12px);
          display: flex;
          flex-direction: column;
          gap: 6px;
          min-width: 140px;
        }

        .label {
          font-size: 12px;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--pm-fg-muted, #9ca3af);
          font-weight: 500;
        }

        .value-row {
          display: flex;
          align-items: baseline;
          gap: 8px;
        }

        .value {
          font-family: var(--pm-font-display, 'Orbitron', system-ui);
          font-size: 28px;
          font-weight: 600;
          color: var(--pm-fg, #FFFFFF);
          line-height: 1.1;
          font-variant-numeric: tabular-nums;
        }

        .trend {
          color: var(--_trend-color);
          font-size: 16px;
          line-height: 1;
        }

        .state {
          font-size: 11px;
          color: var(--pm-fg-muted, #9ca3af);
          font-style: italic;
        }
      </style>

      <article class="tile">
        <div class="label">${this._escapeText(this.label) || 'Metric'}</div>
        <div class="value-row">
          <span class="value">${this._escapeText(this._formatValue())}</span>
          <span class="trend" aria-label="${this._escapeAttr(this._trendLabel())}">${this._trendIcon()}</span>
        </div>
        <span class="state" aria-live="polite">${stateAnnouncement}</span>
      </article>
    `;
  }

  _subscribeIfNeeded() {
    const source = this.getAttribute('data-source');
    if (!source) return;

    this._loadingState = 'loading';
    this._render();
    this._syncHostAria();

    if (source.startsWith('http://') || source.startsWith('https://')) {
      this._subscription = this._fetchHttp(source);
    } else if (source.includes(':')) {
      this._subscription = this._subscribeNats(source);
    } else {
      this._loadingState = 'error';
      this._render();
    }
  }

  _fetchHttp(url) {
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) {
          this._applyData(data);
          this._loadingState = 'live';
        } else {
          this._loadingState = 'error';
        }
        this._render();
      })
      .catch(() => {
        this._loadingState = 'error';
        this._render();
      });
    return { cancel: () => {} };
  }

  _subscribeNats(subject) {
    const url = `/api/nats/sse?subject=${encodeURIComponent(subject)}`;
    let es;
    try {
      es = new EventSource(url);
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          this._applyData(data);
          this._loadingState = 'live';
          this._render();
        } catch (_) {
          // ignore malformed
        }
      };
      es.onerror = () => {
        this._loadingState = 'error';
        this._render();
      };
    } catch (_) {
      this._loadingState = 'error';
      this._render();
      return { cancel: () => {} };
    }
    return {
      cancel: () => {
        if (es) es.close();
      },
    };
  }

  _unsubscribe() {
    if (this._subscription && this._subscription.cancel) {
      this._subscription.cancel();
    }
    this._subscription = null;
  }

  _applyData(data) {
    // v0.1 schema: { value, trend?, unit?, format? }
    if (data.value !== undefined) this.value = data.value;
    if (data.trend) this.trend = data.trend;
    if (data.unit) this.unit = data.unit;
    if (data.format) this.format = data.format;
  }

  _escapeText(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  _escapeAttr(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
}

customElements.define('pm-metric-tile', PmMetricTile);

export { PmMetricTile };
