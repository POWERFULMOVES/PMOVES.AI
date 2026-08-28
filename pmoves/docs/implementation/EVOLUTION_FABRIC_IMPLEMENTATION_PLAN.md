# Evolution Fabric Implementation Plan

**Status:** Proposed
**Version:** 0.1.0
**Execution model:** docs/contracts first, then SPARK rehearsal

## 1. Outcome

Deliver a governed PMOVES improvement loop that can:

1. receive a bounded task;
2. route it to an eligible node and room;
3. run one or more PMOVES-Crush/Hermes attempts;
4. store artifacts and normalized trajectories;
5. score attempts through AgentGym;
6. obtain independent Archon review;
7. optionally evolve a skill/prompt candidate;
8. open a draft PR with complete evidence;
9. archive approved lessons after human review.

## 2. Ground rules

- Extend existing services before adding new ones.
- Keep command subjects separate from durable facts.
- Use append-only attempt, evaluation, review, and promotion records.
- No agent writes directly to `main`.
- No self-evolution output bypasses tests, semantic-preservation gates, review, or PR approval.
- No protected/private memory enters evolution datasets by default.
- Every production candidate requires signed provenance and a human-reviewed GitHub PR.

## 3. Work lanes

| Lane | Owner/runtime | Scope |
|---|---|---|
| A — Contracts | Codex/Crush + reviewer | RFC, NATS schemas, Supabase proposal, TAC tree |
| B — Persistence | SPARK-Crush | additive Supabase migration, RPCs, tests |
| C — Attempt adapters | PMOVES-Crush + Hermes Agent | normalized attempt start/completion export |
| D — Evaluation | AgentGym + Archon | scoring adapter, rubric, review queue |
| E — Self-evolution | Hermes Self-Evolution | dataset adapter, comparative candidate run |
| F — Promotion | GitHub adapter + human | draft PR evidence and promotion facts |
| G — Operator UX | Gum/Glow/VHS + PMOVES UI | launcher, reports, recordings, dashboard |

## 4. Wave 0 — RFC and contracts

### Deliverables

- `pmoves/docs/architecture/EVOLUTION_FABRIC_RFC.md`
- `pmoves/docs/architecture/EVOLUTION_FABRIC_DEPENDENCY_GRAPH.md`
- `pmoves/docs/contracts/EVOLUTION_FABRIC_NATS_CONTRACTS.md`
- `pmoves/docs/database/EVOLUTION_FABRIC_SUPABASE_SCHEMA.md`
- `pmoves/docs/implementation/EVOLUTION_FABRIC_IMPLEMENTATION_PLAN.md`
- `pmoves/docs/handoffs/SPARK_EVOLUTION_FABRIC_HANDOFF_2026-08-04.md`
- `pmoves/configs/tac_trees/evolution-fabric.tac.yaml`

### Review questions

1. Does the RFC duplicate an existing service?
2. Is Archon independent from the worker?
3. Are SPARK responsibilities consistent with current node profiles?
4. Are NATS subjects minimal and versioned?
5. Is the schema additive to AgentGym?
6. Are human and GitHub promotion boundaries explicit?
7. Is private-memory exclusion clear?

### Exit gate

Docs-only draft PR approved for implementation planning.

## 5. Wave 1 — NATS schemas and persistence

### Target files

```text
pmoves/contracts/evolution/
  evolution.task.created.v1.schema.json
  evolution.attempt.started.v1.schema.json
  evolution.attempt.completed.v1.schema.json
  evolution.evaluation.completed.v1.schema.json
  evolution.review.completed.v1.schema.json
  evolution.candidate.proposed.v1.schema.json
  evolution.candidate.promoted.v1.schema.json
  evolution.candidate.rejected.v1.schema.json
  evolution.run.failed.v1.schema.json

pmoves/supabase/migrations/<timestamp>_evolution_fabric.sql
pmoves/tests/contracts/test_evolution_events.py
pmoves/tests/services/test_evolution_storage.py
```

### Tasks

1. Inspect actual AgentGym table/schema types.
2. Implement additive evolution tables.
3. Add idempotent event inbox or equivalent consumer guard.
4. Add RPCs for task creation, attempt completion, review, and promotion.
5. Add service-role writes and operator reads consistent with active security mode.
6. Add Realtime publication for status tables only.
7. Add JSON Schema fixtures and validation tests.
8. Add valid, invalid, duplicate, signature, and redaction tests.
9. Update `.claude/context/nats-subjects.md` and any canonical subject registry.

### Exit gate

