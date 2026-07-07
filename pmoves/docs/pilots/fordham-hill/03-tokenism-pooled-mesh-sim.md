<!-- PMOVES workflow fordham-pilot-convergence lane=tokenism · needsHumanReview=True -->

# Fordham Hill Pooled-Mesh Tokenism Simulation

**Status:** DRAFT — REQUIRES LEGAL/FINANCE REVIEW before any resident-facing or bylaw use.
**Grounding:** Every input knob, API path, and run command below is cited to a file read this session. Every *output* figure is labeled either **PROJECTION** (stochastic sim) or **ARITHMETIC** (deterministic multiplication of measured field data). Nothing here is a measured pilot result.

---

## 1. Which simulator, and why

The ToKenism lane ships three simulator surfaces. This deliverable uses the **Next.js community-economics A/B simulator** as the primary engine because it is the only surface that runs a paired counterfactual — **Scenario A (no co-op)** vs **Scenario B (co-op)** — week by week, and reports the equality/resilience deltas the pilot cares about (`Gini_A/B`, `PovertyRate_A/B`, `LocalEconomyStrength`, `CommunityResilience`, `EconomicVelocity` — `types.ts:37-68`).

The contribution → reward mechanism (residents earn tokens proportional to what they contribute) is authored separately against the real **`DirichletWeights`** CHIT model (`integrations/contracts/chit/dirichlet-weights.ts`), because that is the actual "contribution → attribution weight" primitive in the codebase.

**Real input schema** (`pmoves-nextjs/src/lib/simulation/types.ts:1-22`): a flat `SimulationParams` object of scalar knobs. Defaults are in `utils.ts:5-24` (`DEFAULT_PARAMS`). The API route merges your params over the defaults — `{ ...DEFAULT_PARAMS, ...scenarioData.params }` (`app/api/run-scenario/route.ts:16`) — so a partial block is valid.

### How the Fordham Hill mesh maps onto real knobs

| Pilot concept | Real knob (`types.ts`) | Mapping rationale |
|---|---|---|
| Resident households (members/agents) | `NUM_MEMBERS` | One member = one household. |
| Community exit-node uplink = locally produced connectivity | `LOCAL_PRODUCTION_SAVINGS_PERCENT` | Mesh produces connectivity in-community instead of buying the premium tier. |
| Pooled bulk internet purchasing | `GROUP_BUY_SAVINGS_PERCENT` | One negotiated pipe vs many retail lines. |
| Connectivity spend kept in the co-op | `PERCENT_SPEND_INTERNAL_AVG` | Dollars flow to community node-hosts, not Verizon. |
| Shared node/hosting cost | `WEEKLY_COOP_FEE_B` | The co-op's own weekly cost of running the nodes. |
| Token reward pool + price | `GROTOKEN_REWARD_PER_WEEK_AVG`, `GROTOKEN_USD_VALUE` | Governs how much GroToken value flows to contributors. |

**Field-data anchor:** measured premium upcharge = **$35/mo per household** → **$8.08/wk** in the sim's weekly units (`35 × 12 / 52`). That is the per-household external cost Scenario B is designed to internalize.

---

## 2. The scenario config (real `SimulationParams` format)

Body for `POST /api/run-scenario`. Shape verified against `route.ts:8-16` (`{ name, params }`) and `types.ts:1-22`.

```json
{
  "name": "Fordham Hill Pooled-Mesh Co-op (strong cooperation)",
  "params": {
    "NUM_MEMBERS": 50,
    "SIMULATION_WEEKS": 156,

    "PERCENT_SPEND_INTERNAL_AVG": 0.70,
    "LOCAL_PRODUCTION_SAVINGS_PERCENT": 0.30,
    "GROUP_BUY_SAVINGS_PERCENT": 0.25,

    "WEEKLY_COOP_FEE_B": 2.0,

    "GROTOKEN_REWARD_PER_WEEK_AVG": 0.5,
    "GROTOKEN_USD_VALUE": 2.0,

    "WEEKLY_FOOD_BUDGET_AVG": 75.0,
    "WEEKLY_INCOME_AVG": 150.0,

    "localEconomicActivities": [
      {
        "id": "exit-node-kvm4-1",
        "name": "Host community exit node (kvm4-1)",
        "type": "exit_node",
        "startWeek": 0,
        "schedule": "weekly",
        "params": { "role": "host_node", "uplink_mbps_down": 845, "uplink_mbps_up": 347, "serves_whole_mesh": true },
        "participants": ["M_0"]
      },
      {
        "id": "share-uplink-pool",
        "name": "Share home uplink to mesh",
        "type": "exit_node",
        "startWeek": 0,
        "schedule": "weekly",
        "params": { "role": "share_uplink" },
        "participants": ["M_1", "M_2"]
      },
      {
        "id": "coverage-relay",
        "name": "Add coverage / relay node",
        "type": "exit_node",
        "startWeek": 4,
        "schedule": "weekly",
        "params": { "role": "add_coverage" },
        "participants": ["M_3"]
      }
    ]
  }
}
```

