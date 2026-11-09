# SPARK Evolution Fabric Handoff — Wave 0 Review

> **GRAPHITI_MARK:** `EVOLUTION-FABRIC::SPARK-HANDOFF::2026-08-04`
> **From:** PMOVES owner / Agent Zero planning lane
> **To:** SPARK local PMOVES-Crush + Hermes Agent, with Archon review support
> **Stage:** rehearsal
> **Branch:** `agent/evolution-fabric-rfc`
> **Scope:** review the RFC package; do not implement Wave 1 yet

## 1. Context

PMOVES already has the principal parts of an agent-evolution system:

- PMOVES-Crush bootstrap, MCP context, Graphiti trail signing, and SPARK awakening path;
- Hermes Agent room, profile/TAC plan, skills, gateway, delegation, and planned NATS bridge;
- AgentGym-RL coordinator, Supabase trajectory storage, geometry subscriptions, evaluations, checkpoints, and Hugging Face publication;
- Agent Zero/P7 room and stage control;
- Archon grounding and knowledge management;
- CHIT/Graphiti provenance;
- NATS cross-node assignments;
- GitHub review and merge controls.

Wave 0 reconciles these systems into one governed lifecycle rather than creating duplicate bridges or controllers.

## 2. Released files

```text
pmoves/docs/architecture/EVOLUTION_FABRIC_RFC.md
pmoves/docs/architecture/EVOLUTION_FABRIC_DEPENDENCY_GRAPH.md
pmoves/docs/contracts/EVOLUTION_FABRIC_NATS_CONTRACTS.md
pmoves/docs/database/EVOLUTION_FABRIC_SUPABASE_SCHEMA.md
pmoves/docs/implementation/EVOLUTION_FABRIC_IMPLEMENTATION_PLAN.md
pmoves/docs/handoffs/SPARK_EVOLUTION_FABRIC_HANDOFF_2026-08-04.md
pmoves/configs/tac_trees/evolution-fabric.tac.yaml
```

## 3. SPARK objective

Perform an evidence-backed architecture review using local Crush and Hermes, with Archon as the independent reviewer/teacher.

Deliver:

1. duplicate-service risks;
2. contract conflicts with existing NATS subjects;
3. AgentGym storage compatibility findings;
4. Hermes integration gaps already covered by `node-hermes-agent.tac.yaml`;
5. Crush hook/export feasibility;
6. SPARK sandbox and persistent-inbox recommendation;
7. a go/no-go recommendation for Wave 1;
8. proposed lane owners.

Do not create migrations, services, or production code during this review task.

## 4. Bootstrap on SPARK

```bash
cd ~/pinokio/api/PMOVES.AI

git fetch origin
git checkout agent/evolution-fabric-rfc
git pull --ff-only origin agent/evolution-fabric-rfc

# Ensure the durable receive path is running before cross-node work.
make -C pmoves nats-agent-inbox

# Load PMOVES credentials without committing secrets.
make -C pmoves secrets-funnel

# Bootstrap the existing PMOVES-Crush configuration and trail signing.
make -C pmoves crush-bootstrap

# Validate Hermes configuration.
hermes doctor
```

If SPARK still needs the initial Crush installation/bootstrap, follow:

```text
pmoves/docs/handoffs/SPARK_CRUSH_AWAKENING_2026-07-12.md
```

## 5. Read-only health checks

```bash
curl -fsS http://localhost:8114/healthz | jq .
curl -fsS http://localhost:8114/agentgym/stats | jq .
curl -fsS http://localhost:3030/health 2>/dev/null || true
curl -fsS http://localhost:8086/healthz 2>/dev/null || true
```

Also verify:

- Supabase is reachable using the active PMOVES environment;
- MinIO is reachable without uploading test data;
- NATS shows the SPARK inbox subscription;
- the Hermes SPARK profile does not attempt to place 70B workloads on smaller nodes;
- the GitHub checkout has no unrelated local edits.

## 6. Cross-node assignment

Publish only after the SPARK persistent inbox is confirmed:

```bash
make -C pmoves nats-pub \
  SUBJECT=claw.task.assign.v1 \
  PAYLOAD='{
    "from": "powerfulmoves",
    "to": "pmoves-spark",
    "task": "evolution-fabric-wave-0-review",
    "files_released": [
      "pmoves/docs/architecture/EVOLUTION_FABRIC_RFC.md",
      "pmoves/docs/architecture/EVOLUTION_FABRIC_DEPENDENCY_GRAPH.md",
      "pmoves/docs/contracts/EVOLUTION_FABRIC_NATS_CONTRACTS.md",
      "pmoves/docs/database/EVOLUTION_FABRIC_SUPABASE_SCHEMA.md",
      "pmoves/docs/implementation/EVOLUTION_FABRIC_IMPLEMENTATION_PLAN.md",
      "pmoves/configs/tac_trees/evolution-fabric.tac.yaml"
    ],
    "after_pr": [],
    "note": "Review-only rehearsal. Compare against live AgentGym, Hermes, Crush, P7, CHIT, Supabase, and NATS contracts. Do not implement Wave 1."
  }'
```

