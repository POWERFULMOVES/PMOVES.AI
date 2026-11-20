# Mavis inter-agent handoff v0 — LEARNINGS

This slice closed the **consumer-fork wire-up half of PR #2477**
(Mavis harness v0). The Mavis side of the harness — orchestrator +
bpm_cron — shipped in PR #2477; the missing half was the dispatcher
knowing how to route to the 3 consumer forks (Hermes, KiloClaw,
Pinokio) and surfacing the KVM focus-switch to the operator. The
slice lands 7 commits (PR #2651: 6 lane commits + 1 `main`
merge-sync), 17/17 + 12 subtests pass, and unblocks the
two peer handoffs (SPARK-KIMI for the Hermes fork, CRUSH for the
Pinokio fork) that read the same CGP bootstrap at session init.

## Lesson 1: bootstrap-driven known_targets > hardcoded set

The v0 orchestrator had `KNOWN_TARGETS = {"mavis", "kiloclaw", "hermes"}`
hardcoded. Adding `pinokio` to the routing block would have been
a 2-line orchestrator change. Worse: future forks (a Hermes-KiloClaw
hybrid, a Code-execution peer, etc.) would each need an orchestrator
edit. The fix: derive `known_targets` from `dataclasses.fields(self.bootstrap.routing)`
plus a built-in floor. Adding a routing entry to the CGP now
auto-widens the dispatch surface with zero orchestrator code.

**Important sub-lesson from the operator review:** "Enumerate the
Routing dataclass's FIELDS rather than a literal tuple" — i.e.
`for f in dataclasses.fields(routing): if getattr(routing, f.name, None):`
not `for peer in ("kiloclaw", "hermes", "pinokio"): ...`. The literal
tuple silently contradicts the docstring's promise that adding a
routing entry widens the dispatch surface without an orchestrator
change.

## Lesson 2: KVM control surface belongs on its own subject, not a phase discriminator

The v0 slice put KVM on `pmoves.bpm.phase.v1` with `phase: "kvm-focus"`.
The operator review caught this: that subject is contracted as the
5 lifecycle phases `define -> assign -> execute -> review -> close`,
carrying `task_name`/`previous_phase`. A "kvm-focus" event with
`target_node` is neither — it's a different category of event. A
subscriber reading that stream would see an invalid lifecycle
transition.

**The principle: "A discriminator field does not make an incompatible
payload compatible; it just moves the breakage into the consumer."**
The fix is to split KVM onto its own subject: `pmoves.kvm.focus.v1`
(now registered in `.claude/context/nats-subjects.md`). The KVM
controller subscribes to that subject specifically.

This is the second time the "reuse an existing surface" instinct
was wrong in this slice. The first was Lesson 1's hardcoded peer
list; the second is the KVM-as-phase-discriminator. The right rule:
**a payload that doesn't match the subject's contract is not a
"special case" of the subject; it's a separate subject.** Reuse
existing surfaces when the payload is the same shape; split when
the payload diverges.

## Lesson 3: routing_for() returns a copy, not a reference

`routing_for(target)` returns `dict(routing.<target>)` rather than
the raw dict. This is load-bearing: a caller that mutates the
returned dict (e.g. logging, debugging, partial override) would
otherwise silently mutate the bootstrap's routing, which is
shared across all dispatches. The
`test_routing_for_returns_a_copy_not_a_reference` test (in
`pmoves/tests/tools/test_mavis_handoff_learnings_ratchet.py`) is the
regression check; without it, a future "optimize the dict copy"
would silently re-introduce the aliasing.

This is a generic rule for any read-only accessor on a shared
structure: return a copy unless the contract is explicitly
"return the live reference". The bootstrap is shared across
the orchestrator + bpm_cron + any future consumer; aliasing
is a foot-gun.

## Lesson 4: the wire target is the routing's `target` field, not the routing key

**This was a P1 finding from the operator review.** The orchestrator
was publishing `target: "hermes"` (the alias) on the task envelope.
The Hermes handoff in `AGNOTE4482PHI.t1.md` subscribes on
`target: "hermes-3"` (the configured routing target). So no consumer
ever matched, and the handoff sat pending indefinitely. The
failure had no error message — the work simply never happened.

