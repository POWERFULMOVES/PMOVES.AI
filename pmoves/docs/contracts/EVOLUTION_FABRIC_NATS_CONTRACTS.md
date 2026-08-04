# Evolution Fabric NATS Contracts

**Status:** Proposed
**Version:** 0.1.0

## 1. Contract principles

1. Reuse existing P7, CLAW, Hermes, AgentGym, geometry, and Graphiti subjects.
2. Separate commands from durable facts.
3. Persist Evolution Fabric facts before consumers treat them as authoritative.
4. Make every fact idempotent and attributable to a task, attempt, node, room, and trace.
5. Redact secrets and protected data before publication.
6. Keep runtime-native events optional; normalize all accepted work into the `evolution.*` fact namespace.
7. Require versioned JSON schemas and contract tests before `live` promotion.

## 2. Existing subjects reused

| Subject | Type | Evolution Fabric use |
|---|---|---|
| `p7.nats.launch` | command | Start the selected room/profile on the target node |
| `p7.nats.session` | command | Pause, resume, end, archive, or change stage |
| `p7.room.session.started.v1` | fact | Bind an Evolution task to a live room session |
| `p7.room.checkpoint.v1` | fact | Record resumable task checkpoints |
| `p7.room.stage.changed.v1` | fact | Gate rehearsal/live/review/archive transitions |
| `claw.task.assign.v1` | command | Cross-node handoff to SPARK or another runtime |
| `geometry.event.v1` | fact | Existing AgentGym trajectory geometry input |
| `tokenism.geometry.event.v1` | fact | Existing geometry/prosodic trajectory input |
| `agentgym.train.completed.v1` | fact | Model-training completion |
| `agentgym.model.published.v1` | fact | Approved dataset/model publication |
| `skills.pipeline.model-benchmark-viz.v1` | command/fact trigger | Benchmark visualization pipeline |
| `hermes.gateway.launched.v1` | planned fact | Hermes gateway readiness |
| `hermes.gateway.health.v1` | planned fact | Hermes gateway health |
| `hermes.mcp.toolcall.v1` | planned fact | Hermes tool invocation evidence |
| `hermes.skill.curated.v1` | planned fact | Approved Hermes skill curation |
| `hermes.cron.executed.v1` | planned fact | Scheduled operation evidence |
| `hermes.delegate.completed.v1` | planned fact | Hermes subagent completion evidence |

`claw.task.assign.v1` is currently fire-and-forget. A target node must run the persistent inbox or an equivalent subscribed runtime before assignment is considered reliable.

## 3. Canonical envelope

All new `evolution.*` facts use this envelope:

```json
{
  "event_id": "uuid",
  "event": "evolution.attempt.completed.v1",
  "schema_version": "1.0.0",
  "task_id": "evo-task-uuid",
  "attempt_id": "evo-attempt-uuid",
  "trace_id": "trace-uuid",
  "source": {
    "service": "pmoves-crush-attempt-adapter",
    "agent_id": "crush",
    "runtime": "pmoves-crush",
    "node_id": "pmoves-spark"
  },
  "room": {
    "room_id": "hermes-agent.room.control",
    "session_id": "p7-session-uuid",
    "stage": "rehearsal"
  },
  "occurred_at": "2026-08-04T17:00:00Z",
  "task_spec_sha256": "hex",
  "shape_id": "optional-cgp-shape-id",
  "payload": {},
  "signature": {
    "alg": "HMAC-SHA256",
    "kid": "spark-evolution-1",
    "sig": "base64"
  }
}
```

### Required envelope fields

- `event_id`
- `event`
- `schema_version`
- `task_id`
- `trace_id`
- `source.service`
- `source.agent_id`
- `source.runtime`
- `source.node_id`
- `room.stage`
- `occurred_at`
- `task_spec_sha256`
- `payload`

`attempt_id` is required for attempt, evaluation, review, and candidate facts.

## 4. New durable fact subjects

### 4.1 `evolution.task.created.v1`

Published after the immutable task specification is stored.

```json
{
  "event": "evolution.task.created.v1",
  "task_id": "evo-task-uuid",
  "payload": {
    "title": "Implement skin manifest validator",
    "repository": "POWERFULMOVES/PMOVES.AI",
    "base_ref": "main",
    "target_node": "pmoves-spark",
    "planner": "agent_zero",
    "workers": ["crush", "hermes-agent"],
    "reviewer": "archon",
    "dataset_id": "experience-layer-smoke-v1",
    "dataset_version": "1.0.0",
    "minimum_score": 0.85,
    "hard_gates": ["tests_pass", "no_secret_leak", "review_approved"]
  }
}
```

**Consumers:** P7, SPARK inbox, Hermes scheduler, observability, Open Notebook mirror.

