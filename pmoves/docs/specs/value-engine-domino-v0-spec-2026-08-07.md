# Value-Engine Domino — v0 Spec (one pattern, end to end)

**Date:** 2026-08-07  **Author:** z890-claude (KEYSTONE)  **Status:** draft for operator review
**Goal:** Wire a single verified pattern through the whole value loop — **minted → scored →
paved → attributed → banked** — so one "domino" falls cleanly end to end with a *measured*
value. Once one works, the rest is pushing more.

## The load-bearing definition

**A domino's value = how much it reduces FUTURE error.**
Concretely, for the error class a pattern addresses:

```
value = estimated_reduction × error_weight
  estimated_reduction ∈ [0,1]   # fraction of that error class the pattern prevents (a prior)
  error_weight        ≥ 0       # how costly/frequent that error class has been
```

**`error_weight` is derived, not invented** — it comes from history we already record:
`known-roads.jsonl` + AGNOTE/CHIT trails already show which errors keep recurring. So even v0
is semi-measured. `estimated_reduction` starts as a declared prior at mint and is refined by
observation later (post-v0).

## Trigger (exists today)

A pattern only becomes a domino if it passed QA. Reuse the Archon mint gate unchanged:
`archon.mint.agent.v1` → `archon.qa.result.v1` (blocks on fail) → **`archon.mint.confirmed.v1`**.
v0 subscribes to `archon.mint.confirmed.v1`.

## The four steps

### 1. Score — `domino-scorer` (new, small)
On `archon.mint.confirmed.v1`, produce a **Domino Record**:

```jsonc
{
  "domino_id": "dom_<ulid>",
  "pattern_ref": "<archon mint id / pattern slug>",
  "error_class": "raw-compose-up",          // what future error it prevents
  "estimated_reduction": 0.8,               // declared prior [0,1]
  "error_weight": 12,                        // derived from known-roads.jsonl + trails hit-count
  "value": 9.6,                              // estimated_reduction × error_weight
  "contributors": ["z890-claude", "crush"],  // who authored/verified (for attribution)
  "trail_ref": "<CHIT trail id / sign-trail sig>",
  "ts": "<iso8601, passed in — never Date.now() in scripts>"
}
```
`error_weight` lookup: count prior occurrences of `error_class` in `known-roads.jsonl` + the
AGNOTE trail corpus. Missing class → weight 1 (unknown-but-nonzero).

### 2. Pave — Known-Road line (extend existing mechanism)
Append one provable line to `.claude/hooks/damage-control/known-roads.jsonl` (append-only,
`merge=union`, fail-closed) tagging it as a domino: `{domino_id, pattern_ref, error_class,
value, trail_ref, ts}`. The road is paved the instant the domino is scored.

### 3. Attribute — `tokenism.value.recorded.v1` (new subject, existing bus)
Publish to the geometry/tokenism bus:
```jsonc
{ "domino_id": "...", "value": 9.6, "contributors": ["z890-claude","crush"], "trail_ref": "...", "ts": "..." }
```
ToKenism consumes it and applies the **Dirichlet α>1** split across `contributors` (cooperative,
anti-concentration — see the tokenism model). No single contributor captures the whole 9.6.

### 4. Bank — Wealth ledger entry
ToKenism (or a thin `tokenism→wealth` bridge) writes the attributed shares into **Wealth** as a
value-recorded entry keyed by `domino_id`, so the victory is on the books with provenance.

## Components & ownership
| Step | Component | New/Exists | Lane |
|------|-----------|-----------|------|
| Trigger | Archon mint + QA gate | exists | Archon (4090) |
| Score | `domino-scorer` | **new (small)** | z890 infra |
| Pave | Known-Roads guard | exists (extend) | z890 infra |
| Attribute | ToKenism-Multi | exists (add subject consumer) | tokenism lane |
| Bank | Wealth (+ bridge) | exists (+ thin bridge) | wealth lane |

DoX holds the document/provenance side; BoTZ supplies senses/skills (BoTZ runs **without**
PMOVES-BotZ-gateway — gateway optional).

## Scope

**In (v0):** the single flow above for ONE domino, `estimated_reduction` as a declared prior,
`error_weight` derived from history, the three emissions (road line + tokenism event + Wealth
entry) all sharing one `domino_id` + `trail_ref`.

**Out (later):** measured/Bayesian refinement of `estimated_reduction` as agents adopt the
domino; multi-domino cascade orchestration ("pushing" chains); any UI; cross-node value
reconciliation; retroactive scoring of historical patterns.

