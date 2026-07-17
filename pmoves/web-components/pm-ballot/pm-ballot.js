// <pm-ballot> — v0.2
// Co-op governance ballot. Native radio options, submit, live tally,
// quorum progressbar, CHIT-signed receipt per vote.
//
// Per A2UI v0.2 spec (pmoves/contracts/a2ui-v0.2-ballot.md §5).
//
// Spec compliance:
//   - Custom Element extending HTMLElement
//   - Shadow DOM (open) for style encapsulation
//   - Reads --pm-* tokens for theming
//   - State management via data-state-source (§4.2) + local fallback
//   - Event emission via pm-event slots (§4.3) — 'vote-cast' default
//   - No framework imports, no inline styles, no global listeners
//   - Lifecycle cleanup in disconnectedCallback
//   - ARIA: role="region", progressbar for quorum, native <input type="radio">
//
// Usage:
//   <pm-ballot
//     ballot-id="bylaw-2026-q3"
//     title="Bylaw amendment: recall procedure"
//     description="Adopt a transparent recall procedure so residents can hold the board accountable."
//     options='[{"id":"yes","label":"Yes"},{"id":"no","label":"No"},{"id":"abstain","label":"Abstain"}]'
//     eligible-voters="47"
//     quorum="0.5"
//     closes-at="2026-08-15T23:59:59-04:00"
//   ></pm-ballot>

class PmBallot extends HTMLElement {
  static get observedAttributes() {
    return [
      'ballot-id', 'title', 'description', 'options',
      'eligible-voters', 'quorum', 'closes-at',
      'voter-id', 'data-state-source', 'data-source',
      'allow-insecure-demo-hash',
    ];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._state = { tally: {} };
    // Public receipts, held back until close (see the `state` getter).
    this._sealedReceipts = [];
    this._myChoice = null;
    this._castError = null;
    this._forcedClosed = false;
    this._subscription = null;
    this._listeners = [];  // event-wire subscribers (e.g. <pm-toast>)
  }

  connectedCallback() {
    if (!this.hasAttribute('role')) this.setAttribute('role', 'region');
    this.setAttribute('aria-label', this._computeAriaLabel());
    this._render();
    this._subscribeIfNeeded();
    this._readInitialTally();
  }

  disconnectedCallback() {
    this._unsubscribe();
  }

  attributeChangedCallback(name) {
    if (!this.isConnected) return;
    if (name === 'data-state-source' || name === 'data-source') {
      this._unsubscribe();
      this._subscribeIfNeeded();
      this._readInitialTally();
    } else {
      this._render();
    }
  }

  // ---- Public API ----

  get ballotId() { return this.getAttribute('ballot-id') || ''; }
  set ballotId(v) { this.setAttribute('ballot-id', v); }

  get title() { return this.getAttribute('title') || 'Ballot'; }
  set title(v) { this.setAttribute('title', v); }

  get description() { return this.getAttribute('description') || ''; }
  set description(v) { this.setAttribute('description', v); }

  get options() { return this._parseOptions(); }
  set options(v) { this.setAttribute('options', JSON.stringify(v)); }

  get eligibleVoters() { return parseInt(this.getAttribute('eligible-voters'), 10) || 0; }
  set eligibleVoters(v) { this.setAttribute('eligible-voters', String(v)); }

  get quorum() { return parseFloat(this.getAttribute('quorum')) || 0.5; }
  set quorum(v) { this.setAttribute('quorum', String(v)); }

  get closesAt() { return this.getAttribute('closes-at') || null; }
  set closesAt(v) { v ? this.setAttribute('closes-at', v) : this.removeAttribute('closes-at'); }

  get voterId() { return this.getAttribute('voter-id') || null; }
  set voterId(v) { v ? this.setAttribute('voter-id', v) : this.removeAttribute('voter-id'); }

