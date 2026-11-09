<!-- graphiti:b850-claude phase:token-structure-refresh ts:2026-07-17T13:00:00Z -->

# Token Structure Refresh — Decision Record

> The current token structure carries two layers that contradict each other: a **plutocratic on-chain
> governance/token layer** (stake-locked voting power, a freely-transferable speculative token) and a
> **fair off-chain attribution layer** (Dirichlet, everyone non-zero) that is wired to nothing. This
> record decides the refresh direction: **value and standing come from real, agreed, kept commitments —
> not from capital held, locked, traded, or exchanged.** The structure is anti-extractive,
> anti-rent-seeking, anti-money-changing, anti-speculative — by construction, not by aspiration.
> DRAFT — REQUIRES LEGAL REVIEW (securities).

**Author:** B850-CLAUDE (Knuckles) · **Date:** 2026-07-17
**Current-state source:** [`../TOKENISM_ECONOMIC_MODEL.md`](../TOKENISM_ECONOMIC_MODEL.md) · **Convergence:** [`PMOVES_GRAND_CONVERGENCE.md`](PMOVES_GRAND_CONVERGENCE.md) (ToKenism = L5 Economics, invariant D12)
**Consumes:** [`../pilots/fordham-hill/08-voter-identity-key-custody.md`](../pilots/fordham-hill/08-voter-identity-key-custody.md) (Mode A / Mode B; **B leads to A**)

## 0. What this is (boundary)

A design decision record, not an implementation and not an offering. Nothing here mints, sells, or
represents a token as an investment; the securities question (§7) is counsel-gated and unresolved. The
structure is group-agnostic — the same engine serves workers forming a union, residents forming a
quorum, or a few people forming a pop-up. Every binding economic claim is DRAFT pending legal/accounting
review.

## 1. Design principles (the invariants the structure must satisfy)

1. **Commitment-first.** Parties **define and agree commitments before acting.** Standing is earned by
   *kept* commitments to real work, not by holding, betting, or gatekeeping.
2. **Anti-extractive / anti-rent-seeking.** No one earns from *owning a position* — no value from
   locking capital to accrue power, from gatekeeping access, or from holding a token and waiting.
3. **Anti-money-changing / anti-speculative.** Credit for contribution is **not a tradeable
   instrument.** You cannot profit by exchanging it, arbitraging it, or speculating on it. Utility
   currency for buying real goods (a stablecoin for real purchases) is fine; a *speculative* token is not.
4. **Grounded in the real.** Value tracks **real demand and real contribution** — real lemonade from
   real buyers, real quorum from real residents, real hosting from real nodes. No financialized
   abstraction stands in for the thing.
5. **Positive-sum, shared surplus.** Take the *prediction* out of prediction markets: minimize
   arbitrage, and where surplus/arbitrage is found, **share it** rather than knock over others'
   sandcastles. Every contributor gets non-zero standing (the existing D12 invariant).
6. **No moats — ships that build ships.** The structure is **generative**: attributed contribution
   funds capability (more nodes, tools, agents) that creates more capability. Compounding commons, not
   defensive enclosure.

**Outcome the structure exists to produce:** increase wealth, reduce inequality, raise living
standards, and free individuals' time — by making collaboration on real, agreed work the thing that pays.

## 2. Current structure (grounded)

**On-chain (`pmoves/contracts/solidity/contracts/`):**
- `CoopGovernor.sol` — quadratic-vote governor; vote cost `rawVotes²` (`:72`) checked against
  `vault.votingPower(msg.sender)` (`:73`); flat numeric quorum (`:96`); `onlyChair` admin.
- `GroVault.sol` — stake-and-lock (1–4 yr); `votingPower() = √(stakedAmount) × lockDurationBonus`
  (`:103-104`), zero if unlocked. **Power is bought with capital and time-lock.**
- `GroToken.sol` — `ERC20` + `Ownable`; `mint()` is `onlyOwner` (`:13`), **freely transferable**, no
  soulbound restriction.
- `FoodUSD.sol` — `Ownable`-mintable stablecoin for real co-op purchases; `GroupPurchase.sol` — pooled
  FoodUSD escrow that auto-pays a real supplier once a target is met (`:53-70`). *These two are the
  "real demand" primitives and largely align with §1.*

**Off-chain attribution:**
- `dirichlet-weights.ts` — `alpha = smoothingAlpha + amount × concentrationK`; `weight = alpha/Σalpha`;
  `smoothingAlpha=0.1` (D12: everyone non-zero), 12-week decay. **This is the anti-extractive engine.**
- Fleet service `pmoves/services/tokenism-simulator` (:8103) publishes `tokenism.simulation.result.v1`
  + signed CGP; shape attribution = Dirichlet-weighted CGP packets (`.claude/context/geometry-nats-subjects.md`).

## 3. The core contradiction

| Layer | What it rewards | Which principle it violates |
|-------|-----------------|-----------------------------|
| `GroVault` → `CoopGovernor` voting power | **Staked capital × lock time** | §1.2 rent-seeking, §1.1 commitment-first (rewards holding, not doing) |
| `GroToken` freely-transferable ERC20 | **Holding / trading a token** | §1.3 speculative + money-changing |
| `grotoken-model.ts distributeWeekly()` | **A Gaussian random draw** (`:90-92,111`) — *not* the Dirichlet weights | §1.4 grounded-in-real (distribution is disconnected from actual contribution) |

