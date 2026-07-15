# A2UI v0.2 — `<pm-ballot>` extension + stateful surfaces

> **Status**: DRAFT (sketch) — `WEBSITE_AS_AGENT_CANVAS` lane
> **Date**: 2026-07-15
> **Author**: Mavis-5090
> **Target use case**: Fordham Hill Co-op governance — quorum, bylaw change votes, AG contact, forensic accounting request
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
| **CHIT-signed payloads** (every state change is a signed trail entry) | n/a | ✓ automatic when `data-state-source` is set |

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
- v0.2 supports: `on-vote-cast`, `on-quorum-reached`, `on-ballot-closed` (extensible)
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
| `closed-at` | ISO 8601 |   | When set, the ballot is read-only after this time. |

### 5.2 State shape (the payload at `data-state-source`)

```json
{
  "ballot": {
    "id": "bylaw-2026-q3",
    "title": "Bylaw amendment: recall procedure",
    "description": "...",
    "options": [
      { "id": "yes", "label": "Yes — adopt the new recall procedure" },
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
      "voterId": "unit-12a-bob-m",
      "choice": "yes",
      "ts": "2026-07-15T10:00:00Z",
      "receiptHash": "0xabc123...",
      "signature": "..."
    }
  ]
}
```

The full state is signed via CHIT every time a vote is cast. The signature chain is the audit trail.

### 5.3 ARIA

- Outer: `role="region"` with `aria-label="Ballot: <title>"`
- Each option: `<input type="radio">` (native) with `<label>` (semantic)
- Submit button: `<button type="submit">`
- Quorum bar: `role="progressbar"` with `aria-valuenow`, `aria-valuemin`, `aria-valuemax`
- Live tally: `aria-live="polite"`
- After vote cast: focus moves to the receipt section (a11y flow)

### 5.4 Receipt model

Each vote generates a `receiptHash = sha256(ballotId + voterId + choice + ts)`. The receipt is shown to the voter immediately AND published to the CHIT trail. Any resident can verify their vote was counted by:
1. Computing the expected hash from their inputs
2. Looking up the receipt in the public CHIT trail
3. Verifying the signature against the tenant's signing card

This is the "public, auditable" promise the PMOVES platform makes. The trail IS the record.

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
        "quote": "The board sat on the PMOVES proposal. We're using it anyway — the right way.",
        "attribution": "Resident co-organizer"
      }
    },
    {
      "component": "pm-project-card",
      "props": {
        "title": "Bylaw 2026-Q3: recall procedure",
        "description": "Adopt a transparent recall procedure so residents can hold the board accountable.",
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
        "label": "Quorum progress",
        "dataDerive": "pm-ballot[primary]:tally.quorumPercent",
        "format": "percent"
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

## 7. Open questions (parking lot for v0.3)

1. **Identity verification** — v0.2 takes `voterId` from the auth layer. v0.3 needs to spec the auth layer itself (likely a CHIT-signed attestation per resident).
2. **Multi-ballot pages** — co-ops often run multiple parallel votes. v0.3 will need a `<pm-ballot-board>` component that aggregates multiple `<pm-ballot>` instances.
3. **Delegation** — can a resident delegate their vote? v0.2 forbids; v0.3 may add `delegate-to` field.
4. **Ranked choice / approval voting** — currently FPTP. v0.3 may add option schema extensions.
5. **Two-factor audit** — for forensic accounting requests, we may need co-signing by 2+ residents.
6. **Recurring ballots** — quarterly bylaw votes. v0.3 may add a `ballot-template` mechanism.

## 8. Signoff

- **Architect**: Mavis-5090 (this lane)
- **Locked by**: DARKXSIDE — Fordham governance is the immediate use case
- **Reviewers needed**: 5090-CLAUDE (DL continuity), B850-CLAUDE (CHIT pattern), at least one Fordham resident for legitimacy review
- **Pattern credit**: rooms-on-a-stage eureka from the Mavis/Opus lineage

`ACK::Mavis-5090::A2UI-V0.2-BALLOT-SPEC-DRAFT::2026-07-15`
