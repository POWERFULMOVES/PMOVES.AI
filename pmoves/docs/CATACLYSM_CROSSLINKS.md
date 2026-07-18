# Cataclysm Studios Crosslinks — Crystallized Spec Bridge

**Layer:** L4 Vision ⇄ L3 Implementation
**Status:** DRAFT — counsel-gated (Howey/securities + NY cooperative-corporation law)
**Last Updated:** 2026-07-17 (crystallized via a 9-agent fan-out reconciling `CATACLYSM_STUDIOS_INC/` vision docs against built code)

> Bridge document linking the Cataclysm Studios Inc. business vision (`CATACLYSM_STUDIOS_INC/`, L1–L5 taxonomy) to the PMOVES.AI technical implementation. **This revision reconciles the documented spec against what is actually built** and supersedes the 2026-03-11 vision→tech map, which predated the token-structure refresh, the commitment primitive, the Dirichlet-distribution wiring, and the Fordham decision records.

---

## The core resolution (read first)

The operator asked "how many tokens does the canonical design have — the trinity?" **There is no single trinity. There are two competing designs, and the built one is not the documented one.**

- **DOCUMENTED (authoritative in the newest DAO docs — Constitution v0.1, Fordham Proposal v0.1):** a **three-token trinity** — `$CAT` (governance ERC-20), `$WORK` (reputation SBT), `$CRED` (spend-limited local credit). **This has zero code.**
- **BUILT (what actually exists):** a **dual-token core** — `FoodUSD/FUSD` + `GroToken/GRO` — plus three on-chain *mechanics* (GroVault, CoopGovernor, GroupPurchase) and an off-chain Dirichlet attribution engine. This is the **earlier** design the DAO docs claim to have superseded.

So the built tokens are the design the board-facing docs say they replaced. Notably, the decided refresh direction (sever governance from stake, make earned credit soul-bound) is already moving the built design *toward* the documented trinity (`$WORK` = soul-bound reputation; `$CAT` = governance separated from utility) — but no mapping doc had ever connected them.

> **DECISION (2026-07-17) — Path A adopted.** The built **FoodUSD + GroToken** dual core is **canonical for the simulation / utility layer now**. `$CAT/$WORK/$CRED` is the **target governance-layer redesign — not yet built**. GRO evolves toward soul-bound `$WORK` via the refresh; governance moves off CoopGovernor toward the equal-weight ballot. This resolves Open Decision #1.

**Target mapping — built (canonical now) ⇄ documented trinity (to build):**

