# Model–Harness Fitting

_Design spec · 2026-08-25 · authored on laptop-4090 (`claude_4090`)_

## Summary

A model and a harness are tuned **to each other**. The catalog already says this, in
two halves that were written separately and never joined: `cross_agent` records
*which harness a model fits and how well*, `harness_mappings` records *how to tune*.
Nine suits carry one, nine carry the other, **none carries both**, and no code reads
either.

This spec joins the halves into one object, makes its harness references
verifiable, gives its tuning a controlled vocabulary, and specifies the consumer
that turns it from documentation into routing.

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
the three current Claude suits are all-`full` and absent from this list. That is
harness bias — not intent, but defaults that grew around one model family, with
every other model paying the difference. Someone measured the tax and nothing ever
read it.

This is the single most valuable fact in the catalog and it is currently inert.

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

```yaml
fitting:
  model: glm-5.2
  provider: zai
  base_url: "https://api.z.ai/api/coding/paas/v4"
  api_key_env: Z_AI_API_KEY

  # Model-side facts. Harness-independent.
  context:
    max_window: 1000000
    effective_window: 500000
    working_window: 262144
  defaults: {temperature: 1.0, top_p: 0.95, max_tokens: 131072}

  harnesses:
    claude_pmoves:
      fit: full              # was cross_agent's value
      roles:                 # was harness_mappings
        deep_debugging:   {temperature: 0.3, top_p: 0.90, system_prompt: directive_debugger}
        code_review:      {temperature: 0.4, top_p: 0.95}
      budget:
        prompt_ceiling: 40000    # see §5
    clawz:
      fit: limited
      fit_note: "tool-call parsing assumes an Anthropic-shaped response"
```

Nesting `roles` under `harnesses` is what makes the fitting mutual: the same role
may be tuned differently in different harnesses, because a 1M-context harness and a
CLI harness want different settings for the same task. Where a model needs no
per-harness variation, `roles` may be declared once at fitting level and inherited —
the nesting permits variation, it does not require it.

**Migration is mechanical.** A `cross_agent` map becomes `harnesses.<h>.fit`; a
`harness_mappings` block becomes `harnesses.<h>.roles` under whichever harness the
suit was written for. Neither half is discarded, and a fitting that gains only one
half is still valid — it is simply incomplete, and reports as such.

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
- `fit: untested` — never routed by default; a deliberate flag opts in, which is how
  `untested` becomes `full` or `limited` instead of staying `untested` forever

Transport is NATS, matching the existing dispatch path (`pmoves.agent.task.v1` /
`pmoves.agent.result.v1`, published by `mavis`). The router is a subscriber, not a
new service tier.

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

1. Every one of the 18 suits migrates to a fitting with no recorded value altered —
   verified by diffing extracted `(model, harness, fit)` and `(model, role, setting)`
   tuples before and after.
2. `kong_route_seeder._parse_model_suits` returns the same 18 entries with identical
   `model_id` / `provider` / `api_base` / `api_key_env`.
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

1. **Should `fit` be per-harness or per (harness, role)?** A model may be `full` for
   `code_review` in a harness and `limited` for `agentic_coding` in the same one.
   Per-harness is proposed for simplicity; per-pair is more faithful.
2. **Who writes `fit`?** Hand-recorded today. A measured verdict — from the provider
   verifier, or a harness smoke run — would keep it honest as models change.
3. **Does `dsh` change this?** It hosts other harnesses via hook dialects, so a
   fitting for a model *inside dsh running the claude-code dialect* may need to
   compose two harness entries rather than name one.
4. **Does a harness marker earn its place?** §2 deliberately requires only that a
   harness key resolve to a registered agent. A first-class marker would let the
   gate reject a fitting pointed at, say, `qdrant` — a real agent that hosts no
   model. The cost is a new field or a widened enum, and a second place for the
   truth to live. Worth deciding once a fitting has actually been mis-pointed.
