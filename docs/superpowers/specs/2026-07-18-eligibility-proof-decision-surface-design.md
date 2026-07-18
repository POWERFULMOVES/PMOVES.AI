# Eligibility-Proof Decision Surface — Design Spec (governance replacement, stage 4b)

**Date:** 2026-07-18
**Status:** DRAFT — approved for implementation (stage 4b of the #5 governance-replacement arc)
**Scope:** a **decision surface**, not a production voting protocol. A pluggable `EligibilityProtocol` interface + **two demonstrable models** (single-use tokens, blind signatures) + **one characterized option** (homomorphic/mix-net), and a shared **attack battery** that shows which security properties each protocol holds or breaks. Real cryptography for whichever protocol the group eventually chooses is a later hardening stage, out of scope here. Crypto is stubbed; the models are **property-honest**, not primitive-accurate.
**Where:** submodule `PMOVES-ToKenism-Multi/integrations/contracts/`.
**Builds on:** stage 4a (`ingestSecretTally` — each demonstrated protocol feeds it), stage 2 (the committee signer the tally reaches), stage 3 (the eligible roll). Honors `pmoves/docs/pilots/fordham-hill/08-voter-identity-key-custody.md` (Mode A: eligibility decoupled from choice) and `07-ballot-prior-art-and-reconciliation.md` (receipt-freeness prior art), and [[feedback_inform_dont_decide]] (the platform informs; the group + counsel choose).

## Problem

4a gave secret-ballot counts a Mode-A-safe door into the committee signer and bound *which* ballot they came from. It deliberately did **not** answer: how does a ballot prove **"N distinct *eligible* members voted, one vote each, here are the counts"** — while never linking a voter to their choice? That is the load-bearing cryptographic-protocol decision, and per the north star it is the **group's (and counsel's) choice, not the platform's**.

There is no single right answer — the candidate protocols trade off differently on coercion-resistance, trust assumptions, auditor visibility, usability, weight, and securities exposure. So 4b builds the surface that lets the group **watch each protocol behave under attack** and choose informed, rather than pre-deciding for them. Two protocols are modeled mechanically so the tradeoffs are *demonstrated*; a third is characterized so the option is *visible* without pretending to a mechanics we'd never run.

## Decisions (from brainstorming, approved)

1. **Decision surface, not a chosen protocol (option B).** A pluggable interface with each candidate as a modeled option; the group + counsel choose which to harden. Faithful to inform-don't-decide; lets the interface stabilize before any crypto is hardened.
2. **Mechanics-demonstrable, crypto stubbed (option 2).** Each modeled protocol's properties are **executable and testable** — watch a property hold or break under a simulated attack — with real primitives stubbed. Models are property-honest, not primitive-accurate.
3. **Two demonstrated + one characterized.** Single-use tokens and blind signatures are demonstrated (tractable, explainable, realistic for a co-op); homomorphic/mix-net is characterized (heaviest lift, weakest co-op/LAN fit) — scored on every axis with mechanics explicitly deferred, citing `07`. The two demonstrations **graduate understanding**; the characterized third generalizes from them.
4. **Wired to a signed tally.** Each demonstrated protocol's `tally()` feeds 4a's `ingestSecretTally` → the stage-2 signer, proven by an integration test — the surface is connected to the real seam, not a floating doc.

## The three properties every candidate must satisfy

- **Eligibility** — only members on the roll can obtain a proof/artifact.
- **Uniqueness** — one vote per member; no double-spend, no operator stuffing.
- **Unlinkability** — the proof cannot be traced to the voter's choice (and from this: coercion-resistance — no receipt proves how someone voted).

## Components (submodule `integrations/contracts/`)

### `eligibility-protocols.ts` — interface + models

```ts
export type BallotChoice = 'for' | 'against' | 'abstain';

export interface ProtocolTally {
  votesFor: number;
  votesAgainst: number;
  abstentions: number;
  distinctVoters: number;   // distinct eligible members who cast a vote
  transcript: string;       // public digest/summary (audit + future ballotRef binding)
}

// A voter-held artifact (token / unblinded credential). Opaque to the surface.
export interface Artifact { id: string; issuedTo?: string; /* issuedTo present only where the design links */ }
export interface Receipt { ref: string; revealsChoiceTo?: BallotChoice; /* present only where the design leaks */ }

export interface EligibilityProtocol {
  readonly name: string;
  setRoll(memberIds: string[]): void;
  issue(memberId: string): Artifact;                 // eligibility: throws if not on roll / already issued
  castVote(artifact: Artifact, choice: BallotChoice): Receipt;  // uniqueness: rejects a spent/forged artifact
  tally(): ProtocolTally;

  // Property probes the battery calls — each model answers HONESTLY for its design:
  issuerCanLinkArtifactToVote(): boolean;            // unlinkability (false = unlinkable)
  receiptProvesChoice(receipt: Receipt): boolean;    // coercion (true = leaks a receipt)
  canStuffWithoutArtifact(): boolean;                // stuffing (true = operator can forge)
}
```

**`SingleUseTokenProtocol`** — issue hands the member a one-time token; `setRoll` gates eligibility; spent tokens tracked → double-spend rejected (uniqueness holds). Modeled **naively-honest**: the token is a bearer secret the voter retains, and issuance records map token→member — so `receiptProvesChoice` can return `true` (a retained bearer proof leaks) and `issuerCanLinkArtifactToVote` returns `true` (issuer linkage). Demonstrates: eligibility ✓, uniqueness ✓, but **unlinkability/coercion-resistance break** under the naive design. (A comment notes an anonymous-token variant closes this — but that variant *is* essentially blind-signatures, which is the next model.)

