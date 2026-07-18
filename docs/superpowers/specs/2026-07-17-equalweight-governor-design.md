# EqualWeightGovernor — Design Spec (governance replacement, stage 1)

**Date:** 2026-07-17
**Status:** DRAFT — approved for implementation (stage 1 of the #5 governance-replacement arc)
**Scope:** the tractable, sim/bridge first increment ONLY. Stages 2–5 (real threshold crypto, voter-card credentials, secret-ballot integration, paper parity) are later, heavier, counsel-gated lanes and are out of scope here.
**Where:** submodule `PMOVES-ToKenism-Multi/integrations/contracts/` (alongside the other economic/governance models).
**Boundaries:** honors `pmoves/docs/pilots/fordham-hill/08-voter-identity-key-custody.md` and `pmoves/docs/CATACLYSM_CROSSLINKS.md` (open decision #5). DRAFT — counsel-gated before anything binding/member-facing.

## Problem

The built `CoopGovernorModel` is plutocratic: votes are quadratic (`rawVotes²`) and weighted by `vault.getVotingPower` (stake × lock), quorum is a percentage of *voting power*. The crystallization flagged it "MUST NOT ship for a binding vote." `08` requires the opposite: **equal-weight one-member-one-vote, quorum as a percentage of the eligible member roll, and a tally that no single party (the operator) can forge** — committee M-of-N threshold-signing.

This spec delivers a **drop-in equal-weight governor** as a sim/research model with a **production-shaped interface** (a "bridge"): the k-of-n anti-forgery gate is real and tested; the actual threshold-signature crypto is stubbed behind a pluggable interface for a later stage. The plutocratic `CoopGovernor` stays in place so the sweep can show equal-weight vs stake-weighted as a measured contrast.

## Decisions (from brainstorming)

1. **Interface-compatible bridge** — sim model now; interface matches the future Tally service so it upgrades without a rewrite.
2. **`votingBasis` is a knob**: `member` (default) | `unit` | `share`. `share` is included NOT as an endorsement but so the sweep can show the plutocratic outcome next to the equal one (demonstrating *why* stake-voting is rejected).
3. **Eligible roll is passed in explicitly** — membership/residency, **decoupled from tokens/contribution** (deriving it from holdings would re-couple governance to the token layer and break `08`'s Mode A/B unlinkability invariant). In production the same interface is satisfied by committee-issued voter-card verification.
4. **Model the M-of-N gate, stub the crypto** — the tally finalizes only with k-of-n committee approvals (no single party finalizes alone); the anti-forgery *semantics* are tested; the Ed25519/FROST signature bytes are stubbed behind a `TallySigner` interface.

## Components (one file: `equalweight-governor-model.ts`)

- **`EqualWeightGovernorModel`** — the cohesive governor (mirrors `CoopGovernorModel`'s one-class shape).
- **`TallySigner`** interface + **`MockThresholdSigner`** — the injected M-of-N seam.
- Types: `EligibleMember`, `GovernanceProposal`, `TallyResult`, `TallyAttestation`, `EqualWeightGovernorConfig`, `VotingBasis`.

### Types

```ts
type VotingBasis = 'member' | 'unit' | 'share';

interface EligibleMember {
  id: string;
  units?: number;   // used when votingBasis === 'unit'  (default 1)
  shares?: number;  // used when votingBasis === 'share' (default 1) — plutocratic contrast
}

interface EqualWeightGovernorConfig {
  votingBasis: VotingBasis;      // default 'member'
  quorumPercentage: number;      // fraction of the eligible ROLL that must vote (default 0.5)
  passThreshold: number;         // weightedFor / (for+against) needed to pass (default 0.5 → simple majority)
  committeeSize: number;         // n (default 3)
  committeeThreshold: number;    // k (default 2; must be <= committeeSize; k >= 2 makes "no single party" hold by default)
}

interface TallyResult {
  proposalId: string;
  votesFor: number;              // weighted by basis
  votesAgainst: number;          // weighted by basis
  eligibleCount: number;         // size of the roll
  voterCount: number;            // distinct members who voted
  turnout: number;               // voterCount / eligibleCount
  quorumMet: boolean;
  passed: boolean;               // quorumMet && weightedFor share >= passThreshold
  finalized: boolean;            // true only after a valid M-of-N finalize()
  attestation?: TallyAttestation;
}

interface TallyAttestation {
  algo: string;                  // 'stub-mofn' in the sim; 'ed25519-frost' etc. later
  approvers: string[];           // the committee members who approved (>= k)
  signature: string;             // stubbed in the sim
}

interface TallySigner {
  // Produces an attestation ONLY if approvers satisfy the k-of-n policy; throws otherwise.
  sign(tally: TallyResult, approvers: string[], committee: string[], threshold: number): TallyAttestation;
}
```

### API / data flow

```
setRoll(members: EligibleMember[])          // the eligible membership (decoupled from tokens)
setCommittee(memberIds: string[])           // the election committee (distinct from the roll)
createProposal(id, title, closesAtWeek?)     // binary for/against
castVote(proposalId, voter, support: boolean)
  - rejects a voter not on the roll
  - one vote per member (last-write-wins is out of scope; a second vote throws)
tally(proposalId): TallyResult               // pure read of roll + votes; finalized:false
finalize(proposalId, approvers: string[]): TallyResult
  - the ONLY place a result becomes official
  - delegates the k-of-n check + attestation to the injected TallySigner
```

`castVote` and `tally` are pure reads over the roll and recorded votes. `finalize` is the sole path to an official, attested result.

## Voting basis + quorum semantics

- **Weight per voter**: `member` → 1; `unit` → `member.units ?? 1`; `share` → `member.shares ?? 1`.
- **Quorum (roll-percentage, basis-independent)**: `turnout = voterCount / eligibleCount`; `quorumMet = turnout >= quorumPercentage`. This is `08`'s roll-% quorum — **never** a percentage of stake/voting-power.
- **Passed**: `quorumMet && (votesFor / (votesFor + votesAgainst)) >= passThreshold`. Default `passThreshold 0.5` = simple majority. (If `for+against === 0`, not passed.)

## The M-of-N gate (the anti-forgery property)

`finalize(proposalId, approvers)` calls `signer.sign(tally, approvers, committee, committeeThreshold)`. `MockThresholdSigner`:
- throws if any approver is not in the committee;
- throws if `approvers.length < committeeThreshold` (deduplicated);
- otherwise returns `{ algo: 'stub-mofn', approvers, signature: 'stub:' + proposalId }`.

With `committeeThreshold >= 2`, **no single party — including the operator — can finalize a tally alone.** That is the property `08` demands, and it is exercised by tests, not merely asserted. Real threshold crypto later implements `TallySigner` with the same signature; nothing above `finalize` changes.

## Testing (TDD, red-first)

1. **basis contrast** — roll = `[{id:'A'}, {id:'WHALE', shares:1000}]`, both vote opposite ways. Under `member` basis → tie (not passed); under `share` basis → WHALE wins. Demonstrates *why* stake-voting is rejected.
2. **non-roll voter** — `castVote` by an id not on the roll → throws.
3. **one vote per member** — a second `castVote` by the same member → throws.
4. **quorum** — turnout below `quorumPercentage` → `quorumMet false`, `passed false`, even with unanimous "for".
5. **M-of-N gate (headline)** — `finalize` with `k-1` approvers → throws; with `k` valid committee approvers → `finalized true` + attestation. A single operator (1 approver, k=2) cannot finalize.
6. **non-committee approver** — `finalize` with an approver not in the committee → throws.

No changes to existing models; the plutocratic `CoopGovernor` is left intact as the sweep contrast.

## Out of scope (later arc stages)

2. Real `TallySigner` — Ed25519/FROST threshold signature (same interface; counsel-gated crypto).
3. `voter-card.v1` + MemberRegistry — the roll becomes committee-issued credentials.
4. Secret-ballot integration — A2UI `pm-ballot` (#2153) receipts as the vote source; authenticate eligibility, never sign choice; Mode A/B unlinkability.
5. Paper parity — paper ballots merge into the same signed tally.

## Success criteria

- `EqualWeightGovernorModel` compiles and all TDD tests pass; full submodule suite stays green.
- The plutocratic `CoopGovernor` is untouched.
- The k-of-n gate provably rejects a single-party finalize (test 5).
- The interface is shaped so a real `TallySigner` drops in without changing the governor.
