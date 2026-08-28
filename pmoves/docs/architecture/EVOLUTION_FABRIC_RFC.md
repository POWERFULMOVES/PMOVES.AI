# PMOVES Evolution Fabric RFC

**Status:** Proposed / rehearsal
**Version:** 0.1.0
**Date:** 2026-08-04
**Branch:** `agent/evolution-fabric-rfc`
**Initial execution node:** `pmoves-spark`

## 1. Decision

PMOVES will add an **Evolution Fabric** that coordinates PMOVES-Crush, Hermes Agent, Hermes Agent Self-Evolution, AgentGym-RL, Archon, Agent Zero/P7, CHIT, Supabase, MinIO, NATS, and GitHub into a governed improvement loop.

The fabric does **not** introduce duplicate orchestration services. It extends existing PMOVES capabilities:

- PMOVES-Crush remains the interactive coding/runtime worker.
- Hermes Agent remains the persistent operator, skill curator, scheduler, and delegation runtime.
- Hermes Agent Self-Evolution remains an external optimizer that proposes improved skills, prompts, tools, and code through evaluation and pull requests.
- AgentGym-RL remains the trajectory, evaluation, training, checkpoint, and model-publication plane.
- Archon remains the knowledge teacher, rubric source, and post-work reviewer.
- Agent Zero and P7 remain the planning, routing, room, suit, and stage-control plane.
- SPARK remains a node and execution laboratory, not a new orchestration product.
- CHIT and AI Graphiti remain the provenance, geometry, attribution, and replay layer.
- GitHub pull requests remain the promotion boundary for production changes.

## 2. Why this is needed

PMOVES already contains most of the individual capabilities required for agent evolution, but they currently operate as adjacent systems:

- `CRUSH.md` defines Crush bootstrap, TensorZero routing, MCP context, Graphiti attribution, and SPARK handoff.
- `pmoves/docs/AGENTS/HERMES_AGENT_INTEGRATION.md` and `pmoves/configs/tac_trees/node-hermes-agent.tac.yaml` define Hermes profiles, skills, gateway, NATS, CHIT, and SPARK placement.
- `pmoves/docs/AGENTGYM_RL_OPERATIONS.md` and `pmoves/services/agentgym-rl-coordinator/` define geometry-aware trajectories, evaluations, training runs, MinIO checkpoints, Supabase storage, and model publication.
- `.claude/context/nats-subjects.md` defines cross-node delegation, P7 stage facts, geometry subjects, and agent coordination.
- `pmoves/config/agent_registry.yaml` already registers Crush, Hermes Agent, Agent Zero, Archon, and the Three-Body workflow roles.
- `pmoves/docs/handoffs/SPARK_CRUSH_AWAKENING_2026-07-12.md` already identifies SPARK as the next Crush and Hugging Face execution node.

The missing layer is a shared contract that turns these capabilities into one repeatable loop: **specify → delegate → attempt → observe → score → review → evolve → promote**.

## 3. Non-goals

This RFC does not:

1. Replace AgentGym-RL with a second training service.
2. Replace P7 or Agent Zero with a `spark-controller` service.
3. Create separate `crush-bridge` and `hermes-bridge` products when hooks, MCP, gateway, and NATS adapters can extend the existing runtimes.
4. Allow agents to merge directly to `main`.
5. Allow self-evolution to change production prompts, tools, skills, or code without a versioned candidate, evaluation evidence, and human-reviewed PR.
6. Treat Hermes Agent and the Hermes-3 model as the same component.
7. Move secrets, protected health data, or private user memory into training datasets by default.

## 4. Actors and role boundaries

### 4.1 Agent Zero / P7 — planner and router

Responsibilities:

- Accept operator intent.
- Resolve the target room, repository, stage, node, and suit.
- Create an immutable task specification.
- Route execution to SPARK or another eligible node.
- Enforce stage transitions: `rehearsal → live → review → archive`.
- Refuse promotion when review evidence or CHIT signing is incomplete.

