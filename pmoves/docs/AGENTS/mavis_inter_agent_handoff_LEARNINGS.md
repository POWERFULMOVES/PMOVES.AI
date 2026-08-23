# Mavis inter-agent handoff v0 — LEARNINGS

This slice closed the **consumer-fork wire-up half of PR #2477**
(Mavis harness v0). The Mavis side of the harness — orchestrator +
bpm_cron — shipped in PR #2477; the missing half was the dispatcher
knowing how to route to the 3 consumer forks (Hermes, KiloClaw,
Pinokio) and surfacing the KVM focus-switch to the operator. The
slice lands 4 commits, 17/17 tests pass, and unblocks the two peer
handoffs (SPARK-KIMI for the Hermes fork, CRUSH for the Pinokio
fork) that read the same CGP bootstrap at session init.

## Lesson 1: bootstrap-driven known_targets > hardcoded set

The v0 orchestrator had `KNOWN_TARGETS = {"mavis", "kiloclaw", "hermes"}`
hardcoded. Adding `pinokio` to the routing block would have been
a 2-line orchestrator change. Worse: future forks (a Hermes-KiloClaw
hybrid, a Code-execution peer, etc.) would each need an orchestrator
edit. The fix: derive `known_targets` from `self.bootstrap.routing`
plus a built-in floor. Adding a routing entry to the CGP now
auto-widens the dispatch surface with zero orchestrator code.

**Corollaries:**
- The built-in set is a FLOOR, not a CEILING. An empty routing block
  still gives the 4 built-ins. This is the right semantics for v0
  (the wire is set up even if a peer isn't subscribed yet) but
  the test `test_known_targets_only_includes_peers_with_routing_entries`
  pins the floor behavior so a future change to "routing-only" is
  intentional, not accidental.
- The Routing dataclass mirrors the CGP routing block; the
  `additionalProperties: false` on the schema's routing object
  means adding a peer requires both a schema update AND a
  Routing dataclass field. The v0 test catches a missing Routing
  field for an entry the schema allows.

## Lesson 2: KVM control surface belongs in the orchestrator, not a new subject

The "Mavis should KVM-switch the operator's focus to the target
node" requirement has 2 design options:
- **(A) New NATS subject** `pmoves.kvm.focus.v1` with a dedicated
  subscriber. Cleaner separation; cost is a new subject, a new
  schema, a new wire-up, and a new entry in the .claude/context/
  nats-subjects.md doc.
- **(B) Reuse `pmoves.bpm.phase.v1`** with a `phase: kvm-focus`
  discriminator. Coarser; cost is a slightly overloaded phase
  enum (but KVM-switch IS a phase transition: the operator's
  focus moves from "Mavis in-session" to "remote peer").

Picked (B) because the KVM controller (a separate service) can
reuse the existing phase-event subscriber, and the harness's
"tagged-services-are-advisory" discipline prefers reusing
existing surfaces to inventing new ones. The discriminator in
the payload (`phase: kvm-focus`) is the contract; the controller
filters on it.

**When option A would be right:** if KVM focus switches become
high-frequency (e.g. per-pomodoro-block instead of per-task),
or if multiple KVM controllers need to subscribe to a KVM-only
stream, the dedicated subject is worth the wire-up cost. Not yet.

## Lesson 3: routing_for() returns a copy, not a reference

`routing_for(target)` returns `dict(routing.<target>)` rather than
the raw dict. This is load-bearing: a caller that mutates the
returned dict (e.g. logging, debugging, partial override) would
otherwise silently mutate the bootstrap's routing, which is
shared across all dispatches. The
`test_routing_for_returns_a_copy_not_a_reference` test is the
regression check; without it, a future "optimize the dict copy"
would silently re-introduce the aliasing.

This is a generic rule for any read-only accessor on a shared
structure: return a copy unless the contract is explicitly
"return the live reference". The bootstrap is shared across
the orchestrator + bpm_cron + any future consumer; aliasing
is a foot-gun.

## Lesson 4: x-cgp-* annotations make the consumer contract machine-checkable

The CGP v1.0 spec is YAML/JSON. The consumer contract (what forks
MUST/MUST NOT do) is prose in a comment. The v0 slice adds
`x-cgp-profile`, `x-cgp-base`, `x-cgp-version`,
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

## Lesson 5: KVM no-op on self/host/empty node is the floor, not a special case

`publish_kvm_focus(task_id, target, node)` is a no-op when
`node in ("self", "host", "")`. The no-op is critical:
- `node="self"` — Mavis's own process. KVM-switching to Mavis's
  host is the default state; no event needed.
- `node="host"` — operator device. Same as self; the operator
  is already on host.
- `node=""` — routing entry without a node. Forward-compat
  guard; future CGPs might add a routing entry without naming
  a node (e.g. "Mavis decides at dispatch time").

The orchestrator's dispatch loop ALSO calls
`publish_kvm_focus` for every agent (not just kiloclaw) and
relies on the no-op to skip local targets. The
`test_dispatch_to_mavis_does_not_publish_kvm_focus` and
`test_dispatch_to_pinokio_does_not_publish_kvm_focus` tests
pin the no-op behavior so a future refactor can't accidentally
publish KVM events for self/host.

## Lesson 6: cross-PR coordination via AGNOTE lane board

The slice was 3 parallel PRs (Mavis, Hermes, Pinokio). The
coordination mechanism was the AGNOTE lane board (3 CLAIM
rows in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`):
- Mavis: orchestrator + bpm_cron side (this PR, 4 commits, 17 tests)
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

## What I'd do differently next slice

- **The CGP bootstrap's routing `additionalProperties: false`**
  is a sharp edge: adding a new peer requires both a schema
  update AND a Routing dataclass field. A future slice could
  add a `pmoves/contracts/schemas/pmoves-bootstrap/_routing_dynamic.py`
  schema that uses `propertyNames` + `additionalProperties: true`
  with a per-key schema, so the dataclass can stay generic.
  Not in scope for v0 (the 3-peer floor is enough), but worth
  flagging for the lane-2 PR.
- **The KVM control surface is fire-and-forget.** The
  orchestrator publishes the kvm-focus event but doesn't
  track whether the KVM controller actually switched focus.
  A follow-up slice could add a `pmoves.kvm.ack.v1` subject
  and a wait-for-ack timeout in `dispatch()`. Not in v0
  (the KVM controller spec is a separate workstream).
- **The CGP schema's `x-cgp-version` annotation should be
  checked at load time**, not at lint time. The harness's
  `load_bootstrap()` could refuse to load a bootstrap whose
  `x-cgp-version` doesn't match its expected version. Currently
  the version is documentation-only. Worth a follow-up.