## Acceptance test (proves the domino falls)
A script that: publishes a synthetic `archon.mint.confirmed.v1` for a test pattern → asserts
(1) a Domino Record with `value = estimated_reduction × error_weight`, (2) a matching
`known-roads.jsonl` line, (3) a `tokenism.value.recorded.v1` event on the bus, (4) a Wealth
entry — **all four sharing the same `domino_id` and `trail_ref`.** Green = one domino, end to end.

## Convergence — 3 lanes + MissingLinc (proposed)

Each node owns its natural piece; they meet on the shared NATS subjects. This is a proposal
for the 4090 + 5090 lanes to confirm, not a commitment on their behalf.

| Lane | Owns | Why |
|------|------|-----|
| **4090 · Archon** | the **trigger + flow** — `archon.*` NATS bridge (`orchestrator.py`, restored in **#2464**; contract layer #2336; ARCHON JetStream). Publishes `archon.mint.confirmed.v1` the scorer consumes. | Archon "creates the flow and mints" — that's this lane. #2464 already put the bridge core back. |
| **z890 · infra (me)** | the **engine core** — `domino-scorer`, value = error-reduction metric, Known-Roads pave, ToKenism→Wealth wiring. | KEYSTONE holds the guard + the wiring. |
| **5090 · Mavis/canvas** | the **render** — A2UI view of the engine: the paved road (Known Roads as a visual path), victory stories (trails), the domino cascade + value attribution. The literal "yellow brick road." | Mavis owns A2UI / rooms-on-a-stage; the engine needs an operator-facing surface. |
| **MissingLinc** | the **optimal chain** — given a problem, find the best-verified chain of existing dominos to solve it ("chainlink to the optimal thread"). Grid-Detective finds the missing link. | This is exactly "chainlink but to the optimal thread." |

## First real domino: PR #2464 (ground v0 in a true clutch recovery)

Instead of only a synthetic mint, seed v0 with the real recovery just landed:
- `error_class`: **`collateral-deletion-on-service-retirement`** (a live file deleted alongside genuinely-dead ones)
- pattern: distinguish dead-imports (`import server.main` → crash-loop) from a live, stdlib-only orchestrator via import analysis + does-its-suite-pass — restore selectively.
- `error_weight`: derivable — count prior "retirement deleted something live" incidents in trails.
- `value`: un-redded a **549-line suite aborting collection on main** + prevents the whole class recurring on the next service retirement.
- `contributors`: the 4090 lane. `trail_ref`: #2464.
This is the acceptance run's first input — a domino that actually fell.

## The four decisions are the engine's FIRST simulation case (not picked by fiat)

Operator principle (2026-08-07): design decisions with consequences shouldn't be chosen by
whoever's holding the pen — **their consequences should be modeled, and the optimal surfaced.**
That is precisely what ToKenism-Multi + **EVO SWARM** are for: model each option (from
**grounded** data — e.g. the real #2464 domino — and **synthetic** variants), let the swarm find
equilibrium (no controller), and **MissingLinc** surfaces the missing link. The value engine's
first real job is reconciling its own design.

**Bootstrap:** v0 ships with minimal *seed* choices (below) so it can run at all; the moment it
runs, its first task is to simulate the alternatives to these four and report whether the seed was
optimal. Self-correcting by construction.

| # | Decision | Seed (v0) | Reconcile by simulating… |
|---|----------|-----------|--------------------------|
| 1 | Scoring source | declared `estimated_reduction` prior + derived `error_weight` | grounded (#2464 actual error-recurrence) vs. synthetic reduction priors → which predicts real future-error best |
| 2 | Subject name | `tokenism.value.recorded.v1` | naming/consumer-fanout consequences (cheap; likely stays) |
| 3 | Wealth write path | thin `tokenism→wealth` bridge | bridge vs. direct-subscribe — coupling/latency/failure-isolation modeled |
| 4 | Contributors source | mint payload / trail authors | attribution-identity provenance: which source keeps the Dirichlet split honest under adversarial trails |

**Prereq for the reconciliation run:** Tokenism Simulator (`:8100`, green) + EVO SWARM /
evo-controller (`:8113`) must be live to model the analog-shape consequences. (evo-controller not
currently up on z890 — bring it up before the first reconciliation.)

## The wider frame this sits in (operator, 2026-08-07)
- **Analog shapes:** EVO SWARM models consequences as continuous shapes (grounded ∪ synthetic), not
  discrete picks — the same "meaning has shape" thesis as CHIT.
- **Prosodic ears → prosodic agents:** sensing feeds acting, built to the user's needs (the
  `shift-from-bpm` → `tokenism.prosodic.bpm.v1` layer; #2462 beats→voice is a piece of it).
- **Harness tuned for the model, like a tuning fork — both wrapped like a glove:** the tooling
  co-adapts to the specific model's shape (resonance), not a generic harness. This is the design
  constraint on every domino: it must fit the model that pushes it.
