# Ed25519 Multisig TallySigner — Design Spec (governance replacement, stage 2)

**Date:** 2026-07-18
**Status:** DRAFT — approved for implementation (stage 2 of the #5 governance-replacement arc)
**Scope:** the real committee tally-signature ONLY — a third-party-verifiable Ed25519 k-of-n multisignature replacing the stubbed `MockThresholdSigner`, behind the same `TallySigner` interface. Key custody, CGP/bus emission, secret-ballot integration, and paper parity are later stages, out of scope here.
**Where:** submodule `PMOVES-ToKenism-Multi/integrations/contracts/`.
**Builds on:** stage 1 `EqualWeightGovernorModel` (it calls `this.signer.sign(...)` through `TallySigner`) and stage 3 `MemberRegistryModel` (loose-coupled; see below). Honors `pmoves/docs/pilots/fordham-hill/08-voter-identity-key-custody.md` (§5b: "an election committee threshold-signs the tally … no single party incl. operator can forge — replaces single-operator HMAC") and `CATACLYSM_CROSSLINKS.md` (#5). DRAFT — counsel-gated before anything binding.

## Problem

Stage 1 shipped the *gate* honestly but stubbed the *bytes*: `MockThresholdSigner` enforces the M-of-N committee gate (dedupe + committee-membership + threshold) and returns `signature: "stub:<proposalId>"`. That models "no single party can forge" but proves nothing cryptographically — a stubbed string binds no one to any tally, and a third party (Attorney General, bank) cannot verify it.

Worse, the repo's existing signing primitive — CHIT/CGP — is the wrong tool for this layer. `CGPSignature` is an **HMAC** (`chit/cgp-generator.ts:118`) verified against a **single shared passphrase** (`gateway/api/chit.py:64`, `verify_hmac` → PBKDF2HMAC). That is *exactly* the single-operator forge hole `08` rejected: anyone holding the passphrase — including the operator — can forge any CGP signature, and a regulator cannot verify an HMAC without being handed the forging key.

This stage adds a real committee signature with two non-negotiable properties:

1. **Unforgeable by any single party.** k-of-n distinct committee members must each sign; below-threshold, duplicate, or non-committee approvers are rejected.
2. **Third-party verifiable on public material only.** An AG/bank recomputes the signed bytes and checks each signature against published **public** keys — confirming *who* authorized *this exact tally* without any ability to forge.

## Layering: authorization vs. transport (why not CGP)

Two different questions, two different primitives — kept separate:

| Layer | Question | Primitive | In scope here? |
|---|---|---|---|
| **Authorization** | "did the committee authorize this exact tally, provably, un-forgeably?" | **Ed25519 k-of-n multisig** | **yes — this stage** |
| **Transport/envelope** | "did this packet ride our bus uncorrupted, with provenance?" | CGP packet + its HMAC | deferred (follow-on integration) |

HMAC answers integrity; a signature answers authenticity. CHIT's HMAC was doing double duty. For a contested ballot, authorization cannot be a shared secret. CGP-envelope emission (the tally riding the geometry bus as a CGP, with the multisig attestation carried inside it and HMAC demoted to a transit check) is a clean follow-on that reuses this signer — deferred to keep this unit a tight, auditable crypto surface.

## Decisions (from brainstorming, approved)

1. **Ed25519 k-of-n verifiable multisig, not FROST.** At the tally layer accountability is a *feature* — the record must show which committee members authorized. FROST collapses k signers into one group signature (hides them) and needs a DKG ceremony + external lib. Multisig uses Node's built-in `crypto` (zero deps), is legible ("2 of these 3 named members signed"), and is a low-regret call: FROST remains a same-interface drop-in if the group-signature case ever arrives.
2. **Loose keyring, not coupled to the registry committee.** Stage 2 owns a `committeeMemberId → Ed25519 publicKey` keyring. Whether those IDs are the same people as stage 3's registry committee is a **caller wiring decision** — no hard import between the two (mirrors stage 3's loose coupling to the governor).
3. **Keys injected; custody documented, not coded.** The signer takes keypairs at construction (generated in tests/sim). It has no opinion on where a private key physically lives. Custody options (hardware token / per-device key / paper-backed reconstitution) are named for counsel; injection means whichever is chosen swaps in without touching the crypto.
4. **One shared preimage function** used by both signer and verifier — divergence is then impossible.
5. **Never sign a float.** The preimage encodes integer/boolean result fields only; `turnout`/`forShare` are derived and excluded (non-deterministic float serialization would break verification).
6. **Extract the M-of-N gate** into one shared helper used by both the real signer and (refactored, ~3 lines) `MockThresholdSigner`, so the anti-forgery property has a single definition. This is the only touch to reviewed stage-1 code.
7. **Defer CGP-envelope/bus emission** — this stage is the pure signer + third-party `verify()`.

## Components (one new file: `tally-signer-ed25519.ts`; one small edit to `equalweight-governor-model.ts`)

### Shared preimage (single source of truth)

```ts
import { TallyResult } from './equalweight-governor-model';

// Domain-separated, length-prefixed (netstring) canonical encoding of the
// INTEGER/BOOLEAN result fields only. turnout/forShare are derived floats and
// are deliberately excluded. Signer and verifier both import this — they can
// never disagree on the signed bytes.
export function tallyPreimage(tally: TallyResult): Buffer;

// Encoding: for each field in fixed order, append `<byteLength>:<utf8 bytes>,`
// Order: DOMAIN("pmoves.tally.v1"), proposalId, votesFor, votesAgainst,
//        eligibleCount, voterCount, quorumMet("1"/"0"), passed("1"/"0")
// Numbers -> decimal string; booleans -> "1"/"0".
```

### The M-of-N gate (extracted, shared)

```ts
// Throws on: a non-committee approver, or fewer than `threshold` DISTINCT
// approvers. Returns the deduplicated approver list. This is the anti-forgery
// gate — one definition, used by the real signer and MockThresholdSigner.
export function assertCommitteeThreshold(
  approvers: string[],
  committee: string[],
  threshold: number
): string[];
```

`equalweight-governor-model.ts`'s `MockThresholdSigner.sign` is refactored to call `assertCommitteeThreshold` instead of its inline checks (behavior identical; ~3 lines).

### Keyring + sim helper

```ts
export interface CommitteeKeypair {
  publicKey: string;   // Ed25519 public key, SPKI DER hex
  privateKey: string;  // Ed25519 private key, PKCS8 DER hex (sim/test only; real custody injects)
}

// Sim/test convenience — real custody supplies keys out of band.
export function generateCommitteeKeypair(): CommitteeKeypair;
```

### The signer

```ts
import { TallySigner, TallyResult, TallyAttestation } from './equalweight-governor-model';

// Real Ed25519 k-of-n multisig. Holds a keyring of committee keypairs (sim
// models the ceremony; production collects independently-produced signatures).
export class Ed25519MultisigSigner implements TallySigner {
  // keyring: committeeMemberId -> CommitteeKeypair (must include the private key
  // for members expected to sign in this sim).
  constructor(keyring: Record<string, CommitteeKeypair>);

  // Applies assertCommitteeThreshold, then produces ONE Ed25519 signature per
  // (deduped) approver over tallyPreimage(tally). Throws if an approver has no
  // private key in the keyring.
  sign(
    tally: TallyResult,
    approvers: string[],
    committee: string[],
    threshold: number
  ): TallyAttestation;   // { algo: 'ed25519-multisig', approvers, signatures }
}
```

### The verifier — the deliverable

```ts
export interface VerifyResult {
  valid: boolean;
  signers: string[];      // distinct committee members whose signatures verified
  reason?: string;        // populated on failure (informing)
}

// Third-party verification on PUBLIC material only. Needs no signer/governor.
// An AG/bank runs this with the published committee public keys.
export function verifyTallyAttestation(
  tally: TallyResult,
  attestation: TallyAttestation,
  publicKeyring: Record<string, string>, // committeeMemberId -> publicKey (hex)
  threshold: number
): VerifyResult;
// Steps: recompute tallyPreimage(tally); for each (id -> sig) in
// attestation.signatures: require id in publicKeyring AND crypto.verify passes;
// count DISTINCT verified committee signers; valid iff count >= threshold and
// every listed signature verified. Any unknown id, bad sig, or short count =>
// valid:false with a reason.
```

### Attestation shape — minimal widening

`equalweight-governor-model.ts`'s `TallyAttestation` gains one optional field; nothing existing breaks:

```ts
export interface TallyAttestation {
  algo: string;
  approvers: string[];
  signature?: string;                    // was required; now optional (mock still sets it)
  signatures?: Record<string, string>;   // NEW — real signer: approverId -> hex signature
}
```

## Testing (TDD, red-first)

Test file: `integrations/contracts/__tests__/tally-signer-ed25519.test.ts` (Jest + ts-jest, matching the repo).

1. **Happy 2-of-3** — 3-member committee, 2 sign; `verifyTallyAttestation` → `valid:true`, `signers` = the two IDs (order-insensitive).
2. **Below threshold** — `sign(tally, ['0xC1'], committee, 2)` throws (gate).
3. **Non-committee approver** — `sign(tally, ['0xC1','0xSTRANGER'], committee, 2)` throws (gate).
4. **Duplicate approver** — `sign(tally, ['0xC1','0xC1'], committee, 2)` throws (dedupe → 1 < 2).
5. **Tamper detection** — sign a tally, mutate `votesFor` on the object passed to verify → `valid:false` (the signature binds the exact integer result; HMAC-to-a-third-party cannot do this).
6. **Outsider forgery** — craft a real Ed25519 signature from a keypair NOT in `publicKeyring`, inject it as a signature → `valid:false` (unknown signer id / not on committee).
7. **Wrong-tally** — signatures produced over tally A, presented with tally B (different `proposalId`/counts) → `valid:false`.
8. **Preimage determinism / float-independence** — `tallyPreimage` is bytewise stable across calls; two `TallyResult`s with identical integers/booleans but different `turnout` floats produce identical preimages.
9. **Gate parity** — after the refactor, `MockThresholdSigner` still throws on below-threshold / non-committee / duplicate (guards the extracted helper didn't change stage-1 behavior).
10. **Integration** — `new EqualWeightGovernorModel({}, new Ed25519MultisigSigner(keyring))`, cast votes, `finalize(proposalId, approvers)` → returned `attestation` passes `verifyTallyAttestation` with the matching public keyring.

## Out of scope (later arc stages / follow-ons)

- **Key custody mechanism** — injected here; hardware-token / per-device / paper-backed reconstitution is counsel's choice (documented, not coded).
- **Distributed signing ceremony** — the sim signer holds keys to model it; production collects independently-produced signatures per member. The interface (`approvers` in → per-approver signatures out) is ceremony-agnostic.
- **CGP-envelope/bus emission** — the tally riding the geometry bus as a CGP with the multisig attestation inside and HMAC demoted to transit-integrity. A follow-on that reuses this signer.
- **Config-binding in the preimage** — signing the governor thresholds alongside the result (so "this tally under these rules" is bound). A possible future hardening; the booleans `quorumMet`/`passed` already encode the rule *outcome*.
- **FROST group signature** — reserved as a same-interface drop-in if the committee's authorization ever needs to be private or signatures compact on-chain.
- **A2UI pm-ballot secret-ballot integration** (stage 4) and **paper parity** (stage 5).

## Success criteria

- `tally-signer-ed25519.ts` compiles; all TDD tests pass; full submodule suite stays green.
- `Ed25519MultisigSigner.sign` provably rejects a single-party / below-threshold / duplicate / non-committee action (tests 2–4).
- `verifyTallyAttestation` provably rejects tampering, outsider forgery, and wrong-tally presentation (tests 5–7) using **public keys only** — the third-party informing surface.
- The real signer drops into `EqualWeightGovernorModel` unchanged at the call site (test 10); the only stage-1 edits are the optional `signatures` field and the gate-helper refactor, with behavior preserved (test 9).
