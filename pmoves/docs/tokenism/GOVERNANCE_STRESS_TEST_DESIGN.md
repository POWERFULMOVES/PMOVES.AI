# Governance Stress-Test Design — "Let's put it to the test" (view v1, 2026-08-08)

> Origin: the SEAP-plan reconciliation surfaced a live disagreement. The Gemini
> plan sold quadratic voting + veToken locks as whale *deterrents*; the
> TOKEN_STRUCTURE_REFRESH decision record calls stake-weighted mechanics the
> plutocratic anti-pattern. The operator's ruling: **neither assertion stands
> untested** — the simulator decides, and outputs settle to PMOVES-Wealth.
> This is the test design for review before implementation.

## Question under test

For a community of N members with realistic wealth inequality, which voting
mechanism minimizes *outcome capture by concentrated capital* while preserving
*legitimate influence for high-contribution members*?

## Mechanisms (the contenders)

| id | Mechanism | Whale story (claimed) |
|----|-----------|----------------------|
| M1 | Token-weighted (1 token = 1 vote) | baseline / known-plutocratic control |
| M2 | Quadratic voting, no identity binding | cost² deters whales (plan's claim) |
| M3 | Quadratic voting + sybil-resistant identity (1 person = 1 credit pool) | QV as designed by its authors |
| M4 | veToken time-lock weighting (lock longer → more weight) | "skin in the game" |
| M5 | One-member-one-vote + $WORK-style SBT eligibility gate | decision record's direction |
| M6 | Hybrid: M5 for elections + M3 for budget-allocation signals | two-house frame |

## Attack scenarios (each run against every mechanism)

1. **Whale accumulation** — one actor holds 10× / 50× / 200× median balance.
2. **Sybil split** — whale splits stake across k fake identities (k = 2…100).
   This is the scenario that breaks naive QV (M2) and is why M3 exists.
3. **Lock-race** — whale max-locks veTokens before a contested vote (targets M4).
4. **Collusion ring** — c members (c = 3…15) coordinate votes; measures
   whether mechanism amplifies or dampens coordinated minorities.
5. **Voter apathy** — turnout 10–60%; whales always vote. (Low turnout is the
   real-world whale multiplier.)
6. **Contribution-inversion check** — the *legitimacy* half: a high-contributor
   low-balance member vs a zero-contribution whale on the same proposal; does
   the mechanism let the contributor matter?

## Metrics

- **Capture rate**: fraction of contested proposals decided by the whale/ring
  against majority-member preference.
- **Gini-to-influence transfer**: correlation between wealth Gini and voting
  influence Gini (the plutocracy number — lower is better).
- **Sybil elasticity**: influence gained per identity added (M3 should be ~0;
  M2 will not be).
- **Participation elasticity**: how capture rate moves with turnout.
- **Legitimacy score**: contribution-weighted preference satisfaction (does
  the mechanism reward builders or balances?).

Each cell = 500 Monte-Carlo runs, ≥5 seeds, report medians with CIs — same
evidence bar the Dirichlet drop mandates for CHIT claims.

## Implementation shape

- **Harness**: PMOVES-ToKenism-Multi simulator (`tokenism-simulator` :8103) —
  agents with wealth drawn from the pilot's empirical distribution (Fordham
  household data where available; Pareto fit elsewhere, LABELED ASSUMPTION).
- **Mechanism modules**: pure functions `(balances, locks, identities,
  votes) → decision` so each mechanism is a ~50-line plug-in.
- **Settlement**: run outputs → `export_sim_to_firefly.ts`
  (PMOVES-ToKenism-Multi/integrations/firefly/) → PMOVES-Wealth ledger, one
  Firefly tag per scenario run — ledger-grade evidence, not a chart in a doc.
- **Verdict doc**: results land as a reconciliation-style table (mechanism ×
  scenario → capture rate), published to Open Notebook + the room.

## What would change minds

- If M3 (QV + identity) shows capture ≈ M5 with better legitimacy scores, the
  plan's QV language survives — but only with the sybil-resistance qualifier
  the plan omitted.
- If M4 capture ≥ M1, the decision record's veToken retirement is confirmed
  with numbers attached.
- If M6 dominates, the bicameral Constitution sketch gets its first
  evidence-backed parameter set (replacing the self-flagged FABRICATED ones).

## Non-goals

No on-chain deployment, no real tokens, no governance change ships from this —
it produces *evidence for the operator's decision*, per the pub-gate model.
