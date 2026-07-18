# MemberRegistry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A committee-controlled eligible-member roll where enrol and revoke each require k-of-n committee approval, decoupled from tokens, whose `roll()` feeds `EqualWeightGovernor.setRoll()`.

**Architecture:** One `MemberRegistryModel` class in the ToKenism submodule. A shared private `assertCommitteeApproval(approvers)` M-of-N gate (dedupe, committee-membership, threshold) guards both `enrol` and `revoke`. Members are stored as `MembershipCredential`s; `roll()` returns active members' `EligibleMember` (imported from the stage-1 governor). Crypto is stubbed (`signature: 'stub-mofn:<id>'`).

**Tech Stack:** TypeScript, Jest (ts-jest). Submodule `PMOVES-ToKenism-Multi`, tests from `integrations/`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-17-member-registry-design.md`.
- All new code in `PMOVES-ToKenism-Multi/integrations/contracts/`; do NOT modify `equalweight-governor-model.ts` (import from it only) or any other existing file.
- Config defaults: `committeeSize 3`, `committeeThreshold 2`. Constructor MUST validate `1 <= committeeThreshold <= committeeSize` (throw otherwise).
- M-of-N gate: dedupe approvers; every approver must be on the committee; `distinct approvers >= committeeThreshold`; else throw.
- `roll()` returns ONLY active members. `isEligible(id)` is true iff an active membership exists.
- Import `EligibleMember` from `./equalweight-governor-model`; do not redefine it.
- Tests run from `PMOVES-ToKenism-Multi/integrations/`: `npx jest contracts/__tests__/member-registry-model.test.ts`.
- Set git identity in the submodule before committing (mirror parent) — already done by the controller in Setup.

## Setup (controller does once, before Task 1)

From `PMOVES-ToKenism-Multi/`:
```bash
git checkout PMOVES.AI-Edition-Hardened && git pull --ff-only origin PMOVES.AI-Edition-Hardened
git checkout -b feat/member-registry PMOVES.AI-Edition-Hardened
git config user.name "$(git -C .. config user.name)"; git config user.email "$(git -C .. config user.email)"
```

## File Structure

- **Create:** `PMOVES-ToKenism-Multi/integrations/contracts/member-registry-model.ts` — `MemberRegistryModel`, `MembershipCredential`, `MemberRegistryConfig`.
- **Create:** `PMOVES-ToKenism-Multi/integrations/contracts/__tests__/member-registry-model.test.ts` — all tests.

---

### Task 1: Enrollment with the M-of-N committee gate + config validation

**Files:**
- Create: `PMOVES-ToKenism-Multi/integrations/contracts/member-registry-model.ts`
- Test: `PMOVES-ToKenism-Multi/integrations/contracts/__tests__/member-registry-model.test.ts`

**Interfaces:**
- Consumes: `EligibleMember` from `./equalweight-governor-model` (`{ id: string; units?: number; shares?: number }`).
- Produces: `MemberRegistryModel` with `constructor(config?: Partial<MemberRegistryConfig>)`, `setCommittee(ids: string[]): void`, `enrol(member: EligibleMember, approvers: string[]): MembershipCredential`, `isEligible(id: string): boolean`. Types `MemberRegistryConfig`, `MembershipCredential`.

- [ ] **Step 1: Write the failing test**

```ts
// contracts/__tests__/member-registry-model.test.ts
import { MemberRegistryModel } from '../member-registry-model';

