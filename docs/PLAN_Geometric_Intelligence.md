# Geometric Intelligence & CHIT Integration Plan

**Status:** Planning
**Created:** 2025-12-27
**Feature Branch:** `feat/geometry-intelligence`
**Related:** PMOVES-ToKenism-Multi submodule

---

## Overview

PMOVES integrates with the **GEOMETRY BUS** via CHIT (Compressed Hierarchical Information Transfer) protocol for mathematical and geometric reasoning across agents.

### Architecture Components

| Component | Description | Location |
|-----------|-------------|----------|
| **Geometry Bus** | NATS-based event bus for geometric data | `tokenism.*`, `geometry.*` subjects |
| **CHIT Protocol** | Compressed information encoding/decoding | `PMOVES-ToKenism-Multi/integrations/contracts/chit/` |
| **CGP Packets** | Compressed Geometry Protocol packets | `tokenism.cgp.ready.v1` subject |
| **AgentGym RL** | Reinforcement learning for geometry tasks | `agentgym_trajectories`, `agentgym_training_runs` |

---

## Key Services

### 1. Geometry Swarm Coordinator
- **Port:** TBD
- **Purpose:** Coordinates geometric reasoning across agents
- **NATS Subjects:**
  - `geometry.swarm.coordination.v1`
  - `geometry.parameter.pack.v1`

### 2. AgentGym RL Coordinator
- **Port:** 8114
- **Purpose:** PPO training for geometry tasks
- **Database Tables:**
  - `agentgym_trajectories` - RL trajectory data
  - `agentgym_training_runs` - Training run tracking

### 3. CHIT Encoding/Decoding
- **CLI Commands:** `/chit/encode`, `/chit/decode`, `/chit/bus`, `/chit/visualize`
- **Library:** TypeScript modules in `PMOVES-ToKenism-Multi`

---

## Database Schema

### AgentGym Tables

```sql
-- Trajectories (from 20251225_agentgym_rl.sql)
CREATE TABLE public.agentgym_trajectories (
    id uuid PRIMARY KEY,
    session_id uuid NOT NULL UNIQUE,
    trajectory_data jsonb NOT NULL,
    event_count int DEFAULT 0,
    task_type text,
    environment text,
    agent_id uuid REFERENCES pmoves_core.agent(id),
    published_to_hf boolean DEFAULT false
);

-- Training Runs
CREATE TABLE public.agentgym_training_runs (
    id uuid PRIMARY KEY,
    run_id text UNIQUE NOT NULL,
    config jsonb NOT NULL,
    status text CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    current_epoch int DEFAULT 0,
    total_epochs int,
    checkpoint_path text,
    final_reward float,
    mean_reward float
);
```

### Geometry Tables

```sql
-- Geometry Parameter Packs (from geometry bus schema)
CREATE TABLE public.geometry_parameter_packs (
    id uuid PRIMARY KEY,
    pack_type text,
    parameters jsonb,
    version int
);

-- Geometry Swarm Runs
CREATE TABLE public.geometry_swarm_runs (
    id uuid PRIMARY KEY,
    task_type text,
    status text,
    agents_participating jsonb,
    result_data jsonb
);
```

---

## Integration Points

### 1. Supabase Functions

```sql
-- Upsert trajectory (from migration)
CREATE OR REPLACE FUNCTION upsert_trajectory(
    p_session_id uuid,
    p_trajectory_data jsonb,
    p_event_count int DEFAULT 1
) RETURNS uuid;

-- Create training run
CREATE OR REPLACE FUNCTION create_training_run(
    p_run_id text,
    p_config jsonb,
    p_total_epochs int DEFAULT 100
) RETURNS uuid;

-- Update training status
CREATE OR REPLACE FUNCTION update_training_run_status(
    p_run_id text,
    p_status text,
    p_current_epoch int DEFAULT NULL
) RETURNS boolean;
```

### 2. NATS Subjects

**Research & Geometry:**
- `research.deepresearch.request.v1` / `research.deepresearch.result.v1`
- `tokenism.cgp.ready.v1` - CGP packets from geometry bus
- `geometry.parameter.pack.v1` - Parameter pack distribution
- `geometry.swarm.coordination.v1` - Swarm coordination

**Agent Observability:**
- `claude.code.tool.executed.v1` - Claude CLI tool events

---

## Triggers & Automation

### Auto-Timestamp Triggers

```sql
-- From 20251226_agentgym_triggers.sql
CREATE TRIGGER trg_agentgym_training_timestamps
    BEFORE UPDATE ON public.agentgym_training_runs
    FOR EACH ROW EXECUTE FUNCTION agentgym_set_training_timestamps();

CREATE TRIGGER trg_voice_cloning_timestamps
    BEFORE UPDATE ON public.voice_persona
    FOR EACH ROW EXECUTE FUNCTION voice_cloning_set_training_timestamps();
```

### Timestamp Behavior

| Status Transition | Auto-Set Field |
|-------------------|----------------|
| `pending` → `running` | `started_at` |
| `running` → `completed/failed` | `completed_at` |
| `running` → `cancelled` | `completed_at` |

---

## UI Components Needed

### Geometry Dashboard
| Component | Description |
|-----------|-------------|
| ParameterPackViewer | View/edit geometry parameter packs |
| SwarmMonitor | Real-time swarm coordination view |
| TrainingRunsList | AgentGym training run status |
| TrajectoryVisualizer | Visualize RL trajectories |

### CHIT Tools
| Component | Description |
|-----------|-------------|
| CHITEncoder | Encode data to CHIT format |
| CHITDecoder | Decode CHIT data |
| CHITVisualizer | Visualize CHIT structure |

---

## Implementation Phases

### Phase 1: Database Setup
- [ ] Verify geometry tables exist
- [ ] Apply AgentGym migrations
- [ ] Set up triggers for timestamps

### Phase 2: Service Integration
- [ ] Verify Geometry Swarm coordinator
- [ ] Test CHIT encode/decode
- [ ] Connect AgentGym RL coordinator

### Phase 3: UI Development
- [ ] Create Geometry dashboard pages
- [ ] Parameter pack viewer/editor
- [ ] Training runs monitor
- [ ] Trajectory visualizer

### Phase 4: Testing
- [ ] End-to-end geometry workflow tests
- [ ] CHIT encoding/decoding tests
- [ ] AgentGym training tests

---

## Critical Files

| File | Purpose |
|------|---------|
| `.claude/context/geometry-nats-subjects.md` | NATS subject catalog |
| `.claude/context/chit-geometry-bus.md` | CHIT integration guide |
| `supabase/migrations/20251225_agentgym_rl.sql` | AgentGym tables |
| `supabase/migrations/20251226_agentgym_triggers.sql` | Timestamp triggers |
| `PMOVES-ToKenism-Multi/integrations/contracts/chit/` | CHIT TypeScript modules |

---

## Related Documentation

- **CHIT Human Guide:** `pmoves/docs/PMOVESCHIT/Human_side.md`
- **Integration Guide:** `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md`
- **Math Foundations:** `pmoves/docs/PMOVESCHIT/Integrating Math into PMOVES.AI.md`
