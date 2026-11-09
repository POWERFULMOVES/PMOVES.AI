// <pm-quote-block> — v0.1
// Pull-quote with attribution. Optional role (e.g., "community organizer").
// Per A2UI v0.1 spec §10.

class PmQuoteBlock extends HTMLElement {
  static get observedAttributes() {
    return ['quote', 'attribution', 'attribution-role'];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    if (!this.hasAttribute('role')) this.setAttribute('role', 'figure');
    this._render();
  }

  disconnectedCallback() {}

  attributeChangedCallback() {
    if (this.isConnected) this._render();
  }

  get quote() { return this.getAttribute('quote') || ''; }
  set quote(v) { this.setAttribute('quote', v); }

  get attribution() { return this.getAttribute('attribution') || ''; }
  set attribution(v) { this.setAttribute('attribution', v); }

  // Renamed from `role` to `attributionRole` to avoid clobbering the HTML ARIA
  // role attribute on the host element.
  get attributionRole() { return this.getAttribute('attribution-role') || ''; }
  set attributionRole(v) { this.setAttribute('attribution-role', v); }

  _render() {
    if (!this.quote) {
      this.shadowRoot.innerHTML = `<p style="color:var(--pm-fg-muted);">Empty quote.</p>`;
      return;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--pm-font-body, system-ui, -apple-system, sans-serif);
        }

        figure.quote {
          margin: 0;
          padding: calc(var(--pm-spacing-unit, 8px) * 3) calc(var(--pm-spacing-unit, 8px) * 2);
          background: var(--pm-bg, #0b0b10);
          border-left: 4px solid var(--pm-accent, #7C3AED);
          border-radius: var(--pm-radius, 12px);
          position: relative;
        }

        .quote-mark {
          position: absolute;
          top: -8px;
          left: 12px;
          font-family: var(--pm-font-display, 'Orbitron', system-ui);
          font-size: 64px;
          line-height: 1;
          color: var(--pm-accent, #7C3AED);
          opacity: 0.3;
          pointer-events: none;
        }

        blockquote {
          margin: 0 0 12px 0;
          padding: 0;
          font-size: 18px;
          line-height: 1.5;
          color: var(--pm-fg, #FFFFFF);
          font-style: italic;
        }

        figcaption {
          font-size: 13px;
          color: var(--pm-fg-muted, #9ca3af);
          display: flex;
          align-items: baseline;
          gap: 8px;
        }

        .dash { color: var(--pm-accent, #7C3AED); }
        .name { font-weight: 600; color: var(--pm-fg, #FFFFFF); }
        .role { font-size: 12px; opacity: 0.8; }
      </style>

      <figure class="quote">
        <span class="quote-mark" aria-hidden="true">"</span>
        <blockquote cite="${this._escapeAttr(this.attribution || '')}">${this._escapeText(this.quote)}</blockquote>
        ${this.attribution
          ? `<figcaption>
              <span class="dash" aria-hidden="true">—</span>
              <span class="name">${this._escapeText(this.attribution)}</span>
              ${this.attributionRole ? `<span class="role">${this._escapeText(this.attributionRole)}</span>` : ''}
            </figcaption>`
          : ''}
      </figure>
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

customElements.define('pm-quote-block', PmQuoteBlock);

export { PmQuoteBlock };
