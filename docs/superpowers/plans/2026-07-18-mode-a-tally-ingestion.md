# Mode-A Tally Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Mode-A-safe intake — `ingestSecretTally` — that turns aggregate secret-ballot counts into a signable `TallyResult` without the per-voter `Map<voter → support>`, enforces "never mix modes" structurally, exposes the abstention rule as a swept knob, and binds the ballot source into the signature.

**Architecture:** One new file `mode-a-tally.ts` holds the provenance type + the pure outcome math + the contrast sweep (self-contained, no governor import → no cycle). `equalweight-governor-model.ts` gains the `abstentionPolicy` config, the optional `ballotRef` on `TallyResult`, and the `ingestSecretTally` method + lock-on-first-use mode guard. `tally-signer-ed25519.ts` extends `tallyPreimage` with a backward-compatible `ballotRef` suffix.

**Tech Stack:** TypeScript (ES2022, commonjs, strict), Jest + ts-jest, Node built-in only (zero new deps).

## Global Constraints

- **Zero new dependencies.**
- **Backward-compatible preimage:** a `TallyResult` **without** `ballotRef` must produce byte-identical `tallyPreimage` output to today — all 455 stage-2 tests and existing signatures must still pass. The `ballotRef` suffix is appended **only when present**, led by the sentinel `'ballotref.v1'`.
- **DRY outcome math:** the turnout/quorum/pass computation lives in ONE pure function `computeSecretOutcome`, used by both `ingestSecretTally` and `sweepAbstentionPolicy`. Do not inline a second copy.
- **Hard integrity guards (not knobs):** each count must be `Number.isSafeInteger` and `>= 0`; `voterCount <= eligibleCount`. These live in `computeSecretOutcome` so every caller inherits them.
- **Mode lock is structural:** a proposal touched by `castVote` is `'named'`; one touched by `ingestSecretTally` is `'secret'`; each intake throws on the other's proposals.
- **Knob default:** `abstentionPolicy` defaults to `'quorum'` (abstentions count toward turnout); `'excluded'` omits them from turnout.
- **Decision excludes abstentions:** `passed` uses `votesFor / (votesFor + votesAgainst)`.
- TypeScript strict + noUnusedLocals/noUnusedParameters/noImplicitReturns. Tests in `integrations/contracts/__tests__/`; run from `integrations/` with `npx jest`.

---

### Task 1: Pure outcome math + provenance type + abstention knob (`mode-a-tally.ts`)

**Files:**
- Create: `integrations/contracts/mode-a-tally.ts`
- Modify: `integrations/contracts/equalweight-governor-model.ts` (add `abstentionPolicy` to config + default)
- Test: `integrations/contracts/__tests__/mode-a-tally.test.ts`

**Interfaces:**
- Produces: `BallotRef`, `SecretTallyCounts`, `SecretOutcome`, `computeSecretOutcome(counts, eligibleCount, cfg): SecretOutcome`, `sweepAbstentionPolicy(counts, eligibleCount, cfg): { quorum, excluded }`.
- Consumed by: Task 2 (`BallotRef` on `TallyResult`) and Task 3 (`computeSecretOutcome`, `SecretTallyCounts`, `BallotRef`).

- [ ] **Step 1: Write the failing tests**

Create `integrations/contracts/__tests__/mode-a-tally.test.ts`:

```ts
// contracts/__tests__/mode-a-tally.test.ts
import { computeSecretOutcome, sweepAbstentionPolicy } from '../mode-a-tally';
import { EqualWeightGovernorModel } from '../equalweight-governor-model';

const CFG = { quorumPercentage: 0.5, passThreshold: 0.5 };

describe('computeSecretOutcome', () => {
  it('quorum policy counts abstentions toward turnout', () => {
    const o = computeSecretOutcome({ votesFor: 30, votesAgainst: 10, abstentions: 15 }, 100, { ...CFG, abstentionPolicy: 'quorum' });
    expect(o.voterCount).toBe(55);
    expect(o.turnout).toBeCloseTo(0.55, 6);
    expect(o.quorumMet).toBe(true);
    expect(o.passed).toBe(true); // forShare 30/40 = 0.75 >= 0.5
  });

  it('excluded policy omits abstentions from turnout — flips the outcome', () => {
    const o = computeSecretOutcome({ votesFor: 30, votesAgainst: 10, abstentions: 15 }, 100, { ...CFG, abstentionPolicy: 'excluded' });
    expect(o.voterCount).toBe(55);            // voterCount still includes abstentions
    expect(o.turnout).toBeCloseTo(0.40, 6);   // but turnout omits them
    expect(o.quorumMet).toBe(false);
    expect(o.passed).toBe(false);
  });

  it('decision excludes abstentions (forShare over for+against only)', () => {
    const o = computeSecretOutcome({ votesFor: 3, votesAgainst: 1, abstentions: 90 }, 100, { ...CFG, abstentionPolicy: 'quorum' });
    expect(o.turnout).toBeCloseTo(0.94, 6);
    expect(o.passed).toBe(true); // 3/(3+1)=0.75 >= 0.5, abstentions don't dilute the decision
  });

  it('rejects non-safe-integer / negative counts', () => {
    expect(() => computeSecretOutcome({ votesFor: NaN, votesAgainst: 1, abstentions: 0 }, 10, { ...CFG, abstentionPolicy: 'quorum' })).toThrow(/votesFor/);
    expect(() => computeSecretOutcome({ votesFor: -1, votesAgainst: 1, abstentions: 0 }, 10, { ...CFG, abstentionPolicy: 'quorum' })).toThrow(/votesFor/);
    expect(() => computeSecretOutcome({ votesFor: 1.5, votesAgainst: 1, abstentions: 0 }, 10, { ...CFG, abstentionPolicy: 'quorum' })).toThrow(/votesFor/);
  });

  it('rejects voterCount exceeding eligibleCount', () => {
    expect(() => computeSecretOutcome({ votesFor: 2, votesAgainst: 1, abstentions: 1 }, 3, { ...CFG, abstentionPolicy: 'quorum' })).toThrow(/exceeds|eligible/i);
  });
});

describe('sweepAbstentionPolicy', () => {
  it('returns both outcomes and shows the divergence', () => {
    const s = sweepAbstentionPolicy({ votesFor: 30, votesAgainst: 10, abstentions: 15 }, 100, CFG);
    expect(s.quorum.quorumMet).toBe(true);
    expect(s.excluded.quorumMet).toBe(false);
  });

  it('policies agree when for+against alone clears quorum', () => {
    const s = sweepAbstentionPolicy({ votesFor: 40, votesAgainst: 10, abstentions: 15 }, 100, CFG);
    expect(s.quorum.quorumMet).toBe(true);
    expect(s.excluded.quorumMet).toBe(true); // (40+10)/100 = 0.50 >= 0.5
  });
});

describe('EqualWeightGovernorModel abstentionPolicy config', () => {
  it('defaults abstentionPolicy to quorum', () => {
    const gov = new EqualWeightGovernorModel();
    expect((gov as unknown as { config: { abstentionPolicy: string } }).config.abstentionPolicy).toBe('quorum');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd integrations && npx jest mode-a-tally`
Expected: FAIL — `mode-a-tally` module not found / exports missing.

- [ ] **Step 3: Write the implementation**

Create `integrations/contracts/mode-a-tally.ts`:

