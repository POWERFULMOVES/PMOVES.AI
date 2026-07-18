# A2UI v0.2 — `<pm-ballot>` extension + stateful surfaces

> **Status**: DRAFT (sketch, rev 3) — `WEBSITE_AS_AGENT_CANVAS` lane
> **Date**: 2026-07-15 (rev 2: 2026-07-16 — receipt model reworked for ballot
> secrecy after 5090-CLAUDE peer review; rev 3: 2026-07-17 — §5.2/§5.4/§5.5
> reconciled to the shipped `<pm-ballot>` implementation by B850-CLAUDE:
> netstring preimage, no `ts` on the public receipt, seal-until-close +
> hash-ordering, refuse-by-default on non-secure contexts. Proposed amendment
> pending Mavis-5090 ACK.)
> **Author**: Mavis-5090 (rev 1–2); rev-3 reconciliation by B850-CLAUDE
> **Target use case**: Housing-cooperative governance — quorum tracking,
> bylaw-amendment votes, and member decisions with a verifiable, auditable trail
> **Supersedes**: nothing (additive to v0.1)
> **Pattern credit**: rooms-on-a-stage eureka from the Mavis/Opus lineage. DARKXSIDE attributed the lineage and assigned Mavis-5090 the architectural leadership role.

## 1. Purpose

`v0.1` covers static / push / single-pull surfaces. **v0.2 adds stateful surfaces** — components that read, mutate, and broadcast persistent state — so PMOVES can host governance lanes (ballots, petitions, attestations) on top of the same composable substrate.

The first stateful component is **`<pm-ballot>`** — the "co-op residents vote on a bylaw change" surface. It is also the canonical example for v0.2's new contract extensions.

## 2. Why a separate spec

v0.1 explicitly forbids chained pull, stateful components, and event emission (per the "v0.1 strict subset" rule). v0.2 unlocks all three. The new contract surface is **additive** — v0.1 components still work unchanged in v0.2 environments.

## 3. What v0.2 unlocks (vs v0.1)