The fix: the envelope now carries `target: "hermes-3"` (the
configured target from `routing.hermes.target`) AND `target_alias:
"hermes"` (the routing key) for producer-side correlation. The
consumer subscribes on `target`; the producer's correlation map
uses `target_alias`.

**General principle:** when the contract has a "configured value"
(distinct from a "name" or "alias"), the wire carries the configured
value, not the alias. The alias is documentation; the wire is
operation. A subscriber that filters on the alias when the wire
carries the configured value will never match.

## Lesson 5: placeholders are not machine names; treat them as such

`example.cgp.yaml` ships `hermes.node: TBD` — "the operator hasn't
stood Hermes up yet; wire is ready." The v0 slice's guard was
`node not in ("self", "host", "")`, so a literal TBD passed.
A default-config dispatch then asked the KVM controller to switch
to a machine named TBD. The operator review caught this.

**The fix:** `_is_actionable_node(node)` is now case-insensitive,
whitespace-trimmed, and rejects `tbd/todo/none/n/a/-` alongside
`self/host`. The shipped placeholder is now safe.

**General principle:** config values that mean "not yet wired" must
be filtered out at the boundary that consumes them. The shipped guard
is a **deny-list** of non-actionable values, not an allow-list of
actionable ones: `_is_actionable_node` returns true for every node
name that is NOT in the set, so a placeholder is inert only once it
has been added to it. The literal-string-equality guard is a
foot-gun: every new placeholder the operator adds
(`hold`, `pending`, `TBA`, `???`) requires editing the guard, and
until it is edited the guard treats it as a real machine -- the KVM
controller is asked to switch to a machine named `hold`. A
case-insensitive set lookup against a documented set of
non-actionable values is easy to extend -- one entry in the set --
but it is a deny-list, not a look-ahead: the set has to be kept in
step with the configs it guards.

The tests `test_placeholder_matching_is_case_insensitive` and
`test_placeholder_node_does_not_request_kvm_focus` cover this: the
first enumerates the placeholder forms (including the case and the
whitespace variants), the second asserts against the DEFAULT config,
so a future operator who adds a new placeholder to the config but
forgets to add it to the set is caught at PR time.

## Lesson 6: x-cgp-* annotations make the consumer contract machine-checkable

The CGP v1.0 spec is YAML/JSON. The consumer contract (what forks
MUST/MUST NOT do) is prose in a comment. The v0 slice adds
`x-cgp-profile`, `x-cgp-base`, `x-cgp-spec`, `x-cgp-version`,
`x-cgp-bootstrap-version`, and `x-consumer-contract` (with
`required` + `forbidden` arrays) as JSON-schema annotations.

Why this matters:
- The `x-consumer-contract.required` array is the formal spec
  the consumer forks lint against. SPARK-KIMI and CRUSH can
  write a tiny `pmoves.bootstrap.consumer_contract_check()`
  helper that asserts the schema is present + the contract
  block is populated + the required rules are non-empty.
- The `x-cgp-base` link tells the consumer where to look for
  the CGP v1.0 base schema. Without it, the consumer has to
  guess whether pmoves.bootstrap/v1 is a "narrow variant" of
  the CGP v1.0 spec or a totally separate spec.
- The `x-cgp-version` annotation gives the consumer a way to
  detect "I was written for v1.0.0, this bootstrap says v1.0.1"
  (a soft warning) vs "I was written for v1.0.0, this bootstrap
  says v2.0.0" (a hard refusal).

The x- prefix is JSON Schema's reserved namespace for
non-validating annotations. Standard tooling ignores them; the
harness's consumer-contract linter reads them.

## Lesson 7: cross-PR coordination via AGNOTE lane board

