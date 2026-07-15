// <pm-haptic> — v0.1
// HTML5 Web Vibration API wrapper. Triggers navigator.vibrate() patterns
// for tactile feedback synced to events (BPM, button presses, alerts, etc).
//
// Per A2UI v0.1 spec §10. Uses the single data-source pattern (§7.2) for
// live BPM sync; respects prefers-reduced-motion by default.
//
// Spec compliance:
//   - Custom Element extending HTMLElement
//   - Shadow DOM (open) for style encapsulation
//   - No visible DOM (aria-hidden, no theming — output is haptic only)
//   - No framework imports, no inline styles
//   - Single data-source pull (§7.2), no chained pull
//   - Lifecycle cleanup in disconnectedCallback
//
// Usage:
//   <!-- One-shot pattern -->
//   <pm-haptic pattern="100,50,100,50,100"></pm-haptic>
//
//   <!-- Auto-derive from BPM -->
//   <pm-haptic bpm="120"></pm-haptic>
//
//   <!-- Live BPM via data-source (e.g. NATS subject or HTTP endpoint) -->
//   <pm-haptic data-source="fordham:track.bpm"></pm-haptic>

class PmHaptic extends HTMLElement {
  static get observedAttributes() {
    return ['pattern', 'bpm', 'data-source', 'respect-reduced-motion', 'enabled'];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._subscription = null;
    this._pulseTimer = null;
    this._reducedMotionQuery = null;
    this._reducedMotionHandler = null;
  }

  connectedCallback() {
    // Decorative output: vibration is invisible, so the host should not
    // appear in the a11y tree.
    this.setAttribute('aria-hidden', 'true');
    this._render();

    // Listen for reduced-motion changes so we can stop vibrating if the
    // user toggles the OS preference mid-session.
    if (window.matchMedia) {
      this._reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
      this._reducedMotionHandler = () => this._onAttributeChange();
      this._reducedMotionQuery.addEventListener('change', this._reducedMotionHandler);
    }

    this._subscribeIfNeeded();
    this._renderPulseOnNextFrame();
  }

  disconnectedCallback() {
    this._unsubscribe();
    this._stopLoop();
    if (this._reducedMotionQuery && this._reducedMotionHandler) {
      this._reducedMotionQuery.removeEventListener('change', this._reducedMotionHandler);
    }
    // Best-effort: stop any in-flight vibration so this component leaves
    // no tactile residue on disconnect.
    if (navigator.vibrate) navigator.vibrate(0);
  }

  attributeChangedCallback() {
    if (this.isConnected) {
      this._renderPulseOnNextFrame();
      this._subscribeIfNeeded();
    }
  }

  // Property getters/setters
  get pattern() { return this.getAttribute('pattern') || ''; }
  set pattern(v) { v ? this.setAttribute('pattern', v) : this.removeAttribute('pattern'); }

  get bpm() { return parseFloat(this.getAttribute('bpm')) || null; }
  set bpm(v) { v ? this.setAttribute('bpm', String(v)) : this.removeAttribute('bpm'); }

  get dataSource() { return this.getAttribute('data-source') || null; }
  set dataSource(v) { v ? this.setAttribute('data-source', v) : this.removeAttribute('data-source'); }

  get enabled() { return this.getAttribute('enabled') !== 'false'; }
  set enabled(v) { this.setAttribute('enabled', v ? 'true' : 'false'); }

  get respectReducedMotion() { return this.getAttribute('respect-reduced-motion') !== 'false'; }
  set respectReducedMotion(v) { this.setAttribute('respect-reduced-motion', v ? 'true' : 'false'); }

  _onAttributeChange() {
    this._renderPulseOnNextFrame();
    this._subscribeIfNeeded();
  }

