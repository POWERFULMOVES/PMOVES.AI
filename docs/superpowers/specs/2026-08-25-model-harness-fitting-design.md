# Model–Harness Fitting

_Design spec · 2026-08-25 · authored on laptop-4090 (`claude_4090`)_

## Summary

A model and a harness are tuned **to each other**. Nothing in the catalog records
that pairing today, and the field that looks like it does is answering a different
question.

`harness_mappings` (9 suits) carries per-role tuning. `cross_agent` (9 suits)
carries *which PMOVES components can address this model* — its name is accurate,
and its key space spans agents, a UI, a launcher and two harnesses. Fit is a third
thing: **what a harness costs a model that did not grow around it.**

This spec introduces `fit` as a new, small, harness-only field rather than
reinterpreting `cross_agent`; makes its harness references verifiable; gives the
tuning a controlled vocabulary; and specifies the consumer that turns it from
documentation into routing.

> Revised 2026-08-25 after pair review from `b850-claude` under the watch pairing
> (#2743). Three of its findings changed the design rather than refining it, and
> are marked **[b850]** where they land. Its own headline finding was retracted by
> its author when the operator corrected the referent of `typer`; the narrower
> argument that survived is what this revision is built on.

## Measured starting state

All figures from `pmoves/configs/model-suits/` (18 files) on `origin/main`.

| | count |
|---|---|
| suits carrying `cross_agent` (fit) | 9 |
| suits carrying `harness_mappings` (tuning) | 9 |
| suits carrying **both** | **0** |
| suits carrying neither | 0 |
| distinct top-level schemas across the 18 | **7** |
| code that reads `harness_mappings` | none |
| code that reads `cross_agent` | none |

The only consumers of the directory are `kong_route_seeder._parse_model_suits`
(reads `model_id`, `provider`, `api_base`, `api_key_env` — routing identity only)
and `provider_verifier_gate` (reads `provider.json`, not suits at all).

### Harness bias is already recorded

`cross_agent` values in use: `full` ×35, `untested` ×6, `limited` ×6, `none` ×1.

```
claude-sonnet      typer=untested, pinokio=none
gemma4-dense       clawz=limited,  typer=untested
minimax-m2.1       clawz=limited,  typer=untested
minimax-m2.7       clawz=limited,  typer=untested
nemotron-3-super   clawz=limited,  typer=untested, pinokio=limited
qwen3.6            clawz=limited,  typer=untested
```

Read the `clawz` column: `limited` for **every non-Claude model measured**, while
the three current Claude suits are all-`full` and absent from this list — and the
files carry `# Requires adapter layer` beside it. That is harness bias: not intent,
but defaults that grew around one model family, with every other model paying the
difference.

**This is the evidence the spec rests on, and it is narrower than it first looks.**
[b850] `cross_agent` is a component-compatibility field; the `clawz` rows are a
genuine harness-fit measurement that happens to be recorded inside it. The other
keys (`agent_zero`, `archon`, `typer` — agents; `a2ui` — a UI; `pinokio` — a
launcher) answer the compatibility question the field was built for, not the fit
question this spec needs. `kilocode` is the only other genuine harness key.

So the fact is real and inert, and it is **two columns wide, not seven**. Everything
below follows from taking that seriously.

## The dual

Fit and tuning are not a split to repair. They are two poles of one relationship:

- **Fit** (`cross_agent`) is the harness's answer: *how well do I host this model?*
- **Tuning** (`harness_mappings`) is the model's answer: *what settings do I need to
  work well here?*

Fit without tuning is a verdict with no remedy. Tuning without fit is a setting with
no address. The object needs both poles or it expresses neither, which is why
"suit" is the wrong noun — a suit is worn by one party. This spec calls the joined
object a **fitting**.

## Design

### 1. One schema, both poles

A fitting is keyed by model and carries fit-and-tuning *per harness*:

**Routing identity stays exactly where it is.** [b850, verified] Every lookup in
`kong_route_seeder._parse_model_suits` is top-level or one of two known containers:
`doc.get("model_id")`, `doc.get("model",{})`, `doc.get("model_suit",{})`,
`doc.get("suit",{})`. A new `fitting:` root matches none of them, so every migrated
file would yield `model_id=None`, be skipped, and **every model would drop out of
Kong** — while Kong itself reported healthy, which it has done at zero routes on a
PMOVES node before. The fitting therefore EXTENDS the existing root rather than
re-parenting it:

```yaml
# Unchanged, and load-bearing for Kong. Do not nest these.
model_suit:
  name: glm-5.2
  provider: zai
  base_url: "https://api.z.ai/api/coding/paas/v4"
  api_key_env: Z_AI_API_KEY

  # Model-side facts. Harness-independent.
  context:
    max_window: 1000000
    effective_window: 500000
    working_window: 262144
  defaults: {temperature: 1.0, top_p: 0.95, max_tokens: 131072}

  # NEW. Seeded fresh and harness-only -- not migrated from cross_agent.
  harnesses:
    claude_pmoves:
      fit:
        "*":   {verdict: full, by: darkxside, method: hand, on: 2026-08-25}
      roles:                 # relocated from harness_mappings
        deep_debugging:   {temperature: 0.3, top_p: 0.90, system_prompt: directive_debugger}
        code_review:      {temperature: 0.4, top_p: 0.95}
      budget:
        prompt_ceiling: 40000    # see §5
    clawz:
      fit:
        "*": {verdict: limited, by: darkxside, method: hand, on: 2026-06-11,
              note: "requires adapter layer; tool-call parsing assumes an Anthropic-shaped response"}
        code_review: {verdict: full, by: provider_verifier, method: measured, on: 2026-08-19}
```

`cross_agent` is left exactly as it is, answering the question it was built for. No
value is reinterpreted, so nothing can silently change meaning.

Nesting `roles` under `harnesses` is what makes the fitting mutual: the same role
may be tuned differently in different harnesses, because a 1M-context harness and a
CLI harness want different settings for the same task. Where a model needs no
per-harness variation, `roles` may be declared once at fitting level and inherited —
the nesting permits variation, it does not require it.

**Migration is mechanical.** A `cross_agent` map becomes `harnesses.<h>.fit`; a
`harness_mappings` block becomes `harnesses.<h>.roles` under whichever harness the
suit was written for. Neither half is discarded, and a fitting that gains only one
half is still valid — it is simply incomplete, and reports as such.

### 1b. A role binds seams, not just sampling parameters

This is the part `temperature` and `top_p` cannot express, and it is where most of
the value is.

dsh is the reference. Its `docs/capability-seams.md` names ~28 swappable seams —
`ctx.llm`, `ctx.tools`, `ctx.storage`, `ctx.credentials`, `ctx.systemPrompt`,
`ctx.agentPresets`, `ctx.tokenMeter`, `ctx.toolResultPruner` — each declared by one
package and filled by any of several implementations. `ctx.sessionPersistence`
states the principle plainly: *"Backends persist the same SessionEvent vocabulary;
apps choose a backend at composition time."*

A role is that choice. The same question — *"who should actually do this work?"* —
is a seam binding:

| question | seam | binding |
|---|---|---|
| drive a GUI: chrome plugin and many tool calls, or an authenticated browser? | `ctx.tools` | `pmoves-surf` + `mai_ui` rather than in-harness browser tools |
| comb a large corpus without spending the caller's window | `ctx.llm` | a SPARK-local endpoint with cheap tool calls |
| this needs an agent that does not exist yet | `ctx.agentPresets` | mint via `archon` |
| OCR a fine-tuned medical set | `ctx.llm` | `hf_agent` / unsloth impl |
| search a YouTube library, drive, mail | `ctx.storage`, `ctx.fileReferences` | the corpus-owning service |

So `fit` acquires a fourth answer beyond `full` / `limited` / `none`: **`delegate`** —
this pairing is capable, but the work belongs elsewhere, and here is where. That
turns *"does 4090-CLAUDE do this, or does PMOVES?"* from a per-session judgement
call into a recorded, reviewable binding.

The economics are the point. A caller's context window is a hard, non-renewable
per-session constraint; a local model's tool calls are close to free. A fitting that
routes bulk tool-work to the caller is not merely suboptimal — it converts an
abundant resource into a scarce one. `ctx.tokenMeter` ("replay token measurement")
and `ctx.toolResultPruner` ("model-free tool-result pruning") exist because dsh
treats that as a first-class concern; a fitting should be able to bind them.

Seam names are dsh's vocabulary. PMOVES harnesses that expose no seams simply
declare none, and their roles carry sampling parameters only — the schema does not
require a harness to be seam-aware to be fitted.

### 2. Harness references must resolve

Harness keys are validated against the agent registry. This is now possible because
harnesses are registered agents (decided 2026-08-25): the harness is the vehicle the
model rides in, so it belongs in the registry alongside what rides it.

The check reuses the shape `validate_agent_registry.py` already runs for room
owners:

> `room agent_id 'creator-steward' resolves to neither a registry agent nor an
> external contributor`

A fitting naming a harness that does not exist is a typo that silently disables
routing for that pair, which is exactly the failure class this repo keeps hitting.

**Prerequisite:** the harnesses themselves must be registered. `dsh` is registered in
`.gitmodules`, `fork_registry.json` and `submodule_skill_registry.json` but absent
from `agent_registry.yaml` (see #2740). `claude_4090` was added by #2739.

**No harness marker is proposed, and the omission is deliberate.** The obvious
candidate does not fit: `role_classes` is a declared enum of `planner` / `worker` /
`reviewer` — a workflow role, not an entity kind — so `role_class: harness` would
extend an enum with a category error. The `types` taxonomy has no harness member
either, but it does not need one: `crush` and `clawz`, both terminal harnesses,
already register cleanly as `ui`/`agent`, and `claude_4090` follows them.

So the validation requirement is the weaker and truer one: **a harness key must
resolve to a registered agent.** The fitting asserting the pairing is itself the
claim that the target hosts models; the registry does not have to carry a second,
redundant assertion that can drift from it. Whether a first-class harness marker
earns its place is left open below.

### 3. Controlled role vocabulary

Today: **31 distinct role keys, 22 of them appearing exactly once**, with
overlapping near-duplicates (`debugging` beside `deep_debugging`;
`lightweight_coding` / `agentic_coding` / `code_generation` / `plan_routed_coding`).

A key with no permitted set cannot be validated, and a router cannot dispatch on
free text. The vocabulary lives in one file, and unknown roles fail the gate:

```yaml
# pmoves/configs/model-roles.yaml
roles:
  deep_debugging:   {description: "...", supersedes: [debugging]}
  code_review:      {description: "..."}
  long_context_analysis: {description: "...", supersedes: [long_context_research]}
```

`supersedes` carries the consolidation without silently dropping the old key: a
fitting using a superseded name resolves, and warns.

### 4. The consumer

**PMOVES has no model router.** This is the gap that keeps the catalog inert, and
the reason items 1–3 matter.

The router answers one question: *given a role and a harness, which model, at what
settings?* It reads fittings, applies the role vocabulary, and honours `fit`:

- `fit: full` — eligible
- `fit: limited` — eligible only with no `full` alternative; the degradation is
  logged, not silent
- `fit: none` — never routed
- **absent** — no observation exists. Never routed by default; a deliberate flag
  opts in, which is how absence becomes a verdict. [b850] There is deliberately no
  `untested` value: absence reads as honestly unknown, whereas `untested` reads as a
  completed observation with a null result and survives for months looking like
  data. `typer: untested` x8 is the worked example.
- `fit: delegate` — capable, but the work belongs elsewhere. The binding names the
  destination (§1b), and the router dispatches there rather than executing locally.
  This is the one value that routes to a DIFFERENT substrate rather than choosing a
  model, so it is the only value that must name a target.

**Transport is NATS request/reply BEFORE dispatch — not a subscriber.** [b850,
verified] `orchestrator.py` resolves the destination and only then publishes:

```python
routing = self.routing_for(agent)
wire_target = routing.get("target") or agent
self.publisher.publish(SUBJECT_TASK, {"target": wire_target, ...})
```

The envelope on `pmoves.agent.task.v1` already carries `target`. A subscriber there
receives a decision, not a request, and cannot influence selection however good its
fitting data is. The router must answer a request/reply ahead of `dispatch`, so its
verdict reaches `routing_for` rather than arriving beside the workers.

Local-first remains law: `MODEL_FABRIC_CONTRACT` and the Class A/B/C posture in
`AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md` govern which lane is eligible before
`fit` narrows it further. The router does not get to promote a Class A workload to a
coding plan because a remote model fits better.

### 5. Context budget

A 128k working window spent on a 40k prompt to produce 3k of output is a fitting
failure, not a model failure. Fittings already carry `context.working_window`;
`budget.prompt_ceiling` makes the other half explicit, and the router treats a
pairing whose assembled prompt exceeds the ceiling as a **routing error rather than
a silent truncation**.

This is the mechanism behind "models don't get dropped in blind": the environment is
declared before the model arrives in it.

### 6. Evidence, not a permission bit

[b850] `full` / `limited` / `none` reads like a verdict a router consults to refuse.
`limited # requires adapter layer` reads like a finding someone can act on. The
second form is the one that survives contact, and it is the reason `fit` carries
observations with `by` / `method` / `on` / `note` rather than a bare enum.

This matters beyond bookkeeping. A model that can read its own fitting can behave
differently: not attempting a tool call the harness gates, not planning work that
will hit a context wall the harness imposes. Fit is therefore addressed to **two**
readers — the router deciding where work goes, and the model deciding how to work
once it arrives. A permission bit serves only the first.

That is also the honest answer to "which harness should this model ride": harnesses
sit on a spectrum from model-specific (Claude Code, tuned first for Anthropic
models, some capabilities gated to them) to agnostic (dsh, no privileged core). Both
ends are legitimate. Recording where a harness sits, and what that costs a given
model, is what lets a model ride a car it did not grow up in without being surprised
by the dashboard.

## Boundaries

**In scope:** the fitting schema, harness-reference validation, the role vocabulary,
the router's contract, and migrating the 18 existing suits.

**Out of scope, deliberately:**

- Retuning any model. Migration preserves recorded values exactly; changing a
  temperature is a separate, evidenced decision.
- Re-measuring `fit`. The 13 non-`full` entries are inherited as-is. Turning an
  `untested` into a verdict requires running the pairing, not editing YAML.
- The provider-admission path. `provider_verifier_gate` already owns it and is
  unchanged.
- `kong_route_seeder`. It reads routing identity, which the fitting still carries at
  top level; it must keep working unchanged, and that is an acceptance criterion.

## Acceptance

1. **No `cross_agent` value is migrated, reinterpreted, or removed.** [b850] The
   original criterion here was a before/after tuple diff proving no value changed —
   which would have passed cleanly *while every value silently changed meaning*.
   That is this spec's own stated failure mode in its harder form: nothing is lost,
   the **referent** moves, and a diff cannot see it. The criterion is therefore
   structural, not value-based: `cross_agent` is byte-identical after migration, and
   `fit` contains only entries whose harness key is a genuine harness.
2. `kong_route_seeder._parse_model_suits` returns the same 18 entries with identical
   `model_id` / `provider` / `api_base` / `api_key_env` — asserted by running it, not
   by inspection. This is the criterion the original schema would have failed.
3. Every harness key resolves to a registered harness; an unresolvable key fails the
   gate.
4. Every role key resolves to the vocabulary; an unknown role fails the gate.
5. The router, given `(role, harness)`, returns a model and settings — and refuses
   `fit: none`, warns on `limited`, and skips `untested` unless opted in.
6. A fitting whose assembled prompt would exceed `budget.prompt_ceiling` errors
   rather than truncating.

Criterion 1 is the one that matters most: this is a schema change to a security- and
cost-relevant config, and the way such changes go wrong is by quietly losing a value
nobody re-checks. Two extractions agreeing is the check.

## Open questions

1. ~~Should `fit` be per-harness or per (harness, role)?~~ **Resolved 2026-08-25:
   both.** `fit` is declared per harness AND may be narrowed per role, because the
   seam bindings in §1b differ by role — a model can be `full` for `code_review` in
   a harness and `delegate` for `bulk_ocr` in that same harness. A role-level `fit`
   overrides the harness-level one; a harness-level `fit` with no role override
   applies to every role. This makes migration of the 35 existing `cross_agent`
   entries mechanical (they become harness-level) while leaving room to narrow.
2. ~~Who writes `fit`?~~ **Resolved 2026-08-25: both, and the record keeps more than
   one.** A hand-recorded verdict carries judgement a benchmark cannot ("tool-call
   parsing assumes an Anthropic-shaped response"); a measured one stays honest as
   models change. Neither supersedes the other, so `fit` is not a bare scalar — each
   observation carries its source, and a pairing may hold several:

   ```yaml
   clawz:
     fit: limited                       # effective value the router uses
     observations:
       - {verdict: limited, by: darkxside,        method: hand,    on: 2026-06-11,
          note: "tool-call parsing assumes an Anthropic-shaped response"}
       - {verdict: limited, by: provider_verifier, method: measured, on: 2026-08-19}
   ```

   The effective `fit` is the most conservative verdict among observations, so a
   single credible "this is worse than it looks" is never averaged away. Divergence
   between a hand verdict and a measured one is a signal worth surfacing, not a
   conflict to resolve silently — and the open lane matters: a third perspective (a
   paired node's review, another agent's run) appends rather than overwrites.
3. ~~Does `dsh` change this?~~ **Resolved 2026-08-25 [b850]: record fit against the
   dialect presented to the model; `dsh` is a host attribute, not a fit key.** A
   `dsh` row would mean "whatever dsh was hosting that day" — unfalsifiable, and it
   would degrade exactly as `pinokio: full` already has.
4. ~~Does a harness marker earn its place?~~ **Resolved 2026-08-25 [b850]: yes, as
   `kind:` on the registry entry** — not `role_class`, which is a workflow enum.
   Without an explicit entity kind the `cross_agent` key space mixed several
   categories across 18 files and nothing caught it; more pointedly, a reviewer with
   full repo access resolved `typer` to a same-named Python dependency, called it
   decisive, and had to retract. A `kind:` marker makes that unresolvable by
   guessing. The reviewer offered itself as the worked example, which is the
   strongest form the argument has.