**Two honesty flags on this config (do not skip):**

1. **`localEconomicActivities` is schema-valid but currently INERT.** Its shape matches `LocalEconomicActivity` exactly (`types.ts:145-155`: `id, name, type, startWeek, schedule, params, participants`). But a grep of `pmoves-nextjs/src/lib/simulation/` shows the field is referenced **only in `types.ts`** — there is **no handler in `index.ts` (`runSimulation`, line 397) that reads it**. So today this array is descriptive metadata: it documents *who contributes what*, but it does **not** move the simulated numbers. The knobs that actually drive the A/B divergence are the scalar ones above. Making `exit_node` a live driver requires implementing an activity handler in `runSimulation` — that is net-new code, not a config change (matches the scout gap).

2. **`WEEKLY_COOP_FEE_B: 2.0` and the `WEEKLY_FOOD_BUDGET_AVG` base are placeholders.** The engine applies the savings percentages to the weekly budget line, not to a dedicated "internet cost" field (no such field exists — see §6). To dollar-match the measured $8.08/wk, these must be calibrated against **PMOVES-Wealth actuals** (real node hosting cost + real household essential-services spend). Left uncalibrated, the sim shows the *right direction*, not the exact dollar.

The knob values `0.70 / 0.25 / 0.30` mirror the engine's own built-in **"strong cooperation"** preset (`route.ts:36-41`), which is the documented lever for "more cooperation → better Scenario B outcomes."

---

## 3. Exact command to run it

Start the dashboard/dev server (`ANALYSIS_WORKFLOWS.md:199-215`):

```bash
cd PMOVES-ToKenism-Multi/pmoves-nextjs
npm install       # first time only
npm run dev       # serves on http://localhost:3000
```

Run the scenario (save the §2 JSON as `fordham-mesh.json`):

```bash
curl -X POST http://localhost:3000/api/run-scenario \
  -H "Content-Type: application/json" \
  --data @fordham-mesh.json
```

The route returns `{ scenario_results, comparative_analysis, recommendations }` with Scenario-B metrics `final_wealth, gini, poverty_rate, wealth_growth, inequality_change, resilience` (`route.ts:66-77`).

Direct (no HTTP) alternative — call the engine in a ts-node script:

```ts
import { runSimulation } from './src/lib/simulation';
import params from './fordham-mesh.json';
runSimulation(params.params).then(r =>
  console.log(r.history.at(-1))   // final WeeklyMetrics: Gini_A/B, PovertyRate_A/B, ...
);
```

---

## 4. Contribution → reward: the real Dirichlet (CHIT) attribution

This is the "residents contribute → earn token attribution proportional to contribution" mechanism, using the **actual** `DirichletWeights` API (`dirichlet-weights.ts`). `addContribution(address, amount, category, week)` raises a per-contributor α pseudo-count (`alpha = smoothingAlpha + amount × concentrationK`, line 89); `getExpectedAttribution()` returns each household's weight = `alpha / Σalpha`, summing to 1 (lines 117-139). Defaults: `smoothingAlpha 0.1`, `concentrationK 1.0`, `decayHalfLife 12` (lines 56-58).

```ts
// fordham-attribution.ts — run: npx ts-node fordham-attribution.ts
import { DirichletWeights } from './integrations/contracts/chit/dirichlet-weights';

const d = new DirichletWeights();            // smoothingAlpha 0.1, concentrationK 1.0, decayHalfLife 12
const CATEGORY = 'mesh_contribution';
const week = 1;

// contribution signals -> relative amounts (illustrative weights, tune to policy)
d.addContribution('household_A', 10, CATEGORY, week);  // hosts a community exit node
d.addContribution('household_B', 3,  CATEGORY, week);  // shares home uplink
d.addContribution('household_C', 5,  CATEGORY, week);  // adds coverage / relay
for (let i = 0; i < 47; i++) d.addContribution(`passive_${i}`, 0, CATEGORY, week); // opt-in, no infra

// split a weekly GroToken pool by attribution weight
const POOL = 100;                            // GroToken minted this week (policy knob)
for (const w of d.getExpectedAttribution(CATEGORY))
  console.log(w.address, w.weight.toFixed(4), '->', (w.weight * POOL).toFixed(2), 'GRO');

// weeks later, decay old contributions (half-life 12 wk):
// d.applyDecay(13);  // a household that stopped contributing sees alpha halve
```

**Honesty flag:** this Dirichlet model is **not** currently wired into `grotoken-model.ts` `distributeWeekly()` (line 111 uses a Gaussian draw; no Dirichlet import). So this script is the faithful *primitive* for contribution-weighted rewards, run standalone — connecting it to live GroToken minting is net-new integration work (matches the scout gap).

---

## 5. Optional fleet cross-check (Python service — emits NATS + CGP)