## 7. PMOVES-Crush review lane

Launch from the repository root:

```bash
crush-pmoves
```

Suggested prompt:

```text
You are the PMOVES-Crush implementation reviewer for Evolution Fabric Wave 0.

Read:
- CRUSH.md
- PMOVES.AI_INTEGRATION.md in the PMOVES-Crush fork when available
- pmoves/docs/handoffs/SPARK_CRUSH_AWAKENING_2026-07-12.md
- pmoves/docs/AGENTGYM_RL_OPERATIONS.md
- pmoves/docs/AGENTS/HERMES_AGENT_INTEGRATION.md
- pmoves/configs/tac_trees/node-hermes-agent.tac.yaml
- the six Evolution Fabric RFC documents

Do not modify files.

Report:
1. Which proposed components already exist.
2. Where a hook/adapter is sufficient instead of a service.
3. How Crush can export branch, transcript, changed paths, checks, patch, and Graphiti evidence.
4. Which tests should gate the first Experience Layer benchmark.
5. Any ARM64/SPARK-specific blocker.
6. A go/no-go recommendation for Wave 1.
```

Crush output must be saved as an artifact or review note, not merely left in terminal history.

## 8. Hermes review lane

Use the SPARK PMOVES profile when available:

```bash
hermes profile use pmoves-hermes
hermes
```

Suggested prompt:

```text
Review the Evolution Fabric RFC as the persistent operator and skill-curation runtime.

Do not edit code and do not evolve a skill yet.

Focus on:
- overlap with the existing Hermes Agent integration TAC;
- memory separation between user/private memory and evolution traces;
- the planned NATS/MCP bridge;
- subagent delegation evidence;
- cron/scheduled evaluation use;
- compatibility with Hermes Agent Self-Evolution guardrails;
- which approved trajectories may become skill-evolution datasets.

Produce a structured report with blockers, changes requested, and Wave 1 recommendation.
```

Hermes must not write review findings into private user-memory scope. Store the report in the task artifact/review location.

## 9. Archon review lane

Archon is the independent reviewer and grounding source.

Ground against:

- current service topology;
- current NATS subject catalog;
- AgentGym coordinator/storage code;
- Hermes integration docs/TAC;
- PMOVES-Crush playbook and visual ecosystem;
- Three-Body role separation;
- current security and environment policy.

Archon should produce:

```json
{
  "decision": "approve | revise | reject",
  "confidence": 0.0,
  "duplicate_risks": [],
  "contract_conflicts": [],
  "schema_findings": [],
  "required_changes": [],
  "recommended_lane_owners": {},
  "evidence_refs": []
}
```

Archon may request revisions but must not modify the same RFC during the review role.

## 10. AgentGym lane

Wave 0 is read-only for AgentGym.

Inspect:

- actual Supabase table names and ID types;
- existing trajectory and event fields;
- existing NATS subscriptions;
- storage and event-recording APIs;
- evaluation and training endpoints;
- MinIO/Hugging Face publication assumptions.

Deliver a compatibility note answering:

1. Can Evolution attempts reference existing trajectories directly?
2. Should attempt normalization live in the coordinator or a thin sidecar?
3. Which fields already exist and should not be duplicated?
4. Which deterministic checks can run before any model judge?
5. Which schema foreign keys must wait until live types are confirmed?

Do not start PPO/GRPO training for Wave 0.

## 11. Review scorecard

| Dimension | Weight |
|---|---:|
| Reuse of existing PMOVES components | 0.25 |
| Contract compatibility | 0.20 |
| Security and memory separation | 0.15 |
| SPARK operational feasibility | 0.15 |
| AgentGym compatibility | 0.10 |
| Human review/promotion safety | 0.10 |
| Documentation clarity | 0.05 |

Recommended Wave 1 threshold: `0.85`, with no hard-gate failure.

Hard gates:

- no duplicate controller/service without justification;
- no direct-main mutation path;
- no private-memory training path;
- independent reviewer preserved;
- reliable SPARK inbox confirmed;
- existing event subjects reused where possible.

## 12. Expected Wave 0 output

Create a review artifact such as:

```text
pmoves/docs/reviews/EVOLUTION_FABRIC_WAVE0_SPARK_REVIEW_2026-08-XX.md
```

It should contain:

- Crush findings;
- Hermes findings;
- AgentGym compatibility matrix;
- Archon decision;
- proposed RFC edits;
- Wave 1 lane owners;
- sandbox choice;
- NATS/DB implementation order;
- go/no-go decision.

## 13. Stop condition

Stop after the review artifact is complete.

Do not begin Wave 1 until:

- the docs PR is reviewed;
- requested RFC revisions are incorporated;
- a human owner authorizes implementation;
- SPARK inbox reliability is demonstrated;
- the live AgentGym schema is confirmed.
