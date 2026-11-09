// <pm-timeline> — v0.1
// Chronological event list. Each event: ts (ISO string or relative),
// title, body, icon (optional).
// Per A2UI v0.1 spec §10.

class PmTimeline extends HTMLElement {
  static get observedAttributes() {
    return ['events', 'empty-message'];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    // Don't put role="list" on the host — role="list" requires listitem
    // children to be DIRECT descendants, and axe-core can't see the <li>
    // children inside the shadow root. The inner <ol role="list"> carries
    // the proper list semantics for the rendered surface.
    if (!this.hasAttribute('role')) this.setAttribute('role', 'region');
    this.setAttribute('aria-label', this.getAttribute('aria-label') || 'Timeline');
    this._render();
  }

  disconnectedCallback() {}

  attributeChangedCallback() {
    if (this.isConnected) this._render();
  }

  get events() { return this._parseArray(this.getAttribute('events')); }
  set events(v) { this.setAttribute('events', JSON.stringify(v || [])); }

  get emptyMessage() { return this.getAttribute('empty-message') || 'No events yet'; }
  set emptyMessage(v) { this.setAttribute('empty-message', v); }

  _parseArray(attr) {
    if (!attr) return [];
    try {
      const parsed = JSON.parse(attr);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  }

  _formatTs(ts) {
    if (!ts) return '';
    // ISO 8601 → relative ("2h ago", "yesterday", "3d ago")
    const date = new Date(ts);
    if (Number.isNaN(date.getTime())) return ts;
    const now = Date.now();
    const diffMs = now - date.getTime();
    const sec = Math.floor(diffMs / 1000);
    if (sec < 60) return 'just now';
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min}m ago`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}h ago`;
    const day = Math.floor(hr / 24);
    if (day < 30) return `${day}d ago`;
    // Older than a month → use locale date
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  }

  _render() {
    const events = this.events;
    const empty = events.length === 0;

    const eventsHtml = events
      .map((ev, idx) => {
        const isLast = idx === events.length - 1;
        return `
          <li class="event" role="listitem" aria-posinset="${idx + 1}" aria-setsize="${events.length}">
            <div class="dot" aria-hidden="true">${this._escapeText(ev.icon || '◆')}</div>
            ${!isLast ? '<div class="connector" aria-hidden="true"></div>' : ''}
            <div class="body">
              <div class="row">
                <h4 class="title">${this._escapeText(ev.title || 'Untitled event')}</h4>
                <time class="ts" datetime="${this._escapeAttr(ev.ts || '')}">${this._escapeText(this._formatTs(ev.ts))}</time>
              </div>
              ${ev.body ? `<p class="desc">${this._escapeText(ev.body)}</p>` : ''}
            </div>
          </li>
        `;
      })
      .join('');

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--pm-font-body, system-ui, -apple-system, sans-serif);
        }

        .empty {
          padding: calc(var(--pm-spacing-unit, 8px) * 2);
          color: var(--pm-fg-muted, #9ca3af);
          font-style: italic;
          text-align: center;
          background: var(--pm-bg, #0b0b10);
          border: 1px dashed var(--pm-border, rgba(255, 255, 255, 0.08));
          border-radius: var(--pm-radius, 12px);
        }

        ol.events {
          list-style: none;
          margin: 0;
          padding: 0;
          display: flex;
          flex-direction: column;
        }

        .event {
          display: grid;
          grid-template-columns: auto 1fr;
          gap: 12px;
          padding: calc(var(--pm-spacing-unit, 8px) * 1.5) 0;
          position: relative;
        }

        .dot {
          width: 32px;
          height: 32px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--pm-bg-elevated, #13131a);
          border: 1px solid var(--pm-accent, #7C3AED);
          border-radius: 50%;
          color: var(--pm-accent, #7C3AED);
          font-size: 14px;
          flex-shrink: 0;
          position: relative;
          z-index: 1;
        }

        .connector {
          position: absolute;
          left: 15px;  /* center of 32px dot */
          top: 44px;   /* below dot */
          bottom: -8px;
          width: 2px;
          background: var(--pm-border, rgba(255, 255, 255, 0.08));
        }

        .body {
          min-width: 0;
        }

        .row {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: baseline;
        }

        .title {
          font-size: 14px;
          font-weight: 600;
          color: var(--pm-fg, #FFFFFF);
          margin: 0;
        }

        .ts {
          font-size: 12px;
          color: var(--pm-fg-muted, #9ca3af);
          font-variant-numeric: tabular-nums;
          white-space: nowrap;
        }

        .desc {
          font-size: 13px;
          line-height: 1.5;
          color: var(--pm-fg-muted, #9ca3af);
          margin: 4px 0 0 0;
        }
      </style>

      ${empty
        ? `<p class="empty">${this._escapeText(this.emptyMessage)}</p>`
        : `<ol class="events">${eventsHtml}</ol>`}
    `;
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

customElements.define('pm-timeline', PmTimeline);

export { PmTimeline };