The only fleet-wired surface is the Python service (`pmoves/services/tokenism-simulator`, port `:8100`), which publishes `tokenism.simulation.result.v1` + a signed CGP geometry packet. Its schema differs (`models/simulation.py:36-75`): no A/B counterfactual, no `localEconomicActivities`. Use it only when you need the NATS/Geometry-Bus emission:

```bash
curl -X POST http://localhost:8100/api/v1/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario":"baseline","parameters":{"initial_participants":50,"contract_type":"gro_token","initial_gini":0.5,"gro_token_daily_rate":0.001,"duration_weeks":156}}'
```

`initial_participants = 50` = the household cohort; `contract_type = gro_token` selects the GroToken logic. Scenario modifiers are hardcoded multipliers (`simulation_engine.py:144-166`).

---

## 6. Projected outcomes (labeled)

### Deterministic arithmetic (measured field data × cohort — NOT a sim output)
- Each household today pays **$8.08/wk = $420/yr** in premium ISP upcharge (measured $35/mo).
- For a **50-household** opt-in cohort (**PLACEHOLDER** — real unit count not in repo), that is **~$21,000/yr** of spend the co-op keeps in-community instead of sending to the ISP. Scales linearly with real cohort size.

### Sim dynamics (PROJECTION — stochastic; direction, not exact dollars)
The engine seeds wealth lognormally and steps weekly (`index.ts:404-421`). With the §2 co-op knobs, Scenario B diverges *above* Scenario A over the 156 weeks: higher `PERCENT_SPEND_INTERNAL` + `LOCAL_PRODUCTION_SAVINGS` feed `LocalEconomyStrength`, `CommunityResilience`, and `EconomicVelocity` upward and pull `Gini_B` below `Gini_A`. Exact values vary per run (uses `Math.random`), so treat the shape — B pulls ahead, inequality narrows — as the result, not any single number.

### Token accrual as nodes join (PROJECTION — from the real Dirichlet formula, deterministic given inputs)
Running §4 with cohort 50 (1 host / 1 uplink / 1 coverage / 47 passive), `Σalpha = 0.1+10 + 0.1+3 + 0.1+5 + 47×0.1 = 23.0`:

| Household | Contribution | α | Weight | of 100-GRO pool |
|---|---|---|---|---|
| host | node host (10) | 10.1 | **0.439** | 43.9 GRO |
| coverage | relay (5) | 5.1 | **0.222** | 22.2 GRO |
| uplink | share uplink (3) | 3.1 | **0.135** | 13.5 GRO |
| each passive | none (0) | 0.1 | 0.0044 | 0.44 GRO |

**Network effect, as it shows up in the mechanism:**
- **Every added node raises the whole co-op's position.** Field data shows each KVM (kvm2 448/372, kvm4-1 845/347, kvm4-2 683/704 Mbps) serves the *whole* mesh. In the sim, each new host both (a) raises the realistic ceiling for `LOCAL_PRODUCTION_SAVINGS_PERCENT` in §2 and (b) adds α to the Dirichlet numerator in §4 — so a household that steps up to host visibly claims a larger token slice **without zeroing anyone out**: the `smoothingAlpha` floor (0.1) guarantees every opt-in passive household keeps a nonzero weight (0.44 GRO here). Contribution is rewarded; inclusion is preserved.
- **Free-riding decays, not by punishment but by math.** `applyDecay` (half-life 12 wk, line 58) halves a household's α every 12 weeks of inactivity, so weights continuously re-concentrate toward whoever is *currently* carrying the mesh.

---

## 7. What the sim cannot express (and the closest faithful stand-in)

| Cannot express | Closest faithful representation used |
|---|---|
| A native "Mbps" or "internet cost" input | Mapped onto `LOCAL_PRODUCTION_SAVINGS_PERCENT` / `PERCENT_SPEND_INTERNAL_AVG` / `WEEKLY_COOP_FEE_B`; dollar-match needs PMOVES-Wealth calibration (§2 flag 2). |
| `exit_node` activity actually driving the numbers | Documented in `localEconomicActivities` (schema-valid) as metadata; live driver = unimplemented handler in `runSimulation` (§2 flag 1). |
| Dirichlet weights actually minting GroToken | Standalone §4 script on the real API; wiring into `grotoken-model.ts` is net-new (§4 flag). |
| One canonical scenario file across all three surfaces | Three non-interoperable schemas; §2 (Next.js) is primary, §5 (Python) is the fleet cross-check. |
| Governance quorum / voting / bylaws | **Out of scope** — this engine models wealth & tokens, not governance quorum. Do not present sim output as a voting/quorum result. |
| Connection to the community's real books | `integrations/firefly` calibration exists but needs a running Firefly-iii instance + token; not plumbed here. |

**All numbers in `scenario-configs.ts` (e.g. ROI 1366%) are illustrative business projections, not Fordham Hill data — excluded from this deliverable.**