// <pm-voice-clip> — v0.1
// Embedded audio with metadata. Optional transcript (collapsible).
// Per A2UI v0.1 spec §10.

class PmVoiceClip extends HTMLElement {
  static get observedAttributes() {
    return ['src', 'title', 'duration', 'transcript', 'speaker'];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    if (!this.hasAttribute('role')) this.setAttribute('role', 'region');
    this._render();
  }

  disconnectedCallback() {
    // No subscriptions; native <audio> handles its own cleanup.
  }

  attributeChangedCallback() {
    if (this.isConnected) this._render();
  }

  get src() { return this.getAttribute('src') || ''; }
  set src(v) { this.setAttribute('src', v); }

  get title() { return this.getAttribute('title') || ''; }
  set title(v) { this.setAttribute('title', v); }

  get duration() { return this.getAttribute('duration') || ''; }
  set duration(v) { this.setAttribute('duration', v); }

  get transcript() { return this.getAttribute('transcript') || ''; }
  set transcript(v) { this.setAttribute('transcript', v); }

  get speaker() { return this.getAttribute('speaker') || ''; }
  set speaker(v) { this.setAttribute('speaker', v); }

  _render() {
    if (!this.src) {
      this.shadowRoot.innerHTML = `<p style="color:var(--pm-fg-muted);">No audio source.</p>`;
      return;
    }

    const transcriptHtml = this.transcript
      ? `
        <details class="transcript">
          <summary>Transcript</summary>
          <p>${this._escapeText(this.transcript)}</p>
        </details>
      `
      : '';

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--pm-font-body, system-ui, -apple-system, sans-serif);
        }

        .clip {
          background: var(--pm-bg, #0b0b10);
          border: 1px solid var(--pm-border, rgba(255, 255, 255, 0.08));
          border-radius: var(--pm-radius, 12px);
          padding: calc(var(--pm-spacing-unit, 8px) * 2);
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        header {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          gap: 12px;
        }

        h3.title {
          font-family: var(--pm-font-display, 'Orbitron', system-ui);
          font-size: 16px;
          font-weight: 600;
          color: var(--pm-fg, #FFFFFF);
          margin: 0;
          line-height: 1.3;
        }

        .meta {
          font-size: 12px;
          color: var(--pm-fg-muted, #9ca3af);
          white-space: nowrap;
          display: flex;
          gap: 8px;
        }

        audio {
          width: 100%;
        }

        details.transcript {
          border-top: 1px solid var(--pm-border, rgba(255, 255, 255, 0.08));
          padding-top: 12px;
        }

        details.transcript summary {
          cursor: pointer;
          font-size: 13px;
          color: var(--pm-accent-soft, #A78BFA);
          font-weight: 500;
          list-style: none;
        }
        details.transcript summary::-webkit-details-marker { display: none; }
        details.transcript summary::before { content: '▶ '; font-size: 10px; }
        details.transcript[open] summary::before { content: '▼ '; }

        details.transcript p {
          margin: 8px 0 0 0;
          font-size: 13px;
          line-height: 1.5;
          color: var(--pm-fg-muted, #9ca3af);
        }
      </style>

      <article class="clip" aria-label="${this._escapeAttr(`Voice clip: ${this.title}`)}">
        <header>
          <h3 class="title">${this._escapeText(this.title) || 'Untitled voice clip'}</h3>
          <div class="meta">
            ${this.speaker ? `<span>${this._escapeText(this.speaker)}</span>` : ''}
            ${this.duration ? `<span>${this._escapeText(this.duration)}</span>` : ''}
          </div>
        </header>
        <audio controls preload="metadata" src="${this._escapeAttr(this.src)}">
          Your browser does not support the audio element.
        </audio>
        ${transcriptHtml}
      </article>
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

customElements.define('pm-voice-clip', PmVoiceClip);

export { PmVoiceClip };