The slice was 3 parallel PRs (Mavis, Hermes, Pinokio). The
coordination mechanism was the AGNOTE lane board (3 CLAIM
rows in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`):
- Mavis: orchestrator + bpm_cron side (this PR, 7 commits, 17 tests)
- SPARK-KIMI: Hermes consumer-fork wire-up (PMOVES-hermes-agent
  fork, branch `feat/hermes-cgp-bootstrap`, TTL 72h)
- CRUSH: Pinokio CGP-bootstrap loader (PMOVES-pinokio fork,
  branch `feat/pinokio-cgp-bootstrap`, TTL 72h)

The AGNOTE pattern: each CLAIM names (a) the branch, (b) the
worktree, (c) the TTL, (d) the deliverable test count, (e) the
three-body. A peer agent that picks up a CLAIM in their next
session knows exactly what to do, where to work, and when the
lane expires.

**The CGP bootstrap is the cross-PR contract.** This PR
formalizes the spec; the peer PRs consume it. If a peer PR
drifts from the spec (e.g. wrong field name), the drift shows
up in the CGP-bootstrap test fixtures, not in some
ad-hoc "did you read the spec" check.

## Lesson 8: pair-review catches P1 bugs the original author misses

Four of the eight lessons above (#1 sub-lesson, #2, #4, #5) were
caught by the operator + Claude Opus 5 review of my v0 slice. Each
was a real bug — not a nit, not a style issue. Lesson #4 (the
wire target vs the alias) was the worst: a default-config
dispatch would have sat pending forever with no error message.
The original author (me) missed all four because:
- I wrote the wire contract for the orchestrator's CORRECTNESS
  (the target field exists, the alias field exists, the KVM
  guard filters non-actionable nodes), not for the consumer's
  MATCHING (does the consumer subscribe on what's published).
- I wrote the KVM surface as a phase-discriminator because
  that kept the wire-up minimal, not because the phase stream
  is a fit for the payload shape.
- I wrote the placeholder guard as a literal-tuple check
  because that's what the surface API suggested, not because
  configs are hand-written and will pick up new placeholders.

The pair-review taxonomy (reasoning gap / semantic-naming drift /
contract-correctness / defense-in-depth) applies here:
- **#1 sub-lesson** = defense-in-depth (the docstring promise
  needed a test, not just a comment)
- **#2** = contract-correctness (the phase stream's contract
  was the right thing to check against)
- **#4** = semantic-naming drift (alias vs target — the
  distinction only shows up at the wire boundary)
- **#5** = defense-in-depth again (the literal-tuple guard
  needed a deny-list set lookup)

The operator's review was the cheapest P1 catch possible: a
real review by a peer that knows the contract from the other
side. Future slices should plan for at least one full review
pass before merge, not just codex/ci validation.

## What I'd do differently next slice

- **The CGP bootstrap's routing `additionalProperties: false`**
  is a sharp edge: adding a new peer requires both a schema
  update AND a Routing dataclass field. A future slice could
  add a `pmoves/contracts/schemas/pmoves-bootstrap/_routing_dynamic.py`
  schema that uses `propertyNames` + `additionalProperties: true`
  with a per-key schema, so the dataclass can stay generic.
  Not in scope for v0 (the 3-peer floor is enough), but worth
  flagging for the lane-2 PR.
- **The CGP schema's `x-cgp-version` annotation should be
  checked at load time**, not at lint time. The harness's
  `load_bootstrap()` could refuse to load a bootstrap whose
  `x-cgp-version` doesn't match its expected version. Currently
  the version is documentation-only. Worth a follow-up.
- **The wire-target / target_alias split is verbose.** A future
  slice could collapse the two fields into a single `target`
  field with the routing's `target` value, and have the
  consumer map the configured target back to the routing key
  via a `pmoves.agent.alias.v1` lookup. Worth a follow-up if
  the consumer forks need to look up the alias often.

## Keeping this file honest

This file makes factual claims about the orchestrator, and a LEARNINGS
file that describes a design the code does not implement is worse than
no LEARNINGS file — it is a wrong answer delivered confidently. The
claims here are therefore gated:

- `pmoves/tests/tools/test_mavis_handoff_learnings_ratchet.py` reads
  the LIVE orchestrator source and the LIVE bootstrap config, and asserts
  that the claims in this file agree with them: the KVM subject, the
  `known_targets` derivation, the wire target, the rejected placeholder
  set, the names of the tests this file cites, and the test counts this
  file quotes. Every expectation is derived from the code — or, for the
  counts, from actually running the orchestrator test file — not typed
  out here, so a code change that invalidates a claim fails the gate
  instead of quietly leaving a false sentence behind.
- `pmoves/tests/tools/test_mavis_handoff_learnings_ratchet_mutation_kill.py`
  proves the gate bites: it puts the stale wording back into THIS file
  and requires the named gate test to die, then restores the file
  byte-exactly.