**`BlindSignatureProtocol`** — `issue` models the committee blind-signing a *blinded* credential (issuer never sees the content); the member unblinds; `castVote` presents the unblinded credential. Spent credentials tracked → uniqueness ✓. `issuerCanLinkArtifactToVote` returns `false` (issuer never saw the unblinded credential), `receiptProvesChoice` returns `false` (no bearer proof of choice), `canStuffWithoutArtifact` false. Demonstrates: **all properties hold** — the clean contrast to naive tokens, at higher complexity.

### `eligibility-battery.ts` — attack battery + comparison

```ts
export interface PropertyResult { holds: boolean; how: string; }  // how = the attack/observation outcome
export interface PropertyReport {
  eligibility: PropertyResult;
  uniqueness: PropertyResult;
  unlinkability: PropertyResult;
  coercionResistance: PropertyResult;
  stuffingResistance: PropertyResult;
}

// Runs the IDENTICAL attack scenarios against any protocol, returns which properties survive:
//  - eligibility: issue() for a non-roll member must throw
//  - uniqueness: issue, castVote twice with the same artifact -> second rejected / counted once
//  - unlinkability: issuerCanLinkArtifactToVote() === false
//  - coercionResistance: a castVote receipt where receiptProvesChoice(receipt) === false
//  - stuffingResistance: canStuffWithoutArtifact() === false (and an artifact-less castVote is rejected)
export function runProtocolBattery(protocol: EligibilityProtocol): PropertyReport;

export interface QualitativeAxes {
  elderlyUsability: string;
  operationalWeight: string;
  counselExposure: string;
  lanSecureContextFit: string;
}
export interface ProtocolComparison {
  demonstrated: Array<{ name: string; properties: PropertyReport; qualitative: QualitativeAxes }>;
  characterized: Array<{ name: string; properties: 'deferred'; qualitative: QualitativeAxes; note: string }>;
}
export function compareProtocols(
  demonstrated: Array<{ protocol: EligibilityProtocol; qualitative: QualitativeAxes }>,
  characterized: Array<{ name: string; qualitative: QualitativeAxes; note: string }>
): ProtocolComparison;
```

The **characterized** entry (`HOMOMORPHIC_MIXNET`) is passed to `compareProtocols` as data: all qualitative axes scored, `properties: 'deferred'`, `note` citing `07` (Helios/BeleniosRF/mixnets) and "heaviest lift, weakest co-op/LAN fit; mechanics deferred until/unless chosen."

### Integration to 4a (one demo per demonstrated protocol)

Each demonstrated protocol runs an honest election (roll → issue to each eligible member → each casts once), its `tally()` produces `{ votesFor, votesAgainst, abstentions }`, which flows into `EqualWeightGovernorModel.ingestSecretTally(proposalId, { ...counts, ballotRef })` → `finalize()` → `verifyTallyAttestation` accepts. Proves the surface reaches a real signed tally.

## Testing (TDD, red-first)

Test file(s): `__tests__/eligibility-protocols.test.ts`, `__tests__/eligibility-battery.test.ts`.

1. **Eligibility** — `issue('non-roll')` throws for both demonstrated protocols.
2. **Uniqueness** — issue, `castVote` twice → second rejected; tally counts the member once, for both.
3. **Token coercion LEAK (the lesson)** — `runProtocolBattery(new SingleUseTokenProtocol())` reports `coercionResistance.holds === false` and `unlinkability.holds === false`, with `how` naming the retained bearer proof / issuer linkage.
4. **Blind-sig HOLDS (the contrast)** — `runProtocolBattery(new BlindSignatureProtocol())` reports all five properties `holds === true`.
5. **Uniqueness holds for both** — battery reports `uniqueness.holds === true` and `eligibility.holds === true` for tokens and blind-sig alike (the shared floor).
6. **Stuffing** — `canStuffWithoutArtifact() === false` for both; an artifact-less `castVote` is rejected.
7. **Comparison shape** — `compareProtocols([...two demonstrated...], [HOMOMORPHIC_MIXNET])` returns 2 demonstrated (with full `PropertyReport`) + 1 characterized (`properties: 'deferred'`, all qualitative axes populated, note cites `07`).
8. **Integration** — each demonstrated protocol's honest election → `ingestSecretTally` → `finalize` → `verifyTallyAttestation` valid, with counts matching the protocol's `tally()`.

## Out of scope (later stages)

- **Real cryptography** for the chosen protocol (production blind signatures / anonymous tokens) — the hardening stage AFTER the group chooses.
- **Mix-net mechanics** — characterized only here.
- **Binding an eligibility-proof digest into the signed tally** (extending `ballotRef` with the protocol transcript) — deferred to the chosen-protocol hardening.
- **Cross-repo pm-ballot wiring** — needs the branch-coexistence prerequisite.
- **Stage 5 paper parity.**

## Success criteria

- The interface + two demonstrable models + the battery compile; all TDD tests pass; full submodule suite stays green.
- The battery **demonstrates** the naive-token coercion/unlinkability break (test 3) and the blind-signature clean hold (test 4) — the graduated lesson is executable, not asserted.
- Eligibility, uniqueness, and stuffing-resistance hold for both demonstrated protocols (the shared floor); the comparison surfaces all three options with the mix-net honestly characterized-not-demonstrated.
- Each demonstrated protocol reaches a real committee-signed, independently-verifiable tally through 4a (test 8) — the surface is wired to the seam, not floating.