Agent Zero/P7 may plan and route but should not silently become the implementation worker for an Evolution Fabric task.

### 4.2 Archon — teacher and reviewer

Responsibilities:

- Assemble grounding packs, architecture constraints, prior decisions, failed attempts, and evaluation rubrics.
- Provide pre-work context without editing production code.
- Review completed attempts against the task specification and repo conventions.
- Emit evidence-backed approval, rejection, or revision requests.
- Store lessons and approved patterns for future tasks.

Archon is the Memory/Control surface. It must not review and modify the same candidate in one role.

### 4.3 PMOVES-Crush — implementation worker

Responsibilities:

- Work inside a bounded repository and branch.
- Use LSP, MCP, repository context, tests, and PMOVES trail signing.
- Produce patches, commits, test evidence, and a concise reflection.
- Publish session/attempt facts to the Evolution Fabric.
- Never self-approve a candidate.

PMOVES-Crush should use the existing `crush-pmoves` bootstrap and PMOVES-Crush integration contract rather than a second configuration system.

### 4.4 Hermes Agent — persistent operator and skill curator

Responsibilities:

- Maintain cross-session context and approved procedural memory.
- Schedule and supervise bounded work.
- Delegate parallel subtasks when the task specification allows it.
- Curate reusable skills from approved trajectories.
- Publish gateway, MCP, skill, cron, and delegation facts through the planned Hermes NATS bridge.
- Keep user memory, clinical/private memory, and training/evolution memory in explicitly separated scopes.

### 4.5 Hermes Agent Self-Evolution — candidate optimizer

Responsibilities:

- Generate candidate variants for skills, tool descriptions, prompt sections, and later code.
- Use DSPy/GEPA or another configured optimizer over versioned evaluation datasets and execution traces.
- Enforce tests, size limits, semantic preservation, and caching compatibility.
- Produce a candidate branch or patch and evaluation report.
- Never write directly to production branches.

### 4.6 AgentGym-RL — trajectory and evaluation plane

Responsibilities:

- Receive normalized attempts and CHIT/geometry events.
- Store trajectories and evaluation metadata in Supabase.
- Run deterministic and model-based scoring.
- Coordinate optional PPO/GRPO training runs.
- Store checkpoints in MinIO and publish approved datasets/models through existing pipelines.
- Keep software-change evaluation separate from model-weight promotion.

### 4.7 SPARK — execution laboratory

Responsibilities:

- Host large-model inference, AgentGym, Hugging Face tooling, sandboxed attempts, and comparative evaluation.
- Run PMOVES-Crush and Hermes profiles appropriate to the node.
- Maintain the persistent NATS inbox before cross-node delegation is considered reliable.
- Produce PR-ready artifacts; never bypass GitHub review.

## 5. The evolution loop

```text
Operator intent
    |
    v
Agent Zero / P7 creates immutable task specification
    |
    v
Archon assembles grounding pack + rubric + known constraints
    |
    v
claw.task.assign.v1 routes the task to SPARK
    |
    +-------------------------------+
    |                               |
    v                               v
PMOVES-Crush attempt          Hermes delegated attempt
(code/config/docs/tests)      (operations/skills/workflows)
    |                               |
    +---------------+---------------+
                    v
         Normalized trajectory + artifacts
                    |
                    v
          AgentGym scoring and replay
                    |
                    v
             Archon review gate
                    |
        +-----------+-----------+
        |                       |
        v                       v
    revise/retry          candidate accepted
                                |
                                v
                    optional self-evolution run
                                |
                                v
                      comparative evaluation
                                |
                                v
                      human-reviewed draft PR
                                |
                                v
                    merge → archive → learn
```

## 6. Task specification

Every task must be created from an immutable, versioned specification with at least:

```json
{
  "task_id": "evo-uuid",
  "title": "Implement the Experience Layer skin manifest validator",
  "repository": "POWERFULMOVES/PMOVES.AI",
  "base_ref": "main",
  "target_node": "pmoves-spark",
  "room_id": "hermes-agent.room.control",
  "stage": "rehearsal",
  "planner": "agent_zero",
  "workers": ["crush", "hermes-agent"],
  "reviewer": "archon",
  "scope": {
    "allowed_paths": ["pmoves/ui/**", "pmoves/docs/**"],
    "forbidden_paths": ["**/.env*", "**/secrets/**"]
  },
  "acceptance": {
    "checks": ["unit", "lint", "typecheck", "security"],
    "minimum_score": 0.85,
    "hard_gates": ["tests_pass", "no_secret_leak", "review_approved"]
  },
  "dataset": {
    "id": "experience-layer-smoke-v1",
    "version": "1.0.0"
  }
}
```

The task specification is hashed and referenced by all attempt, review, and promotion records.

## 7. Attempt isolation

Each attempt must have:

- a unique branch or sandbox workspace;
- a fixed base commit;
- an explicit runtime (`pmoves-crush`, `hermes-agent`, `hermes-self-evolution`);
- a node identity and model route;
- a captured command/tool transcript with secret redaction;
- test and benchmark output;
- artifact references stored outside chat context;
- a CHIT/Graphiti attribution record;
- a terminal status: `completed`, `failed`, `cancelled`, or `timed_out`.

Parallel agents may work on different subtasks or competing candidates. They must not concurrently edit the same path unless the task explicitly defines a merge strategy.

## 8. Evaluation and promotion

### 8.1 Default score

```text
score =
  0.35 * functional_correctness +
  0.20 * automated_checks +
  0.15 * architecture_compliance +
  0.10 * security_and_privacy +
  0.10 * efficiency +
  0.05 * documentation_quality +
  0.05 * geometry_and_provenance_quality
```

Default promotion threshold: `0.85`.

### 8.2 Hard gates

A candidate cannot be promoted when any of the following is true:

- required tests fail;
- a secret or protected-data leak is detected;
- the attempt modifies forbidden paths;
- the reviewer is the same identity that produced the candidate;
- the task or dataset hash does not match the recorded version;
- CHIT/Graphiti attribution is missing for a production candidate;
- the change bypasses repository branch protections or required checks;
- self-evolution changes the candidate's declared purpose.

### 8.3 Promotion levels

1. **Observed:** trajectory captured; no reuse decision.
2. **Reusable pattern:** lesson or snippet approved for Archon/Cipher memory.
3. **Skill candidate:** versioned Hermes/agent skill proposed.
4. **Code candidate:** branch and draft PR created.
5. **Model candidate:** checkpoint evaluated; separate model-promotion process required.
6. **Production:** human-reviewed merge and post-merge smoke pass.

## 9. Memory separation

The fabric uses four explicit memory scopes:

| Scope | Purpose | Default destination |
|---|---|---|
| Task memory | Immutable task and acceptance criteria | Supabase |
| Attempt memory | Tool calls, patches, tests, metrics | AgentGym trajectories + object storage |
| Approved procedural memory | Reusable lessons and skills | Archon/Cipher/Hermes skills |
| Private user/domain memory | User profile, clinical, financial, or personal data | Existing protected store; excluded from training by default |

No private user/domain memory enters an evolution dataset unless a separate consent, redaction, and data-governance process approves it.

## 10. Existing contracts reused

The Evolution Fabric reuses these existing surfaces:

- `claw.task.assign.v1` for cross-node assignment.
- `p7.nats.launch`, `p7.nats.session`, and P7 room facts for lifecycle control.
- `geometry.event.v1` and `tokenism.geometry.event.v1` for trajectory geometry.
- `agentgym.train.completed.v1` and `agentgym.model.published.v1` for training/model facts.
- `skills.pipeline.model-benchmark-viz.v1` for benchmark visualization.
- planned Hermes subjects in `node-hermes-agent.tac.yaml` for gateway, MCP, skill, cron, and delegation facts.
- PMOVES-Crush Graphiti trail signing and existing bootstrap/configuration.