  // Published state (what `data-state-source` exposes to every client).
  //
  // Receipts are SEALED until the ballot closes. A 128-bit nonce hides the
  // choice inside the hash, but it does nothing if a receipt is published in
  // the same state update that increments its option's tally: an observer
  // polling this getter diffs two snapshots, sees one new receipt and one
  // bumped option, and re-links them without touching the hash. For a 47-unit
  // co-op recall that reconstructs the whole ballot.
  //
  // Three things are required together, and each closes a different re-link:
  //   1. seal until close      -> no live receipt/tally coincidence
  //   2. no `ts` on the public receipt -> an observer who recorded the tally
  //      timeline cannot re-link by timestamp after close (the voter keeps
  //      the exact ts in their own tuple; presence-in-log is what verifies)
  //   3. order by hash, not insertion -> position cannot re-link to the order
  //      the live tally moved in
  //
  // Deviates from spec §5.4/§5.2, which publish {receiptHash, ts} live —
  // raised as a spec amendment on PR #2133.
  get state() {
    const sealed = this._isSealed();
    return {
      ...this._state,
      receipts: sealed
        ? []
        : this._sealedReceipts.slice().sort((a, b) => (a.receiptHash < b.receiptHash ? -1 : 1)),
      receiptsSealed: sealed ? this._sealedReceipts.length : 0,
    };
  }
  get tally() { return this._state.tally || {}; }
  get myChoice() { return this._myChoice; }

  // Cast a vote. Generates a receipt, updates local state, fires the
  // 'vote-cast' event (v0.2 §4.3). Async because _hashReceipt uses the
  // (async) SubtleCrypto API.
  async castVote(optionId, voterIdOverride) {
    // A ballot served over plain http:// (a co-op LAN at http://192.168.x.x is
    // the realistic case) has no crypto.subtle, so the sha256 path is gone.
    // getRandomValues still works, so a 128-bit nonce would be minted and then
    // committed with a 32-bit FNV checksum — a colliding receipt is findable in
    // under a second, meaning the commitment binds to nothing and the voter is
    // told to verify with a hash that opens to more than one choice.
    // Refuse rather than silently downgrade: the old code disclosed the
    // downgrade in the receipt panel, i.e. only AFTER the vote was irrevocable.
    if (!this._canHashSecurely() && !this.hasAttribute('allow-insecure-demo-hash')) {
      this._castError = 'insecure-context';
      this._render();
      this._fire('ballot-unavailable', { reason: 'insecure-context' });
      return null;
    }
    if (!this._isVotingOpen()) {
      this._fire('ballot-closed', { reason: 'closed-or-not-yet-open' });
      return null;
    }
    const options = this.options;
    if (!options.find((o) => o.id === optionId)) {
      throw new Error(`unknown option: ${optionId}`);
    }
    const voterId = voterIdOverride || this.voterId || `anonymous-${Date.now()}`;
    const ts = new Date().toISOString();
    const nonce = this._nonce();
    const { hash: receiptHash, algo } = await this._hashReceipt(voterId, optionId, ts, nonce);

    // The voter's receipt. Held ONLY in this browser — it is the (choice, ts,
    // nonce) tuple §5.4 tells the resident to keep. It is returned to the
    // caller and rendered locally; it must never reach `_state`.
    const voterReceipt = {
      ballotId: this.ballotId, voterId, choice: optionId, ts, nonce, receiptHash, algo,
    };

    // The public receipt. Carries no voterId and no choice — not even in
    // recomputable form (§5.5 rule 1) — and no `ts`, which would let an
    // observer re-link it to a tally increment (see the `state` getter).
    //
    // No `signature` key: the CHIT signature is applied by the state authority
    // over each appended mutation, not minted client-side. A placeholder here
    // was a prefix of receiptHash — derivable by anyone, authenticating
    // nothing — and a field named `signature` invites a consumer to trust it.
    // An absent field fails loudly; a fake one fails silently.
    const publicReceipt = { receiptHash, status: 'cast' };
    this._sealedReceipts.push(publicReceipt);

    this._state = {
      ...this._state,
      tally: {
        ...this._state.tally,
        [optionId]: (this._state.tally[optionId] || 0) + 1,
        _total: (this._state.tally._total || 0) + 1,
      },
    };
    this._myChoice = { optionId, receipt: voterReceipt };
    this._render();

    // Event carries the PUBLIC receipt ONLY — no nonce, no choice, and no tally.
    // Shipping the post-cast tally beside the receiptHash re-links them for any
    // listener: the key that just incremented IS the choice. That is the same
    // correlation the `state` getter seals against, so emitting it here would
    // re-open it on the outward wire (§4.3 routes this off-component).
    // Consumers needing the aggregate read the `tally` getter, which carries no
    // receipt and so cannot be correlated with one.
    this._fire('vote-cast', { receipt: publicReceipt });
    if (this._hasReachedQuorum()) {
      this._fire('quorum-reached', { quorum: this.quorumPercent() });
    }
    // The voter's receipt goes to the caller, not to shared state.
    return voterReceipt;
  }

