# Part 1: GRAPHITI TAC Trees Comprehensive Structured Analysis

**Generated**: 2026-04-17
**Source**: 6 TAC tree YAML files under `pmoves/configs/tac_trees/`
**Scope**: All GRAPHITI/CHIT-related definitions across the TAC tree corpus
**Total lines analyzed**: 3,081 across 6 files (122,685 bytes)

---

## Table of Contents

1. [File Inventory](#1-file-inventory)
2. [GRAPHITI_MARK Comments](#2-graphiti_mark-comments)
3. [pr-monitor-graphiti-chit Flow: End-to-End Trace](#3-pr-monitor-graphiti-chit-flow-end-to-end-trace)
4. [NATS Subject Master Catalog](#4-nats-subject-master-catalog)
5. [Agent Roles with GRAPHITI-Specific Responsibilities](#5-agent-roles-with-graphiti-specific-responsibilities)
6. [CHIT/GRAPHITI Skill Definitions](#6-chitgraphiti-skill-definitions)
7. [Phase Definitions and Transitions](#7-phase-definitions-and-transitions)
8. [Cross-Tree Dependencies](#8-cross-tree-dependencies)
9. [Component Status Summary](#9-component-status-summary)
10. [Per-File Detailed Extraction](#10-per-file-detailed-extraction)

---

## 1. File Inventory

| # | File | Lines | Bytes | Contains "graphiti" | Contains "chit" |
|---|------|-------|-------|---------------------|-------------------|
| 1 | tokenism-chit.tac.yaml | 122 | 4,934 | No | Yes |
| 2 | training-pipeline.tac.yaml | 298 | 12,210 | Yes (Agent Graphiti trail entries) | Yes |
| 3 | archon-agents.tac.yaml | 134 | 5,290 | Yes (pr-monitor-graphiti-chit) | No |
| 4 | skills-taxonomy.tac.yaml | 1,506 | 52,771 | Yes (graphiti-trail-sync, agent.graphiti.signed.v1) | Yes |
| 5 | p7-agents-skills-lifecycle.tac.yaml | 280 | 11,554 | Yes (Graphiti trail entry) | No |
| 6 | agent-teams-taxonomy.tac.yaml | 741 | 36,089 | Yes (agent.graphiti.signed.v1) | Yes |

**Additional files searched**: grep for `graphiti` or `pr-monitor-graphiti` across all 35 TAC tree files returned ONLY these 6. No additional GRAPHITI TAC trees exist.

---

## 2. GRAPHITI_MARK Comments

**NONE FOUND.** Zero `GRAPHITI_MARK` comments exist in any of the 6 TAC tree files.

---

## 3. pr-monitor-graphiti-chit Flow: End-to-End Trace

This is the core GRAPHITI attribution pipeline, traced across 4 TAC trees:

### 3.1 Pipeline Definition (skills-taxonomy.tac.yaml)

~~~yaml
chain.pr-monitor-graphiti-chit:
  name: "PR Monitor Graphiti CHIT Flow"
  nats_subject: "skills.pipeline.pr-monitor-graphiti-chit.v1"
  steps:
    - step: 1
      skill: "pr-monitor"
      command: "/pr-monitor"
      agent: codex
      output: pr_monitor_report
      nats_hook: "ops.pr.monitor.completed.v1"
      make_target: "make -C pmoves pr-monitor"
    - step: 2
      skill: "pr-hedge-trim"
      command: "/pr-trim"
      agent: claude-opus
      output: trim_report
      nats_hook: "ops.pr.trim.completed.v1"
      make_target: "make -C pmoves pr-trim PR=<N>"
    - step: 3
      skill: "pr-learnings-encode"
      command: "/chit:review-sweep"
      agent: tokenism
      output: pr_learnings_packet
      nats_hook: "ops.pr.learnings.encoded.v1"
      make_target: "make -C pmoves pr-monitor-chit-packet"
    - step: 4
      skill: "graphiti-trail-sync"
      command: "/chit:sign-trail"
      agent: archon
      output: graphiti_handoff
      nats_hook: "agent.graphiti.signed.v1"
      make_target: "make -C pmoves sign-trail"
~~~

### 3.2 Flow Diagram

```
codex ──[/pr-monitor]──> ops.pr.monitor.completed.v1
                                  |
                                  v
claude-opus ──[/pr-trim]──> ops.pr.trim.completed.v1
                                  |
                                  v
tokenism ──[/chit:review-sweep]──> ops.pr.learnings.encoded.v1
                                  |
                                  v
archon ──[/chit:sign-trail]──> agent.graphiti.signed.v1
```

### 3.3 Cross-Tree Trace

| Step | Tree | Location | Detail |
|------|------|----------|--------|
| Step 1: codex | skills-taxonomy | `skills.pr-review.pr-monitor` | pairing: pr-monitor-graphiti-chit, step 1, agent: codex |
| Step 1: codex | agent-teams-taxonomy | `team.external.skill_pairings` | "codex (external) — pr-monitor step" |
| Step 1 NATS | agent-teams-taxonomy | `team.external.nats_subjects` | `ops.pr.monitor.completed.v1` |
| Step 2: claude-opus | skills-taxonomy | `skills.pr-review.pr-trim` | pairing: pr-monitor-graphiti-chit, step 2, agent: claude-opus |
| Step 2: claude-opus | agent-teams-taxonomy | `team.external.skill_pairings` | "claude-opus (external) — pr-hedge-trim step" |
| Step 2 NATS | agent-teams-taxonomy | `team.external.nats_subjects` | `ops.pr.trim.completed.v1` |
| Step 3: tokenism | skills-taxonomy | `skills.chit.review-sweep` | pairing: pr-monitor-graphiti-chit, step 3, agent: tokenism |
| Step 3: tokenism | agent-teams-taxonomy | `team.evolution.skill_pairings` | "tokenism (evolution) — pr-learnings-encode step" |
| Step 3 NATS | agent-teams-taxonomy | `team.external.nats_subjects` | `ops.pr.learnings.encoded.v1` |
| Step 4: archon | skills-taxonomy | `skills.chit.sign-trail` | pairing: pr-monitor-graphiti-chit, step 4, agent: archon |
| Step 4: archon | agent-teams-taxonomy | `team.orchestration.skill_pairings` | "archon (orchestration) — graphiti-trail-sync step" |
| Step 4: archon | archon-agents | `archon.tensorzero.code-review` | "Used in pr-monitor-graphiti-chit skill pairing" |
| Step 4 NATS | agent-teams-taxonomy | `team.orchestration.nats_subjects` | `agent.graphiti.signed.v1` (BoTZ gateway) |
| Step 4 NATS | agent-teams-taxonomy | `team.external.nats_subjects` | `agent.graphiti.signed.v1` (shared with orchestration) |

### 3.4 Agent Team Mapping for pr-monitor-graphiti-chit

| Agent | Team | Node Affinity | Role in Pipeline |
|-------|------|---------------|------------------|
| codex | External Contributors | None (external) | PR state collection |
| claude-opus | External Contributors | None (external) | CodeRabbit thread classification/fixing |
| tokenism | Evolution & CHIT | powerfulmoves, z890 | CGP encoding of PR learnings |
| archon | Orchestration | kvm4-1, z890, powerfulmoves | Graphiti trail HMAC signing |

---

## 4. NATS Subject Master Catalog

### 4.1 GRAPHITI-Direct NATS Subjects

~~~
agent.graphiti.signed.v1          # Graphiti trail attribution (BoTZ gateway publisher)
                                  # Shared by: team.orchestration (BoTZ gateway), team.external (trail signing)
                                  # Published by: archon (step 4 of pr-monitor-graphiti-chit)
                                  # Used by: skills.chit.sign-trail, skills.agent-sdk.handoff
~~~

### 4.2 pr-monitor-graphiti-chit Pipeline NATS Subjects

~~~
ops.pr.monitor.completed.v1       # PR monitor scan completed (codex publisher)
ops.pr.trim.completed.v1          # PR hedge trim completed (claude-opus publisher)
ops.pr.learnings.encoded.v1       # PR learnings encoded to CGP (tokenism publisher)
ops.pr.review.completed.v1        # PR review learnings encoded (archon publisher)
ops.pr.monitor.failed.v1          # PR monitor failure
skills.pipeline.pr-monitor-graphiti-chit.v1  # Pipeline orchestration subject
~~~

### 4.3 CHIT/CGP Geometry Bus NATS Subjects

~~~
geometry.cgp.v1                   # CGP via Supabase Realtime (transport layer)
geometry.cgp.calibration.v1       # CGP calibration (evo-controller publisher)
geometry.event.v1                 # Raw geometry events
geometry.packet.encoded.v1        # CGP packet encoded (tokenism publisher, chit-encode output)
geometry.swarm.meta.v1            # Swarm metadata
tokenism.cgp.ready.v1             # CGP packet readiness
                                  # Published by: consciousness_service (orchestration), evolution team
                                  # Referenced in: tokenism-chit.tac.yaml (tokenism.nats.cgp-subject)
tokenism.cgp.weekly.v1            # Weekly CGP export
tokenism.simulation.result.v1     # Simulation results
tokenism.swarm.population.v1      # Swarm population updates
tokenism.attribution.recorded.v1  # Attribution recording
tokenism.credential.rotated.v1    # Credential rotation audit
tokenism.geometry.event.v1        # Voice attribution (flute_gateway publisher)
tokenism.prosodic.bpm.v1          # BPM prosodic timeline (flute_gateway publisher)
~~~

### 4.4 All Other NATS Subjects Referenced in GRAPHITI TAC Trees

~~~
# Training Pipeline
training.job.started.v1
training.job.completed.v1
training.job.failed.v1
training.eval.result.v1
training.model.published.v1
training.model.deployed.v1

# Skill Pipeline Orchestration (all 9 pairings)
skills.pipeline.model-benchmark-viz.v1
skills.pipeline.ingest-chit-index.v1
skills.pipeline.research-render.v1
skills.pipeline.chit-3d-viz.v1
skills.pipeline.voice-synthesis.v1
skills.pipeline.agent-card-gen.v1
skills.pipeline.health-sync.v1
skills.pipeline.finance-sync.v1
skills.pipeline.training-eval-deploy.v1
skills.pipeline.*.v1               # Wildcard monitoring (chit:floos)

# Skill Step Hooks
skills.step.model-trainer.done.v1
skills.step.hf-benchmark.done.v1
skills.step.a2ui-chart.done.v1
skills.step.remotion-render.done.v1
skills.step.extract-worker.done.v1
skills.step.text-generate.done.v1
skills.step.prosodic-analyze.done.v1
skills.step.tts-synthesize.done.v1
skills.step.theme-lookup.done.v1
skills.step.comfyui-generate.done.v1
skills.step.chit-encode.done.v1    # (implicit from geometry.packet.encoded.v1)
skills.pipeline.ingest-chit-index.done.v1
skills.pipeline.chit-3d-viz.done.v1
skills.pipeline.voice-synthesis.done.v1

# Orchestration Team
supaserch.request.v1
supaserch.result.v1
agent.tool.executed.v1
botz.mcp.github.tool.executed.v1
botz.mcp.github.pr.created.v1

# Research Team
research.deepresearch.request.v1
research.deepresearch.result.v1
research.autoresearch.result.v1
cipher.memory.stored.v1
cipher.memory.searched.v1
cipher.reasoning.stored.v1
ingest.file.added.v1

# Media Team
ingest.transcript.ready.v1
ingest.summary.ready.v1
ingest.chapters.ready.v1
voice.agent.response.v1
voice.cast.completed.v1

# Data/Infra Team
mesh.node.announce.v1
test.smoke.v1
dev.debug.v1

# UI Team
remote.session.started.v1
remote.session.ended.v1
openclaw.message.received.v1
openclaw.message.sent.v1
openclaw.channel.connected.v1

# Automation Team (publisher_discord subscriptions)
health.workouts.synced.v1
finance.transactions.synced.v1

# Evolution Team
mesh.gpu.status.v1
mesh.gpu.model.loaded.v1
mesh.gpu.model.unloaded.v1
mesh.gpu.command.v1
mesh.gpu.command.result.v1
model.registry.updated.v1
agentgym.train.started.v1
agentgym.train.completed.v1
agentgym.model.published.v1

# Infrastructure Team
vpn.node.connected.v1
vpn.node.disconnected.v1
vpn.auth_key.created.v1
vpn.route.advertised.v1

# External Team
claude.code.tool.executed.v1

# Life Integration Team (mostly planned)
health.metrics.updated.v1
health.workout.completed.v1
health.weekly.summary.v1
finance.transactions.ingested.v1
finance.budget.alert.v1
finance.monthly.summary.v1

# Discord
 Discord.messages.fetched.v1
~~~

### 4.5 NATS Subject Count by Team

| Team | Subject Count | Notes |
|------|---------------|-------|
| Orchestration | 7 | Includes agent.graphiti.signed.v1 |
| Research & Knowledge | 7 | cipher.* subjects |
| Media & Voice | 7 | tokenism.geometry.*, tokenism.prosodic.* |
| Data & Storage | 3 | Transport layer ownership |
| User Interfaces | 5 | openclaw.*, remote.session.* |
| Automation & Notifications | 8 | publisher_discord subscriptions |
| Evolution & CHIT | 18 | Largest owner - mesh.gpu.*, geometry.*, tokenism.*, agentgym.* |
| Infrastructure & Networking | 5 | vpn.*, mesh.node.announce.v1 |
| Sandbox & Execution | 3 | agentgym.* (consumed, not published) |
| External Contributors | 7 | ops.pr.*, claude.code.*, agent.graphiti.signed.v1 |
| Life Integration | 8 | Most are planned status |
| **TOTAL** | **78** | Across 11 teams |

---

## 5. Agent Roles with GRAPHITI-Specific Responsibilities

### 5.1 tokenism (Evolution & CHIT team)

- **Port**: Not specified in TAC trees (service in docker-compose)
- **GRAPHITI role**: CGP encoding engine — encodes PR learnings into CHIT CGP packets
- **Pipeline participation**:
  - `pr-monitor-graphiti-chit` step 3: `pr-learnings-encode` (command: `/chit:review-sweep`)
  - `ingest-chit-index` step 2: `chit-encode` (command: `/chit:encode`)
  - `chit-3d-viz` step 1: `chit-encode` (command: `/chit:encode`)
  - `health-sync` step 2: `health-weekly-cgp`
  - `finance-sync` step 2: `finance-monthly-cgp`
- **NATS publishes**: `geometry.packet.encoded.v1`, `tokenism.cgp.ready.v1`, `tokenism.simulation.result.v1`, `ops.pr.learnings.encoded.v1`
- **NATS subscribes**: (implicit via FlOO$ pipeline)
- **Node affinity**: powerfulmoves, z890
- **CHIT contract modules**: 9 TypeScript modules in `PMOVES-ToKenism-Multi/integrations/contracts/chit/`
- **CGP schema versions**: Transport: `geometry.cgp.v1`, Payload: `chit.cgp.v0.2`, Canonical: `chit.cgp.v1.0`

### 5.2 archon (Orchestration team)

- **Port**: 8091 (API), 3737 (UI)
- **GRAPHITI role**: Graphiti trail sync — signs trail entries with CHIT HMAC via Supabase
- **Pipeline participation**:
  - `pr-monitor-graphiti-chit` step 4: `graphiti-trail-sync` (command: `/chit:sign-trail`)
- **NATS publishes**: `agent.graphiti.signed.v1`
- **TensorZero functions**: `archon_work_orders` (autonomous workflow), `archon_code_review` (PR review, used in pr-monitor-graphiti-chit)
- **Integrations**: Supabase (prompts/forms storage), Agent Zero MCP (API calls), TensorZero (LLM routing)
- **Node affinity**: kvm4-1, z890, powerfulmoves
- **Health endpoint**: `GET http://localhost:8091/healthz`

### 5.3 codex (External Contributors team)

- **Port**: None (external CLI agent)
- **GRAPHITI role**: PR state collection — first step in pr-monitor-graphiti-chit
- **Pipeline participation**:
  - `pr-monitor-graphiti-chit` step 1: `pr-monitor` (command: `/pr-monitor`, make: `make -C pmoves pr-monitor`)
- **NATS publishes**: `ops.pr.monitor.completed.v1`, `claude.code.tool.executed.v1`
- **Compute**: None (uses client-side compute)

### 5.4 claude-opus (External Contributors team)

- **Port**: None (external CLI agent)
- **GRAPHITI role**: CodeRabbit thread classification and fixing
- **Pipeline participation**:
  - `pr-monitor-graphiti-chit` step 2: `pr-hedge-trim` (command: `/pr-trim`, make: `make -C pmoves pr-trim PR=<N>`)
- **NATS publishes**: `ops.pr.trim.completed.v1`
- **Compute**: None (uses client-side compute)

### 5.5 consciousness_service (Orchestration team)

- **Port**: Not specified
- **GRAPHITI role**: CGP consciousness mapper, publishes CGP readiness signals
- **NATS publishes**: `tokenism.cgp.ready.v1`
- **Team**: Orchestration

### 5.6 swarm_attribution (Evolution & CHIT team)

- **Port**: Not specified
- **GRAPHITI role**: Shape-attribution engine — used by tokenism for chit-encode steps
- **Pipeline participation**:
  - `ingest-chit-index`: tokenism uses swarm_attribution for chit-encode

---

## 6. CHIT/GRAPHITI Skill Definitions

### 6.1 CHIT Domain Skills (skills-taxonomy.tac.yaml, domain: `skills.chit`)

| Skill ID | Command | File | Description | NATS Subjects | Pairing | Step | Agent |
|----------|---------|------|-------------|---------------|---------|------|-------|
| skills.chit.encode | `/chit:encode` | chit/encode.md | Encode content into CHIT CGP packets | `geometry.packet.encoded.v1`, `geometry.cgp.v1` | ingest-chit-index | 2 | tokenism |
| skills.chit.decode | `/chit:decode` | chit/decode.md | Decode CHIT CGP packets | `geometry.cgp.v1` | null | — | tokenism |
| skills.chit.bus | `/chit:bus` | chit/bus.md | Interact with GEOMETRY BUS NATS subjects | `geometry.cgp.v1`, `geometry.swarm.meta.v1`, `geometry.event.v1`, `tokenism.cgp.ready.v1`, `tokenism.simulation.result.v1` | null | — | tokenism |
| skills.chit.visualize | `/chit:visualize` | chit/visualize.md | Visualize CHIT constellation geometry | [] | chit-3d-viz | — | hyperdimensions |
| skills.chit.floos | `/chit:floos` | chit/floos.md | FlOO$ pipeline status and validation | `skills.pipeline.*.v1` | null | — | — |
| skills.chit.review-sweep | `/chit:review-sweep` | chit/review-sweep.md | Encode PR learnings as CGP packet for Graphiti | `ops.pr.review.completed.v1`, `ops.pr.learnings.encoded.v1` | pr-monitor-graphiti-chit | 3 | tokenism |
| skills.chit.sign-trail | `/chit:sign-trail` | chit/sign-trail.md | Sign Graphiti trail entry with CHIT HMAC | `agent.graphiti.signed.v1` | pr-monitor-graphiti-chit | 4 | archon |
| skills.chit.bpm | `/chit:bpm` | chit/bpm.md | CHIT BPM rhythm analysis | [] | null | — | tokenism |

### 6.2 PR-Review Domain Skills (GRAPHITI-relevant)

| Skill ID | Command | File | Description | NATS Subjects | Pairing | Step | Agent |
|----------|---------|------|-------------|---------------|---------|------|-------|
| skills.pr-review.pr-monitor | `/pr-monitor` | pr-monitor.md | Collect PR state and review learnings | `ops.pr.monitor.completed.v1` | pr-monitor-graphiti-chit | 1 | codex |
| skills.pr-review.pr-trim | `/pr-trim` | pr-trim.md | Classify and fix CodeRabbit review threads | `ops.pr.trim.completed.v1` | pr-monitor-graphiti-chit | 2 | claude-opus |

### 6.3 GitHub Domain Skills (GRAPHITI-relevant)

| Skill ID | Command | File | Description | NATS Subjects | Pairing |
|----------|---------|------|-------------|---------------|---------|
| skills.github.pr-review | `/github:pr-review` | github/actions.md | Full AI-assisted PR review with structured output | `ops.pr.review.completed.v1` | pr-monitor-graphiti-chit |

### 6.4 Agent-SDK Domain Skills (GRAPHITI-relevant)

| Skill ID | Command | File | Description | NATS Subjects | Pairing |
|----------|---------|------|-------------|---------------|---------|
| skills.agent-sdk.handoff | `/agent-sdk:handoff` | agent-sdk/handoff.md | Hand off work between agents | `agent.graphiti.signed.v1` | null |

### 6.5 Deploy Domain Skills (CHIT-adjacent)

| Skill ID | Command | File | Description | CHIT Relevance |
|----------|---------|------|-------------|----------------|
| skills.deploy.secrets-funnel | `/deploy:secrets-funnel` | deploy/secrets-funnel.md | CHIT export, manifest sync, audit gates | References "CHIT export" |

### 6.6 Hyperdimensions Domain Skills (CHIT-adjacent)

| Skill ID | Command | File | Description | NATS Subjects | Pairing | Step | Agent |
|----------|---------|------|-------------|---------------|---------|------|-------|
| skills.hyperdim.render | `/hyperdim:render` | hyperdim/render.md | Render 3D visualization via Three.js | `skills.pipeline.chit-3d-viz.done.v1` | chit-3d-viz | 2 | hyperdimensions |
| skills.hyperdim.animate | `/hyperdim:animate` | hyperdim/animate.md | Animate 3D constellation geometry | [] | chit-3d-viz | — | — |

### 6.7 Skill Pairing Chain Definitions (GRAPHITI-relevant)

#### chain.pr-monitor-graphiti-chit
~~~yaml
nats_subject: "skills.pipeline.pr-monitor-graphiti-chit.v1"
steps:
  1: pr-monitor (codex) -> ops.pr.monitor.completed.v1
  2: pr-hedge-trim (claude-opus) -> ops.pr.trim.completed.v1
  3: pr-learnings-encode (tokenism) -> ops.pr.learnings.encoded.v1
  4: graphiti-trail-sync (archon) -> agent.graphiti.signed.v1
~~~

#### chain.ingest-chit-index
~~~yaml
nats_subject: "skills.pipeline.ingest-chit-index.v1"
steps:
  1: extract-worker (extract-worker) -> skills.step.extract-worker.done.v1
  2: chit-encode (tokenism) -> geometry.packet.encoded.v1
  3: hirag-index (hirag) -> skills.pipeline.ingest-chit-index.done.v1
~~~

#### chain.chit-3d-viz
~~~yaml
nats_subject: "skills.pipeline.chit-3d-viz.v1"
steps:
  1: chit-encode (tokenism) -> geometry.packet.encoded.v1
  2: threejs-render (hyperdimensions) -> skills.pipeline.chit-3d-viz.done.v1
~~~

---

## 7. Phase Definitions and Transitions

### 7.1 tokenism-chit.tac.yaml — 4 Phases

| Phase | ID | Task | Agent Hint | Children |
|-------|----|------|------------|----------|
| Phase 1: Submodule & Modules | tokenism.submodule | ToKenism submodule health | codex | initialized, chit-contracts |
| Phase 2: NATS Geometry Bus | tokenism.nats | NATS geometry bus integration | codex | cgp-subject, simulation |
| Phase 3: Environment & Docker | tokenism.env | Environment configuration | codex | no-export, compose |
| Phase 4: Skill Pairing Integration | tokenism.skills | Skill pairing wiring | codex | pairings, cgp-schema |

**Transitions**: Linear: Phase 1 -> Phase 2 -> Phase 3 -> Phase 4

### 7.2 archon-agents.tac.yaml — 4 Phases

| Phase | ID | Task | Agent Hint | Children |
|-------|----|------|------------|----------|
| Phase 1: Service Definition | archon.service | Archon service configuration | codex | submodule, compose-defined, healthcheck |
| Phase 2: Supabase Integration | archon.supabase | Supabase integration for prompts/forms | codex | url-config, service-key |
| Phase 3: Agent Zero MCP | archon.mcp | Agent Zero MCP integration | codex | url-config, client-auth |
| Phase 4: TensorZero Integration | archon.tensorzero | TensorZero model routing | codex | work-orders, code-review |

**Transitions**: Linear: Phase 1 -> Phase 2 -> Phase 3 -> Phase 4

### 7.3 training-pipeline.tac.yaml — 3 Phases + Infrastructure + FlOO$

| Phase | ID | Task | Agent Hint | Children |
|-------|----|------|------------|----------|
| Phase 1: Embeddings (Crawl) | training.embed | Embedding fine-tuning for Hi-RAG retrieval | 5090-claude | data_prep, validate, train, eval, publish, register, deploy |
| Phase 2: Agentic Models (Walk) | training.agent | Agentic model fine-tuning for PMOVES tool-use | 5090-claude | data_prep, train, eval, publish, deploy |
| Phase 3: Voice Adaptation (Run) | training.voice | Voice model adaptation for personas | 5090-claude | data_prep, train, eval, deploy |
| Infrastructure | training.infra | Training infrastructure management | 5090-claude | vram_swap, z890_tts, e2b_sandbox, nats_events |
| FlOO$ | training.floos | training-eval-deploy skill pairing | 5090-claude | (leaf node) |

**Transitions**: Crawl -> Walk -> Run (sequential). Infrastructure is cross-cutting. FlOO$ is separate.

### 7.4 skills-taxonomy.tac.yaml — No Phases

This is a catalog/taxonomy tree, not a phased pipeline. Organized by 36 skill domains under a single root.

### 7.5 p7-agents-skills-lifecycle.tac.yaml — 7 Phases

| Phase | ID | Task | Status | Children |
|-------|----|------|--------|----------|
| Phase 1: Agent Registration | p7.lifecycle.registration | Agent registration and identity | done | signatures, agents_md, personas |
| Phase 2: SKILL.md Discovery | p7.lifecycle.discovery | P7 SKILL.md discovery and indexing | done | format, catalog, pterm_search |
| Phase 3: Model Assignment | p7.lifecycle.models | Model assignment per agent and skill | active/planned | tensorzero (active), assignment (planned), local_mesh (planned) |
| Phase 4: VRAM Budget | p7.lifecycle.vram | VRAM budget management per node | active | 5090, z890, 4090 |
| Phase 5: Skill Pairing Validation | p7.lifecycle.pairings | Skill pairing validation and FlOO$ pipelines | done | catalog, voice_synthesis |
| Phase 6: Onboarding Flow | p7.lifecycle.onboarding | Agent onboarding — new agent registration flow | planned | steps (7-step checklist) |
| Phase 7: Platform Migration | p7.lifecycle.migration | Platform migration readiness | planned | chat_adapter, standalone |

**Transitions**: Linear: Registration -> Discovery -> Assignment -> VRAM -> Pairings -> Onboarding -> Migration

**Onboarding step 7**: "Sign Graphiti trail entry for attribution" — the only explicit GRAPHITI reference in this tree.

### 7.6 agent-teams-taxonomy.tac.yaml — 11 Teams + Cross-References + Audit

Not a phased tree. Structure:
- 11 team sections (team.orchestration through team.life)
- Cross-references section (9 skill pairing agent maps)
- Audit rules section (4 invariants)

---

## 8. Cross-Tree Dependencies

### 8.1 Explicit Cross-References in File Headers

| Source Tree | References |
|-------------|-----------|
| tokenism-chit.tac.yaml | `PMOVES-ToKenism-Multi/ submodule`, `pmoves/docker-compose.yml`, `pmoves/configs/skill-pairings.yaml` |
| archon-agents.tac.yaml | `PMOVES-Archon/ submodule`, `pmoves/docker-compose.yml`, `pmoves/tensorzero/config/tensorzero.toml` |
| training-pipeline.tac.yaml | `p7-agents-skills-lifecycle.tac.yaml` (model assignment, VRAM budget), `tensorzero-gpu.tac.yaml` (model routing), `voice-agents.tac.yaml` (persona binding), `pmoves/configs/skill-pairings.yaml` (FlOO$ pipelines) |
| skills-taxonomy.tac.yaml | `.claude/commands/`, `pmoves/configs/skill-pairings.yaml`, `.claude/CLAUDE.md` |
| p7-agents-skills-lifecycle.tac.yaml | `agent-teams-taxonomy.tac.yaml` (62 agents, 11 teams), `skills-taxonomy.tac.yaml` (119 skills, 36 domains), `pinokio-p7.tac.yaml` (P7 platform phases), `pmoves/config/agent_signatures.yaml` (11 CLI personas), `POWERFULMOVES/PMOVES-agents.md` (AGENTS.md spec) |
| agent-teams-taxonomy.tac.yaml | `pmoves/configs/agent-teams.yaml`, `pmoves/configs/skill-pairings.yaml`, `.claude/context/nats-subjects.md` |

### 8.2 Implicit GRAPHITI Dependency Chain

```
agent-teams-taxonomy.tac.yaml  (defines teams, NATS subjects, agent mappings)
        |
        v
skills-taxonomy.tac.yaml      (defines skills, pairing chains, NATS hooks per skill)
        |
        v
tokenism-chit.tac.yaml      (verifies ToKenism submodule, CGP subjects, skill pairings)
        |
        v
archon-agents.tac.yaml       (verifies Archon service, TensorZero code-review function)
        |
        v
p7-agents-skills-lifecycle.tac.yaml  (onboarding step 7: sign Graphiti trail)
        |
        v
training-pipeline.tac.yaml   (training data sources include Agent Graphiti trail entries)
```

### 8.3 Shared Entities Across Trees

| Entity | Trees Where Defined/Referenced |
|--------|-------------------------------|
| `agent.graphiti.signed.v1` | agent-teams (orchestration + external), skills-taxonomy (sign-trail, handoff) |
| `pr-monitor-graphiti-chit` | skills-taxonomy (full chain), agent-teams (cross_references), archon-agents (code-review context) |
| `tokenism` agent | agent-teams (evolution team), skills-taxonomy (chit domain agent_hint), tokenism-chit (root agent) |
| `archon` agent | agent-teams (orchestration team), skills-taxonomy (chit.sign-trail, archon domain), archon-agents (root) |
| `geometry.cgp.v1` | agent-teams (evolution nats), skills-taxonomy (chit.encode, chit.decode, chit.bus), tokenism-chit (cgp-subject) |
| `tokenism.cgp.ready.v1` | agent-teams (orchestration + evolution), skills-taxonomy (chit.bus), tokenism-chit (cgp-subject) |
| Skill pairings YAML | Referenced by: tokenism-chit, training-pipeline, skills-taxonomy, p7-lifecycle, agent-teams |

---

## 9. Component Status Summary

### 9.1 By TAC Tree

| Tree | Implicit Status | Notes |
|------|----------------|-------|
| tokenism-chit.tac.yaml | Active/Implemented | Audit tree for existing submodule — checks file_exists, grep patterns |
| archon-agents.tac.yaml | Active/Implemented | Audit tree for existing service — checks file_exists, grep patterns |
| training-pipeline.tac.yaml | Planned | ALL sub-tasks have `status: planned` — no training has occurred |
| skills-taxonomy.tac.yaml | Active/Implemented | Catalog of 118 mapped skills (0 unmapped) — audit coverage complete |
| p7-agents-skills-lifecycle.tac.yaml | Mixed | Registration: done, Discovery: done, Models: active/planned, VRAM: active, Pairings: done, Onboarding: planned, Migration: planned |
| agent-teams-taxonomy.tac.yaml | Active/Implemented | Taxonomy of 62 agents, 11 teams — audit rules defined |

### 9.2 Status of GRAPHITI-Specific Components

| Component | Status | Evidence |
|-----------|--------|----------|
| pr-monitor-graphiti-chit pipeline | Defined (not implemented) | Full chain in skills-taxonomy, but no `status` field on the chain itself |
| `/pr-monitor` skill | Defined | skills-taxonomy with make_target |
| `/pr-trim` skill | Defined | skills-taxonomy with make_target |
| `/chit:review-sweep` skill | Defined | skills-taxonomy with make_target |
| `/chit:sign-trail` skill | Defined | skills-taxonomy with make_target |
| `agent.graphiti.signed.v1` NATS subject | Defined | Referenced in 3 locations across 2 trees |
| ToKenism CHIT contract modules | Defined (not verified) | tokenism-chit checks file_exists for `integrations/contracts/chit/` |
| CGP geometry bus subjects | Defined | 5 subjects in chit:bus skill, referenced across trees |
| Graphiti trail signing in onboarding | Planned | p7-lifecycle onboarding step 7, status: planned |
| Training data from Graphiti trails | Planned | training.embed.data_prep lists "Agent Graphiti trail entries" as source, status: planned |
| archon_code_review TensorZero function | Defined | archon-agents checks grep for `archon_code_review` in tensorzero.toml |

---

## 10. Per-File Detailed Extraction

### 10.1 tokenism-chit.tac.yaml

~~~yaml
name: "ToKenism CHIT Attribution Engine"
version: "1.0.0"
description: "Verify ToKenism CGP encoding, simulation pipeline, NATS geometry bus integration, and TypeScript module health"
root.id: tokenism
root.agent_hint: codex
~~~

**NATS subjects referenced**:
- `geometry.cgp.v1` (transport)
- `tokenism.cgp.ready.v1` (readiness)
- `tokenism.simulation.result.v1` (simulation)

**Agent hints**: codex (all nodes)

**Skill pairing references**: 5 pairings mentioned (ingest-chit-index, chit-3d-viz, pr-monitor-graphiti-chit, etc.)

**CGP schema versions**:
- Transport: `geometry.cgp.v1`
- Payload: `chit.cgp.v0.2`
- Canonical: `chit.cgp.v1.0`

**Check types used**: `file_exists`, `grep` (with `invert` option)

**Known finding**: P1 — env.shared uses `export` syntax (Docker incompatible)

**Docker services**: tokenism-simulator (port 8103), Next.js UI

---

### 10.2 archon-agents.tac.yaml

~~~yaml
name: "Archon Agent Service"
version: "1.0.0"
description: "Verify Archon service configuration, Supabase-backed prompts, Agent Zero MCP integration, and agent form management"
root.id: archon-agents
root.agent_hint: codex
~~~

**NATS subjects**: None directly (archon publishes `agent.graphiti.signed.v1` per agent-teams)

**Ports**: 8091 (API), 3737 (UI)

**Integrations verified**:
1. Supabase: URL config, service role key
2. Agent Zero MCP: service URL, client credentials (MCP_CLIENT_ID, MCP_CLIENT_SECRET)
3. TensorZero: `archon_work_orders` function, `archon_code_review` function (explicitly noted as "Used in pr-monitor-graphiti-chit skill pairing")

**Health endpoint**: `GET http://localhost:8091/healthz`

**Compose profile**: `agents`

---

### 10.3 training-pipeline.tac.yaml

~~~yaml
name: TAC_TRAINING_PIPELINE
version: "1.0.0"
root.id: training
root.agent_hint: 5090-claude
~~~

**NATS subjects (metadata block)**:
~~~
training.job.started.v1
training.job.completed.v1
training.job.failed.v1
training.eval.result.v1
training.model.published.v1
training.model.deployed.v1
~~~

**GRAPHITI relevance**: Training data sources include "Agent Graphiti trail entries" (Phase 1: data_prep)

**All sub-task statuses**: `planned` (every single one)

**Multi-node coordination**: 5090 trains, z890 serves TTS during training, VPS runs E2B eval

**VRAM swap protocol**: `pterm stop TTS -> train -> pterm start TTS` with NATS trigger

**FlOO$ pairing**: `training-eval-deploy` (planned) — data-prep -> unsloth-train -> e2b-eval -> hf-publish -> tz-register

**Base models**:
- Embeddings: Qwen3-4b (2560d)
- Agentic: Qwen2.5-7B-Instruct or Llama-3.1-8B-Instruct
- Voice: Fish S2 Pro, F5-TTS

**HuggingFace targets**: POWERFULMOVES/pmoves-qwen3-4b-embed, POWERFULMOVES/pmoves-agent-7b

---

### 10.4 skills-taxonomy.tac.yaml

~~~yaml
name: TAC_SKILLS_TAXONOMY
version: "1.0.0"
metadata.total_skills: 119
metadata.total_domains: 36
metadata.generated: "2026-03-16"
~~~

**Audit coverage**: 118 command files mapped, 0 unmapped (note: metadata says 119 but audit says 118)

**CHIT domain skills**: 8 (bpm, bus, decode, encode, floos, review-sweep, sign-trail, visualize)

**GRAPHITI-specific skills**:
- `skills.chit.review-sweep` — pr-monitor-graphiti-chit step 3
- `skills.chit.sign-trail` — pr-monitor-graphiti-chit step 4
- `skills.agent-sdk.handoff` — publishes `agent.graphiti.signed.v1`

**Dependency chains**: 9 chains defined, 3 are GRAPHITI-relevant (pr-monitor-graphiti-chit, ingest-chit-index, chit-3d-viz)

**Pairing coverage**: 28 skills participate in 9 pairings

---

### 10.5 p7-agents-skills-lifecycle.tac.yaml

~~~yaml
name: TAC_P7_AGENTS_SKILLS_LIFECYCLE
version: "1.0.0"
metadata.total_agents: 62
metadata.total_skills: 119
metadata.total_skill_md_files: 6
~~~

**GRAPHITI reference**: Onboarding step 7: "Sign Graphiti trail entry for attribution"

**SKILL.md deployed apps**: pmoves-services, pmoves-remote, pmoves-cipher-beats, pmoves-holographic-blocks, pmoves-discord-bot, ultimate-tts-studio

**Nodes with GPU**:
- powerfulmoves-5090: RTX 5090 32GB (GPU primary)
- z890: RTX 3090 Ti 24GB (data services)
- laptop-4090: RTX 4090 Mobile 16GB (mobile agent)

**Nodes without GPU**: kvm4-1 (API gateway), kvm4-2 (data storage)

**7 skill pairings listed**: model-benchmark-viz, ingest-chit-index, research-summarize-render, chit-3d-viz, voice-synthesis, agent-card-gen, pr-monitor-graphiti-chit

**Agent signatures**: 11 CLI agents with glyphs, colors, voice descriptors

---

### 10.6 agent-teams-taxonomy.tac.yaml

~~~yaml
name: TAC_AGENT_TEAMS_TAXONOMY
version: "1.0.0"
~~~

**11 teams, 62 agents**:

| # | Team | Agents | GRAPHITI Relevance |
|---|------|--------|-------------------|
| 1 | Orchestration | 6 | archon (graphiti-trail-sync), consciousness_service (cgp.ready publisher) |
| 2 | Research & Knowledge | 9 | cipher_memory (knowledge graph for CHIT context) |
| 3 | Media & Voice | 11 | flute_gateway (tokenism.geometry.event.v1, tokenism.prosodic.bpm.v1) |
| 4 | Data & Storage | 9 | neo4j (knowledge graph backend), qdrant (CGP vector storage) |
| 5 | User Interfaces | 6 | hyperdimensions (chit-3d-viz step 2) |
| 6 | Automation & Notifications | 4 | publisher_discord subscribes to tokenism.cgp.weekly.v1, tokenism.attribution.recorded.v1 |
| 7 | Evolution & CHIT | 4 | tokenism (CGP encoder), swarm_attribution, evoswarm_controller (CGP calibration) |
| 8 | Infrastructure & Networking | 3 | None directly |
| 9 | Sandbox & Execution | 8 | None directly |
| 10 | External Contributors | 0 in-house | codex (pr-monitor step 1), claude-opus (pr-hedge-trim step 2), publishes agent.graphiti.signed.v1 |
| 11 | Life Integration | 2 | tokenism (health-weekly-cgp, finance-monthly-cgp) |

**Audit rules**:
1. Single team membership per agent
2. At least one NATS subject per team
3. Total agent count = 62
4. All 9 skill pairings covered in cross_references

**Cross-reference section**: 9 skill pairing agent maps with full pipeline, NATS subject, and agent+team details

---

## Appendix A: Complete NATS Subject List (GRAPHITI TAC Trees Only)

```
agent.graphiti.signed.v1
agent.tool.executed.v1
agentgym.model.published.v1
agentgym.train.completed.v1
agentgym.train.started.v1
claude.code.tool.executed.v1
cipher.memory.searched.v1
cipher.memory.stored.v1
cipher.reasoning.stored.v1
dev.debug.v1
discord.messages.fetched.v1
finance.budget.alert.v1
finance.monthly.summary.v1
finance.transactions.ingested.v1
finance.transactions.synced.v1
geometry.cgp.calibration.v1
geometry.cgp.v1
geometry.event.v1
geometry.packet.encoded.v1
geometry.swarm.meta.v1
health.metrics.updated.v1
health.weekly.summary.v1
health.workout.completed.v1
health.workouts.synced.v1
ingest.chapters.ready.v1
ingest.file.added.v1
ingest.summary.ready.v1
ingest.transcript.ready.v1
mesh.gpu.command.result.v1
mesh.gpu.command.v1
mesh.gpu.model.loaded.v1
mesh.gpu.model.unloaded.v1
mesh.gpu.status.v1
mesh.node.announce.v1
model.registry.updated.v1
openclaw.channel.connected.v1
openclaw.message.received.v1
openclaw.message.sent.v1
ops.pr.learnings.encoded.v1
ops.pr.monitor.completed.v1
ops.pr.monitor.failed.v1
ops.pr.review.completed.v1
ops.pr.trim.completed.v1
remote.session.ended.v1
remote.session.started.v1
research.autoresearch.result.v1
research.deepresearch.request.v1
research.deepresearch.result.v1
skills.pipeline.agent-card-gen.v1
skills.pipeline.chit-3d-viz.v1
skills.pipeline.finance-sync.v1
skills.pipeline.health-sync.v1
skills.pipeline.ingest-chit-index.v1
skills.pipeline.model-benchmark-viz.v1
skills.pipeline.pr-monitor-graphiti-chit.v1
skills.pipeline.research-render.v1
skills.pipeline.training-eval-deploy.v1
skills.pipeline.voice-synthesis.v1
skills.pipeline.*.v1
skills.pipeline.ingest-chit-index.done.v1
skills.pipeline.chit-3d-viz.done.v1
skills.pipeline.voice-synthesis.done.v1
skills.pipeline.model-benchmark-viz.done.v1
skills.pipeline.research-render.done.v1
skills.pipeline.agent-card-gen.done.v1
skills.step.a2ui-chart.done.v1
skills.step.comfyui-generate.done.v1
skills.step.extract-worker.done.v1
skills.step.hf-benchmark.done.v1
skills.step.model-trainer.done.v1
skills.step.prosodic-analyze.done.v1
skills.step.remotion-render.done.v1
skills.step.text-generate.done.v1
skills.step.theme-lookup.done.v1
skills.step.tts-synthesize.done.v1
supaserch.request.v1
supaserch.result.v1
test.smoke.v1
tokenism.attribution.recorded.v1
tokenism.cgp.ready.v1
tokenism.cgp.weekly.v1
tokenism.credential.rotated.v1
tokenism.geometry.event.v1
tokenism.prosodic.bpm.v1
tokenism.simulation.result.v1
tokenism.swarm.population.v1
training.eval.result.v1
training.job.completed.v1
training.job.failed.v1
training.job.started.v1
training.model.deployed.v1
training.model.published.v1
vpn.auth_key.created.v1
vpn.node.connected.v1
vpn.node.disconnected.v1
vpn.route.advertised.v1
voice.agent.response.v1
voice.cast.completed.v1
```

**Total unique NATS subjects: 88** (across 6 GRAPHITI TAC trees)
