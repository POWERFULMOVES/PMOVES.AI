# EqualWeightGovernor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an equal-weight (member/unit/share) governor with roll-percentage quorum and a modeled k-of-n committee finalize gate, as a drop-in sim/bridge replacement for the plutocratic `CoopGovernor`.

**Architecture:** One cohesive `EqualWeightGovernorModel` class (mirrors `CoopGovernorModel`) in the ToKenism submodule. Eligibility is an explicit roll passed in (decoupled from tokens). A `tally()` computes weighted for/against + roll-% quorum. `finalize()` is the only path to an official result and delegates a k-of-n approval check to an injected `TallySigner` (a `MockThresholdSigner` stub now; real Ed25519/FROST later). The plutocratic `CoopGovernor` is left untouched as the sweep contrast.

**Tech Stack:** TypeScript, Jest (ts-jest). Submodule `PMOVES-ToKenism-Multi`, tests run from `integrations/`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-17-equalweight-governor-design.md`.
- All new code in `PMOVES-ToKenism-Multi/integrations/contracts/`; do NOT modify `coopgovernor-model.ts` or any other existing model.
- Run tests from `PMOVES-ToKenism-Multi/integrations/`: `npx jest contracts/__tests__/equalweight-governor-model.test.ts`.
- Config defaults: `votingBasis 'member'`, `quorumPercentage 0.5`, `passThreshold 0.5`, `committeeSize 3`, `committeeThreshold 2`.
- Voting weight: `member`→1, `unit`→`member.units ?? 1`, `share`→`member.shares ?? 1`.
- Quorum is roll-percentage: `voterCount / eligibleCount >= quorumPercentage` — never stake-weighted.
- `committeeThreshold >= 2` by default so no single party can finalize.
- Set git identity in the submodule before committing: `git config user.name/user.email` mirrored from the parent repo (the submodule has no identity configured).

## Setup (do once, before Task 1)

From `PMOVES-ToKenism-Multi/`:
```bash
git checkout PMOVES.AI-Edition-Hardened && git pull --ff-only origin PMOVES.AI-Edition-Hardened
git checkout -b feat/equalweight-governor PMOVES.AI-Edition-Hardened
git config user.name "$(git -C .. config user.name)"; git config user.email "$(git -C .. config user.email)"
```

## File Structure

- **Create:** `PMOVES-ToKenism-Multi/integrations/contracts/equalweight-governor-model.ts` — all types, `EqualWeightGovernorModel`, `TallySigner` interface, `MockThresholdSigner`. One file (the class + its injected signer are one cohesive unit, mirroring the codebase's one-model-per-file pattern).
- **Create:** `PMOVES-ToKenism-Multi/integrations/contracts/__tests__/equalweight-governor-model.test.ts` — all tests.

---

### Task 1: Core skeleton — roll, proposal, member-basis tally

**Files:**
- Create: `PMOVES-ToKenism-Multi/integrations/contracts/equalweight-governor-model.ts`
- Test: `PMOVES-ToKenism-Multi/integrations/contracts/__tests__/equalweight-governor-model.test.ts`

**Interfaces:**
- Produces: `EqualWeightGovernorModel` with `setRoll(members: EligibleMember[]): void`, `createProposal(id: string, title: string, closesAtWeek?: number): void`, `castVote(proposalId: string, voter: string, support: boolean): void`, `tally(proposalId: string): TallyResult`. Types `VotingBasis`, `EligibleMember`, `EqualWeightGovernorConfig`, `TallyResult` (fields per spec; `finalized:false` here).

- [ ] **Step 1: Write the failing test**

```ts
// contracts/__tests__/equalweight-governor-model.test.ts
import { EqualWeightGovernorModel } from '../equalweight-governor-model';

