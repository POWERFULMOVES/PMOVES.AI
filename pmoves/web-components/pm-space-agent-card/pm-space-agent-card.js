// <pm-space-agent-card> — v0.1
// Agent identity card. Renders avatar (or glyph), name, role, presence signal.
// Per A2UI v0.1 spec §10.
//
// Spec compliance:
//   - Custom Element extending HTMLElement
//   - Shadow DOM (open) for style encapsulation
//   - Reads --pm-* tokens for theming (no hardcoded colors)
//   - No framework imports, no inline styles, no global listeners
//   - ARIA: role="article" + aria-label includes name
//   - data-source support: pull single subject for live presence updates
//   - Lifecycle: connectedCallback/disconnectedCallback clean up subscriptions
//
// Usage:
//   <pm-space-agent-card
//     agent-name="CLAUDE-OPUS"
//     role="analytical"
//     glyph="◆"
//     presence="live"
//     theme="armor"
//   ></pm-space-agent-card>

class PmSpaceAgentCard extends HTMLElement {
  static get observedAttributes() {
    return ['agent-name', 'agent-role', 'avatar', 'presence', 'glyph', 'theme', 'data-source'];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._subscription = null;
  }

  connectedCallback() {
    // Avoid ARIA role attribute conflict — this custom element does not carry
    // a host-level ARIA role; the article inside the shadow root has role="article".
    if (!this.hasAttribute('role')) this.setAttribute('role', 'article');
    this._render();
    this._subscribeIfNeeded();
  }

  disconnectedCallback() {
    this._unsubscribe();
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue === newValue) return;
    if (this.isConnected) {
      this._render();
      if (name === 'data-source') {
        this._unsubscribe();
        this._subscribeIfNeeded();
      }
    }
  }

  // Property getters/setters for ergonomic JS use
  get agentName() { return this.getAttribute('agent-name') || ''; }
  set agentName(v) { this.setAttribute('agent-name', v); }

  // Renamed from `role` to `agentRole` to avoid clashing with the HTML `role`
  // attribute (which is reserved for ARIA roles on elements).
  get agentRole() { return this.getAttribute('agent-role') || ''; }
  set agentRole(v) { this.setAttribute('agent-role', v); }

  get avatar() { return this.getAttribute('avatar') || null; }
  set avatar(v) { v ? this.setAttribute('avatar', v) : this.removeAttribute('avatar'); }

  get presence() { return this.getAttribute('presence') || 'offline'; }
  set presence(v) { this.setAttribute('presence', v); }

  get glyph() { return this.getAttribute('glyph') || '◆'; }
  set glyph(v) { this.setAttribute('glyph', v); }

  get theme() { return this.getAttribute('theme') || 'armor'; }
  set theme(v) { this.setAttribute('theme', v); }

  _render() {
    const presenceLabel = {
      live: 'Live now',
      rehearsal: 'In rehearsal',
      offline: 'Offline',
    }[this.presence] || this.presence;

    const presenceIcon = {
      live: '●',
      rehearsal: '◐',
      offline: '○',
    }[this.presence] || '○';

    const avatarHtml = this.avatar
      ? `<img class="avatar" src="${this._escapeAttr(this.avatar)}" alt="" />`
      : `<span class="glyph" aria-hidden="true">${this._escapeText(this.glyph)}</span>`;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --_presence-color: var(--pm-fg-muted);
          display: block;
          font-family: var(--pm-font-body, system-ui, -apple-system, sans-serif);
        }
        /* Use --pm-accent-soft (lighter purple) for the presence TEXT so it
           passes WCAG AA contrast on the dark card background. The dot itself
           can stay as --pm-accent since the dot is decorative (the text carries
           the accessible meaning). */
        :host([presence="live"]) { --_presence-color: var(--pm-accent-soft, #A78BFA); }
        :host([presence="rehearsal"]) { --_presence-color: var(--pm-accent-soft, #A78BFA); }
        :host([presence="offline"]) { --_presence-color: var(--pm-fg-muted); }

        .card {
          display: grid;
          grid-template-columns: auto 1fr;
          gap: var(--pm-spacing-unit, 8px);
          padding: calc(var(--pm-spacing-unit, 8px) * 2);
          background: var(--pm-bg, #0b0b10);
          border: 1px solid var(--pm-border, rgba(255, 255, 255, 0.08));
          border-radius: var(--pm-radius, 12px);
          align-items: center;
        }

        .avatar,
        .glyph {
          width: 48px;
          height: 48px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--pm-bg-elevated, #13131a);
          border-radius: var(--pm-radius, 12px);
          color: var(--pm-accent, #7C3AED);
          font-size: 24px;
          flex-shrink: 0;
        }

        .avatar {
          object-fit: cover;
        }

        .meta {
          min-width: 0;
        }

        .name {
          font-family: var(--pm-font-display, 'Orbitron', system-ui);
          font-size: 16px;
          font-weight: 600;
          color: var(--pm-fg, #FFFFFF);
          margin: 0 0 2px 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .role {
          font-size: 13px;
          color: var(--pm-fg-muted, #9ca3af);
          margin: 0;
        }

        .presence {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          margin-top: 6px;
          font-size: 12px;
          color: var(--_presence-color);
          font-weight: 500;
        }

        .presence-dot {
          font-size: 10px;
          line-height: 1;
        }
      </style>

      <article class="card" role="article" aria-label="${this._escapeAttr(`Agent card: ${this.agentName}`)}">
        ${avatarHtml}
        <div class="meta">
          <h3 class="name">${this._escapeText(this.agentName) || 'Unnamed agent'}</h3>
          ${this.agentRole ? `<p class="role">${this._escapeText(this.agentRole)}</p>` : ''}
          <p class="presence" aria-live="polite">
            <span class="presence-dot" aria-hidden="true">${presenceIcon}</span>
            <span>${this._escapeText(presenceLabel)}</span>
          </p>
        </div>
      </article>
    `;
  }

  _subscribeIfNeeded() {
    const source = this.getAttribute('data-source');
    if (!source) return;

    // v0.1 data-source: NATS subject via SSE bridge OR HTTP endpoint.
    // Shape: "<tenant>:<subject>" (NATS) or "http(s)://..." (HTTP)
    // Returns JSON: { presence: "live"|"rehearsal"|"offline", ... }
    if (source.startsWith('http://') || source.startsWith('https://')) {
      this._subscription = this._pollHttp(source);
    } else if (source.includes(':')) {
      this._subscription = this._subscribeNats(source);
    }
  }

  _pollHttp(url) {
    // v0.1: simple one-shot fetch. v0.2: SSE or polling with debounce.
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && data.presence) {
          this.presence = data.presence;
        }
      })
      .catch(() => {
        // Graceful degradation: log + keep current presence value
        // Per spec §13.3 v0.1: log + display fallback (no exception)
      });
    return { cancel: () => {} };
  }

  _subscribeNats(subject) {
    // v0.1: NATS subscription via pmoves-bus SSE bridge.
    // The bridge exposes an EventSource at /api/nats/sse?subject=<subject>
    // and emits { type: "message", data: { presence: ... } } events.
    const url = `/api/nats/sse?subject=${encodeURIComponent(subject)}`;
    let es;
    try {
      es = new EventSource(url);
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data && data.presence) {
            this.presence = data.presence;
          }
        } catch (_) {
          // ignore malformed messages
        }
      };
    } catch (_) {
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

  // HTML/text escaping helpers (anti-pattern guard: no XSS via props)
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

customElements.define('pm-space-agent-card', PmSpaceAgentCard);

export { PmSpaceAgentCard };