  // ---- v0.2 event wire (pm-event slots §4.3) ----

  // Parse `on-<event>` attributes and wire them up.
  // Format: `on-<event-name>="<component-id>:<method-name>"`
  // (without the bracket-by-id selector for v0.2 single-instance targets).
  _wireEvents() {
    // The renderer (tenant-renderer.js) wires events at the page level.
    // This method is a no-op here but kept for documentation.
  }

  // Fire a custom event. Components listening for `vote-cast` etc.
  // (e.g. a <pm-toast> registered for this ballot) can subscribe.
  _fire(eventName, detail) {
    this.dispatchEvent(new CustomEvent(eventName, {
      bubbles: true,
      composed: true,
      detail,
    }));
  }

  // ---- Internal helpers ----

  _parseOptions() {
    const raw = this.getAttribute('options');
    if (!raw) return [];
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  }

  // Close time in ms, or: null when unset, NaN when unparseable.
  _closeTime() {
    if (!this.closesAt) return null;
    return new Date(this.closesAt).getTime();   // NaN if the author typo'd it
  }

  // Is this ballot accepting votes? FAILS OPEN on a config error.
  // A malformed closes-at is an authoring mistake; disenfranchising every
  // resident because of one is the worse failure. Surfaced visibly instead.
  _isVotingOpen() {
    if (this._forcedClosed) return false;
    const t = this._closeTime();
    if (t === null || Number.isNaN(t)) return true;
    return Date.now() < t;
  }

  // Are receipts still sealed? FAILS CLOSED (sealed) on a config error.
  // Publishing receipts early leaks votes irreversibly; staying sealed is
  // merely inconvenient. Opposite default to _isVotingOpen by design — these
  // two consumers previously shared one boolean, so one was always wrong:
  // an unparseable date closed the voting AND lifted the seal simultaneously.
  _isSealed() {
    if (this._forcedClosed) return false;
    const t = this._closeTime();
    if (t === null || Number.isNaN(t)) return true;
    return Date.now() < t;
  }

  // Explicit close, so the seal has a lift condition that does not depend on an
  // optional attribute. Without this, a ballot authored with no closes-at (the
  // spec's own §6 sample, and this component's test fixture) stays sealed
  // forever and its receipts NEVER publish — residents could never verify.
  close() {
    this._forcedClosed = true;
    this._render();
  }

  // True when the ballot can never publish receipts on its own. Rendered as a
  // visible authoring error rather than silently swallowed.
  _hasNoCloseCondition() {
    const t = this._closeTime();
    return !this._forcedClosed && (t === null || Number.isNaN(t));
  }

  _hasReachedQuorum() {
    return this.quorumPercent() >= this.quorum;
  }

  quorumPercent() {
    if (this.eligibleVoters <= 0) return 0;
    return (this._state.tally._total || 0) / this.eligibleVoters;
  }

  // Is a real cryptographic hash available? crypto.subtle requires a secure
  // context (https:, or http://localhost — but NOT http://192.168.x.x).
  _canHashSecurely() {
    return !!(window.crypto && window.crypto.subtle);
  }