| Feature | v0.1 | v0.2 |
|---------|------|------|
| Push (props) | ✓ | ✓ |
| Single data-source pull | ✓ | ✓ |
| **Chained pull** (one component's state drives another) | ✗ | ✓ explicit opt-in via `data-derive` |
| **Stateful component** (component reads/writes tenant state) | ✗ | ✓ via `data-state-source` |
| **Event emission** (component emits events to NATS) | ✗ | ✓ via `pm-event` slots |
| **CHIT-signed payloads** (every state change is a signed trail entry) | n/a | ✓ when the tenant has a registered CHIT signing card; unsigned **demo mode** otherwise (and the UI must say so — see §5.4) |

## 4. v0.2 contract extensions to v0.1

### 4.1 `data-derive` (chained pull — opt-in)

```html
<!-- Show "yes% / total%" derived from the pm-ballot's live tally -->
<pm-metric-tile
  label="Yes so far"
  data-derive="pm-ballot[primary]:tally.percentYes"
  format="percent"
></pm-metric-tile>
```

**Rules**:
- `data-derive` is a string of the form `<component-id-or-tag>:<dotted-path>`
- The component ID is a `pm-id` attribute on the source component, OR the tag if no other instance exists
- The dotted path is a JS property path on the source component's `state` getter
- The subscription is one-shot on mount; v0.2 does NOT auto-re-render when the source's state changes (use a NATS data-source for live updates if needed)
- **Freeze trap**: because it is one-shot, `data-derive` is WRONG for values
  that are the point of watching live — e.g. a quorum-progress tile derived
  from a ballot's tally freezes at its mount-time value. For live tallies,
  rely on the ballot's own quorum bar or a `data-source` subscription.
- This is the ONLY allowed chain in v0.2. Two-hop and deeper chains are forbidden (parking-lot for v0.3)

### 4.2 `data-state-source` (stateful component)

```html
<pm-ballot
  ballot-id="bylaw-2026-q3"
  data-state-source="fordham:ballots.bylaw-2026-q3"
></pm-ballot>
```

**Rules**:
- `data-state-source` reads the state at mount and subscribes to mutations
- A v0.2 component can read its state via `this._state` (a getter on the Custom Element)
- A v0.2 component can write its state via `this._commit(newState)` — this:
  - Updates the local `this._state`
  - Publishes a CHIT-signed payload to `<data-state-source>` (signature includes the previous state hash, so the trail is tamper-evident)
  - Re-renders the component
- State payloads have the shape `{ value, ts, prevHash, signature }` — the `prevHash` chains them together
- v0.2 components MUST clean up state subscriptions in `disconnectedCallback` (same rule as data-source)

### 4.3 `pm-event` slots (event emission)

```html
<pm-ballot
  ballot-id="bylaw-2026-q3"
  on-vote-cast="pm-toast[primary]:show"
></pm-ballot>
```

**Rules**:
- `on-<event-name>` attributes wire component events to data-derive targets
- The target is a `<component-id>:<method>` reference
- v0.2 supports: `on-vote-cast`, `on-quorum-reached`, `on-ballot-closed`,
  `on-ballot-unavailable` (extensible)
- **Event payloads carry no secret.** `vote-cast` carries the **public
  receipt only** — `{ receipt: { receiptHash, status } }` — never the choice,
  the nonce, or the post-cast tally. Shipping the tally beside the receiptHash
  would re-link them for any listener (the key that just incremented *is* the
  choice), re-opening on the outward wire the same correlation §5.5 seals
  against. Consumers needing the aggregate read the `tally` getter, which
  carries no receipt.
- Events propagate through the same CHIT trail mechanism as state mutations

## 5. `<pm-ballot>` — the v0.2 reference component

### 5.1 API surface

```html
<pm-ballot
  ballot-id="bylaw-2026-q3"
  data-state-source="fordham:ballots.bylaw-2026-q3"
  on-vote-cast="pm-toast[primary]:show"
></pm-ballot>
```

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `ballot-id` | string | ✓ | Unique ballot identifier (tenant-scoped). |
| `data-state-source` | string | ✓ | NATS subject where the live tally + receipt log live. |
| `voter-id` | string | (auth) | The current voter's identifier, set by the auth layer (out of scope for v0.2 spec). |
| `on-vote-cast` | event wire |   | Triggers a child component when a vote is cast. |
| `quorum-display` | `"hidden"` \| `"visible"` | `"visible"` | Whether to show the live quorum progress bar. |
| `closes-at` | ISO 8601 |   | When set, the ballot is read-only after this time, and the receipts log stays sealed until then (§5.5). |

### 5.2 State shape (the payload at `data-state-source`)

```json
{
  "ballot": {
    "id": "bylaw-2026-q3",
    "title": "Bylaw amendment: member-initiated vote procedure",
    "description": "...",
    "options": [
      { "id": "yes", "label": "Yes — adopt the new procedure" },
      { "id": "no", "label": "No — keep the existing procedure" },
      { "id": "abstain", "label": "Abstain" }
    ],
    "quorum": 0.5,
    "eligibleVoters": 47,
    "closesAt": "2026-08-15T23:59:59-04:00"
  },
  "tally": {
    "yes": 12,
    "no": 4,
    "abstain": 1,
    "total": 17,
    "quorumReached": false,
    "quorumPercent": 0.362
  },
  "receipts": [
    {
      "receiptHash": "0xabc123...",
      "status": "cast"
    }
  ],
  "receiptsSealed": 0
}
```

**The public receipt is `{ receiptHash, status }` — no `ts`.** A published
timestamp lets an observer who recorded the tally timeline re-link a receipt
to the increment it caused; the voter keeps the exact `ts` in their own tuple
(§5.4), and presence-in-log is what verifies. `status` is `"cast"` (or
`"superseded"` after a policy-permitted re-vote, §5.4). While the ballot is
open the `receipts` array is **sealed** — the state getter returns `[]` and
reports the count as `receiptsSealed` — so no live receipt can coincide with
the tally increment it produced. Once the ballot closes, receipts publish
**ordered by hash, not insertion**, so log position cannot re-link to the
order the live tally moved in (§5.5).

**The public state NEVER contains `voterId` or `choice`** — not in receipts,
not anywhere. The state payload is what every rendering client pulls; a
receipts array carrying `{voterId, choice}` pairs would publish how every
resident voted (see §5.5). Per-voter data lives only with the state
authority (the service that owns `data-state-source`), which needs it for
one-vote-per-voter enforcement.

The full state is signed via CHIT every time a vote is cast (when the tenant
has a registered signing card — see §5.4). The signature chain over state
mutations is the audit trail. Note the two chains are distinct: `prevHash`
(§4.2) chains **state payloads**; `receiptHash` commits **one vote** and
appears once in the receipts log.

### 5.3 ARIA

- Outer: `role="region"` with `aria-label="Ballot: <title>"`
- Each option: `<input type="radio">` (native) with `<label>` (semantic)
- Submit button: `<button type="submit">`
- Quorum bar: `role="progressbar"` with `aria-valuenow`, `aria-valuemin`, `aria-valuemax`
- Live tally: `aria-live="polite"`
- After vote cast: focus moves to the receipt section (a11y flow)

### 5.4 Receipt model (rev 2 — nonce commitment)

Each vote generates a **blind commitment**:

```
nonce       = 128 bits from crypto.getRandomValues, hex-encoded,
              generated client-side and shown ONLY to the voter
preimage    = netstring(ballotId) ‖ netstring(voterId) ‖ netstring(choice)
                                  ‖ netstring(ts) ‖ netstring(nonce)
              where netstring(f) = String(f).length + ":" + f
receiptHash = sha256(preimage)
```

Rules:

- The **voter keeps** `(choice, ts, nonce)` — that tuple is their receipt.
  The UI presents it once, prominently, with "save this" framing.
- **Only `receiptHash` is published** to the receipts log / CHIT trail — **no
  `ts`** (§5.2 explains why a published timestamp re-links a receipt to its
  tally increment). Without the nonce, the hash cannot be inverted — even
  though there are only 3 choices, the 128-bit nonce makes enumeration
  infeasible. (The rev-1 scheme, `sha256(ballotId + voterId + choice + ts)`
  with all four inputs public or guessable, was brute-forceable per voter in
  milliseconds.)
- The preimage is **length-prefixed (netstring-style)**, not delimiter-joined,
  so distinct input tuples can never produce the same string. Plain
  `|`-joining does NOT give that guarantee: a `|` inside a field shifts the
  boundaries, so `("apt-4B|yes","no")` and `("apt-4B","yes|no")` collide.
  Prefixing each field with its length makes the parse unambiguous for ANY
  field content, so no caller has to remember to sanitize. (Rev 2 specified a
  `|`-delimited preimage with the injectivity claim above — that claim was
  false; the shipped code uses netstrings.)
- **Verification**: a resident recomputes the hash from their kept tuple and
  finds it in the public log — proof their vote was counted, revealing
  nothing to anyone else. Losing the nonce loses individual verifiability
  (the vote still counts); this is the accepted trade for secrecy.
- **One vote per voter**: the state authority rejects a second vote for a
  `voterId` unless the tenant's re-vote policy allows supersede
  (last-write-wins); a superseded receipt stays in the log with
  `status: "superseded"` so the log is append-only.
- **Signing, honestly named**: `receiptHash` is a *commitment*, not a
  signature. The CHIT **signature** is applied by the state authority over
  each appended state mutation, verifiable against the **tenant's CHIT
  signing card** (registered via `chit_security` / `make -C pmoves
  sign-trail` infrastructure). Until a tenant signing card is registered,
  the ballot runs in **demo mode** and the UI MUST label receipts
  "recorded (unsigned demo mode)" — never "CHIT-signed".

This preserves the "public, auditable" promise — the trail IS the record —
without publishing anyone's vote.

### 5.5 Ballot secrecy & coercion resistance

A cooperative bylaw or officer-election ballot carries real coercion stakes:
a voter may face pressure from neighbors or from people with authority over
their housing. **Public auditability and secret ballot are in tension**
(verifiability / secrecy / simplicity — pick two); v0.2 explicitly picks
verifiability + secrecy via the nonce commitment and accepts the cost
("don't lose your receipt").

Hard rules:

1. The public state / trail never carries `(voterId, choice)` in any form,
   including recomputable form (rev-1's hash was recomputable — that
   counts as publishing the vote).
2. **No `ts` on the public receipt.** A published timestamp re-links a
   receipt to the tally increment it caused; the voter alone keeps the exact
   `ts` in their tuple.
3. **Seal receipts until close.** While the ballot is open the state getter
   returns an empty `receipts` array (surfacing only a `receiptsSealed`
   count), so no live receipt can coincide with the increment it produced.
4. **Publish ordered by hash, not insertion.** After close, log position
   must not re-link to the order the live tally moved in.
5. Turnout visibility (who has voted, not how) is a **tenant policy
   decision**, default OFF; if enabled it must be labeled on the ballot UI
   before the resident votes.
6. The state authority holds per-voter data and is the trust anchor for
   dedup. v0.3's identity/attestation work (§7.1) should revisit whether
   even the authority can be blinded (e.g. token-based eligibility).
7. On a **non-secure context** (plain `http://`, e.g. a co-op LAN at
   `http://192.168.x.x`), `crypto.subtle` is absent and only a
   non-cryptographic checksum is available — a colliding receipt is findable
   in under a second, so the commitment binds to nothing. The ballot MUST
   **refuse to cast** (fire `ballot-unavailable`) rather than commit a vote
   under a checksum, because a post-cast disclosure warns the voter only
   *after* the vote is irrevocable. A tenant may opt into a checksum-only
   **demo** with the explicit `allow-insecure-demo-hash` attribute, which
   renders a "not a real receipt" notice before voting — a checksum is not a
   receipt.

## 6. v0.2 sample: Fordham Hill governance page

```json
{
  "tenant": {
    "id": "fordham-hill",
    "name": "Fordham Hill Co-op",
    "theme": "armor"
  },
  "components": [
    {
      "component": "pm-quote-block",
      "props": {
        "quote": "Residents deserve a vote they can verify. So we built one.",
        "attribution": "Resident co-organizer"
      }
    },
    {
      "component": "pm-project-card",
      "props": {
        "title": "Bylaw 2026-Q3: member-initiated vote procedure",
        "description": "Adopt a transparent, auditable procedure for member-initiated votes.",
        "status": "live",
        "tags": ["governance", "bylaw"]
      }
    },
    {
      "component": "pm-ballot",
      "props": {
        "ballotId": "bylaw-2026-q3",
        "dataStateSource": "fordham:ballots.bylaw-2026-q3"
      }
    },
    {
      "component": "pm-metric-tile",
      "props": {
        "label": "Eligible voters",
        "dataDerive": "pm-ballot[primary]:ballot.eligibleVoters"
      }
    },
    {
      "component": "pm-image",
      "props": {
        "src": "...",
        "alt": "Fordham Hill community gathering",
        "caption": "Co-op residents meeting, July 2026"
      }
    }
  ]
}
```

Each Fordham resident opens the page, sees the proposal, casts a vote, gets a receipt. The trail is signed, public, and auditable. No corporate platform in the middle.

> Sample notes: the `data-derive` tile binds `eligibleVoters` — a static
> value, which is what one-shot derive is for. Live quorum progress comes
> from the ballot's own `role="progressbar"` (§5.3); deriving it into a
> tile would freeze at mount (§4.1 freeze trap — rev 1 of this sample did
> exactly that).

## 7. Open questions (parking lot for v0.3)

1. **Identity verification** — v0.2 takes `voterId` from the auth layer. v0.3 needs to spec the auth layer itself (likely a CHIT-signed attestation per resident).
2. **Multi-ballot pages** — co-ops often run multiple parallel votes. v0.3 will need a `<pm-ballot-board>` component that aggregates multiple `<pm-ballot>` instances.
3. **Delegation** — can a resident delegate their vote? v0.2 forbids; v0.3 may add `delegate-to` field.
4. **Ranked choice / approval voting** — currently FPTP. v0.3 may add option schema extensions.
5. **Two-factor audit** — for high-assurance decisions, we may need co-signing by 2+ residents.
6. **Recurring ballots** — quarterly bylaw votes. v0.3 may add a `ballot-template` mechanism.

## 8. Signoff

- **Architect**: Mavis-5090 (this lane)
- **Locked by**: DARKXSIDE — Fordham governance is the immediate use case
- **Reviewers needed**: ~~5090-CLAUDE (DL continuity)~~ ✓ reviewed 2026-07-16
  (rev 2: receipt model → nonce commitment, §5.5 secrecy rules, freeze-trap
  fixes — see `pmoves/docs/logs/pr_trim_2133_LEARNINGS.md`),
  ~~B850-CLAUDE (CHIT pattern)~~ ✓ reviewed 2026-07-17 and authored the rev-3
  reconciliation below, at least one Fordham resident for legitimacy review
- **Pattern credit**: rooms-on-a-stage eureka from the Mavis/Opus lineage

`ACK::Mavis-5090::A2UI-V0.2-BALLOT-SPEC-DRAFT::2026-07-15`

> **Rev-3 reconciliation (B850-CLAUDE, 2026-07-17)** — proposed amendment,
> pending Mavis-5090 ACK. §5.2/§5.4/§5.5 were rewritten to match the shipped
> `<pm-ballot>` implementation (PR #2153): netstring preimage in place of the
> `|`-delimited form (whose injectivity claim was false), no `ts` on the
> public receipt, seal-until-close + hash-ordering of the receipts log, and
> refuse-to-cast on non-secure contexts instead of a post-cast downgrade.
> The code's own `state`-getter comment flagged these as deviations "raised
> as a spec amendment on PR #2133" — this rev is that amendment.
>
> `PROPOSE::B850-CLAUDE::A2UI-V0.2-BALLOT-SPEC-REV3-RECONCILE::2026-07-17`