### 4.2 `evolution.attempt.started.v1`

Published after the sandbox/branch and runtime are confirmed.

```json
{
  "event": "evolution.attempt.started.v1",
  "task_id": "evo-task-uuid",
  "attempt_id": "evo-attempt-uuid",
  "payload": {
    "branch": "agent/evo-task-uuid-crush-1",
    "base_commit": "sha",
    "workspace": "sandbox://spark/evo-attempt-uuid",
    "model_route": "tensorzero:agent_zero",
    "allowed_paths": ["pmoves/ui/**", "pmoves/docs/**"],
    "started_by": "crush"
  }
}
```

**Consumers:** AgentGym accumulator, observability, Open Notebook mirror.

### 4.3 `evolution.attempt.completed.v1`

Normalized completion fact for PMOVES-Crush, Hermes, Codex, or another approved worker.

```json
{
  "event": "evolution.attempt.completed.v1",
  "task_id": "evo-task-uuid",
  "attempt_id": "evo-attempt-uuid",
  "payload": {
    "status": "completed",
    "commit_sha": "sha",
    "patch_uri": "s3://evolution-artifacts/evo-attempt-uuid/patch.diff",
    "transcript_uri": "s3://evolution-artifacts/evo-attempt-uuid/transcript.jsonl",
    "test_report_uri": "s3://evolution-artifacts/evo-attempt-uuid/tests.json",
    "changed_paths": ["pmoves/ui/runtime/skin/schema.ts"],
    "checks": {
      "unit": "passed",
      "lint": "passed",
      "typecheck": "passed",
      "security": "passed"
    },
    "reflection": "Implemented the bounded manifest validator without changing existing A2UI contracts.",
    "artifact_sha256": "hex"
  }
}
```

**Consumers:** AgentGym evaluator, Archon review queue, CHIT/Graphiti trail processor, Open Notebook mirror.

### 4.4 `evolution.evaluation.completed.v1`

Published when deterministic and model-based scoring is stored.

```json
{
  "event": "evolution.evaluation.completed.v1",
  "task_id": "evo-task-uuid",
  "attempt_id": "evo-attempt-uuid",
  "payload": {
    "evaluation_id": "uuid",
    "dataset_id": "experience-layer-smoke-v1",
    "dataset_version": "1.0.0",
    "score": 0.91,
    "scores": {
      "functional_correctness": 0.96,
      "automated_checks": 1.0,
      "architecture_compliance": 0.88,
      "security_and_privacy": 1.0,
      "efficiency": 0.78,
      "documentation_quality": 0.85,
      "geometry_and_provenance_quality": 0.9
    },
    "hard_gates": {
      "tests_pass": true,
      "no_secret_leak": true,
      "review_approved": null
    },
    "report_uri": "s3://evolution-artifacts/evo-attempt-uuid/evaluation.json"
  }
}
```

**Consumers:** Archon review queue, dashboard, comparative evaluation, promotion gate.

### 4.5 `evolution.review.completed.v1`

Published after an independent review is persisted.

```json
{
  "event": "evolution.review.completed.v1",
  "task_id": "evo-task-uuid",
  "attempt_id": "evo-attempt-uuid",
  "payload": {
    "review_id": "uuid",
    "reviewer": "archon",
    "decision": "approve",
    "confidence": 0.89,
    "rubric_version": "experience-layer-review-v1",
    "findings": [],
    "required_changes": [],
    "evidence_refs": [
      "s3://evolution-artifacts/evo-attempt-uuid/evaluation.json",
      "git://POWERFULMOVES/PMOVES.AI@sha"
    ],
    "independent_from_worker": true
  }
}
```

`decision` is `approve | revise | reject`.

**Consumers:** Candidate builder, P7 stage gate, Hermes skill curator, dashboard.

### 4.6 `evolution.candidate.proposed.v1`

Published for a versioned skill, prompt, tool, code, config, or model candidate.

```json
{
  "event": "evolution.candidate.proposed.v1",
  "task_id": "evo-task-uuid",
  "attempt_id": "evo-attempt-uuid",
  "payload": {
    "candidate_id": "uuid",
    "kind": "code",
    "name": "experience-layer-skin-validator",
    "version": "0.1.0",
    "source_runtime": "pmoves-crush",
    "artifact_uri": "git://POWERFULMOVES/PMOVES.AI@sha",
    "semantic_hash": "hex",
    "evaluation_id": "uuid",
    "review_id": "uuid",
    "promotion_status": "draft_pr_ready"
  }
}
```

`kind` is `skill | prompt | tool_description | code | config | model | dataset`.

**Consumers:** GitHub PR adapter, Hermes Self-Evolution, dashboard, Open Notebook mirror.

### 4.7 `evolution.candidate.promoted.v1`