describe('MemberRegistryModel', () => {
  const withCommittee = (config = {}) => {
    const r = new MemberRegistryModel(config);
    r.setCommittee(['0xC1', '0xC2', '0xC3']);
    return r;
  };

  it('enrol requires k-of-n committee approval', () => {
    const r = withCommittee();
    expect(() => r.enrol({ id: '0xA' }, ['0xC1'])).toThrow(/threshold|approv/i);
    const cred = r.enrol({ id: '0xA' }, ['0xC1', '0xC2']);
    expect(cred.status).toBe('active');
    expect(r.isEligible('0xA')).toBe(true);
  });

  it('rejects a duplicate approver (dedupe below threshold)', () => {
    const r = withCommittee();
    expect(() => r.enrol({ id: '0xA' }, ['0xC1', '0xC1'])).toThrow(/threshold/i);
  });

  it('rejects an approver not on the committee', () => {
    const r = withCommittee();
    expect(() => r.enrol({ id: '0xA' }, ['0xC1', '0xSTRANGER'])).toThrow(/committee/i);
  });

  it('validates committee config bounds', () => {
    expect(() => new MemberRegistryModel({ committeeThreshold: 0 })).toThrow();
    expect(() => new MemberRegistryModel({ committeeThreshold: 4, committeeSize: 3 })).toThrow();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/member-registry-model.test.ts`
Expected: FAIL — `Cannot find module '../member-registry-model'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// contracts/member-registry-model.ts
import { EligibleMember } from './equalweight-governor-model';

export interface MemberRegistryConfig {
  committeeSize: number;
  committeeThreshold: number;
}

export interface MembershipCredential {
  member: EligibleMember;
  status: 'active' | 'revoked';
  approvers: string[];
  signature: string;
}

export class MemberRegistryModel {
  private config: MemberRegistryConfig;
  private committee: Set<string> = new Set();
  private members: Map<string, MembershipCredential> = new Map();

  constructor(config: Partial<MemberRegistryConfig> = {}) {
    this.config = { committeeSize: 3, committeeThreshold: 2, ...config };
    if (this.config.committeeThreshold < 1) {
      throw new Error('committeeThreshold must be >= 1');
    }
    if (this.config.committeeThreshold > this.config.committeeSize) {
      throw new Error('committeeThreshold must be <= committeeSize');
    }
  }

  setCommittee(ids: string[]): void {
    this.committee = new Set(ids);
  }

  private assertCommitteeApproval(approvers: string[]): string[] {
    const unique = Array.from(new Set(approvers));
    for (const a of unique) {
      if (!this.committee.has(a)) {
        throw new Error(`Approver ${a} is not on the committee`);
      }
    }
    if (unique.length < this.config.committeeThreshold) {
      throw new Error(
        `Below committee threshold: ${unique.length} approvers < ${this.config.committeeThreshold}`
      );
    }
    return unique;
  }

  enrol(member: EligibleMember, approvers: string[]): MembershipCredential {
    const unique = this.assertCommitteeApproval(approvers);
    const credential: MembershipCredential = {
      member,
      status: 'active',
      approvers: unique,
      signature: `stub-mofn:${member.id}`,
    };
    this.members.set(member.id, credential);
    return credential;
  }

  isEligible(id: string): boolean {
    return this.members.get(id)?.status === 'active';
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/member-registry-model.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd PMOVES-ToKenism-Multi
git add integrations/contracts/member-registry-model.ts integrations/contracts/__tests__/member-registry-model.test.ts
git commit -m "feat(gov): MemberRegistry enrol with k-of-n committee gate + config validation"
```

---

### Task 2: Revoke (M-of-N) + roll()

**Files:**
- Modify: `PMOVES-ToKenism-Multi/integrations/contracts/member-registry-model.ts` (add `revoke`, `roll`)
- Test: same test file

**Interfaces:**
- Consumes: `assertCommitteeApproval`, `members` from Task 1.
- Produces: `revoke(memberId: string, approvers: string[]): void`; `roll(): EligibleMember[]`.

- [ ] **Step 1: Write the failing test**

```ts
  it('revoke requires k-of-n and removes the member from the roll', () => {
    const r = withCommittee();
    r.enrol({ id: '0xA' }, ['0xC1', '0xC2']);
    expect(() => r.revoke('0xA', ['0xC1'])).toThrow(/threshold/i);
    r.revoke('0xA', ['0xC1', '0xC2']);
    expect(r.isEligible('0xA')).toBe(false);
    expect(r.roll().map((m) => m.id)).not.toContain('0xA');
  });

  it('rejects revoking a non-member', () => {
    const r = withCommittee();
    expect(() => r.revoke('0xNOBODY', ['0xC1', '0xC2'])).toThrow(/not an active member/i);
  });

  it('roll() returns only active members', () => {
    const r = withCommittee();
    r.enrol({ id: '0xA' }, ['0xC1', '0xC2']);
    r.enrol({ id: '0xB' }, ['0xC1', '0xC2']);
    r.revoke('0xB', ['0xC1', '0xC2']);
    expect(r.roll().map((m) => m.id).sort()).toEqual(['0xA']);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/member-registry-model.test.ts`
Expected: FAIL — `r.revoke is not a function` / `r.roll is not a function`.

- [ ] **Step 3: Write minimal implementation** (add these two methods to the class)

```ts
  revoke(memberId: string, approvers: string[]): void {
    const existing = this.members.get(memberId);
    if (!existing || existing.status !== 'active') {
      throw new Error(`${memberId} is not an active member`);
    }
    this.assertCommitteeApproval(approvers);
    existing.status = 'revoked';
  }

  roll(): EligibleMember[] {
    return Array.from(this.members.values())
      .filter((c) => c.status === 'active')
      .map((c) => c.member);
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/member-registry-model.test.ts`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
cd PMOVES-ToKenism-Multi
git add integrations/contracts/member-registry-model.ts integrations/contracts/__tests__/member-registry-model.test.ts
git commit -m "feat(gov): MemberRegistry revoke (M-of-N) + active-only roll()"
```

---

### Task 3: Integration — registry roll() drives the governor

**Files:**
- Test only: `PMOVES-ToKenism-Multi/integrations/contracts/__tests__/member-registry-model.test.ts`

**Interfaces:**
- Consumes: `MemberRegistryModel.roll()` (Task 2), `EqualWeightGovernorModel` `setRoll`/`createProposal`/`castVote`/`tally` (stage 1, already merged).

- [ ] **Step 1: Write the failing test**

```ts
import { EqualWeightGovernorModel } from '../equalweight-governor-model';

  it('roll() drives the governor: only enrolled members can vote', () => {
    const r = withCommittee();
    r.enrol({ id: '0xA' }, ['0xC1', '0xC2']);
    r.enrol({ id: '0xB' }, ['0xC1', '0xC2']);

    const gov = new EqualWeightGovernorModel();
    gov.setRoll(r.roll());
    gov.createProposal('p', 'x');
    gov.castVote('p', '0xA', true);
    gov.castVote('p', '0xB', false);

    const t = gov.tally('p');
    expect(t.eligibleCount).toBe(2);
    expect(t.votesFor).toBe(1);
    expect(t.votesAgainst).toBe(1);
    // a member NOT on the registry roll is rejected by the governor
    expect(() => gov.castVote('p', '0xSTRANGER', true)).toThrow(/roll|eligible/i);
  });
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest contracts/__tests__/member-registry-model.test.ts`
Expected: PASS immediately IF `roll()` returns the right shape (both models already exist). This is an integration/characterization test proving the roll wires into the governor; no new production code is expected. If it FAILS, the `EligibleMember` shape from `roll()` does not match what the governor expects — fix `roll()` to return `EligibleMember` objects.

- [ ] **Step 3: (only if Step 2 failed) fix `roll()`** to return `EligibleMember` objects. Otherwise no code change.

- [ ] **Step 4: Run the full submodule suite (no regression)**

Run: `cd PMOVES-ToKenism-Multi/integrations && npx jest`
Expected: all suites pass; `equalweight-governor-model.ts` and every other existing file untouched.

- [ ] **Step 5: Commit**

```bash
cd PMOVES-ToKenism-Multi
git add integrations/contracts/__tests__/member-registry-model.test.ts
git commit -m "test(gov): MemberRegistry roll() drives EqualWeightGovernor end-to-end"
```

---

## After the plan (open the PR)

```bash
cd PMOVES-ToKenism-Multi
git push -u origin feat/member-registry
gh pr create --base PMOVES.AI-Edition-Hardened --head feat/member-registry \
  --title "feat(gov): MemberRegistry — committee-controlled eligibility roll (M-of-N enrol/revoke)" \
  --body "Stage 3 of the #5 governance replacement (spec: docs/superpowers/specs/2026-07-17-member-registry-design.md). Committee k-of-n enrol/revoke (closes the enrollment chokepoint 08 flags), decoupled from tokens; roll() drives EqualWeightGovernor.setRoll(). Crypto stubbed. Independent review + TDD-green expected."
```

Then: independent code-review, fold fixes back, admin-merge.

## Self-Review

**Spec coverage:** enrol M-of-N (Task 1) ✓; revoke M-of-N (Task 2) ✓; isEligible (Task 1) ✓; roll() active-only (Task 2) ✓; config validation (Task 1) ✓; duplicate/non-committee approver (Task 1) ✓; roll→governor integration (Task 3) ✓; decoupled from tokens (no token import anywhere — Global Constraints) ✓; all 7 spec tests mapped (T1: enrol+dup+non-committee+config, T2: revoke+non-member+roll, T3: integration) ✓; no existing model modified ✓.

**Placeholder scan:** none — every code step is complete; every run step has command + expected result.

**Type consistency:** `MembershipCredential`/`MemberRegistryConfig` identical across tasks; `enrol`/`revoke`/`roll`/`isEligible`/`setCommittee`/`assertCommitteeApproval` signatures consistent between Interfaces blocks and code; `roll()` returns `EligibleMember[]` matching the governor's `setRoll(members: EligibleMember[])` from stage 1.