```ts
// contracts/mode-a-tally.ts
// Mode-A (secret-ballot) tally ingestion math: pure outcome computation shared by
// the governor's ingestSecretTally and the abstention-policy contrast sweep.
// Self-contained (no governor import) so there is no import cycle. See
// docs/superpowers/specs/2026-07-18-mode-a-tally-ingestion-design.md.

export type AbstentionPolicy = 'quorum' | 'excluded';

// Provenance: which ballot's evidence a tally claims to summarize. receiptLogDigest
// is a caller-supplied hash of the sorted sealed receiptHash list (the proof that
// counts CORRESPOND to receipts is stage 4b — this only binds which ballot).
export interface BallotRef {
  ballotId: string;
  receiptLogDigest: string;
}

export interface SecretTallyCounts {
  votesFor: number;
  votesAgainst: number;
  abstentions: number;
  ballotRef?: BallotRef;
}

export interface SecretOutcome {
  votesFor: number;
  votesAgainst: number;
  eligibleCount: number;
  voterCount: number;
  turnout: number;
  quorumMet: boolean;
  passed: boolean;
}

interface OutcomeConfig {
  abstentionPolicy: AbstentionPolicy;
  quorumPercentage: number;
  passThreshold: number;
}

function assertCount(n: number, label: string): void {
  if (!Number.isSafeInteger(n) || n < 0) {
    throw new Error(`invalid ${label}: ${n}`);
  }
}

// Pure. Hard integrity guards (safe-integer/non-negative counts, voterCount <=
// eligibleCount) live here so every caller inherits them. abstentionPolicy
// selects whether abstentions count toward turnout; the for/against decision
// always excludes them.
export function computeSecretOutcome(
  counts: { votesFor: number; votesAgainst: number; abstentions: number },
  eligibleCount: number,
  cfg: OutcomeConfig
): SecretOutcome {
  assertCount(counts.votesFor, 'votesFor');
  assertCount(counts.votesAgainst, 'votesAgainst');
  assertCount(counts.abstentions, 'abstentions');
  const voterCount = counts.votesFor + counts.votesAgainst + counts.abstentions;
  if (voterCount > eligibleCount) {
    throw new Error(`voterCount ${voterCount} exceeds eligibleCount ${eligibleCount}`);
  }
  const participating =
    cfg.abstentionPolicy === 'excluded'
      ? counts.votesFor + counts.votesAgainst
      : voterCount;
  const turnout = eligibleCount > 0 ? participating / eligibleCount : 0;
  const quorumMet = eligibleCount > 0 && turnout >= cfg.quorumPercentage;
  const decided = counts.votesFor + counts.votesAgainst;
  const forShare = decided > 0 ? counts.votesFor / decided : 0;
  const passed = quorumMet && forShare >= cfg.passThreshold;
  return {
    votesFor: counts.votesFor,
    votesAgainst: counts.votesAgainst,
    eligibleCount,
    voterCount,
    turnout,
    quorumMet,
    passed,
  };
}

// The "where the chips land" surface: same counts under both policies.
export function sweepAbstentionPolicy(
  counts: { votesFor: number; votesAgainst: number; abstentions: number },
  eligibleCount: number,
  cfg: { quorumPercentage: number; passThreshold: number }
): { quorum: SecretOutcome; excluded: SecretOutcome } {
  return {
    quorum: computeSecretOutcome(counts, eligibleCount, { ...cfg, abstentionPolicy: 'quorum' }),
    excluded: computeSecretOutcome(counts, eligibleCount, { ...cfg, abstentionPolicy: 'excluded' }),
  };
}
```

Then edit `integrations/contracts/equalweight-governor-model.ts` — add the knob to the config interface and its default:

```ts
// import at top:
import { AbstentionPolicy } from './mode-a-tally';

// in EqualWeightGovernorConfig interface, add:
  abstentionPolicy: AbstentionPolicy;

// in the constructor's this.config = { ... } defaults block, add (before ...config):
  abstentionPolicy: 'quorum',
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd integrations && npx jest mode-a-tally`
Expected: PASS (all `computeSecretOutcome`, `sweepAbstentionPolicy`, and config-default tests).

- [ ] **Step 5: Commit**

```bash
git add integrations/contracts/mode-a-tally.ts integrations/contracts/equalweight-governor-model.ts integrations/contracts/__tests__/mode-a-tally.test.ts
git commit -m "feat(gov): Mode-A outcome math + abstentionPolicy knob + contrast sweep (stage 4a)"
```

---

### Task 2: Bind `ballotRef` into the tally preimage

**Files:**
- Modify: `integrations/contracts/equalweight-governor-model.ts` (add `ballotRef?` to `TallyResult`)
- Modify: `integrations/contracts/tally-signer-ed25519.ts` (extend `tallyPreimage`)
- Test: `integrations/contracts/__tests__/tally-signer-ed25519.test.ts` (add ballotRef tests)

**Interfaces:**
- Consumes: `BallotRef` from `./mode-a-tally` (Task 1).
- Produces: `TallyResult.ballotRef?: BallotRef`; `tallyPreimage` binds it when present.

- [ ] **Step 1: Write the failing tests**

Append to `integrations/contracts/__tests__/tally-signer-ed25519.test.ts`:

```ts
import { BallotRef } from '../mode-a-tally';

describe('tallyPreimage ballotRef binding', () => {
  const ref: BallotRef = { ballotId: 'b-2026-recall', receiptLogDigest: 'abc123' };

  it('is byte-identical to the no-ballotRef encoding when absent (backward compatible)', () => {
    const noRef = baseTally();                       // no ballotRef
    const withRef = baseTally({ ballotRef: ref });
    const pmNo = tallyPreimage(noRef);
    const pmWith = tallyPreimage(withRef);
    // no-ballotRef preimage is a strict prefix of the with-ballotRef one, and shorter
    expect(pmWith.length).toBeGreaterThan(pmNo.length);
    expect(pmWith.subarray(0, pmNo.length).equals(pmNo)).toBe(true);
    // the no-ballotRef preimage contains no sentinel bytes
    expect(pmNo.includes(Buffer.from('ballotref.v1'))).toBe(false);
    expect(pmWith.includes(Buffer.from('ballotref.v1'))).toBe(true);
  });

  it('binds ballotRef into the signature — tampering the digest fails verification', () => {
    const keyring = { '0xC1': generateCommitteeKeypair(), '0xC2': generateCommitteeKeypair(), '0xC3': generateCommitteeKeypair() };
    const committee = ['0xC1', '0xC2', '0xC3'];
    const tally = baseTally({ ballotRef: ref });
    const att = new Ed25519MultisigSigner(keyring).sign(tally, ['0xC1', '0xC2'], committee, 2);
    const pub = Object.fromEntries(Object.entries(keyring).map(([id, kp]) => [id, kp.publicKey]));

    expect(verifyTallyAttestation(tally, att, pub, 2).valid).toBe(true);

    const tampered = baseTally({ ballotRef: { ballotId: ref.ballotId, receiptLogDigest: 'DIFFERENT' } });
    expect(verifyTallyAttestation(tampered, att, pub, 2).valid).toBe(false);

    const tamperedId = baseTally({ ballotRef: { ballotId: 'OTHER-BALLOT', receiptLogDigest: ref.receiptLogDigest } });
    expect(verifyTallyAttestation(tamperedId, att, pub, 2).valid).toBe(false);
  });
});
```