| Documented (target) | Built analogue (canonical now) | Redesign path |
|---|---|---|
| `$CRED` (spend-limited vendor credit) | **FoodUSD / FUSD** (free-transfer 1:1 USD) | later: narrow transferability toward vendor-locked spend credit (Open Decision #7) |
| `$WORK` (soul-bound reputation SBT) | **earned GroToken** via Dirichlet/commitment attribution | later: make earned credit soul-bound / split an SBT (Open Decision #4) |
| `$CAT` (governance ERC-20 / Token House) | **CoopGovernor + GroVault** (stake-weighted — non-canonical for binding votes) | replace with equal-weight ballot; `$CAT` is a *future* capital-house layer, never the binding member vote |

---

## Trinity of tokens

### Built canonical core (exists in code)

| Token | Role | Built | Standing vs direction |
|---|---|---|---|
| **FoodUSD / FUSD** | Stablecoin, **utility-only** medium of exchange. 1:1 USD peg, treasury-only mint, burn-on-spend. Feeds group-buy pooling + supplier payout. | `FoodUSD.sol` (ERC20+Ownable) + `foodusd-model.ts` (pegValue 1.0). | ALIGNED. Nearest analogue to documented `$CRED`, but free-transfer 1:1 USD, not a spend-limited vendor credit. |
| **GroToken / GRO** | Governance + reward token. Staked into GroVault to derive voting power. Sim USD value $2.00. | `GroToken.sol` (ERC20+Ownable, onlyOwner mint) + `grotoken-model.ts` (code-invented 1,000,000 cap). | ALIGNED with earlier spec; **VIOLATES** refresh direction — freely transferable, no soulbound guard; live distribution still Gaussian. |

### On-chain mechanics (not tokens)

| Mechanic | Role | Built | Standing |
|---|---|---|---|
| **GroVault** (ve-lock staking) | Locks GRO 1–4 yrs → `V_i = √(amount)·(1+0.5·(years−1))`. veToken = locked STATE of GRO. | `GroVault.sol` `votingPower()`. Interest/APR is **sim-only** (`grovault-model.ts`), absent on-chain. | Math ALIGNED with v2 spec; rewards simulated only. |
| **CoopGovernor** (governance) | Quadratic vote cost `rawVotes²` vs GroVault power; execute gated by `proposalThreshold` + `forVotes>againstVotes`; single chair admin. | `CoopGovernor.sol` + tests. TS model adds a quorum-%-of-voting-power the `.sol` lacks. | Mechanics ALIGNED with v2 but **plutocratic**. **Must not ship for a binding vote.** |
| **GroupPurchase** (group-buy escrow) | Pool FoodUSD; auto-execute at target; pay supplier; refund on deadline. Sim adds 15% rebate + min-5 gate. | `GroupPurchase.sol` + `grouppurchase-model.ts`. | ALIGNED with the group-buy through-line. |

### Off-chain economic layer

| Model | Role | Built | Standing |
|---|---|---|---|
| **Dirichlet attribution** | Fair-share primitive. `smoothingAlpha=0.1` ⇒ every contributor NON-ZERO (D12); weights sum to 1; 12-wk decay. | `chit/dirichlet-weights.ts`. `distributeByAttribution()` wired to it exists but the live coordinator still calls Gaussian. | ALIGNED with intent. The "one wire" is unfinished. |
| **Commitment** | "agree → keep → earn attribution" escrow feeding AttributionRecords. | `commitment-model.ts`, hardened (merged PR #54). **Ahead of doc.** | BUILT-NOT-SPECCED. No dispute-cure path for `broken`. |
| **LoyaltyPoints** | Streak bonuses (10%/wk cap 100%), 5%/wk decay, redeem 100→1 GRO. | `loyaltypoints-model.ts`, wired. Doc calls it "named, not built." | BUILT-NOT-SPECCED. Not in vision spec. |
| **RewardsPool** | 0.1% tx fee + staking-boosted epoch distribution (4-wk, 1.5×, min 1 GRO). | `rewardspool-model.ts`, wired. Doc calls it "named, not built." | BUILT-NOT-SPECCED. Re-couples reward to stake — tension with the direction. |

### Documented trinity (authoritative in newest DAO docs, ZERO code)

| Token | Role | Built |
|---|---|---|
| **`$CAT`** | ERC-20 governance / Token House (capital). Elect stewards, budgets, strategy. | **Not built.** |
| **`$WORK`** | Non-transferable reputation **SBT** / Citizen House vote weight. Soul-bound proof-of-work. | **Not built** (no SBT mechanism). |
| **`$CRED`** | Stable, **spend-limited**, vendor-redeemable local credit. Not free-floating. | **Not built.** |

---

## Economic mechanics (contribution → attribution → distribution)

1. **Contribution.** Producers/operators supply goods or verified workloads (OCR/RAG, transcode, mesh exit-node bandwidth). Group-buy pooling captures bulk savings, booked as community surplus ("the money doesn't leave the building").
2. **Attribution.** Recorded contribution → **Dirichlet weights** (`smoothingAlpha=0.1`, 12-week decay). **D12 invariant:** passive/low-activity members never fall to zero standing. The **Commitment primitive** feeds AttributionRecords into this layer (commitment-first: agree → keep → earn).
3. **Distribution.** `distributeByAttribution()` mints GRO proportional to a single normalized Dirichlet attribution (Σweight≈1, throws otherwise to avoid N× over-mint). **DONE (PR #55, pending merge):** `contract-coordinator.processWeek()` now drives the mint from kept-commitment attribution (each household keeps a flat weekly commitment → Dirichlet → distribute), retiring the Gaussian `distributeWeekly` draw from the sim flow. Distribution is now deterministic and contribution-anchored. Flat per-capita share is the sim default, swappable for a real contribution measure.
4. **Rewards/yield.** GroVault interest/APR and RewardsPool epoch payouts exist in TS sim only; on-chain GroVault returns principal-only. Staking-based reward re-couples to stake — in tension with the sever-from-stake direction.

---

## Governance

**Built:** single-chamber **CoopGovernor** — quadratic vote cost `rawVotes²` charged against **GroVault voting power = √(staked GRO) × lock-multiplier**. Execution gated on flat `proposalThreshold` + `forVotes>againstVotes` + period-ended. One chairperson admin. This is **stake-weighted / plutocratic**.

**Required (Fordham + refresh direction), NOT built:**
- **Equal-weight** one-member/one-unit/per-share voting — stake/token weight MUST NEVER translate into vote weight.
- **Quorum as a percentage of the eligible member roll** — not a flat count, not a percentage of staked voting power.
- **Committee M-of-N threshold-signing** of the tally (FROST/Ed25519, non-operator committee) replacing single-operator **symmetric HMAC** (operator-forgeable — disqualifying for a contested recall).
- **Eligibility credential** (`voter-card.v1`), committee-issued, human-witnessed, **decoupled from Archon minting and the token structure**.
- **Mode A (secret/adversarial)** vs **Mode B (attributable)** separation with a hard **key-unlinkability invariant**; residents authenticate eligibility only and never sign their choice; **paper ballot is a first-class equal path**.

**Documented alternative (unbuilt):** bicameral two-house dual-consent (Token House `$CAT` + Citizen House `$WORK`). ⚠️ The "~500→~750 token" collusion simulation and the Constitution quorum numbers (20/25/60%) are **FABRICATED/unsourced** (Fordham `07` §3.1) and must not be cited as binding.

---

## Fordham pilot boundaries

- The built Fordham records describe an **internet exit-node pooling + self-governance** pilot, **not** the food-cooperative substrate. Food-USD / group-buy / farmers-payment appear only in the upstream vision spec and **must not be represented as built**.
- **Everything binding is DRAFT** pending NY cooperative-corporation counsel. The platform provides transparency/attestation and deterministic tally **only** — it adjudicates nothing and alleges nothing (fraud investigation stays human-led).
- **HMAC-receipted ballots must not be offered as evidence.** A voter-provable receipt is a **coercion instrument** (receipt-freeness) — an anti-protection, independent of cryptography.
- **Disenfranchisement guardrail:** no crypto-credential/device prerequisite may exclude elderly members; paper equal path + non-operator recovery required.
- All dollar anchors ($5 product / $10 due / $35 premium) are DRAFT; reconcile to one adopted rate via the Committee/board.

---

## Spec ⇄ code gap matrix

| Item | Spec | Code | Verdict |
|---|---|---|---|
| `$CAT / $WORK / $CRED` trinity | Authoritative (newest DAO docs) | Zero code | **Specced-not-built (high)** |
| Soul-bound reputation | Required | GRO freely transferable; no SBT | **Specced-not-built / contradiction (high)** |
| Equal-weight vote + roll quorum | Required | Stake-weighted, flat threshold | **Specced-not-built / contradiction (high)** |
| Committee threshold-signing | Required | Single-operator HMAC | **Specced-not-built (high)** |
| Bicameral two-house passage | Required | Single-chamber | **Specced-not-built** |
| ERC-1155 machine-time, OEE multiplier, <15% cap | Required (Fordham) | None | **Specced-not-built** |
| Sector variants, Fame Coin | Documented | None | **Specced-not-built** |
| Dirichlet-wired distribution | Required (§4.3) | Wired in coordinator (PR #55); Gaussian retired from sim flow | **Aligned (pending merge)** |
| FoodUSD + GroToken dual core | Earlier spec | Built + aligned | **Aligned** |
| veToken / QV math | v2 spec | Built exactly | **Aligned** |
| Group-buy escrow | Through-line | Built | **Aligned** |
| LoyaltyPoints, RewardsPool | "named, not built" | Built + wired | **Built-not-specced (doc lags code)** |
| Commitment, `distributeByAttribution` | Future work | Built + hardened (merged) | **Built-not-specced (code ahead)** |
| GroVault APR, FoodUSD spend analytics | None | TS-only | **Built-not-specced** |
| GroToken 1,000,000 cap | Unspecified | Hard-coded | **Built-not-specced** |

---

## Contradictions to resolve

1. **Token suite** (resolve first): documented `$CAT/$WORK/$CRED` vs built `FoodUSD+GroToken`. No mapping doc. Pick one canonical roster.
2. **Governance basis** (disqualifying for pilot): stake-weighted CoopGovernor vs required equal-weight one-member-one-vote.
3. **Soulbound:** GRO freely transferable vs required non-transferable reputation.
4. **Distribution:** Gaussian random live vs required Dirichlet-by-attribution.
5. **Fabricated evidence:** collusion simulation + quorum numbers are unsourced yet appear as MUST boundaries.
6. **Signing primitive:** one HMAC underwriting both trails and ballots is operator-forgeable — self-contradiction inside the built package.
7. **Receipt/coercion:** verifiable individual receipt framed as protection vs shown to be a coercion tool.
8. **Maturity claim:** "L5 production DAO" vs "unaudited Research Track / nothing built."
9. **Built-vs-built:** `.sol` flat threshold vs TS model's (capital-weighted) quorum floor.

---

## Boundaries (binding for new work)

- **Legal/securities (BLOCKING):** Howey/token-characterization unresolved; unqualified 8–20% investor returns appear in docs. No token as investment, none surfaced to real members, until counsel confirms. Both decision records are DRAFT.
- **Decided refresh direction:** sever governance from stake · make earned credit soul-bound · wire distribution to Dirichlet not Gaussian · keep FoodUSD utility-only. Do not reintroduce stake-weighted governance or a tradeable reputation token.
- **Governance:** a binding co-op vote MUST be equal-weight; quorum MUST be % of the eligible roll; CoopGovernor MUST NOT ship as-is.
- **Secret-ballot custody:** residents authenticate eligibility only, never sign choice; private key never operator-custodied; tally threshold-signed by non-operator M-of-N committee; paper is first-class. HMAC-receipted ballots inadmissible.
- **Mode A/B unlinkability (invariant):** eligibility credential decoupled from Archon + token structure; governance never re-coupled to the token layer; a contested secret ballot never runs in attributable Mode B.
- **D12 invariant:** preserve non-zero standing (`smoothingAlpha=0.1`); `distributeByAttribution` needs one normalized attribution (Σweight≈1, tol 1e-6).
- **Anti-extractive / anti-speculation:** resident-owned, value circulates locally, surplus→members; spending token pegged and non-free-floating; governance token separated from utility; FoodUSD utility-only (no store-of-value).
- **Execution floor:** keep `forVotes>=proposalThreshold AND forVotes>againstVotes AND period-ended`; never weaken to `>10` or `>0`.
- **Platform scope:** transparency/records only; no legal authority; no accusations; do not cite the fabricated simulation.
- **Messaging:** label all tokenomics **"pilot"** until audits (vault math, governance griefing, supplier payouts) + treasury multi-sig + Supabase telemetry complete.

---

## Policy variables (woven in — "show where the chips land")

Rather than pre-deciding the open decisions, the sweepable ones are **parameterized as config knobs** (default = current behavior) and measured by a **scenario-sweep harness** (PR #57) that reports Gini / top-holder concentration / D12 per setting. The knob library so far (submodule `PMOVES-ToKenism-Multi`, PRs #53–#59, all TDD-green + independently reviewed):

| Knob | Model | Effect (measured) |
|---|---|---|
| `contributionMeasure` (`flat`/`income`/`foodBudget`) | coordinator | flat→Gini 0; income→Gini 0.38 (concentrates) |
| `maxConcentration` | coordinator | bounds top share; e.g. cap 0.30 → Gini 0.13, floor ↑ |
| `soulbound` | GroToken | GRO non-transferable when on ($WORK direction) |
| `vendorLocked` | FoodUSD | spend-limited toward `$CRED`; escrow/refund exempt |

D12 (every contributor non-zero) holds under all settings. The distribution itself is now commitment-first + Dirichlet (Gaussian retired, PR #55).

## Open decisions (operator)

1. ~~**Canonical roster**~~ ✅ **RESOLVED 2026-07-17 — Path A** (built FoodUSD+GroToken canonical; trinity is the target redesign). Mapping table in "The core resolution" above.
2. **LoyaltyPoints + RewardsPool** — keep / deprecate / spec? *(still open — a dedicated increment: needs staking activity in scenarios + GRO-minting plumbing to show effect; RewardsPool re-couples reward to stake, so the sweep will show it raising concentration.)*
3. ~~**The one wire**~~ ✅ **DONE (PR #55)** — `processWeek` distributes GRO by kept-commitment Dirichlet attribution; Gaussian retired from the sim flow.
4. ~~**GroToken soulbound**~~ 🎛️ **PARAMETERIZED (PR #56)** — `soulbound` knob on GroToken (default off = transferable). Toggle to make earned GRO non-transferable ($WORK direction). Left OPEN as a variable.
5. **Governance replacement** — build equal-weight Ballot + deterministic Tally + committee threshold-signing, or keep CoopGovernor strictly non-binding sim? *(still open — larger build.)*
6. ~~**Concentration cap**~~ 🎛️ **PARAMETERIZED (PR #58)** — `maxConcentration` knob (water-filling; bounds topShare, lowers Gini, raises the floor, D12 held). Supply-cap (invented 1,000,000) ratify/remove still open.
7. ~~**FoodUSD transferability**~~ 🎛️ **PARAMETERIZED (PR #59)** — `vendorLocked` + `approvedVendors` knob (default free-transfer). Toggle to narrow toward the spend-limited `$CRED` model; internal escrow/refund exempt.
8. **Commitment remediation** — define the broken-commitment dispute-cure economy.
9. **Legal sequencing** — which gate first: NY co-op counsel or securities counsel? No binding vote / member-facing token until both clear.
10. **Naming** — retire generic U-Credits/G-Tokens + sector variants as scaffolding, or spec them as a portability abstraction?

---

## Document cross-reference index

### Vision source (`CATACLYSM_STUDIOS_INC/`)

| Document | Location | Layer |
|----------|----------|-------|
| Tokenomics & Smart Contract Design (v2.0) | `L2-DESIGN/tokenomics/…(v2.0).md` | L2 (authoritative token math) |
| pmoves_hybrid_tokens | `L2-DESIGN/tokenomics/pmoves_hybrid_tokens.md` | L2 (`$CAT/$WORK/$CRED`) |
| DAO Constitution v0.1 | `L2-DESIGN/constitution/Cataclysm_DAO_Constitution_v0.1.md` | L2 (bicameral, quorum) |
| Fordham Hill DAO Proposal v0.1 | `L2-DESIGN/proposals/…Fordham_Hill_Proposal_v0.1.md` | L2 |
| Fordham pilot set (6 docs) | `L3-PILOT/fordham/*.md` | L3 |
| TCM Research + FAQ | `L1-FOUNDATION/Cataclysmstudios_Research_SIM_TCM.md`, `…_TCM_FAQ.md` | L1 |

### Built implementation (PMOVES.AI)

| Concept | Implementation | Doc |
|---|---|---|
| Token structure refresh (direction) | — | [TOKEN_STRUCTURE_REFRESH.md](architecture/TOKEN_STRUCTURE_REFRESH.md) |
| Current economic model | — | [TOKENISM_ECONOMIC_MODEL.md](TOKENISM_ECONOMIC_MODEL.md) |
| Dirichlet attribution + distribution | `chit/dirichlet-weights.ts`, `grotoken-model.ts` `distributeByAttribution()` | (merged PR #53) |
| Commitment primitive | `commitment-model.ts` | (merged PR #54) |
| Fordham ballot prior-art | — | [pilots/fordham-hill/07-ballot-prior-art-and-reconciliation.md](pilots/fordham-hill/07-ballot-prior-art-and-reconciliation.md) |
| Voter identity / key custody | — | [pilots/fordham-hill/08-voter-identity-key-custody.md](pilots/fordham-hill/08-voter-identity-key-custody.md) |
| Token/economic contracts | `PMOVES-ToKenism-Multi/integrations/contracts/*.ts`, `contracts/solidity/contracts/*.sol` | — |

---

## Reading path: vision → crystallized reality → implementation

1. **This document** — the crystallized spec + the two-design resolution.
2. **The direction**: [TOKEN_STRUCTURE_REFRESH.md](architecture/TOKEN_STRUCTURE_REFRESH.md) — anti-extractive incentive engine.
3. **The governance/ballot boundaries**: Fordham [07](pilots/fordham-hill/07-ballot-prior-art-and-reconciliation.md) + [08](pilots/fordham-hill/08-voter-identity-key-custody.md).
4. **The code**: `PMOVES-ToKenism-Multi/integrations/contracts/` (token models + Dirichlet + commitment).

---

*Crystallized 2026-07-17 via a 9-agent fan-out (5 extractors over `CATACLYSM_STUDIOS_INC/` L1–L5 → 3 reconcilers against built code → 1 synthesizer). DRAFT — every clause touching a binding vote or a token-as-investment is counsel-gated. Living artifact tracked by [CHIT_CHANGE_TRACKER.md](CHIT_CHANGE_TRACKER.md).*