- migration applies to a clean local Supabase instance;
- all contract/storage tests pass;
- duplicate events do not duplicate rows;
- unsigned live-stage promotion facts are rejected.

## 6. Wave 2 — PMOVES-Crush attempt adapter

### Preferred extension point

Use PMOVES-Crush hooks and existing Graphiti trail/bootstrap surfaces rather than a separate full service.

### Proposed files

```text
pmoves/tools/evolution/crush_attempt_exporter.py
pmoves/config/evolution/crush-attempt.schema.json
pmoves/tests/tools/test_crush_attempt_exporter.py
```

### Input

- branch and base commit;
- session ID/workspace;
- model route;
- tool/command transcript;
- changed paths;
- test output;
- Graphiti trail/signature;
- patch/commit SHA.

### Output

- artifact bundle in MinIO or configured object store;
- `evolution.attempt.started.v1`;
- `evolution.attempt.completed.v1`;
- optional geometry event for trajectory alignment.

### Guardrails

- redact secret values before transcript upload;
- enforce allowed/forbidden paths from task spec;
- compute checksums locally;
- do not infer test success from exit text; record actual exit codes;
- do not publish completion until artifacts are durable.

### Exit gate

One synthetic Crush attempt is persisted, replayable, and visible in the task scoreboard.

## 7. Wave 3 — Hermes NATS/MCP adapter

### Preferred extension point

Implement the already planned Hermes NATS/MCP bridge from `node-hermes-agent.tac.yaml`.

### Proposed files

```text
pmoves/services/hermes-agent-bridge/
  app.py
  models.py
  nats_client.py
  redaction.py
  README.md
  tests/
```

A sidecar is acceptable when upstream Hermes extension APIs are insufficient. It must remain thin and delegate core behavior to Hermes.

### Tasks

1. Publish planned Hermes gateway/health/tool/skill/cron/delegation facts.
2. Normalize completed Hermes/delegate work into Evolution attempt envelopes.
3. Separate evolution memory from user/profile/private memory.
4. Implement task-spec hashing and artifact checksums.
5. Add idempotency and redaction.
6. Add local CLI mode when the gateway is not running.

### Exit gate

One Hermes-managed attempt and one delegated subagent attempt are stored without leaking private memory.

## 8. Wave 4 — AgentGym evaluation adapter

### Existing service

`pmoves/services/agentgym-rl-coordinator/`

### Proposed additions

```text
coordinator/evolution.py
coordinator/rubrics.py
coordinator/artifact_reader.py
tests/test_evolution_evaluation.py
```

### Tasks

1. Subscribe to `evolution.attempt.completed.v1`.
2. Validate task hash, checks, artifact checksums, and redaction status.
3. Link or create an AgentGym trajectory.
4. Run deterministic checks before any LLM-based judge.
5. Calculate component scores.
6. Persist evaluation and publish `evolution.evaluation.completed.v1`.
7. Emit failure facts to the existing event/DLQ path.
8. Keep model-training runs optional and separate.

### Default rubric

```text
functional_correctness          0.35
automated_checks                0.20
architecture_compliance         0.15
security_and_privacy            0.10
efficiency                      0.10
documentation_quality           0.05
geometry_and_provenance_quality 0.05
```

### Exit gate

The same fixed attempt produces the same deterministic score components across repeated runs; model-judge variance is recorded separately.

## 9. Wave 5 — Archon review gate

### Tasks

1. Create a versioned review grounding pack containing:
   - task specification;
   - repository architecture docs;
   - changed-file evidence;
   - automated checks;
   - evaluation report;
   - prior relevant decisions.
2. Start a fresh reviewer context.
3. Prevent reviewer tools from writing candidate files.
4. Persist `approve | revise | reject`, confidence, findings, evidence, and rubric version.
5. Publish `evolution.review.completed.v1`.
6. Store approved lessons only after promotion level permits it.

### Exit gate

- reviewer identity differs from worker;
- an intentionally drifting candidate is rejected;
- review findings cite actual evidence.

## 10. Wave 6 — Hermes Self-Evolution adapter

### Repository

`POWERFULMOVES/pmoves-hermes-agent-self-evolution`

### First target

A PMOVES-specific Hermes skill used in the Experience Layer pilot, not production code.

### Tasks

1. Export approved and experimental trajectories into a versioned eval dataset.
2. Add PMOVES task/attempt/evaluation readers.
3. Run DSPy/GEPA with fixed iteration and spend limits.
4. Enforce:
   - full tests;
   - ≤15KB skill size;
   - semantic-preservation rubric;
   - caching compatibility;
   - no secret/private-memory references.
