// <pm-toast> — v0.2
// Notification toast. ARIA role="status" with aria-live="polite".
// Variants: success, error, info, warning. Auto-dismiss with timeout.
//
// Per A2UI v0.2 ballot spec §4.3 (event wire). Used as the target of
// <pm-ballot on-vote-cast="pm-toast[primary]:show"> and similar.
//
// Spec compliance:
//   - Custom Element extending HTMLElement
//   - Shadow DOM (open)
//   - Reads --pm-* tokens
//   - Lifecycle cleanup in disconnectedCallback
//   - ARIA: role="status" + aria-live="polite"
//
// Usage:
//   <pm-toast id="vote-toast" timeout="5000"></pm-toast>
//   <pm-ballot on-vote-cast="vote-toast:show">...</pm-ballot>

class PmToast extends HTMLElement {
  static get observedAttributes() {
    return ['variant', 'timeout', 'position'];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._dismissTimer = null;
  }

  connectedCallback() {
    if (!this.hasAttribute('role')) this.setAttribute('role', 'status');
    this.setAttribute('aria-live', 'polite');
    this._render();
  }

  disconnectedCallback() {
    this._clearTimer();
  }

  attributeChangedCallback() {
    if (this.isConnected) this._render();
  }

  // Property getters/setters
  get variant() { return this.getAttribute('variant') || 'info'; }
  set variant(v) { this.setAttribute('variant', v); }

  get timeout() { return parseInt(this.getAttribute('timeout'), 10) || 5000; }
  set timeout(v) { this.setAttribute('timeout', String(v)); }

  get position() { return this.getAttribute('position') || 'bottom-right'; }
  set position(v) { this.setAttribute('position', v); }

  get visible() { return this._body?.classList.contains('visible') || false; }

  // Show a toast message. Variants: success, error, info, warning.
  // If message is omitted, uses textContent (slot content).
  show(message, variant, duration) {
    if (variant) this.variant = variant;
    if (duration !== undefined) this.timeout = duration;
    // Write only to the .text span — writing to _body (the container) would
    // wipe the icon and dismiss button, breaking every show() after the first.
    this._text.textContent = message || this.textContent || '';
    this._body.classList.add('visible');
    this.setAttribute('data-visible', 'true');
    this._resetTimer();
  }

  // Hide the toast immediately.
  hide() {
    this._body.classList.remove('visible');
    this.setAttribute('data-visible', 'false');
    this._clearTimer();
  }

  // Reset the auto-dismiss timer.
  _resetTimer() {
    this._clearTimer();
    if (this.timeout > 0) {
      this._dismissTimer = setTimeout(() => this.hide(), this.timeout);
    }
  }

  _clearTimer() {
    if (this._dismissTimer) {
      clearTimeout(this._dismissTimer);
      this._dismissTimer = null;
    }
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          position: fixed;
          z-index: 9999;
          pointer-events: none;
        }
        :host([position="top-right"]) { top: 16px; right: 16px; }
        :host([position="top-left"]) { top: 16px; left: 16px; }
        :host([position="bottom-right"]) { bottom: 16px; right: 16px; }
        :host([position="bottom-left"]) { bottom: 16px; left: 16px; }
        :host([position="top"]) { top: 16px; left: 50%; transform: translateX(-50%); }
        :host([position="bottom"]) { bottom: 16px; left: 50%; transform: translateX(-50%); }

        .body {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          min-width: 240px;
          max-width: 420px;
          padding: 12px 16px;
          background: var(--pm-bg-elevated, #13131a);
          border: 1px solid var(--pm-border, rgba(255, 255, 255, 0.08));
          border-left: 4px solid var(--pm-accent, #7C3AED);
          border-radius: var(--pm-radius, 12px);
          color: var(--pm-fg, #FFFFFF);
          font-family: var(--pm-font-body, system-ui, -apple-system, sans-serif);
          font-size: 14px;
          line-height: 1.4;
          pointer-events: auto;
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
          opacity: 0;
          transform: translateY(8px);
          transition: opacity 200ms cubic-bezier(0.2, 0, 0, 1), transform 200ms cubic-bezier(0.2, 0, 0, 1);
        }
        .body.visible {
          opacity: 1;
          transform: translateY(0);
        }

        :host([variant="success"]) .body { border-left-color: #10b981; }
        :host([variant="error"])   .body { border-left-color: #ef4444; }
        :host([variant="warning"]) .body { border-left-color: #f59e0b; }
        :host([variant="info"])    .body { border-left-color: var(--pm-accent, #7C3AED); }

        .icon {
          font-size: 16px;
          line-height: 1;
          flex-shrink: 0;
        }
        :host([variant="success"]) .icon { color: #10b981; }
        :host([variant="error"])   .icon { color: #ef4444; }
        :host([variant="warning"]) .icon { color: #f59e0b; }
        :host([variant="info"])    .icon { color: var(--pm-accent, #7C3AED); }

        .text {
          flex: 1;
          min-width: 0;
        }

        .close {
          background: none;
          border: none;
          color: var(--pm-fg-muted, #9ca3af);
          font-size: 18px;
          line-height: 1;
          cursor: pointer;
          padding: 0 0 0 4px;
          margin-left: 4px;
        }
        .close:hover { color: var(--pm-fg, #FFFFFF); }
        .close:focus-visible {
          outline: 2px solid var(--pm-accent, #7C3AED);
          outline-offset: 2px;
        }
      </style>
      <div class="body" role="alert">
        <span class="icon" aria-hidden="true">◆</span>
        <span class="text"></span>
        <button class="close" type="button" aria-label="Dismiss notification">×</button>
      </div>
    `;
    this._body = this.shadowRoot.querySelector('.body');
    this._text = this._body.querySelector('.text');
    this._body.querySelector('.close').addEventListener('click', () => this.hide());
  }
}

customElements.define('pm-toast', PmToast);

export { PmToast };