  // 128-bit voter-held nonce (§5.4). getRandomValues — unlike crypto.subtle —
  // is available in non-secure contexts, so the nonce never silently degrades.
  _nonce() {
    const b = new Uint8Array(16);
    (window.crypto || window.msCrypto).getRandomValues(b);
    return Array.from(b).map((x) => x.toString(16).padStart(2, '0')).join('');
  }

  // Length-prefixed (netstring-style) encoding of the receipt preimage.
  //
  // §5.4 requires that distinct input tuples can never produce the same
  // preimage. Plain `|`-joining does NOT give that: a `|` inside a field
  // shifts the boundaries, so ('apt-4B|yes','no') and ('apt-4B','yes|no')
  // collide. Prefixing each field with its length makes the parse unambiguous
  // for ANY field content, so no caller has to remember to sanitize.
  _preimage(ballotId, voterId, choice, ts, nonce) {
    return [ballotId, voterId, choice, ts, nonce]
      .map((f) => `${String(f).length}:${f}`)
      .join('');
  }

  // Receipt hash: sha256 over the nonce commitment where a secure context is
  // available; otherwise a non-cryptographic FNV-1a checksum. Returns
  // { hash, algo } so the receipt UI can be honest about which ran.
  async _hashReceipt(voterId, choice, ts, nonce) {
    const input = this._preimage(this.ballotId, voterId, choice, ts, nonce);
    if (window.crypto && window.crypto.subtle) {
      const buf = new TextEncoder().encode(input);
      const digest = await window.crypto.subtle.digest('SHA-256', buf);
      const hex = Array.from(new Uint8Array(digest))
        .map((b) => b.toString(16).padStart(2, '0')).join('');
      return { hash: `0x${hex}`, algo: 'sha256' };
    }
    // Fallback: FNV-1a (32-bit). Non-cryptographic, but works without a
    // secure context (e.g. plain http:// or file://) for local demos.
    let h = 0x811c9dc5;
    for (let i = 0; i < input.length; i++) {
      h = (h ^ input.charCodeAt(i)) >>> 0;
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return { hash: `0xfnv1a${h.toString(16).padStart(8, '0')}`, algo: 'fnv1a-32' };
  }

  _computeAriaLabel() {
    return `Ballot: ${this.title}`;
  }

  _readInitialTally() {
    // v0.2: read from data-state-source. Local mode just starts at zero.
    // (In production, the subscribe handler updates this._state.)
  }

  _subscribeIfNeeded() {
    const source = this.getAttribute('data-state-source') || this.getAttribute('data-source');
    if (!source) return;
    if (source.startsWith('http://') || source.startsWith('https://')) {
      this._subscription = this._fetchHttp(source);
    } else if (source.includes(':')) {
      this._subscription = this._subscribeNats(source);
    }
  }

  _unsubscribe() {
    if (this._subscription && this._subscription.cancel) {
      this._subscription.cancel();
    }
    this._subscription = null;
  }

  _applyData(data) {
    if (data && data.tally) {
      this._state = { ...this._state, tally: data.tally };
      this._render();
    }
    if (data && data.receipts) {
      // Authority-published log lands in the sealed store; the `state` getter
      // decides whether it is visible yet. Never assign to _state.receipts —
      // that would bypass the seal.
      this._sealedReceipts = data.receipts.slice();
      this._render();
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
          this._applyData(JSON.parse(ev.data));
        } catch (_) {}
      };
    } catch (_) {
      return { cancel: () => {} };
    }
    return { cancel: () => { if (es) es.close(); } };
  }

  // ---- Render helpers ----

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

  // ---- Render ----

  _render() {
    const options = this.options;
    const tally = this._state.tally || {};
    const total = tally._total || 0;
    const quorumPct = this.quorumPercent();
    const quorumTarget = this.quorum;
    const reachedQuorum = this._hasReachedQuorum();
    const open = this._isVotingOpen();
    const myChoice = this._myChoice;
    // A ballot that cannot hash securely must not accept a vote at all, and the
    // resident must learn that BEFORE they choose — not in the receipt panel
    // after the button has already locked.
    const insecure = !this._canHashSecurely() && !this.hasAttribute('allow-insecure-demo-hash');
    // A ballot with no parseable close time can never publish its receipts, so
    // no resident could ever verify. Surface it instead of sealing silently.
    const noClose = this._hasNoCloseCondition();
    const usable = open && !insecure;

    // Blocking notices, rendered above the options so they are read first.
    const noticeHtml = [
      insecure ? `<p class="notice notice-error" role="alert"><strong>Voting is unavailable on this
        connection.</strong> This page is not served over a secure connection (https), so your
        browser cannot create a real cryptographic receipt. Casting a vote here would give you a
        receipt that does not actually prove anything. Open this ballot over https and try again.</p>` : '',
      noClose ? `<p class="notice notice-warn" role="alert"><strong>This ballot has no valid closing
        time set.</strong> Receipts stay sealed until a ballot closes, so until this is fixed by
        whoever published it, no one will be able to verify the result.</p>` : '',
    ].join('');

    // Per-option rows
    const optionsHtml = options.map((opt) => {
      const count = tally[opt.id] || 0;
      const pct = total > 0 ? (count / total * 100).toFixed(0) : 0;
      const checked = myChoice?.optionId === opt.id;
      const disabled = !usable || !!myChoice;
      return `
        <label class="option ${checked ? 'selected' : ''}" data-option-id="${this._escapeAttr(opt.id)}">
          <input type="radio" name="ballot-${this._escapeAttr(this.ballotId)}" value="${this._escapeAttr(opt.id)}" ${checked ? 'checked' : ''} ${disabled ? 'disabled' : ''} />
          <span class="opt-label">${this._escapeText(opt.label)}</span>
          <span class="opt-count" aria-label="${count} votes">${count} (${pct}%)</span>
        </label>
      `;
    }).join('');

    // Receipt display if user has voted. The verify instruction and trust
    // language depend on which hash algorithm actually ran: sha256 in a
    // secure context, or a non-cryptographic local checksum as fallback.
    const receiptNote = myChoice
      ? (myChoice.receipt.algo === 'sha256'
        ? `Your vote is recorded (CHIT signature pending signing-card registration). <strong>Save your secret code above — it is shown once and only you have it.</strong> Without it your vote still counts, but you lose the ability to check it yourself. When the ballot closes, recompute your receipt from your saved code and find it in the published list — that proves your vote was counted without revealing to anyone how you voted.</p>`
        : `Your vote is recorded (CHIT signature pending signing-card registration). This receipt is a non-cryptographic local demo checksum (FNV-1a) because the page is not running in a secure context — it is not verifiable with sha256.</p>`)
      : '';
    const receiptHtml = myChoice ? `
      <div class="receipt" role="status">
        <h4>Your vote was cast</h4>
        <dl>
          <dt>Choice</dt><dd>${this._escapeText(myChoice.optionId)}</dd>
          <dt>Time</dt><dd>${this._escapeText(myChoice.receipt.ts)}</dd>
          <dt>Receipt</dt><dd class="hash">${this._escapeText(myChoice.receipt.receiptHash)}</dd>
          <dt>Your secret code</dt><dd class="hash nonce">${this._escapeText(myChoice.receipt.nonce || '')}</dd>
        </dl>
        <p class="receipt-note">${receiptNote}
      </div>
    ` : '';

    // Quorum bar
    const quorumPctStyle = Math.min(100, (quorumPct / Math.max(quorumTarget, 0.01)) * 100);
    const quorumHtml = `
      <div class="quorum" role="progressbar"
           aria-valuenow="${Math.round(quorumPct * 100)}"
           aria-valuemin="0" aria-valuemax="100"
           aria-label="Quorum progress: ${(quorumPct * 100).toFixed(1)} percent of ${(quorumTarget * 100).toFixed(0)} percent required">
        <div class="quorum-bar">
          <div class="quorum-fill" style="width: ${quorumPctStyle.toFixed(1)}%"></div>
          <div class="quorum-target" style="left: ${(quorumTarget * 100).toFixed(1)}%"></div>
        </div>
        <div class="quorum-text">
          <span><strong>${(quorumPct * 100).toFixed(1)}%</strong> quorum (need ${(quorumTarget * 100).toFixed(0)}%)</span>
          <span class="quorum-count">${total} / ${this.eligibleVoters} voted</span>
        </div>
      </div>
    `;

    // Status banner
    const statusHtml = !open
      ? `<p class="status status-closed">⏰ This ballot closed at ${this._escapeText(this.closesAt)}.</p>`
      : (this.closesAt
        ? `<p class="status status-open">⏰ Closes at ${this._escapeText(this.closesAt)}.</p>`
        : '');

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--pm-font-body, system-ui, -apple-system, sans-serif);
        }
        article {
          background: var(--pm-bg, #0b0b10);
          border: 1px solid var(--pm-border, rgba(255, 255, 255, 0.08));
          border-radius: var(--pm-radius, 12px);
          padding: calc(var(--pm-spacing-unit, 8px) * 3);
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        header h3 {
          font-family: var(--pm-font-display, 'Orbitron', system-ui);
          font-size: 20px;
          font-weight: 700;
          color: var(--pm-fg, #FFFFFF);
          margin: 0 0 8px 0;
          line-height: 1.3;
        }
        p.description {
          font-size: 14px;
          line-height: 1.5;
          color: var(--pm-fg-muted, #9ca3af);
          margin: 0;
        }
        p.status {
          font-size: 12px;
          padding: 6px 10px;
          border-radius: var(--pm-radius-sm, 6px);
          background: var(--pm-bg-elevated, #13131a);
          color: var(--pm-fg-muted, #9ca3af);
          margin: 0;
        }
        p.status.status-closed { opacity: 0.7; }
        p.status.status-error {
          background: var(--pm-danger-bg, rgba(225, 29, 72, 0.12));
          color: var(--pm-danger, #E11D48);
        }
        .options {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .option {
          display: grid;
          grid-template-columns: auto 1fr auto;
          gap: 12px;
          align-items: center;
          padding: 12px 16px;
          background: var(--pm-bg-elevated, #13131a);
          border: 1px solid var(--pm-border, rgba(255, 255, 255, 0.08));
          border-radius: var(--pm-radius, 12px);
          cursor: pointer;
          transition: border-color var(--pm-motion-fast, 120ms cubic-bezier(0.2, 0, 0, 1));
        }
        .option:hover { border-color: var(--pm-accent-soft, #A78BFA); }
        .option.selected {
          border-color: var(--pm-accent, #7C3AED);
          background: var(--pm-accent, #7C3AED);
          color: white;
        }
        .option input[type="radio"] {
          accent-color: var(--pm-accent, #7C3AED);
        }
        .option.selected input[type="radio"] { accent-color: white; }
        .opt-label {
          font-size: 14px;
          font-weight: 500;
        }
        .opt-count {
          font-size: 12px;
          color: var(--pm-fg-muted, #9ca3af);
          font-variant-numeric: tabular-nums;
          white-space: nowrap;
        }
        .option.selected .opt-count { color: rgba(255, 255, 255, 0.8); }
        button.cast {
          background: var(--pm-accent, #7C3AED);
          color: white;
          border: none;
          border-radius: var(--pm-radius, 12px);
          padding: 12px 24px;
          font: inherit;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
        }
        button.cast:hover { background: var(--pm-accent-soft, #A78BFA); }
        .notice {
          margin: 0 0 12px; padding: 10px 12px; border-radius: 6px;
          font-size: 0.9rem; line-height: 1.45;
        }
        .notice-error {
          background: rgba(220, 38, 38, 0.12);
          border: 1px solid rgba(220, 38, 38, 0.5);
          color: var(--pm-color-text, inherit);
        }
        .notice-warn {
          background: rgba(217, 119, 6, 0.12);
          border: 1px solid rgba(217, 119, 6, 0.5);
          color: var(--pm-color-text, inherit);
        }
        button.cast:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        button.cast:focus-visible {
          outline: 2px solid var(--pm-accent-soft, #A78BFA);
          outline-offset: 2px;
        }
        .quorum {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .quorum-bar {
          position: relative;
          height: 8px;
          background: var(--pm-bg-elevated, #13131a);
          border-radius: 4px;
          overflow: hidden;
        }
        .quorum-fill {
          height: 100%;
          background: var(--pm-accent, #7C3AED);
          transition: width 300ms cubic-bezier(0.2, 0, 0, 1);
        }
        .quorum-target {
          position: absolute;
          top: -2px;
          bottom: -2px;
          width: 2px;
          background: var(--pm-fg, #FFFFFF);
          opacity: 0.6;
        }
        .quorum-text {
          display: flex;
          justify-content: space-between;
          font-size: 12px;
          color: var(--pm-fg-muted, #9ca3af);
        }
        .quorum-text strong { color: var(--pm-fg, #FFFFFF); font-weight: 600; }
        .quorum-count { font-variant-numeric: tabular-nums; }

        .receipt {
          background: var(--pm-bg-elevated, #13131a);
          border: 1px solid var(--pm-accent, #7C3AED);
          border-radius: var(--pm-radius, 12px);
          padding: 16px;
        }
        .receipt h4 {
          font-size: 14px;
          font-weight: 600;
          color: var(--pm-accent-soft, #A78BFA);
          margin: 0 0 12px 0;
        }
        .receipt dl {
          display: grid;
          grid-template-columns: auto 1fr;
          gap: 4px 12px;
          margin: 0 0 12px 0;
          font-size: 13px;
        }
        .receipt dt {
          color: var(--pm-fg-muted, #9ca3af);
          font-weight: 500;
        }
        .receipt dd {
          color: var(--pm-fg, #FFFFFF);
          margin: 0;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 12px;
        }
        .receipt dd.hash {
          word-break: break-all;
        }
        .receipt-note {
          font-size: 11px;
          color: var(--pm-fg-muted, #9ca3af);
          line-height: 1.4;
          margin: 0;
        }
        .receipt-note code {
          background: rgba(255, 255, 255, 0.05);
          padding: 1px 4px;
          border-radius: 3px;
          font-size: 10px;
        }
      </style>

      <article>
        <header>
          <h3>${this._escapeText(this.title)}</h3>
          ${this.description ? `<p class="description">${this._escapeText(this.description)}</p>` : ''}
        </header>
        ${statusHtml}
        <form class="options" role="radiogroup" aria-label="Ballot options">
          ${noticeHtml}
          ${optionsHtml}
        </form>
        <button type="button" class="cast" ${!usable || !!myChoice ? 'disabled' : ''}>
          ${myChoice ? '✓ Vote cast' : insecure ? 'Voting unavailable' : open ? 'Cast vote' : 'Ballot closed'}
        </button>
        ${this._castError ? `<p class="status status-error" role="alert">⚠ Could not cast vote: ${this._escapeText(this._castError)}</p>` : ''}
        ${quorumHtml}
        ${receiptHtml}
      </article>
    `;

    // Wire submit
    const form = this.shadowRoot.querySelector('form.options');
    if (form) {
      form.addEventListener('change', (ev) => {
        if (ev.target.matches('input[type="radio"]')) {
          // Update visual selection (the actual cast happens on submit)
          form.querySelectorAll('.option').forEach((el) => el.classList.remove('selected'));
          ev.target.closest('.option')?.classList.add('selected');
        }
      });
    }
    const btn = this.shadowRoot.querySelector('button.cast');
    if (btn && !btn.disabled) {
      btn.addEventListener('click', () => {
        const selected = this.shadowRoot.querySelector('input[type="radio"]:checked');
        if (!selected) return;
        // castVote is async (uses crypto.subtle). Disable the button while it
        // resolves and surface any failure inline rather than only to console.
        btn.disabled = true;
        this._castError = null;
        this.castVote(selected.value).catch((err) => {
          this._castError = err && err.message ? err.message : String(err);
          this._render();
        });
      });
    }
  }
}

customElements.define('pm-ballot', PmBallot);

export { PmBallot };