New subjects are intentionally limited to the gaps documented in `EVOLUTION_FABRIC_NATS_CONTRACTS.md`.

## 11. First pilot

The first Evolution Fabric benchmark will be a bounded implementation slice from the PMOVES Experience Layer:

> Add and validate a versioned UI skin manifest contract without replacing the existing Next.js/Supabase UI or A2UI bridge.

Why this pilot:

- bounded paths and clear tests;
- exercises JSON schema, TypeScript, docs, UI integration, and review;
- can produce competing Crush and Hermes-assisted candidates;
- supports VHS-recorded demonstrations and Glow-rendered reports;
- low risk to production services;
- directly advances the rich-avatar/Open Notebook objective.

## 12. Delivery waves

### Wave 0 — RFC and handoff

- Architecture RFC.
- Dependency graph.
- NATS contracts.
- Supabase schema proposal.
- SPARK handoff.
- TAC tree.

### Wave 1 — Event and storage adapters

- Add minimal Evolution Fabric NATS contracts to catalogs/registries.
- Add additive Supabase migrations referencing existing AgentGym tables.
- Add service-role write paths and read policies.
- Add contract tests.

### Wave 2 — Runtime adapters

- PMOVES-Crush attempt exporter using hooks and Graphiti trail data.
- Hermes NATS/MCP bridge implementation from the existing TAC plan.
- Normalization into a shared attempt envelope.

### Wave 3 — SPARK execution

- Validate SPARK persistent inbox.
- Bootstrap PMOVES-Crush and Hermes profiles.
- Run the first comparative benchmark.
- Store artifacts, trajectories, and review evidence.

### Wave 4 — Self-evolution

- Connect approved Hermes trajectories to `pmoves-hermes-agent-self-evolution`.
- Run skill optimization with fixed datasets and hard gates.
- Create a PR-only candidate.

### Wave 5 — Operator experience

- Evolution dashboard in the existing UI workspace.
- Open Notebook mirrors for tasks, attempts, reviews, and accepted lessons.
- Gum launch menus, Glow reports, and VHS reproducible demos.

## 13. Acceptance criteria for live-stage promotion

The Evolution Fabric may move from `rehearsal` to `live` only when:

- SPARK receives delegated work through a verified persistent inbox;
- at least three complete task runs are stored and replayable;
- one failed candidate is correctly rejected by a hard gate;
- one accepted candidate produces a draft PR with complete evidence;
- Archon review is independent from the worker identity;
- secrets and private-memory redaction tests pass;
- NATS contracts are catalogued and contract-tested;
- Supabase records, MinIO artifacts, and CHIT/Graphiti trails reconcile;
- operator documentation and rollback procedures are complete;
- a human owner signs the P7 live-stage transition.

## 14. Open decisions

1. Whether the normalized attempt exporter lives inside the existing AgentGym coordinator or as a small sidecar.
2. Whether software-change evaluation remains under `agentgym.*` or uses the proposed `evolution.*` namespace.
3. Which sandbox backend SPARK should use first: Docker, E2B Danger Room, or Hermes terminal backend.
4. Whether Archon stores approved procedural lessons directly or through Cipher/Graphiti first.
5. Whether the first self-evolution target is a Hermes skill, a Crush system prompt prefix, or an Experience Layer review rubric.

## 15. Recommendation

Approve Wave 0 as a docs/contracts PR. After review, hand Wave 1 to SPARK with:

- Agent Zero/P7 as planner/router;
- PMOVES-Crush and Hermes Agent as workers;
- AgentGym-RL as trajectory/evaluation plane;
- Archon as independent reviewer and teacher;
- CHIT/Graphiti as provenance;
- GitHub draft PRs as the only production promotion path.
