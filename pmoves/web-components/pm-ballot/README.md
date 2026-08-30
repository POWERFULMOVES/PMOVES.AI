# `<pm-ballot>` — v0.2

Co-op governance ballot. Native radio options, submit, live tally, quorum progressbar, and nonce-commitment receipts. Implements [A2UI v0.2 ballot spec §5](../../contracts/a2ui-v0.2-ballot.md#5-pm-ballot--the-v02-reference-component).

> **Status**: SHIPPED as v0.2 DRAFT (Fordham bylaw-2026-q3 use case is the legitimacy test).
> **v0.2 contract extensions used**: `data-state-source` (state), `pm-event` slots (event emission).

## Usage

```html
<pm-toast id="t" position="bottom-right"></pm-toast>

<pm-ballot
  id="b"
  ballot-id="bylaw-2026-q3"
  title="Bylaw amendment: recall procedure"
  description="Adopt a transparent recall procedure so residents can hold the board accountable."
  options='[{"id":"yes","label":"Yes"},{"id":"no","label":"No"},{"id":"abstain","label":"Abstain"}]'
  eligible-voters="47"
  quorum="0.5"
  closes-at="2026-08-15T23:59:59-04:00"
  voter-id="unit-12a-bob-m"
  data-state-source="fordham:ballots.bylaw-2026-q3"
  on-vote-cast="t:show"
></pm-ballot>
```

## Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `ballot-id` | string | ✓ | Unique ballot identifier. Used in receipt hash. |
| `title` | string | ✓ | Ballot title (displayed as `<h3>`). |
| `description` | string |   | Plain-text proposal description. |
| `options` | JSON array of `{id, label}` | ✓ | Voter options. |
| `eligible-voters` | number | ✓ | Roster size (for quorum math). |
| `quorum` | number (0-1) | ✓ | Quorum threshold. Default 0.5. |
| `closes-at` | ISO 8601 |   | When the ballot closes. Past = read-only. |
| `voter-id` | string | (auth) | Current voter's ID. Set by the auth layer. |
| `data-state-source` | string |   | NATS subject or HTTP URL for live tally + receipt sync. |
| `on-vote-cast` | event wire |   | `pm-event` slot (§4.3). Format: `"<id>:<method>"`. |
| `allow-insecure-demo-hash` | boolean attribute |   | Demo-only opt-in to the non-cryptographic fallback when `crypto.subtle` is unavailable. Never use for a real ballot. |

## Methods

| Method | Description |
|--------|-------------|
| `castVote(optionId, voterIdOverride?)` | Cast a vote, generate receipt, fire `vote-cast` event. |
| `state` (getter) | The current `{tally, receipts}` state. |
| `tally` (getter) | Convenience: just the tally. |
| `myChoice` (getter) | The current voter's choice + receipt (or null). |
| `quorumPercent()` | Current / eligible as a 0-1 fraction. |
| `close()` | Explicitly close the ballot and publish the hash-ordered public receipt log. |

## Events

| Event | When | Detail |
|-------|------|--------|
| `vote-cast` | After `castVote()` succeeds | `{ receipt: { receiptHash, status } }` |
| `quorum-reached` | When `quorumPercent >= quorum` | `{ quorum }` |
| `ballot-closed` | When `castVote()` is called after `closes-at` | `{ reason }` |
| `ballot-unavailable` | When a real cryptographic hash is unavailable | `{ reason: "insecure-context" }` |

All events are `composed: true, bubbles: true` so they cross shadow DOM boundaries. The page-level renderer wires them to other components via `on-<event>` attributes.

## Receipt model

Every vote generates a private voter-held receipt:

```json
{
  "voterId": "unit-12a-bob-m",
  "choice": "yes",
  "ts": "2026-07-15T10:00:00.000Z",
  "nonce": "128-bit-random-hex",
  "receiptHash": "0x9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "algo": "sha256"
}
```

Only `{ "receiptHash": "...", "status": "cast" }` enters public state. Public receipts stay sealed until close and are then sorted by hash; `voterId`, `choice`, `ts`, and `nonce` never enter the public receipt log or the `vote-cast` event.

The commitment is SHA-256 over an unambiguous length-prefixed encoding of `ballotId`, `voterId`, `choice`, `ts`, and the 128-bit nonce. A resident verifies inclusion by recomputing that commitment from the private tuple and finding the hash in the closed public log. CHIT signs the authority's state mutation chain separately; the component does not manufacture a placeholder signature.

## ARIA

- Outer: `role="region"` with `aria-label="Ballot: <title>"`
- Options: `role="radiogroup"` on the form, native `<input type="radio">` per option
- Quorum: `role="progressbar"` with `aria-valuenow`, `aria-valuemin`, `aria-valuemax`
- Submit button: native `<button type="button">`
- Receipt: `role="status"` (announced when user has voted)
- After cast: submit button changes to "✓ Vote cast" + disabled; options become disabled radios; receipt section becomes visible

## Theming

Reads all 15 tokens from [A2UI v0.1 §6](../../contracts/a2ui-v0.1.md#6-persona-theming-css-custom-properties). Uses `--pm-accent` for selected option + quorum fill; `--pm-accent-soft` for focus rings + receipt header.

## Anti-patterns avoided

- ✅ No framework
- ✅ No inline styles
- ✅ No global listeners
- ✅ XSS-safe (all prop values escaped before insertion)
- ✅ No localStorage / sessionStorage reads
- ✅ Lifecycle cleanup in `disconnectedCallback`
- ✅ Chained pull not used (single `data-state-source` only; the renderer handles event wiring)

## Demo

```bash
python -m http.server 8765 --directory pmoves/web-components/pm-ballot
# open http://localhost:8765/demo.html
```

The demo is a complete Fordham-style bylaw vote:
- 3 options (yes / no / abstain)
- 47 eligible voters, 50% quorum
- Auto-fires `on-vote-cast` to a `<pm-toast>` (the renderer-style event wire is done inline in the demo since the production renderer wires it at page level)
- After cast, the receipt section appears with a real SHA-256 hash (or FNV-1a fallback over HTTP)
