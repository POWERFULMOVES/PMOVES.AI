# Mode-A Tally Ingestion — Design Spec (governance replacement, stage 4a)

**Date:** 2026-07-18
**Status:** DRAFT — approved for implementation (stage 4a of the #5 governance-replacement arc)
**Scope:** the governance-side seam that ingests **aggregate secret-ballot counts** and produces a signable `TallyResult` — counts in, signed tally out — WITHOUT the per-voter `Map<voter → support>`. The cryptographic proof that counts correspond to the sealed receipt log (blind-sig / token / homomorphic), and the cross-repo wiring to the live `pm-ballot` component, are later stages (4b and the branch-coexistence prerequisite), out of scope here.
**Where:** submodule `PMOVES-ToKenism-Multi/integrations/contracts/`.
**Builds on:** stage 1 `EqualWeightGovernorModel`, stage 2 `tally-signer-ed25519.ts` (`tallyPreimage` + `Ed25519MultisigSigner` + `verifyTallyAttestation`), stage 3 `MemberRegistryModel` (supplies the roll). Honors `pmoves/docs/pilots/fordham-hill/08-voter-identity-key-custody.md` (Mode A/B **never mix**; eligibility decoupled from content) and [[feedback_inform_dont_decide]] (surface where the chips land per choice; power in the group's hands).

## Problem

The stage-1 governor's only vote intake is `castVote(proposalId, voter, support)`, which stores `Map<voterId → support>` — it enforces eligibility and one-vote-per-member **by knowing who voted which way**. That is exactly the voter↔choice link Mode A forbids (a stored link is a coercion vector; `08` §5b). A secret ballot cannot be routed through that path.

Stage 4a adds a Mode-A-safe intake: `ingestSecretTally(proposalId, counts)` accepts **aggregate counts** (from a ballot tallier), sources eligibility from the registry roll we already hold, and produces a `TallyResult` the stage-2 committee signer can sign — with no per-voter link anywhere. It also makes the `08` "never mix modes" invariant a **structural property** of the model, exposes the abstention rule as a **swept knob** (contexts choose; the sweep shows the contrast), and **binds the ballot source** into the signature.

## Decisions (from brainstorming, approved)

1. **Lock-on-first-use mode, on the existing model (not a separate Mode-A governor).** The tally/quorum/pass math and the `finalize()`→signer plumbing are identical for both modes; duplicating a whole model to change only the *intake* would drift. Instead a per-proposal `mode` locks on first use and each intake refuses the other's proposals — the "never mix" invariant becomes un-bypassable, the same way stage 2's k-of-n gate is.
2. **`eligibleCount` from the roll, never from the ballot.** Eligibility is the registry's truth (`this.roll.size`); the ballot only reports how people voted. Keeping them on separate sides is the Mode-A point.
3. **`abstentionPolicy` is a knob (default `'quorum'`), not a hardcode.** Different bylaws want different handling; the alternative stays open and the scenario helper shows the downstream contrast. Third category (`'present-not-voting'`) deferred (YAGNI).
4. **Integrity guards are hard invariants, not knobs.** Safe-integer, non-negative counts; `voterCount ≤ eligibleCount`. These catch a malformed or stuffed tally regardless of policy — not the group's to relax.
5. **Bind the ballot source now.** An optional `ballotRef` (id + receipt-log digest) is carried in `TallyResult` and bound into the signature via a backward-compatible preimage extension. This ties a signed tally to *which ballot's evidence* it claims to summarize (provenance); it does NOT prove the counts match the receipts (that is 4b).

## Components

### `equalweight-governor-model.ts` (extend)

**Config** — add the knob:
```ts
interface EqualWeightGovernorConfig {
  // ...existing...
  abstentionPolicy: 'quorum' | 'excluded';   // default 'quorum'
}
```

**`TallyResult`** — add optional provenance:
```ts
interface BallotRef {
  ballotId: string;
  receiptLogDigest: string;   // caller-supplied hash of the sorted sealed receiptHash list
}
interface TallyResult {
  // ...existing...
  ballotRef?: BallotRef;      // present only for ingested (secret) tallies
}
```

**`Proposal`** — add the lock:
```ts
interface Proposal {
  // ...existing: id, title, closesAtWeek, votes...
  mode?: 'named' | 'secret';   // set on first intake; locks the proposal to one path
  ingestedTally?: TallyResult; // for secret proposals: the precomputed result tally() returns
}
```

**Mode guard:**
- `castVote(...)`: if `proposal.mode === 'secret'` → throw; else set `proposal.mode = 'named'` (idempotent), proceed as today.
- `ingestSecretTally(...)`: if `proposal.mode === 'named'` → throw; else set `proposal.mode = 'secret'`.

**`ingestSecretTally(proposalId, counts)`:**
```ts
interface SecretTallyCounts {
  votesFor: number;
  votesAgainst: number;
  abstentions: number;
  ballotRef?: BallotRef;
}
// Guards (hard): proposal exists; mode not 'named'; each of votesFor/votesAgainst/
//   abstentions is Number.isSafeInteger and >= 0; voterCount <= eligibleCount.
// Derivation:
//   eligibleCount = this.roll.size
//   voterCount    = votesFor + votesAgainst + abstentions
//   turnout       = abstentionPolicy === 'excluded'
//                     ? (votesFor + votesAgainst) / eligibleCount
//                     : voterCount / eligibleCount          // 'quorum' (default)
//   quorumMet     = eligibleCount > 0 && turnout >= quorumPercentage
//   decided       = votesFor + votesAgainst
//   forShare      = decided > 0 ? votesFor / decided : 0
//   passed        = quorumMet && forShare >= passThreshold
// Stores proposal.ingestedTally = { proposalId, votesFor, votesAgainst, eligibleCount,
//   voterCount, turnout, quorumMet, passed, finalized: false, ballotRef }.
```

**`tally(proposalId)`** — if `proposal.mode === 'secret'`, return `proposal.ingestedTally` (do NOT recompute from the empty votes map); otherwise recompute as today. `finalize()` is unchanged — it calls `tally()` then signs, working for both modes.

### `tally-signer-ed25519.ts` (extend `tallyPreimage`)

Append a domain-tagged suffix **only when `tally.ballotRef` is present**:
```
// after the existing fields (…, quorumMet, passed):
if (tally.ballotRef) {
  fields.push('ballotref.v1', tally.ballotRef.ballotId, tally.ballotRef.receiptLogDigest);
}
```
Backward-compatible: a tally without `ballotRef` yields byte-identical preimage to today (all stage-2 signatures/tests still hold). A bound tally gets three extra netstring fields; because the signature covers the full byte string, a `ballotRef` cannot be stripped from a signed tally and still verify. The `'ballotref.v1'` sentinel keeps the suffix self-describing and unambiguous.

### Contrast helper (small — the "where the chips land" surface)

A pure function (co-located with the governor or in a `governance-sweep.ts`) that, given a set of counts + a config, returns the outcome under **both** abstention policies:
```ts
// sweepAbstentionPolicy(counts, cfg) -> { quorum: {turnout, quorumMet, passed},
//                                         excluded: {turnout, quorumMet, passed} }
```
Lets a caller see, for the same ballot, how the quorum/pass outcome diverges between policies — the informing surface, not a decision.

## Testing (TDD, red-first)

Test file: `integrations/contracts/__tests__/mode-a-tally-ingestion.test.ts`.

1. **Mode lock, both directions** — `castVote` then `ingestSecretTally` on the same proposal throws; `ingestSecretTally` then `castVote` throws.
2. **Safe-integer / non-negative guards** — `ingestSecretTally` rejects `NaN`, `-1`, `1.5` in any of the three counts.
3. **`voterCount ≤ eligibleCount`** — a roll of 3 with `votesFor+votesAgainst+abstentions = 4` throws.
4. **`eligibleCount` from the roll** — with a 5-member roll, an ingest of `{for:3, against:1, abstain:0}` yields `eligibleCount = 5`, `voterCount = 4`, `turnout = 0.8`.
5. **Abstention knob contrast (the outcome flips)** — 30 for / 10 against / 15 abstain on 100 eligible at 50% quorum: `'quorum'` → `turnout 0.55, quorumMet true`; `'excluded'` → `turnout 0.40, quorumMet false`. Same ballot, opposite quorum outcome purely from the policy choice — the genuine divergence the sweep surfaces. (Also assert the equal case: 40/10/15 gives `'quorum' 0.65` vs `'excluded' 0.50`, both meeting a 0.5 quorum, to show the policies agree when `for+against` alone clears the bar.)
6. **Decision excludes abstentions** — `passed` uses `for/(for+against)`; an all-abstention-heavy tally with `for > against` passes/fails on the for/against split, not the abstentions.
7. **`ballotRef` binds** — sign an ingested tally with a `ballotRef`, verify accepts; mutate `ballotRef.receiptLogDigest` before verify → `valid:false`.
8. **No-`ballotRef` regression** — `tallyPreimage` of a tally without `ballotRef` is byte-identical to the pre-4a encoding (guards backward-compatibility; e.g. compare against a hard-coded expected buffer or a Mode-B tally).
9. **Integration** — `ingestSecretTally` → `finalize(proposalId, approvers)` with `Ed25519MultisigSigner` → `verifyTallyAttestation` accepts, and the attestation's signed bytes include the `ballotRef`.
10. **Contrast helper** — `sweepAbstentionPolicy` returns both outcomes for the knife-edge counts and they diverge.

## Out of scope (later stages)

- **4b:** the cryptographic proof that ingested counts correspond to the sealed `receiptHash` log without linking voter↔choice (blind signatures / single-use eligibility tokens / homomorphic-or-mixnet tally — the group's choice, surfaced with tradeoffs).
- **Cross-repo `pm-ballot` wiring** — needs the branch-coexistence prerequisite (pm-ballot lives on `feat/a2ui-ballot-nonce-rev2`; governance in this submodule).
- **`'present-not-voting'`** third abstention category (YAGNI until a caller needs it).
- **Stage 5 paper parity** — rides on this ingestion path (source-agnostic counts), later.

## Success criteria

- `ingestSecretTally` compiles; all TDD tests pass; full submodule suite stays green (including the 455 stage-2 tests — the preimage extension is backward-compatible).
- The mode lock provably prevents mixing named votes and ingested counts on one proposal (test 1).
- Eligibility comes from the roll and `voterCount ≤ eligibleCount` is enforced (tests 3, 4).
- The abstention knob changes the quorum outcome measurably and the contrast helper surfaces it (tests 5, 10).
- A signed ingested tally binds its `ballotRef`, and stripping/tampering it fails verification (test 7); no-`ballotRef` tallies are unchanged (test 8).
- `finalize()` → `verifyTallyAttestation` works end-to-end for an ingested tally (test 9).