describe('EqualWeightGovernorModel', () => {
  it('tallies weighted for/against and turnout under member basis', () => {
    const gov = new EqualWeightGovernorModel();
    gov.setRoll([{ id: '0xA' }, { id: '0xB' }, { id: '0xC' }, { id: '0xD' }]);
    gov.createProposal('p1', 'Adopt bylaw');
    gov.castVote('p1', '0xA', true);
    gov.castVote('p1', '0xB', true);
    gov.castVote('p1', '0xC', false);

    const t = gov.tally('p1');
    expect(t.votesFor).toBe(2);
    expect(t.votesAgainst).toBe(1);
    expect(t.eligibleCount).toBe(4);
    expect(t.voterCount).toBe(3);
    expect(t.turnout).toBeCloseTo(0.75, 6);
    expect(t.finalized).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/equalweight-governor-model.test.ts`
Expected: FAIL — `Cannot find module '../equalweight-governor-model'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// contracts/equalweight-governor-model.ts
export type VotingBasis = 'member' | 'unit' | 'share';

export interface EligibleMember {
  id: string;
  units?: number;
  shares?: number;
}

export interface EqualWeightGovernorConfig {
  votingBasis: VotingBasis;
  quorumPercentage: number;
  passThreshold: number;
  committeeSize: number;
  committeeThreshold: number;
}

export interface TallyResult {
  proposalId: string;
  votesFor: number;
  votesAgainst: number;
  eligibleCount: number;
  voterCount: number;
  turnout: number;
  quorumMet: boolean;
  passed: boolean;
  finalized: boolean;
}

interface Proposal {
  id: string;
  title: string;
  closesAtWeek?: number;
  votes: Map<string, boolean>; // voter -> support
}

export class EqualWeightGovernorModel {
  private config: EqualWeightGovernorConfig;
  private roll: Map<string, EligibleMember> = new Map();
  private proposals: Map<string, Proposal> = new Map();

  constructor(config: Partial<EqualWeightGovernorConfig> = {}) {
    this.config = {
      votingBasis: 'member',
      quorumPercentage: 0.5,
      passThreshold: 0.5,
      committeeSize: 3,
      committeeThreshold: 2,
      ...config,
    };
  }

  setRoll(members: EligibleMember[]): void {
    this.roll = new Map(members.map((m) => [m.id, m]));
  }

  createProposal(id: string, title: string, closesAtWeek?: number): void {
    this.proposals.set(id, { id, title, closesAtWeek, votes: new Map() });
  }

  private weightOf(member: EligibleMember): number {
    switch (this.config.votingBasis) {
      case 'unit':
        return member.units ?? 1;
      case 'share':
        return member.shares ?? 1;
      case 'member':
      default:
        return 1;
    }
  }

  castVote(proposalId: string, voter: string, support: boolean): void {
    const proposal = this.proposals.get(proposalId);
    if (!proposal) throw new Error(`Proposal ${proposalId} not found`);
    proposal.votes.set(voter, support);
  }

  tally(proposalId: string): TallyResult {
    const proposal = this.proposals.get(proposalId);
    if (!proposal) throw new Error(`Proposal ${proposalId} not found`);

    let votesFor = 0;
    let votesAgainst = 0;
    for (const [voter, support] of proposal.votes) {
      const member = this.roll.get(voter);
      if (!member) continue;
      const w = this.weightOf(member);
      if (support) votesFor += w;
      else votesAgainst += w;
    }

    const eligibleCount = this.roll.size;
    const voterCount = proposal.votes.size;
    const turnout = eligibleCount > 0 ? voterCount / eligibleCount : 0;

    return {
      proposalId,
      votesFor,
      votesAgainst,
      eligibleCount,
      voterCount,
      turnout,
      quorumMet: false,
      passed: false,
      finalized: false,
    };
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/equalweight-governor-model.test.ts`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
cd PMOVES-ToKenism-Multi
git add integrations/contracts/equalweight-governor-model.ts integrations/contracts/__tests__/equalweight-governor-model.test.ts
git commit -m "feat(gov): EqualWeightGovernor skeleton — roll, proposal, member-basis tally"
```

---

### Task 2: castVote validation — non-roll rejected, one-vote-per-member

**Files:**
- Modify: `PMOVES-ToKenism-Multi/integrations/contracts/equalweight-governor-model.ts` (`castVote`)
- Test: same test file

**Interfaces:**
- Consumes: `castVote(proposalId, voter, support)` from Task 1.
- Produces: `castVote` now throws for a non-roll voter and for a repeat vote by the same member.

- [ ] **Step 1: Write the failing test**

```ts
  it('rejects a voter not on the roll', () => {
    const gov = new EqualWeightGovernorModel();
    gov.setRoll([{ id: '0xA' }]);
    gov.createProposal('p1', 'x');
    expect(() => gov.castVote('p1', '0xSTRANGER', true)).toThrow(/roll|eligible/i);
  });

  it('rejects a second vote by the same member (one vote per member)', () => {
    const gov = new EqualWeightGovernorModel();
    gov.setRoll([{ id: '0xA' }]);
    gov.createProposal('p1', 'x');
    gov.castVote('p1', '0xA', true);
    expect(() => gov.castVote('p1', '0xA', false)).toThrow(/already voted/i);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/equalweight-governor-model.test.ts`
Expected: FAIL — the two new tests do not throw.

- [ ] **Step 3: Write minimal implementation** (replace `castVote` body)

```ts
  castVote(proposalId: string, voter: string, support: boolean): void {
    const proposal = this.proposals.get(proposalId);
    if (!proposal) throw new Error(`Proposal ${proposalId} not found`);
    if (!this.roll.has(voter)) {
      throw new Error(`${voter} is not on the eligible roll`);
    }
    if (proposal.votes.has(voter)) {
      throw new Error(`${voter} has already voted on ${proposalId}`);
    }
    proposal.votes.set(voter, support);
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/equalweight-governor-model.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd PMOVES-ToKenism-Multi
git add integrations/contracts/equalweight-governor-model.ts integrations/contracts/__tests__/equalweight-governor-model.test.ts
git commit -m "feat(gov): castVote rejects non-roll voters and double votes"
```

---

### Task 3: Voting basis — member vs share contrast

**Files:**
- Test only (weighting already implemented in Task 1's `weightOf`; this task proves the basis knob and locks the contrast).

**Interfaces:**
- Consumes: `new EqualWeightGovernorModel({ votingBasis })`, `tally`.
- Produces: (no new API) — a regression guard proving `member` vs `share` diverge.

- [ ] **Step 1: Write the failing test**

```ts
  it('member basis ignores shares; share basis lets a whale dominate', () => {
    const roll = [{ id: '0xWHALE', shares: 1000 }, { id: '0xA' }, { id: '0xB' }];

    const byMember = new EqualWeightGovernorModel({ votingBasis: 'member' });
    byMember.setRoll(roll);
    byMember.createProposal('p', 'x');
    byMember.castVote('p', '0xWHALE', true);
    byMember.castVote('p', '0xA', false);
    byMember.castVote('p', '0xB', false);
    const m = byMember.tally('p');
    expect(m.votesFor).toBe(1); // whale counts as one member
    expect(m.votesAgainst).toBe(2);

    const byShare = new EqualWeightGovernorModel({ votingBasis: 'share' });
    byShare.setRoll(roll);
    byShare.createProposal('p', 'x');
    byShare.castVote('p', '0xWHALE', true);
    byShare.castVote('p', '0xA', false);
    byShare.castVote('p', '0xB', false);
    const s = byShare.tally('p');
    expect(s.votesFor).toBe(1000); // plutocratic: whale dominates
    expect(s.votesAgainst).toBe(2);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/equalweight-governor-model.test.ts`
Expected: PASS immediately IF Task 1's `weightOf` is correct. If it does not pass, `weightOf` is wrong — fix it. (This test is a characterization guard on the basis knob; it exercises the previously-untested `share`/whale path.)

- [ ] **Step 3: (only if Step 2 failed) fix `weightOf`** to match the Global Constraints weighting. Otherwise no code change.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/equalweight-governor-model.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd PMOVES-ToKenism-Multi
git add integrations/contracts/__tests__/equalweight-governor-model.test.ts
git commit -m "test(gov): member vs share basis contrast (why stake-voting is rejected)"
```

---

### Task 4: Quorum (roll-%) + passed logic

**Files:**
- Modify: `PMOVES-ToKenism-Multi/integrations/contracts/equalweight-governor-model.ts` (`tally` — set `quorumMet` and `passed`)
- Test: same test file

**Interfaces:**
- Consumes: `tally` from Task 1.
- Produces: `tally` now returns real `quorumMet` (roll-% turnout) and `passed` (quorum met AND for-share ≥ passThreshold).

- [ ] **Step 1: Write the failing test**

```ts
  it('fails quorum below the roll-percentage threshold even if unanimous', () => {
    const gov = new EqualWeightGovernorModel({ quorumPercentage: 0.5 });
    gov.setRoll([{ id: '0xA' }, { id: '0xB' }, { id: '0xC' }, { id: '0xD' }]);
    gov.createProposal('p', 'x');
    gov.castVote('p', '0xA', true); // 1/4 = 25% turnout < 50%
    const t = gov.tally('p');
    expect(t.quorumMet).toBe(false);
    expect(t.passed).toBe(false);
  });

  it('passes on majority once quorum is met', () => {
    const gov = new EqualWeightGovernorModel({ quorumPercentage: 0.5, passThreshold: 0.5 });
    gov.setRoll([{ id: '0xA' }, { id: '0xB' }, { id: '0xC' }, { id: '0xD' }]);
    gov.createProposal('p', 'x');
    gov.castVote('p', '0xA', true);
    gov.castVote('p', '0xB', true);
    gov.castVote('p', '0xC', false); // 3/4 turnout, for-share 2/3 >= 0.5
    const t = gov.tally('p');
    expect(t.quorumMet).toBe(true);
    expect(t.passed).toBe(true);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/equalweight-governor-model.test.ts`
Expected: FAIL — `quorumMet`/`passed` are still hard-coded `false` from Task 1.

- [ ] **Step 3: Write minimal implementation** (replace the `return` block in `tally`)

```ts
    const eligibleCount = this.roll.size;
    const voterCount = proposal.votes.size;
    const turnout = eligibleCount > 0 ? voterCount / eligibleCount : 0;
    const quorumMet = turnout >= this.config.quorumPercentage;
    const decided = votesFor + votesAgainst;
    const forShare = decided > 0 ? votesFor / decided : 0;
    const passed = quorumMet && forShare >= this.config.passThreshold;

    return {
      proposalId,
      votesFor,
      votesAgainst,
      eligibleCount,
      voterCount,
      turnout,
      quorumMet,
      passed,
      finalized: false,
    };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/equalweight-governor-model.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
cd PMOVES-ToKenism-Multi
git add integrations/contracts/equalweight-governor-model.ts integrations/contracts/__tests__/equalweight-governor-model.test.ts
git commit -m "feat(gov): roll-percentage quorum + majority pass logic"
```

---

### Task 5: M-of-N finalize gate + TallySigner (the anti-forgery property)

**Files:**
- Modify: `PMOVES-ToKenism-Multi/integrations/contracts/equalweight-governor-model.ts` (add `TallySigner`, `TallyAttestation`, `MockThresholdSigner`, `setCommittee`, `finalize`; inject signer in constructor)
- Test: same test file

**Interfaces:**
- Consumes: `tally` (Task 1/4), `EqualWeightGovernorConfig.committeeThreshold`.
- Produces: `setCommittee(memberIds: string[]): void`; `finalize(proposalId: string, approvers: string[]): TallyResult` (returns `{...tally, finalized:true, attestation}`); `TallySigner` interface `sign(tally, approvers, committee, threshold): TallyAttestation`; `MockThresholdSigner` (default injected); `TallyAttestation { algo, approvers, signature }`.

- [ ] **Step 1: Write the failing test**

```ts
import {
  EqualWeightGovernorModel,
  MockThresholdSigner,
} from '../equalweight-governor-model';

// ...inside describe:
  describe('committee finalize (M-of-N)', () => {
    const build = () => {
      const gov = new EqualWeightGovernorModel({ committeeThreshold: 2, committeeSize: 3 });
      gov.setRoll([{ id: '0xA' }, { id: '0xB' }]);
      gov.setCommittee(['0xC1', '0xC2', '0xC3']);
      gov.createProposal('p', 'x');
      gov.castVote('p', '0xA', true);
      gov.castVote('p', '0xB', true);
      return gov;
    };

    it('a single approver cannot finalize (no single party can forge)', () => {
      const gov = build();
      expect(() => gov.finalize('p', ['0xC1'])).toThrow(/threshold|approv/i);
    });

    it('k valid committee approvers finalize and attest', () => {
      const gov = build();
      const result = gov.finalize('p', ['0xC1', '0xC2']);
      expect(result.finalized).toBe(true);
      expect(result.attestation?.approvers).toEqual(['0xC1', '0xC2']);
      expect(result.attestation?.algo).toBe('stub-mofn');
    });

    it('rejects an approver who is not on the committee', () => {
      const gov = build();
      expect(() => gov.finalize('p', ['0xC1', '0xNOTCOMMITTEE'])).toThrow(/committee/i);
    });

    it('MockThresholdSigner throws below threshold', () => {
      const signer = new MockThresholdSigner();
      const tally = { proposalId: 'p' } as any;
      expect(() => signer.sign(tally, ['0xC1'], ['0xC1', '0xC2', '0xC3'], 2)).toThrow(/threshold/i);
    });
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/equalweight-governor-model.test.ts`
Expected: FAIL — `MockThresholdSigner`, `setCommittee`, `finalize` do not exist.

- [ ] **Step 3: Write minimal implementation**

Add to `equalweight-governor-model.ts` (types near the top, after `TallyResult`):

```ts
export interface TallyAttestation {
  algo: string;
  approvers: string[];
  signature: string;
}

export interface TallySigner {
  sign(
    tally: TallyResult,
    approvers: string[],
    committee: string[],
    threshold: number
  ): TallyAttestation;
}

// Sim stub: models the k-of-n GATE (the anti-forgery property); the signature
// bytes are stubbed. Real Ed25519/FROST implements this same interface later.
export class MockThresholdSigner implements TallySigner {
  sign(
    tally: TallyResult,
    approvers: string[],
    committee: string[],
    threshold: number
  ): TallyAttestation {
    const unique = Array.from(new Set(approvers));
    for (const a of unique) {
      if (!committee.includes(a)) {
        throw new Error(`Approver ${a} is not on the committee`);
      }
    }
    if (unique.length < threshold) {
      throw new Error(
        `Below committee threshold: ${unique.length} approvers < ${threshold}`
      );
    }
    return { algo: 'stub-mofn', approvers: unique, signature: `stub:${tally.proposalId}` };
  }
}
```

Add the `TallyResult.attestation` field (make it optional):

```ts
export interface TallyResult {
  proposalId: string;
  votesFor: number;
  votesAgainst: number;
  eligibleCount: number;
  voterCount: number;
  turnout: number;
  quorumMet: boolean;
  passed: boolean;
  finalized: boolean;
  attestation?: TallyAttestation;
}
```

Add a committee field + inject the signer in the class (constructor gains a second param):

```ts
  private committee: Set<string> = new Set();
  private signer: TallySigner;

  constructor(
    config: Partial<EqualWeightGovernorConfig> = {},
    signer: TallySigner = new MockThresholdSigner()
  ) {
    this.config = {
      votingBasis: 'member',
      quorumPercentage: 0.5,
      passThreshold: 0.5,
      committeeSize: 3,
      committeeThreshold: 2,
      ...config,
    };
    this.signer = signer;
  }

  setCommittee(memberIds: string[]): void {
    this.committee = new Set(memberIds);
  }

  finalize(proposalId: string, approvers: string[]): TallyResult {
    const result = this.tally(proposalId);
    const attestation = this.signer.sign(
      result,
      approvers,
      Array.from(this.committee),
      this.config.committeeThreshold
    );
    return { ...result, finalized: true, attestation };
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/equalweight-governor-model.test.ts`
Expected: PASS (10 tests).

- [ ] **Step 5: Run the full submodule suite (no regression)**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest`
Expected: all suites pass (CoopGovernor and every other model untouched).

- [ ] **Step 6: Commit**

```bash
cd PMOVES-ToKenism-Multi
git add integrations/contracts/equalweight-governor-model.ts integrations/contracts/__tests__/equalweight-governor-model.test.ts
git commit -m "feat(gov): k-of-n committee finalize gate + TallySigner (no single party can forge)"
```

---

## After the plan (open the PR)

```bash
cd PMOVES-ToKenism-Multi
git push -u origin feat/equalweight-governor
gh pr create --base PMOVES.AI-Edition-Hardened --head feat/equalweight-governor \
  --title "feat(gov): EqualWeightGovernor — equal-weight tally + roll-% quorum + M-of-N finalize" \
  --body "Stage 1 of the #5 governance replacement (spec: docs/superpowers/specs/2026-07-17-equalweight-governor-design.md). Drop-in equal-weight (member/unit/share) governor with roll-% quorum and a modeled k-of-n committee finalize gate (crypto stubbed behind TallySigner). CoopGovernor left intact as the sweep contrast. Independent review + TDD-green expected."
```

Then: independent code-review (like #53–#59), fold fixes back, admin-merge.

## Self-Review

**Spec coverage:** Components (Task 1/5) ✓; API/data flow (Tasks 1,2,4,5) ✓; voting basis member/unit/share (Task 1 `weightOf` + Task 3 contrast) ✓; roll-% quorum (Task 4) ✓; passed logic (Task 4) ✓; M-of-N gate + TallySigner + MockThresholdSigner (Task 5) ✓; all 6 spec tests mapped (Task1 tally, Task2 non-roll+double, Task3 basis contrast, Task4 quorum, Task5 M-of-N + non-committee) ✓; CoopGovernor untouched (Global Constraints) ✓. `unit` basis is implemented (Task 1) though only `member`/`share` are directly asserted — acceptable (the switch covers it; a unit test can be added later if desired).

**Placeholder scan:** none — every code step has complete code; every run step has an exact command + expected result.

**Type consistency:** `TallyResult` fields identical across Tasks 1/4/5; `finalize`/`sign`/`setCommittee`/`setRoll`/`castVote`/`tally` signatures consistent between the Interfaces blocks and the code; `MockThresholdSigner.sign(tally, approvers, committee, threshold)` matches the governor's `finalize` call. `weightOf` weighting matches Global Constraints.