5. Compare baseline and evolved variants.
6. Publish a candidate; never commit directly to the target default branch.
7. Open a draft PR only when the evolved variant beats baseline and passes all gates.

### Exit gate

An evolved skill candidate shows a measurable improvement on the fixed dataset and remains semantically within scope.

## 11. Wave 7 — GitHub promotion adapter

### Tasks

1. Build a draft-PR evidence body from durable records.
2. Include task hash, attempt, checks, score, review, artifact links, and Graphiti/CHIT provenance.
3. Refuse PR creation when hard gates fail.
4. Watch required checks and review state.
5. Publish promotion only after human-reviewed merge.
6. Run post-merge smoke tests.
7. Transition P7 room to archive and store approved lessons.

### Draft PR template

```markdown
## Task
<task title and immutable task hash>

## Candidate
<runtime, agent, node, branch, commit>

## Evidence
- Automated checks: ...
- AgentGym score: ...
- Archon review: ...
- Artifacts: ...
- CHIT/Graphiti trail: ...

## Risks and rollback
...

## Human decision required
This candidate cannot promote automatically.
```

## 12. Wave 8 — Operator UX

### Gum

- choose task or dataset;
- choose eligible node/runtime;
- confirm allowed paths and cost limits;
- approve retries and candidate submission.

### Glow

- render task specs;
- render scorecards and review reports;
- browse handoffs and accepted lessons.

### VHS

Add reproducible tapes:

```text
pmoves-crush-evolution-bootstrap.tape
spark-evolution-pilot.tape
hermes-skill-evolution.tape
archon-review-gate.tape
```

### PMOVES UI/Open Notebook

- task list and lifecycle;
- attempt comparison;
- score/review evidence;
- snapshot/replay;
- candidate/PR state;
- accepted lessons;
- CHIT geometry links.

### Exit gate

An operator can understand why a candidate passed or failed without reading raw database rows or terminal logs.

## 13. First benchmark: Experience Layer skin manifest

### Goal

Add a versioned skin manifest validator compatible with the existing PMOVES UI/A2UI direction.

### Allowed paths

```text
pmoves/ui/**
pmoves/docs/**
pmoves/tests/**
```

### Forbidden paths

```text
**/.env*
**/secrets/**
pmoves/supabase/migrations/**   # not needed for this benchmark
```

### Required checks

- JSON Schema validation;
- TypeScript typecheck;
- unit tests for valid/invalid manifests;
- deterministic seeded procedural parameters;
- backwards-compatible fallback for unskinned components;
- no raw remote asset URL without an allowlisted storage policy;
- docs and example manifest.

### Competing attempts

- Attempt A: PMOVES-Crush implementation.
- Attempt B: Hermes-managed bounded code subagent.
- Optional Attempt C: Codex baseline.

### Review focus

- does it extend existing UI contracts instead of replacing them?
- is the manifest modality-agnostic?
- are bubbles/views separate from content blocks?
- are seeds reproducible?
- is asset loading safe?
- are tests sufficient?

## 14. SPARK execution checklist

1. Pull the RFC branch.
2. Run the persistent NATS inbox.
3. Verify AgentGym, TensorZero, Hi-RAG, Supabase, MinIO, and NATS health.
4. Bootstrap PMOVES-Crush.
5. Validate the SPARK Hermes profile and `hermes doctor`.
6. Confirm sandbox backend.
7. Publish task assignment.
8. Run first attempt in rehearsal.
9. Verify durable artifacts before evaluation.
10. Stop before code promotion unless Wave 1 contracts and storage are merged.

## 15. Rollback

Because Wave 0 is docs/config only, rollback is branch deletion or PR closure.

For later waves:

- disable `evolution.*` consumers;
- stop EVOLUTION stream consumers without deleting records;
- mark running tasks cancelled;
- retain immutable artifacts and records;
- remove UI routes without dropping tables;
- never rewrite previously published promotion facts;
- use a compensating rejection/supersession record when needed.

## 16. Definition of done

The initial implementation is done when:

- three replayable attempts exist;
- one candidate fails a hard gate;
- one candidate passes evaluation and independent review;
- a draft PR is created with complete evidence;
- no agent merges directly;
- a human merge emits promotion and archive facts;
- approved lessons are visible to Archon/Hermes;
- the operator can replay the lifecycle from Supabase, MinIO, NATS, and CHIT/Graphiti evidence.
