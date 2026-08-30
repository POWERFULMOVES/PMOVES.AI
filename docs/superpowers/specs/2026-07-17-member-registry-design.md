# MemberRegistry — Design Spec (governance replacement, stage 3)

**Date:** 2026-07-17
**Status:** IMPLEMENTED AND TESTED — merged in ToKenism PR #64 (`d17ea07b`); activation remains counsel- and operations-gated
**Scope:** the committee-controlled eligibility layer ONLY. Real voter-card crypto, secret-ballot integration, and paper parity are later counsel-gated stages, out of scope here.
**Where:** submodule `PMOVES-ToKenism-Multi/integrations/contracts/`.
**Builds on:** stage 1 `EqualWeightGovernorModel` (this stage produces the roll it consumes). Honors `pmoves/docs/pilots/fordham-hill/08-voter-identity-key-custody.md` and `CATACLYSM_CROSSLINKS.md` (#5). The model is implemented; any binding use remains counsel-gated.

## Problem

`EqualWeightGovernorModel` consumes an eligible roll via `setRoll(members)`, but nothing legitimizes that roll. `08` names **enrollment as the step where operator fraud lives** — "the operator could bind a key it controls to a resident's name, refuse to enrol a disfavored resident, or mint duplicates." A single-registrar roll re-creates exactly that chokepoint.

This stage adds `MemberRegistryModel`: a committee-controlled roll where **enrollment and revocation each require k-of-n committee approval** — so no single party (operator included) can pack, deny, or forge the membership roll. Membership is **decoupled from tokens/contribution** (an explicit roll of residents, `08`'s Mode A/B invariant). The crypto is stubbed behind the same M-of-N gate pattern as stage 1's `TallySigner`; real `voter-card.v1` credentials come later.

## Decisions (from brainstorming, approved)

1. **Enrollment (and revocation) require k-of-n committee approval** — the anti-chokepoint design, reusing stage 1's M-of-N gate pattern. Not a single registrar.
2. **Own committee + threshold** config (mirrors the governor's); constructor validates integer `committeeSize >= 2` and `2 <= committeeThreshold <= committeeSize` (the forge-hole lesson from stage 1's review).
3. **Reuse `EligibleMember`** from `equalweight-governor-model.ts` so `roll()` output drops straight into `EqualWeightGovernor.setRoll()` (DRY; loose coupling — the caller wires `registry.roll()` → `governor.setRoll()`, no hard dependency between them at runtime).
4. **Decoupled from tokens** — membership is residency/committee-issued, never derived from holdings/contribution.

## Components (one file: `member-registry-model.ts`)

- **`MemberRegistryModel`** — the registry.
- Types: `MembershipCredential`, `MemberRegistryConfig`. Imports `EligibleMember` from `./equalweight-governor-model`.

### Types

```ts
import { EligibleMember } from './equalweight-governor-model';

interface MemberRegistryConfig {
  committeeSize: number;       // n (default 3)
  committeeThreshold: number;  // k (default 2; 2 <= k <= n)
}

interface MembershipCredential {
  member: EligibleMember;      // id + optional units/shares (for the governor's votingBasis)
  status: 'active' | 'revoked';
  approvers: string[];         // the committee members who approved (>= k, deduplicated)
  signature: string;           // stubbed ('stub-mofn:<memberId>'); real voter-card crypto later
}
```

### API

```
setCommittee(memberIds: string[]): void         // exactly committeeSize distinct ids; else throws
enrol(member: EligibleMember, approvers: string[]): MembershipCredential
  - M-of-N gate: approvers deduped, all in committee, count >= committeeThreshold; else throw
  - records the member as 'active'; returns the credential
revoke(memberId: string, approvers: string[]): void
  - M-of-N gate (same checks); sets the member's status to 'revoked'; throws if not enrolled
isEligible(memberId: string): boolean            // true iff an active membership exists
roll(): EligibleMember[]                          // active members only → feeds EqualWeightGovernor.setRoll()
```

## The M-of-N gate (anti-chokepoint property)

Both `enrol` and `revoke` require ≥ `committeeThreshold` **distinct** committee approvers. With `committeeThreshold >= 2`, **no single party — including the operator — can add, remove, or forge a member.** The gate logic mirrors stage 1's `MockThresholdSigner`: dedupe approvers (a member approving twice counts once), reject any approver not on the committee, reject below-threshold. Constructor validation rejects non-integer/undersized configurations, and `setCommittee` requires exactly `committeeSize` distinct IDs so configured *n* equals the installed committee.

## Testing (TDD, red-first)

1. **enrol requires threshold** — `enrol(m, ['0xC1'])` with k=2 throws; `enrol(m, ['0xC1','0xC2'])` succeeds and `isEligible(m.id)` is true.
2. **duplicate approver** — `enrol(m, ['0xC1','0xC1'])` throws (dedupe → 1 < 2).
3. **non-committee approver** — `enrol(m, ['0xC1','0xSTRANGER'])` throws.
4. **revoke requires threshold + removes from roll** — enrol m, then `revoke(m.id, ['0xC1'])` throws; `revoke(m.id, ['0xC1','0xC2'])` succeeds, `isEligible` false, `roll()` excludes m.
5. **revoke of a non-member** — `revoke('0xNOBODY', ['0xC1','0xC2'])` throws.
6. **roll() feeds the governor** — enrol A + B (with committee approval), `roll()` returns `[{id:'A'},{id:'B'}]` (order-insensitive), and passing it to `new EqualWeightGovernorModel().setRoll(registry.roll())` lets A and B vote (integration proof).
7. **config validation** — `new MemberRegistryModel({ committeeThreshold: 0 })` throws; `{ committeeThreshold: 4, committeeSize: 3 }` throws.
8. **integration count** — the Task-3 roll→governor case is counted in the expected suite total.
9. **committee cardinality** — committees smaller or larger than configured `committeeSize` throw.
10. **duplicate committee ID** — a committee with repeated member IDs throws even when its array length equals `committeeSize`.

No changes to existing models; `EqualWeightGovernorModel` is imported (for `EligibleMember`) but not modified.

## Out of scope (later arc stages)

- Real `voter-card.v1` credential crypto (the `signature` stub becomes a real committee-signed credential).
- Secret-ballot integration (A2UI `pm-ballot` receipts as the vote source).
- Paper parity.
- Human-witnessed identity proofing (the real-world step behind an approval) — modeled here only as committee approval.
- **Committee constitution / rotation.** `setCommittee` is a **trusted genesis act** — the anti-chokepoint ("no single party can enrol/revoke") guarantee holds *given a trustworthily-constituted committee*. It is ungated by design: gating it would create a bootstrap paradox and give false security (an operator who controls constitution could seat sock-puppets at genesis regardless). Runtime committee rotation (adding/removing committee members under M-of-N approval) is a later arc stage. This assumption is stated explicitly rather than assumed closed (per stage-3 review).

## Success criteria

- `MemberRegistryModel` compiles; all TDD tests pass; full submodule suite stays green.
- `enrol`/`revoke` provably reject a single-party action (tests 1, 4) and a below-threshold/duplicate/non-committee approver (tests 2, 3).
- `roll()` output drives `EqualWeightGovernor.setRoll()` end-to-end (test 6).
- No existing model modified.