The fair mechanism (Dirichlet) already exists and already satisfies the principles — **it is simply not
connected to anything that matters.** The plutocratic mechanism is connected. The refresh inverts that.

## 4. The refresh (concrete diffs, mapped to principles)

1. **Sever governance power from stake.** Governance (who decides) must not derive from
   `GroVault.votingPower()`. For a membership vote it is **one-member-one-vote** (Mode A, per the
   voter-identity decision record); contribution weight informs *attribution/credit*, never a
   governance ballot. → retire the stake-weighted governor for governance; keep quadratic/stake nowhere
   near a member election. *(satisfies §1.1, §1.2)*
2. **Make credit non-transferable and earned.** Contribution credit is **soul-bound** (non-transferable,
   non-tradeable) — you cannot sell or arbitrage it. A separate *utility* currency (FoodUSD-style) may
   remain transferable **only** for buying real goods, never as a store-of-value speculation.
   → GroToken's role splits: earned standing becomes soul-bound credit; any tradeable token is
   utility-only. *(satisfies §1.3)*
3. **Wire distribution to the fair attribution.** Replace the Gaussian draw in
   `distributeWeekly()` with the **Dirichlet weights** from `dirichlet-weights.ts`. This is the single
   most concrete fix and the one that makes the structure *actually* contribution-based. → import
   Dirichlet; preserve D12 (α=0.1, everyone non-zero). *(satisfies §1.4, §1.5)*
4. **Add a commitment primitive.** Before work, parties record an **agreed commitment** (deliverable,
   contributors, terms). Attribution accrues on the *kept* commitment — this is what "sign to form the
   group" means. `GroupPurchase.sol` (pool → buy real thing) is the template: a bounded, real-outcome
   escrow, generalized from goods to any agreed deliverable. *(satisfies §1.1, §1.4)*
5. **Share surplus; no prediction/arbitrage extraction.** Surplus is distributed by the same
   non-zero-for-everyone Dirichlet, not captured; there is no prediction market or betting surface to
   arbitrage. Where arbitrage is discovered, it is surfaced and shared. *(satisfies §1.5)*
6. **Keep it generative.** Attributed surplus funds shared capability (nodes, tools, agents) that raises
   everyone's future attribution — the "ships that build ships" loop, not an enclosed moat. *(satisfies §1.6)*

## 5. Why B leads to A (the important half)

The economic engine (Mode B — consensual, attributable formation) comes before the ballot (Mode A)
as a way to demonstrate activity and standing. Its commitment and attribution records **do not prove
residency, membership, or legal voting eligibility** and therefore are not the Mode-A eligible roll.
Mode A requires an independently governed, committee-attested eligibility credential and roll. Mode-B
records may inform a human eligibility review only through a privacy-preserving bridge that preserves
the modes' **unlinkable keys**; they must never automatically admit or exclude a voter, and a contested
secret ballot must never run in Mode B (see `08:§8`).

## 6. Real vs aspirational (honesty)

Built today: the Dirichlet primitive; the tokenism simulator on host `:8103` (`GET /healthz`), which
publishes `tokenism.simulation.result.v1`; the cataloged `shape.trace.recorded.v1` and
`shape.profile.updated.v1` contracts; FoodUSD + GroupPurchase escrow; and Firefly calibration/export
modules. **Not wired / aspirational:** Dirichlet→distribution in every production path; soul-bound
credit (doc-only, no SBT code); live Firefly settlement execution; and production activation of the
governance rehearsal. The canonical mappings live in `.claude/context/nats-subjects.md`,
`.claude/context/services-catalog.md`, and `pmoves/contracts/topics.json`.

## 7. Open decisions + legal

- **SECURITIES / HOWEY (counsel-gated, blocking):** soul-bound, non-transferable, contribution-earned
  credit is *designed* to fall outside an investment-contract characterization (no expectation of profit
  from others' efforts, no tradeable instrument) — but this **must be confirmed by counsel** before any
  credit concept is member-facing. Extends `README:§Legal-review` "SECURITIES / TOKEN CHARACTERIZATION".
- **Governance basis:** one-member-one-vote vs unit vs shares — must be fixed (per Fordham `README:§Open
  decisions`) and must not reintroduce stake-weighting.
- **Utility-currency boundary:** where FoodUSD-style utility ends and speculation would begin — the line
  that keeps §1.3 intact.
- **Commitment enforcement:** what happens when an agreed commitment is *not* kept — the dispute/curing
  path, without an extractive penalty economy.

## 8. What to validate next

- **The one wire:** prototype `distributeWeekly()` on Dirichlet weights (not Gaussian) and show
  attribution matches real recorded contribution, D12 preserved.
- **Soul-bound credit:** decide the mechanism (non-transferable token vs off-chain signed ledger) and
  whether it needs a chain at all.
- **Commitment primitive:** generalize `GroupPurchase.sol` from goods to an agreed-deliverable escrow;
  the smallest version that records "who committed to what, and was it kept."
- **Counsel:** the §7 securities question, before anything is surfaced to real members.

---

`PROPOSE::B850-CLAUDE::TOKEN-STRUCTURE-REFRESH-DECISION::2026-07-17`
