// <pm-project-card> — v0.1
// Project summary card. Title + description + status badge + tags + links.
// Per A2UI v0.1 spec §10.
//
// Spec compliance:
//   - Custom Element extending HTMLElement
//   - Shadow DOM (open) for style encapsulation
//   - Reads --pm-* tokens for theming
//   - No framework, no inline styles, no global listeners
//   - ARIA: role="article" with accessible name
//   - Lifecycle: connectedCallback/disconnectedCallback
//
// Usage:
//   <pm-project-card
//     title="Mesh pilot: Fordham Hill"
//     description="50-family mesh + private AI..."
//     status="live"
//     tags='["mesh", "voice", "tenancy"]'
//     links='[{"label":"Brief","href":"#"}]'
//   ></pm-project-card>

class PmProjectCard extends HTMLElement {
  static get observedAttributes() {
    return ['title', 'description', 'status', 'tags', 'links'];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    if (!this.hasAttribute('role')) this.setAttribute('role', 'article');
    this._render();
  }

  disconnectedCallback() {
    // no subscriptions in v0.1
  }

  attributeChangedCallback() {
    if (this.isConnected) this._render();
  }

  // Property getters/setters
  get title() { return this.getAttribute('title') || ''; }
  set title(v) { this.setAttribute('title', v); }

  get description() { return this.getAttribute('description') || ''; }
  set description(v) { this.setAttribute('description', v); }

  get status() { return this.getAttribute('status') || 'planned'; }
  set status(v) { this.setAttribute('status', v); }

  get tags() { return this._parseArray(this.getAttribute('tags')); }
  set tags(v) { this.setAttribute('tags', JSON.stringify(v || [])); }

  get links() { return this._parseArray(this.getAttribute('links')); }
  set links(v) { this.setAttribute('links', JSON.stringify(v || [])); }

  _parseArray(attr) {
    if (!attr) return [];
    try {
      const parsed = JSON.parse(attr);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  }

  _render() {
    const statusLabel = {
      live: 'Live',
      rehearsal: 'Rehearsal',
      planned: 'Planned',
      archived: 'Archived',
    }[this.status] || this.status;

    const tagsHtml = this.tags
      .map((t) => `<span class="tag">${this._escapeText(String(t))}</span>`)
      .join('');

    const linksHtml = this.links
      .map((link) => {
        const label = this._escapeText(link.label || link.href || 'Link');
        const href = this._escapeAttr(this._safeHref(link.href));
        const external = /^https?:/i.test(link.href || '');
        return `<a class="link" href="${href}" ${external ? 'rel="noopener noreferrer" target="_blank"' : ''}>${label} →</a>`;
      })
      .join('');

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--pm-font-body, system-ui, -apple-system, sans-serif);
        }

        .card {
          padding: calc(var(--pm-spacing-unit, 8px) * 2);
          background: var(--pm-bg, #0b0b10);
          border: 1px solid var(--pm-border, rgba(255, 255, 255, 0.08));
          border-radius: var(--pm-radius, 12px);
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
        }

        h3.title {
          font-family: var(--pm-font-display, 'Orbitron', system-ui);
          font-size: 18px;
          font-weight: 600;
          color: var(--pm-fg, #FFFFFF);
          margin: 0;
          line-height: 1.3;
          flex: 1;
        }

        .status {
          flex-shrink: 0;
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          padding: 4px 8px;
          border-radius: var(--pm-radius-sm, 6px);
          background: var(--pm-bg-elevated, #13131a);
          color: var(--pm-fg-muted, #9ca3af);
        }
        /* Use --pm-accent-soft for status text (passes WCAG AA on dark bg).
           The accent-strong variant is reserved for backgrounds/borders. */
        :host([status="live"]) .status { color: var(--pm-accent-soft, #A78BFA); }
        :host([status="rehearsal"]) .status { color: var(--pm-accent-soft, #A78BFA); }
        :host([status="planned"]) .status { color: var(--pm-fg, #FFFFFF); }
        :host([status="archived"]) .status { color: var(--pm-fg-muted, #9ca3af); opacity: 0.7; }

        p.description {
          font-size: 14px;
          line-height: 1.5;
          color: var(--pm-fg-muted, #9ca3af);
          margin: 0;
        }

        .tags {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }

        .tag {
          font-size: 11px;
          padding: 3px 8px;
          border-radius: var(--pm-radius-sm, 6px);
          background: var(--pm-bg-elevated, #13131a);
          color: var(--pm-fg, #FFFFFF);
          font-weight: 500;
        }

        .links {
          display: flex;
          flex-direction: column;
          gap: 6px;
          padding-top: 4px;
        }

        .link {
          font-size: 13px;
          color: var(--pm-accent, #7C3AED);
          text-decoration: none;
          align-self: flex-start;
          transition: color var(--pm-motion-fast, 120ms cubic-bezier(0.2, 0, 0, 1));
        }
        .link:hover {
          color: var(--pm-accent-soft, #A78BFA);
        }
        .link:focus-visible {
          outline: 2px solid var(--pm-accent, #7C3AED);
          outline-offset: 2px;
          border-radius: var(--pm-radius-sm, 6px);
        }
      </style>

      <article class="card" role="article" aria-label="${this._escapeAttr(`Project: ${this.title || 'Untitled'}`)}">
        <header>
          <h3 class="title">${this._escapeText(this.title) || 'Untitled project'}</h3>
          <span class="status" aria-label="Status: ${this._escapeAttr(statusLabel)}">${this._escapeText(statusLabel)}</span>
        </header>
        ${this.description ? `<p class="description">${this._escapeText(this.description)}</p>` : ''}
        ${tagsHtml ? `<div class="tags" aria-label="Tags">${tagsHtml}</div>` : ''}
        ${linksHtml ? `<div class="links" role="list">${linksHtml}</div>` : ''}
      </article>
    `;
  }

  _escapeText(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  _safeHref(href) {
    // _escapeAttr stops attribute breakout but not scheme abuse — a
    // javascript: href survives escaping and executes on click. Allow
    // http(s), mailto, and scheme-less (relative/fragment) URLs only.
    if (!href) return '#';
    const v = String(href).trim();
    if (/^(https?:|mailto:)/i.test(v)) return v;
    if (/^[a-z][a-z0-9+.-]*:/i.test(v)) return '#';
    return v;
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

customElements.define('pm-project-card', PmProjectCard);

export { PmProjectCard };