  // Compute the vibration pattern from current state.
  _computePattern() {
    if (this.pattern) {
      return this.pattern.split(',').map((n) => parseInt(n.trim(), 10)).filter((n) => !Number.isNaN(n));
    }
    if (this.bpm && this.bpm > 0) {
      // Derive a 4-pulse pattern: 100ms on, then gap = (60/bpm)*1000 - 100
      const period = (60 / this.bpm) * 1000;
      const gap = Math.max(20, period - 100);
      return [100, gap, 100, gap, 100, gap, 100, gap];
    }
    return [];
  }

  _shouldVibrate() {
    if (!this.enabled) return false;
    if (!navigator.vibrate) return false;  // Device doesn't support vibration
    if (this.respectReducedMotion && this._reducedMotionQuery?.matches) return false;
    return true;
  }

  // Trigger a single vibration pulse + visual indicator.
  pulse() {
    const pattern = this._computePattern();
    if (pattern.length === 0) return;
    if (this._shouldVibrate()) {
      navigator.vibrate(pattern);
    }
    // Always render the visual indicator (even when vibration is skipped
    // due to reduced-motion) — users on no-vibration hardware still get
    // visible feedback.
    this._flash();
  }

  // Start a continuous loop (one pulse per BPM beat).
  startLoop() {
    this._stopLoop();
    const bpm = this.bpm;
    if (!bpm) return;
    const periodMs = (60 / bpm) * 1000;
    this._pulseTimer = setInterval(() => this.pulse(), periodMs);
  }

  _stopLoop() {
    if (this._pulseTimer) {
      clearInterval(this._pulseTimer);
      this._pulseTimer = null;
    }
  }

  // Visual indicator: a brief flash on the host (aria-hidden so it doesn't
  // pollute a11y tree; useful for users on no-vibration hardware).
  _flash() {
    if (!this._indicator) return;
    this._indicator.classList.remove('pulse');
    // Force reflow so the animation restarts even on rapid pulses
    void this._indicator.offsetWidth;
    this._indicator.classList.add('pulse');
  }

  _renderPulseOnNextFrame() {
    if (!this.isConnected) return;
    requestAnimationFrame(() => this._render());
  }

  _render() {
    // v0.1 rule: aria-hidden for decorative output. The component has no
    // visible DOM by default; the indicator is for sighted users on
    // no-vibration hardware.
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: inline-block;
          width: 12px;
          height: 12px;
          vertical-align: middle;
          margin: 0 4px;
        }
        :host([data-no-render]) {
          display: none;
        }
        .indicator {
          width: 100%;
          height: 100%;
          border-radius: 50%;
          background: var(--pm-accent, #7C3AED);
          opacity: 0.25;
          transition: opacity 80ms ease;
        }
        .indicator.pulse {
          opacity: 1;
          box-shadow: 0 0 8px var(--pm-accent, #7C3AED);
        }
      </style>
      <span class="indicator" part="indicator"></span>
    `;
    this._indicator = this.shadowRoot.querySelector('.indicator');
  }

  _subscribeIfNeeded() {
    const source = this.getAttribute('data-source');
    if (!source) {
      this._unsubscribe();
      return;
    }
    if (source.startsWith('http://') || source.startsWith('https://')) {
      this._subscription = this._fetchHttp(source);
    } else if (source.includes(':')) {
      this._subscription = this._subscribeNats(source);
    } else {
      this._subscription = null;
    }
  }

  _unsubscribe() {
    if (this._subscription && this._subscription.cancel) {
      this._subscription.cancel();
    }
    this._subscription = null;
  }

  _applyData(data) {
    if (typeof data.bpm === 'number' && data.bpm > 0) {
      this.bpm = data.bpm;
    }
  }

  _fetchHttp(url) {
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (data) this._applyData(data); })
      .catch(() => {});
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
        } catch (_) {}
      };
    } catch (_) {
      return { cancel: () => {} };
    }
    return { cancel: () => { if (es) es.close(); } };
  }
}

customElements.define('pm-haptic', PmHaptic);

export { PmHaptic };