(Note: `baseTally` — the helper defined in the Task-1 block of this file back in the stage-2 plan — accepts an overrides object; `ballotRef` flows straight through the spread.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd integrations && npx jest tally-signer-ed25519 -t "ballotRef binding"`
Expected: FAIL — `TallyResult` has no `ballotRef` / preimage does not append it.

- [ ] **Step 3: Write the implementation**

In `integrations/contracts/equalweight-governor-model.ts`, extend the `TallyResult` interface and import the type:

```ts
// add to the mode-a-tally import (or a new import line):
import { AbstentionPolicy, BallotRef } from './mode-a-tally';

// in the TallyResult interface, add:
  ballotRef?: BallotRef;
```

In `integrations/contracts/tally-signer-ed25519.ts`, extend `tallyPreimage` — append the sentinel-led suffix only when present:

```ts
export function tallyPreimage(tally: TallyResult): Buffer {
  const fields = [
    TALLY_DOMAIN,
    tally.proposalId,
    String(tally.votesFor),
    String(tally.votesAgainst),
    String(tally.eligibleCount),
    String(tally.voterCount),
    tally.quorumMet ? '1' : '0',
    tally.passed ? '1' : '0',
  ];
  // Backward-compatible provenance binding: only when a ballotRef is present do we
  // append its sentinel + fields. A tally without ballotRef yields byte-identical
  // output to before, so existing signatures/tests still hold; because the
  // signature covers the whole byte string, a ballotRef cannot be stripped from a
  // signed tally and still verify.
  if (tally.ballotRef) {
    fields.push('ballotref.v1', tally.ballotRef.ballotId, tally.ballotRef.receiptLogDigest);
  }
  return Buffer.concat(fields.map(ns));
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd integrations && npx jest tally-signer-ed25519`
Expected: PASS — the new ballotRef tests plus every pre-existing stage-2 test (backward-compatible: no-ballotRef preimages unchanged).

- [ ] **Step 5: Commit**

```bash
git add integrations/contracts/equalweight-governor-model.ts integrations/contracts/tally-signer-ed25519.ts integrations/contracts/__tests__/tally-signer-ed25519.test.ts
git commit -m "feat(gov): bind ballotRef provenance into the tally preimage (stage 4a)"
```

---

### Task 3: `ingestSecretTally` + lock-on-first-use mode guard

**Files:**
- Modify: `integrations/contracts/equalweight-governor-model.ts` (add `mode`/`ingestedTally` to `Proposal`; mode guard in `castVote`; `ingestSecretTally`; `tally()` returns ingested result for secret proposals)
- Test: `integrations/contracts/__tests__/mode-a-tally.test.ts` (add ingestion + integration tests)

**Interfaces:**
- Consumes: `computeSecretOutcome`, `SecretTallyCounts` from `./mode-a-tally` (Task 1); `ballotRef` binding (Task 2); `Ed25519MultisigSigner`/`verifyTallyAttestation` from stage 2.
- Produces: `EqualWeightGovernorModel.ingestSecretTally(proposalId, counts: SecretTallyCounts): TallyResult`.

- [ ] **Step 1: Write the failing tests**

Append to `integrations/contracts/__tests__/mode-a-tally.test.ts`:

```ts
import { Ed25519MultisigSigner, generateCommitteeKeypair, verifyTallyAttestation } from '../tally-signer-ed25519';

describe('EqualWeightGovernorModel.ingestSecretTally', () => {
  function gov(overrides = {}) {
    const g = new EqualWeightGovernorModel({ committeeSize: 3, committeeThreshold: 2, ...overrides });
    g.setRoll([{ id: 'A' }, { id: 'B' }, { id: 'C' }, { id: 'D' }, { id: 'E' }]); // 5 eligible
    g.createProposal('p1', 'Recall');
    return g;
  }

  it('sources eligibleCount from the roll and derives voterCount', () => {
    const g = gov();
    const t = g.ingestSecretTally('p1', { votesFor: 3, votesAgainst: 1, abstentions: 0 });
    expect(t.eligibleCount).toBe(5);
    expect(t.voterCount).toBe(4);
    expect(t.turnout).toBeCloseTo(0.8, 6);
  });

  it('locks the proposal to secret mode — a later castVote throws', () => {
    const g = gov();
    g.ingestSecretTally('p1', { votesFor: 3, votesAgainst: 1, abstentions: 0 });
    expect(() => g.castVote('p1', 'A', true)).toThrow(/mode|secret|named/i);
  });

  it('refuses ingestion on a proposal already used for named votes', () => {
    const g = gov();
    g.castVote('p1', 'A', true);
    expect(() => g.ingestSecretTally('p1', { votesFor: 1, votesAgainst: 0, abstentions: 0 })).toThrow(/mode|secret|named/i);
  });

  it('propagates the voterCount<=eligibleCount guard', () => {
    const g = gov();
    expect(() => g.ingestSecretTally('p1', { votesFor: 4, votesAgainst: 2, abstentions: 0 })).toThrow(/exceeds|eligible/i);
  });

  it('tally() returns the ingested result for a secret proposal', () => {
    const g = gov();
    const ingested = g.ingestSecretTally('p1', { votesFor: 3, votesAgainst: 1, abstentions: 0 });
    expect(g.tally('p1')).toEqual(ingested);
  });

  it('finalize() signs an ingested tally and verifyTallyAttestation accepts, with ballotRef in the signed bytes', () => {
    const keyring = { '0xC1': generateCommitteeKeypair(), '0xC2': generateCommitteeKeypair(), '0xC3': generateCommitteeKeypair() };
    const g = new EqualWeightGovernorModel({ committeeSize: 3, committeeThreshold: 2 }, new Ed25519MultisigSigner(keyring));
    g.setRoll([{ id: 'A' }, { id: 'B' }, { id: 'C' }, { id: 'D' }, { id: 'E' }]);
    g.setCommittee(['0xC1', '0xC2', '0xC3']);
    g.createProposal('p1', 'Recall');
    g.ingestSecretTally('p1', { votesFor: 3, votesAgainst: 1, abstentions: 1, ballotRef: { ballotId: 'b1', receiptLogDigest: 'd1' } });

    const result = g.finalize('p1', ['0xC1', '0xC2']);
    expect(result.finalized).toBe(true);
    expect(result.ballotRef).toEqual({ ballotId: 'b1', receiptLogDigest: 'd1' });

    const pub = Object.fromEntries(Object.entries(keyring).map(([id, kp]) => [id, kp.publicKey]));
    expect(verifyTallyAttestation(result, result.attestation!, pub, 2).valid).toBe(true);
    // tampering the bound ballotRef breaks verification
    const tampered = { ...result, ballotRef: { ballotId: 'b1', receiptLogDigest: 'HACKED' } };
    expect(verifyTallyAttestation(tampered, result.attestation!, pub, 2).valid).toBe(false);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd integrations && npx jest mode-a-tally -t ingestSecretTally`
Expected: FAIL — `ingestSecretTally` does not exist.

- [ ] **Step 3: Write the implementation**

In `integrations/contracts/equalweight-governor-model.ts`:

(a) Extend the imports and the `Proposal` interface:

```ts
import { AbstentionPolicy, BallotRef, SecretTallyCounts, computeSecretOutcome } from './mode-a-tally';

interface Proposal {
  id: string;
  title: string;
  closesAtWeek?: number;
  votes: Map<string, boolean>;
  mode?: 'named' | 'secret';       // set on first intake; locks the proposal to one path
  ingestedTally?: TallyResult;     // secret proposals: the precomputed result tally() returns
}
```

(b) Add the mode guard to `castVote` (at the top, after the proposal lookup and before the roll/duplicate checks):

```ts
  castVote(proposalId: string, voter: string, support: boolean): void {
    const proposal = this.proposals.get(proposalId);
    if (!proposal) throw new Error(`Proposal ${proposalId} not found`);
    if (proposal.mode === 'secret') {
      throw new Error(`Proposal ${proposalId} is in secret mode; named castVote is not allowed`);
    }
    proposal.mode = 'named';
    // ...existing roll check, duplicate check, votes.set...
  }
```

(c) Add `ingestSecretTally`:

```ts
  ingestSecretTally(proposalId: string, counts: SecretTallyCounts): TallyResult {
    const proposal = this.proposals.get(proposalId);
    if (!proposal) throw new Error(`Proposal ${proposalId} not found`);
    if (proposal.mode === 'named') {
      throw new Error(`Proposal ${proposalId} is in named mode; secret ingestion is not allowed`);
    }
    proposal.mode = 'secret';
    const outcome = computeSecretOutcome(
      { votesFor: counts.votesFor, votesAgainst: counts.votesAgainst, abstentions: counts.abstentions },
      this.roll.size,
      {
        abstentionPolicy: this.config.abstentionPolicy,
        quorumPercentage: this.config.quorumPercentage,
        passThreshold: this.config.passThreshold,
      }
    );
    const result: TallyResult = {
      proposalId,
      votesFor: outcome.votesFor,
      votesAgainst: outcome.votesAgainst,
      eligibleCount: outcome.eligibleCount,
      voterCount: outcome.voterCount,
      turnout: outcome.turnout,
      quorumMet: outcome.quorumMet,
      passed: outcome.passed,
      finalized: false,
      ...(counts.ballotRef ? { ballotRef: counts.ballotRef } : {}),
    };
    proposal.ingestedTally = result;
    return result;
  }
```

(d) Make `tally()` return the ingested result for secret proposals (at the top of `tally`, after the proposal lookup):

```ts
  tally(proposalId: string): TallyResult {
    const proposal = this.proposals.get(proposalId);
    if (!proposal) throw new Error(`Proposal ${proposalId} not found`);
    if (proposal.mode === 'secret' && proposal.ingestedTally) {
      return proposal.ingestedTally;
    }
    // ...existing recompute-from-votes-map logic unchanged...
  }
```

Note: `BallotRef` and `AbstentionPolicy` may already be imported from Task 2 / Task 1 — merge into a single `./mode-a-tally` import (no duplicate import lines).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd integrations && npx jest mode-a-tally`
Expected: PASS — all ingestion + integration tests, plus the Task-1 tests in the same file.

- [ ] **Step 5: Run the full submodule suite**

Run: `cd integrations && npx jest`
Expected: PASS — whole suite green, including every stage-1/2/3 test (named `castVote` path and existing governor behavior unchanged).

- [ ] **Step 6: Commit**

```bash
git add integrations/contracts/equalweight-governor-model.ts integrations/contracts/__tests__/mode-a-tally.test.ts
git commit -m "feat(gov): ingestSecretTally — Mode-A count intake + lock-on-first-use mode guard (stage 4a)"
```
