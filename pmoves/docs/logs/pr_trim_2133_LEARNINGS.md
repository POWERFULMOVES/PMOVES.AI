# PR #2133 — Peer-Review Trim LEARNINGS

> Reviewer: 5090-CLAUDE (peer-CLAUDE angle). Style:
> `pmoves/docs/operations/REVIEW_STYLE_2026-07-15.md`.
> Fixes on this branch: ballot spec rev 2, pm-haptic behavior drift.

## Conformance delta

| Gate | Pre-trim | Post-trim |
|------|----------|-----------|
| compose python tests | 19/19 | 19/19 (spec/docs + pm-haptic only; no compose changes) |
| spec internal consistency | §6 sample contradicted §4.1 | §6 uses derive for a static value; freeze trap documented |

## missed-signal

1. **P1 — the rev-1 receipt model destroyed ballot secrecy.** `receipts[]`
   carried plaintext `(voterId, choice)` in the state payload every client
   pulls, AND the bare `sha256(ballotId+voterId+choice+ts)` was
   brute-forceable (3 choices, public ts) even without the plaintext. For a
   recall vote this is coercion-enabling. Rev 2: 128-bit voter-held nonce
   commitment, public log carries hash+ts only, §5.5 hard rules added.
   Pattern: **"public + auditable" and "secret ballot" conflict by default;
   the reconciliation (commitment schemes) must be designed, not assumed.**
2. **"CHIT-signed" was a naming overclaim** — a content hash anyone can
   recompute is a *commitment*, not a signature; the actual signer (tenant
   signing card) was undefined. Rev 2 names both honestly and mandates
   "unsigned demo mode" labeling until a signing card is registered. Same
   naming-vs-mechanism gap as the CGP "encoding ≠ encryption" lesson
   (B850, 2026-07-10) — this class of overclaim recurs; check every
   "signed/encrypted/verified" word against the mechanism.
3. **No one-vote-per-voter rule existed** — ballot-stuffable by design;
   rev 2 assigns dedup to the state authority with an explicit supersede
   policy.
4. **pm-haptic subscription leak (found while fixing, not in the original
   review):** `attributeChangedCallback` → `_subscribeIfNeeded()` created a
   new EventSource on every observed-attribute change — including `bpm`
   changes arriving *from the subscription itself*, so every live BPM
   message leaked a connection. Guard: skip when already subscribed to the
   same source. Pattern: **subscribe-on-change handlers must be idempotent
   per source.**

## fix-pattern

5. **§6 sample used one-shot `data-derive` for the live quorum bar** —
   frozen at mount per §4.1's own rules. The reference sample now derives a
   static value (`eligibleVoters`) and the freeze trap is documented in
   §4.1. When a spec ships a sample, the sample is the spec — test it
   against the rules in the same doc.
6. **README/code drift on pm-haptic** (`enabled=false` still flashed;
   `pulse()` "no-op if unsupported" vs deliberate visual fallback;
   `_renderPulseOnNextFrame` renders but never pulses). Code and README
   reconciled; method renamed `_renderOnNextFrame` with a comment on the
   user-activation gate. Undelimited hash preimage also fixed (`|`
   separators).

## wrong-suggestion

7. (none — all review findings verified against the branch)

## already-addressed

8. pm-haptic iOS/desktop degradation, `disconnectedCallback` cleanup
   (unsub, stopLoop, listener removal, `vibrate(0)`), and live
   reduced-motion handling verified correct as shipped.
9. v0.2 is genuinely additive to v0.1; `sensory` category (used by the
   registry README) is now declared in the v0.1 naming list — registry and
   spec agree.
