// <pm-image> — v0.1
// Figure with caption. Optional credit line. Responsive (object-fit: cover).
// Per A2UI v0.1 spec §10.

class PmImage extends HTMLElement {
  static get observedAttributes() {
    return ['src', 'alt', 'caption', 'credit', 'aspect-ratio'];
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

  get src() { return this.getAttribute('src') || ''; }
  set src(v) { this.setAttribute('src', v); }

  get alt() { return this.getAttribute('alt') || ''; }
  set alt(v) { this.setAttribute('alt', v); }

  get caption() { return this.getAttribute('caption') || ''; }
  set caption(v) { this.setAttribute('caption', v); }

  get credit() { return this.getAttribute('credit') || ''; }
  set credit(v) { this.setAttribute('credit', v); }

  get aspectRatio() {
    // Interpolated into the shadow <style> block — constrain to <int>/<int>
    // (the spec §10 enum shape) so the value can never carry CSS/HTML out
    // of that context. Invalid values fall back to the spec default.
    const v = (this.getAttribute('aspect-ratio') || '').trim();
    return /^\d{1,3}\/\d{1,3}$/.test(v) ? v : '16/9';
  }
  set aspectRatio(v) { this.setAttribute('aspect-ratio', v); }

  _render() {
    if (!this.src) {
      this.shadowRoot.innerHTML = `<p style="color:var(--pm-fg-muted);">No image source.</p>`;
      return;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--pm-font-body, system-ui, -apple-system, sans-serif);
        }

        figure {
          margin: 0;
          background: var(--pm-bg, #0b0b10);
          border: 1px solid var(--pm-border, rgba(255, 255, 255, 0.08));
          border-radius: var(--pm-radius, 12px);
          overflow: hidden;
        }

        .img-wrap {
          width: 100%;
          aspect-ratio: ${this.aspectRatio};
          overflow: hidden;
          background: var(--pm-bg-elevated, #13131a);
        }

        img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          display: block;
        }

        figcaption {
          padding: calc(var(--pm-spacing-unit, 8px) * 1.5) calc(var(--pm-spacing-unit, 8px) * 2);
          font-size: 13px;
          line-height: 1.5;
          color: var(--pm-fg-muted, #9ca3af);
        }

        .credit {
          display: block;
          font-size: 11px;
          margin-top: 4px;
          color: var(--pm-fg-muted, #9ca3af);
          opacity: 0.7;
          font-style: italic;
        }
      </style>

      <figure aria-label="${this._escapeAttr(this.alt || 'Image')}">
        <div class="img-wrap">
          <img src="${this._escapeAttr(this.src)}" alt="${this._escapeAttr(this.alt)}" loading="lazy" />
        </div>
        ${this.caption || this.credit
          ? `<figcaption>
              ${this.caption ? `<span>${this._escapeText(this.caption)}</span>` : ''}
              ${this.credit ? `<span class="credit">${this._escapeText(this.credit)}</span>` : ''}
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

customElements.define('pm-image', PmImage);

export { PmImage };