Published only after a human-reviewed merge or an explicitly approved non-code promotion.

```json
{
  "event": "evolution.candidate.promoted.v1",
  "task_id": "evo-task-uuid",
  "attempt_id": "evo-attempt-uuid",
  "payload": {
    "candidate_id": "uuid",
    "promotion_level": "production",
    "repository": "POWERFULMOVES/PMOVES.AI",
    "pull_request": 2301,
    "merge_sha": "sha",
    "approved_by": ["powerfulmoves"],
    "post_merge_checks": "passed",
    "archived_at": "2026-08-04T19:00:00Z"
  }
}
```

**Consumers:** Archon/Cipher lesson store, Hermes skill registry, P7 archive transition, dashboard.

### 4.8 `evolution.candidate.rejected.v1`

```json
{
  "event": "evolution.candidate.rejected.v1",
  "task_id": "evo-task-uuid",
  "attempt_id": "evo-attempt-uuid",
  "payload": {
    "candidate_id": "uuid",
    "reason": "architecture_drift",
    "hard_gate": null,
    "review_id": "uuid",
    "reusable_lessons_allowed": true
  }
}
```

### 4.9 `evolution.run.failed.v1`

Used when a task, attempt, evaluation, review, or promotion pipeline fails unexpectedly.

```json
{
  "event": "evolution.run.failed.v1",
  "task_id": "evo-task-uuid",
  "attempt_id": "evo-attempt-uuid",
  "payload": {
    "phase": "evaluation",
    "error_class": "dependency_unavailable",
    "message": "AgentGym coordinator unavailable",
    "retryable": true,
    "retry_after_seconds": 60,
    "dlq_id": "optional-id"
  }
}
```

## 5. Runtime-native adapter mapping

| Runtime fact | Normalized fact |
|---|---|
| PMOVES-Crush hook/session export | `evolution.attempt.started.v1` / `evolution.attempt.completed.v1` |
| `hermes.mcp.toolcall.v1` | attempt evidence only; not completion by itself |
| `hermes.delegate.completed.v1` | `evolution.attempt.completed.v1` after artifact validation |
| `hermes.skill.curated.v1` | `evolution.candidate.proposed.v1` with `kind=skill` |
| Hermes Self-Evolution optimizer result | `evolution.candidate.proposed.v1` plus evaluation fact |
| AgentGym deterministic/model score | `evolution.evaluation.completed.v1` |
| Archon decision | `evolution.review.completed.v1` |
| GitHub merge | `evolution.candidate.promoted.v1` |

## 6. Command versus fact flow

```text
claw.task.assign.v1                  command: please run work on SPARK
  ↓
evolution.task.created.v1            fact: task persisted and immutable
  ↓
evolution.attempt.started.v1         fact: workspace/runtime confirmed
  ↓
evolution.attempt.completed.v1       fact: artifacts persisted
  ↓
evolution.evaluation.completed.v1    fact: scoring persisted
  ↓
evolution.review.completed.v1        fact: independent review persisted
  ↓
evolution.candidate.proposed.v1      fact: versioned candidate exists
  ↓
evolution.candidate.promoted.v1      fact: human-reviewed promotion completed
```

No downstream consumer should infer completion from a command subject.

## 7. JetStream recommendation

Create a durable stream after schemas are approved:

```text
Stream: EVOLUTION
Subjects: evolution.>
Storage: file
Retention: limits
Max age: 90 days for bus replay
Duplicate window: 24 hours
```

Long-term records remain in Supabase/MinIO. JetStream is transport replay, not the canonical audit database.

Recommended durable consumers:

- `agentgym-evolution-accumulator`
- `archon-evolution-review-queue`
- `notebook-evolution-mirror`
- `evolution-observability`
- `evolution-github-promoter`

## 8. Idempotency

Consumers must use `event_id` as the primary idempotency key. Artifact-producing facts also include a content checksum. Reprocessing the same event may refresh observability but must not create duplicate task, attempt, evaluation, review, or candidate rows.

## 9. Security and redaction

Before publishing:

- remove environment-variable values and access tokens;
- replace protected paths with logical references;
- redact private user/domain memory unless explicitly approved;
- truncate untrusted command output in bus messages and store full output in protected object storage;
- validate `task_spec_sha256` and artifact checksums;
- require CHIT signing for production candidate and promotion facts;
- reject unsigned node identities when the room is in `live` stage.

## 10. Contract-test requirements

Each subject requires:

1. JSON Schema fixture.
2. Valid-event test.
3. Missing-required-field test.
4. Unsupported-version test.
5. Duplicate-event idempotency test.
6. Redaction test.
7. Signature verification test for live-stage facts.
8. Supabase persistence test.
9. NATS publish/consume smoke test.
10. Open Notebook mirror test where applicable.
