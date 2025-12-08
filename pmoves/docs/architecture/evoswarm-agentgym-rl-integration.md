# EvoSwarm + AgentGym-RL Integration Architecture

**Version:** 1.0
**Date:** 2025-12-08
**Status:** Design Phase

## Executive Summary

This document outlines the integration architecture between **EvoSwarm controller** and **AgentGym-RL** to enable geometry-aware reinforcement learning for LLM agents. The integration creates a feedback loop where:

1. **Geometry guides training** - CGP fitness signals inform RL reward functions
2. **Agents learn retrieval** - AgentGym-RL agents train on Hi-RAG query tasks
3. **Population-based evolution** - EvoSwarm coordinates parallel agent populations
4. **Continuous improvement** - Agent performance feeds back to geometry parameter evolution

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    PMOVES.AI Ecosystem                           │
│                                                                   │
│  ┌──────────────────┐          ┌──────────────────┐            │
│  │  EvoSwarm        │◄────────►│  AgentGym-RL     │            │
│  │  Controller      │  Fitness │  Training Coord  │            │
│  │  (Port 8113)     │  Signals │  (Port 8114)     │            │
│  └────────┬─────────┘          └────────┬─────────┘            │
│           │                              │                       │
│           │ geometry.swarm.meta.v1       │ agentgym.train.*     │
│           ├──────────────────────────────┤                       │
│           │                              │                       │
│           ▼                              ▼                       │
│  ┌─────────────────────────────────────────────────────┐        │
│  │              NATS JetStream Event Bus                │        │
│  └─────────────────────────────────────────────────────┘        │
│           ▲                              ▲                       │
│           │                              │                       │
│  ┌────────┴─────────┐          ┌────────┴─────────┐            │
│  │  Hi-RAG v2       │          │  Agent Zero       │            │
│  │  Gateway         │          │  MCP API          │            │
│  │  (Port 8086)     │          │  (Port 8080)      │            │
│  └──────────────────┘          └──────────────────┘             │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  TensorZero Gateway (Port 3030)                           │  │
│  │  - LLM routing for agent policy inference                 │  │
│  │  - Embedding generation for trajectory encoding           │  │
│  │  - Observability for training metrics                     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Supabase (PostgREST Port 3010)                           │  │
│  │  - geometry_cgp_v1: CGP packets with fitness              │  │
│  │  - geometry_parameter_packs: Evolved parameters           │  │
│  │  - agentgym_training_runs: Training metadata              │  │
│  │  - agentgym_trajectories: Agent interaction logs          │  │
│  │  - agentgym_checkpoints: Model snapshots                  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  MinIO (Port 9000)                                        │  │
│  │  Buckets:                                                 │  │
│  │  - agentgym-models: Model checkpoints                     │  │
│  │  - agentgym-trajectories: Full episode data               │  │
│  │  - agentgym-datasets: Training data snapshots             │  │
│  └───────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. AgentGym-RL Training Coordinator (New Service)

**Location:** `pmoves/services/agentgym-rl-coordinator/`
**Port:** 8114
**Purpose:** Bridge between EvoSwarm and AgentGym-RL training framework

#### Responsibilities

1. **Training Job Management**
   - Receive training requests from EvoSwarm
   - Launch AgentGym-RL training processes
   - Monitor training progress and metrics
   - Publish completion events to NATS

2. **Environment Orchestration**
   - Configure PMOVES-aware environments
   - Inject Hi-RAG query capabilities into agents
   - Manage environment server lifecycle

3. **Trajectory Collection**
   - Stream agent interactions to Supabase
   - Store episode data to MinIO
   - Compute geometry-aware rewards

4. **Model Management**
   - Version and store checkpoints
   - Register models in TensorZero
   - Enable A/B testing of agent policies

#### API Endpoints

```python
# POST /agentgym/train/start
{
  "environment": "pmoves-hirag",  # Custom environment
  "base_model": "Qwen2.5-7B-Instruct",
  "population_id": "pop-123",
  "training_config": {
    "algorithm": "ppo",  # ppo|grpo|rloo|reinforce++
    "horizon": 10,       # Interaction turns per episode
    "num_epochs": 25,
    "batch_size": 32,
    "learning_rate": 1e-6,
    "kl_coef": 0.001
  },
  "geometry_config": {
    "cgp_fitness_weight": 0.3,  # How much CGP fitness influences reward
    "retrieval_quality_weight": 0.5,
    "task_success_weight": 0.2
  }
}

# Response
{
  "training_run_id": "run-456",
  "status": "started",
  "environment_url": "http://agentgym-env-pmoves:36000",
  "monitoring_url": "http://localhost:3002/d/agentgym"  # Grafana
}

# GET /agentgym/train/{run_id}/status
{
  "run_id": "run-456",
  "status": "training",  # queued|training|completed|failed
  "current_epoch": 10,
  "total_epochs": 25,
  "metrics": {
    "avg_reward": 0.72,
    "success_rate": 0.68,
    "avg_episode_length": 8.3,
    "geometry_fitness": 0.81
  },
  "checkpoints": [
    {"epoch": 5, "path": "s3://agentgym-models/run-456/epoch-5.ckpt"},
    {"epoch": 10, "path": "s3://agentgym-models/run-456/epoch-10.ckpt"}
  ]
}

# POST /agentgym/train/{run_id}/stop
# POST /agentgym/eval/run
# GET /agentgym/models/list
```

### 2. PMOVES Custom Environment (pmoves-hirag)

**Location:** `pmoves/vendor/agentgym-rl/environments/pmoves_hirag/`
**Purpose:** Geometry-aware agent environment using Hi-RAG v2

#### Environment Specification

```python
class PMOVESHiRAGEnv:
    """
    AgentGym environment for training agents on geometry-aware retrieval tasks.

    Agents interact with Hi-RAG v2 Gateway to:
    - Query knowledge base with semantic search
    - Navigate constellation relationships
    - Construct multi-hop retrieval chains
    - Answer questions grounded in geometry packets
    """

    def __init__(
        self,
        hirag_url: str = "http://hi-rag-gateway-v2:8086",
        namespace: str = "pmoves.consciousness",
        max_turns: int = 15,
        task_config: dict = None
    ):
        self.hirag_url = hirag_url
        self.namespace = namespace
        self.max_turns = max_turns
        self.task_config = task_config or {}

        # CGP-based task generator
        self.task_generator = ConstellationTaskGenerator(namespace)

    def reset(self) -> dict:
        """Start new episode with CGP-guided task."""
        task = self.task_generator.sample_task()

        return {
            "task_description": task["description"],
            "constellation_id": task["constellation_id"],
            "target_concepts": task["target_concepts"],
            "difficulty": task["difficulty"],
            "metadata": {
                "cgp_id": task["cgp_id"],
                "namespace": self.namespace
            }
        }

    def step(self, action: dict) -> tuple:
        """
        Execute agent action and return (observation, reward, done, info).

        Actions:
        - query_hirag: Semantic search with query text
        - follow_edge: Navigate graph relationship
        - answer: Submit final answer
        """
        if action["type"] == "query_hirag":
            results = self._query_hirag(action["query"])
            observation = self._format_results(results)
            reward = self._compute_retrieval_reward(results, action)
            done = False

        elif action["type"] == "follow_edge":
            results = self._traverse_graph(action["entity_id"], action["relation"])
            observation = self._format_graph_results(results)
            reward = self._compute_navigation_reward(results, action)
            done = False

        elif action["type"] == "answer":
            correctness = self._evaluate_answer(action["answer"])
            observation = {"feedback": correctness["explanation"]}
            reward = self._compute_final_reward(correctness)
            done = True

        info = {
            "step": self.current_step,
            "geometry_coherence": self._compute_geometry_coherence(),
            "retrieval_quality": self._compute_retrieval_quality()
        }

        return observation, reward, done, info

    def _compute_geometry_coherence(self) -> float:
        """
        Measure how well agent's retrieval aligns with CGP structure.

        Higher score when:
        - Retrieved chunks belong to same constellation
        - Navigation follows graph edges
        - Queries use constellation-relevant concepts
        """
        # Fetch CGP for current task
        cgp = self._fetch_cgp(self.current_task["cgp_id"])

        # Compare agent's retrieval path to CGP structure
        coherence = compute_cgp_alignment(
            retrieval_path=self.retrieval_history,
            cgp_structure=cgp["geometry"]["constellation"]
        )

        return coherence

    def _compute_retrieval_quality(self) -> float:
        """
        Measure relevance of retrieved information.

        Uses:
        - Cross-encoder reranking scores
        - Graph centrality of retrieved nodes
        - Meilisearch keyword match scores
        """
        if not self.retrieval_history:
            return 0.0

        scores = []
        for retrieval in self.retrieval_history:
            # Hi-RAG v2 returns rerank scores
            rerank_score = retrieval.get("rerank_score", 0.0)

            # Graph importance
            graph_score = retrieval.get("centrality", 0.0)

            # Lexical match
            lexical_score = retrieval.get("meili_score", 0.0)

            combined = (
                0.5 * rerank_score +
                0.3 * graph_score +
                0.2 * lexical_score
            )
            scores.append(combined)

        return sum(scores) / len(scores)
```

#### Task Generator

```python
class ConstellationTaskGenerator:
    """
    Generate training tasks based on constellation structure.

    Task types:
    1. Single-hop QA: Answer from one constellation node
    2. Multi-hop reasoning: Chain through graph relationships
    3. Comparison: Contrast concepts from different constellations
    4. Synthesis: Combine information across multiple CGPs
    """

    def __init__(self, namespace: str):
        self.namespace = namespace
        self.cgp_cache = self._load_recent_cgps(namespace)

    def sample_task(self, difficulty: str = "medium") -> dict:
        """Sample task with difficulty-appropriate complexity."""

        if difficulty == "easy":
            # Single-hop QA within one constellation
            return self._generate_single_hop_task()

        elif difficulty == "medium":
            # Multi-hop reasoning across 2-3 nodes
            return self._generate_multi_hop_task(max_hops=3)

        elif difficulty == "hard":
            # Cross-constellation synthesis
            return self._generate_synthesis_task()

    def _generate_multi_hop_task(self, max_hops: int) -> dict:
        """
        Create task requiring graph traversal.

        Example:
        "What is the relationship between consciousness and
         quantum mechanics according to Roger Penrose's theory?"

        Required path:
        consciousness -> quantum_theory -> penrose_orch_or -> microtubules
        """
        cgp = random.choice(self.cgp_cache)
        constellation = cgp["geometry"]["constellation"]

        # Sample random walk through constellation
        path = self._sample_graph_path(constellation, max_hops)

        # Generate question requiring this path
        question = self._path_to_question(path, constellation)

        return {
            "description": question,
            "constellation_id": constellation["id"],
            "cgp_id": cgp["cgp_id"],
            "target_concepts": path,
            "difficulty": "medium",
            "optimal_path": path,
            "ground_truth": self._extract_answer(path, constellation)
        }
```

### 3. EvoSwarm Controller Extensions

**Location:** `pmoves/services/evo-controller/app.py`
**Changes:** Add AgentGym-RL training coordination

#### New Methods

```python
class EvoSwarmController:
    """Extended with AgentGym-RL coordination."""

    async def _tick(self) -> None:
        """
        Existing: Fetch CGPs, evaluate fitness, publish packs
        NEW: Trigger RL training when fitness trends indicate need
        """
        # Existing CGP evaluation
        payload = await self._fetch_recent_cgps()
        logger.debug("fetched %s CGPs for evaluation", len(payload))

        # NEW: Check if training should be triggered
        training_decision = await self._evaluate_training_trigger(payload)

        if training_decision["should_train"]:
            await self._launch_agentgym_training(training_decision)

        # Existing: Upsert parameter pack
        namespace = self.config.namespace or ...
        pack = {...}
        ok = await self._upsert_pack(pack)
        if ok:
            await self._publish_swarm_meta(pack)

    async def _evaluate_training_trigger(
        self,
        cgps: list
    ) -> dict:
        """
        Decide if RL training should start based on:

        1. Fitness plateau: No improvement in N generations
        2. New constellation: Novel geometry structure detected
        3. Scheduled interval: Periodic retraining every K epochs
        4. Fitness degradation: Performance dropped below threshold
        """
        recent_fitness = [
            cgp.get("meta", {}).get("fitness", 0.0)
            for cgp in cgps
        ]

        avg_fitness = sum(recent_fitness) / len(recent_fitness) if recent_fitness else 0.0

        # Check plateau
        if self._is_fitness_plateau(recent_fitness):
            return {
                "should_train": True,
                "reason": "fitness_plateau",
                "config": {
                    "algorithm": "grpo",  # Exploration-focused
                    "horizon": 15,
                    "num_epochs": 25
                }
            }

        # Check for new constellations
        new_constellations = self._detect_new_constellations(cgps)
        if new_constellations:
            return {
                "should_train": True,
                "reason": "new_constellation",
                "config": {
                    "algorithm": "ppo",
                    "horizon": 10,
                    "num_epochs": 15,
                    "focus_namespace": new_constellations[0]["namespace"]
                }
            }

        # Check scheduled interval
        if self._should_periodic_train():
            return {
                "should_train": True,
                "reason": "scheduled",
                "config": {
                    "algorithm": "ppo",
                    "horizon": self._get_current_horizon(),  # Progressive scaling
                    "num_epochs": 20
                }
            }

        return {"should_train": False}

    async def _launch_agentgym_training(self, decision: dict) -> None:
        """
        Launch AgentGym-RL training via coordinator API.
        """
        coordinator_url = os.getenv(
            "AGENTGYM_COORDINATOR_URL",
            "http://agentgym-rl-coordinator:8114"
        )

        # Get latest parameter pack for geometry config
        pack = await self._get_latest_pack()

        training_request = {
            "environment": "pmoves-hirag",
            "base_model": os.getenv("AGENTGYM_BASE_MODEL", "Qwen2.5-7B-Instruct"),
            "population_id": f"pop-{self._current_generation}",
            "training_config": decision["config"],
            "geometry_config": {
                "cgp_fitness_weight": 0.3,
                "retrieval_quality_weight": 0.5,
                "task_success_weight": 0.2,
                "parameter_pack_id": pack.get("pack_id")
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{coordinator_url}/agentgym/train/start",
                    json=training_request
                )
                resp.raise_for_status()
                result = resp.json()

                logger.info(
                    "Launched AgentGym training run: %s (reason: %s)",
                    result["training_run_id"],
                    decision["reason"]
                )

                # Publish event to NATS
                await self._publish_training_event(result, decision)

        except Exception as e:
            logger.error("Failed to launch AgentGym training: %s", e)

    async def _publish_training_event(
        self,
        training_result: dict,
        decision: dict
    ) -> None:
        """
        Publish to NATS: agentgym.train.started.v1
        """
        base = os.getenv("AGENT_ZERO_BASE_URL", "http://agent-zero:8080")
        url = f"{base.rstrip('/')}/events/publish"

        body = {
            "topic": "agentgym.train.started.v1",
            "source": "evo-controller",
            "payload": {
                "training_run_id": training_result["training_run_id"],
                "environment": "pmoves-hirag",
                "trigger_reason": decision["reason"],
                "population_id": training_result.get("population_id"),
                "config": decision["config"],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json=body)
        except Exception:
            logger.warning("Failed to publish agentgym.train.started.v1")

    def _is_fitness_plateau(self, recent_fitness: list, window: int = 5) -> bool:
        """
        Detect if fitness has plateaued (no improvement in last N evals).
        """
        if len(recent_fitness) < window:
            return False

        recent = recent_fitness[-window:]
        variance = sum((x - sum(recent)/len(recent))**2 for x in recent) / len(recent)

        # Low variance + no trend = plateau
        return variance < 0.01 and max(recent) == recent[0]

    def _get_current_horizon(self) -> int:
        """
        Progressive horizon scaling for ScalingInter-RL.

        Horizon schedule:
        - Epochs 0-10: horizon=5
        - Epochs 11-20: horizon=10
        - Epochs 21+: horizon=15
        """
        epoch = self._current_epoch

        if epoch < 10:
            return 5
        elif epoch < 20:
            return 10
        else:
            return 15
```

### 4. Geometry-Aware Reward Function

**Location:** `pmoves/vendor/agentgym-rl/environments/pmoves_hirag/rewards.py`

```python
def compute_geometry_aware_reward(
    task: dict,
    action: dict,
    observation: dict,
    trajectory_history: list,
    cgp: dict,
    config: dict
) -> float:
    """
    Multi-component reward function combining:
    1. Task success (did agent answer correctly?)
    2. Retrieval quality (relevance of retrieved info)
    3. CGP alignment (did agent follow constellation structure?)
    4. Efficiency (fewer steps = better)
    """

    # 1. Task success reward (0.0 to 1.0)
    task_reward = 0.0
    if action.get("type") == "answer":
        correctness = evaluate_answer(
            answer=action["answer"],
            ground_truth=task["ground_truth"]
        )
        task_reward = correctness["score"]  # 0.0 to 1.0

    # 2. Retrieval quality reward
    retrieval_reward = 0.0
    if action.get("type") == "query_hirag":
        retrieval_quality = observation.get("retrieval_quality", 0.0)
        retrieval_reward = retrieval_quality

    # 3. Geometry alignment reward
    cgp_alignment = compute_cgp_alignment(
        retrieval_path=trajectory_history,
        cgp_structure=cgp["geometry"]["constellation"]
    )
    geometry_reward = cgp_alignment

    # 4. Efficiency penalty
    step_count = len(trajectory_history)
    efficiency_penalty = max(0, (step_count - task["optimal_steps"]) / 10)

    # Weighted combination
    w_task = config.get("task_success_weight", 0.4)
    w_retrieval = config.get("retrieval_quality_weight", 0.3)
    w_geometry = config.get("cgp_fitness_weight", 0.2)
    w_efficiency = config.get("efficiency_weight", 0.1)

    total_reward = (
        w_task * task_reward +
        w_retrieval * retrieval_reward +
        w_geometry * geometry_reward -
        w_efficiency * efficiency_penalty
    )

    return total_reward


def compute_cgp_alignment(
    retrieval_path: list,
    cgp_structure: dict
) -> float:
    """
    Measure how well agent's retrieval follows constellation structure.

    Constellation structure example:
    {
      "id": "consciousness-quantum",
      "nodes": [
        {"id": "consciousness", "centrality": 0.9},
        {"id": "quantum_theory", "centrality": 0.8},
        {"id": "penrose_orch_or", "centrality": 0.6}
      ],
      "edges": [
        {"from": "consciousness", "to": "quantum_theory", "weight": 0.7},
        {"from": "quantum_theory", "to": "penrose_orch_or", "weight": 0.8}
      ]
    }

    Agent gets higher score for:
    - Retrieving high-centrality nodes
    - Following existing edges
    - Staying within constellation
    """

    if not retrieval_path:
        return 0.0

    node_ids = {node["id"] for node in cgp_structure["nodes"]}
    edge_map = {
        (edge["from"], edge["to"]): edge["weight"]
        for edge in cgp_structure["edges"]
    }

    scores = []

    for i, retrieval in enumerate(retrieval_path):
        entity_id = retrieval.get("entity_id")

        # Score 1: Is node in constellation?
        in_constellation = 1.0 if entity_id in node_ids else 0.0

        # Score 2: Node centrality
        centrality = next(
            (node["centrality"] for node in cgp_structure["nodes"]
             if node["id"] == entity_id),
            0.0
        )

        # Score 3: Edge traversal
        edge_score = 0.0
        if i > 0:
            prev_entity = retrieval_path[i-1].get("entity_id")
            if (prev_entity, entity_id) in edge_map:
                edge_score = edge_map[(prev_entity, entity_id)]

        step_score = (
            0.4 * in_constellation +
            0.3 * centrality +
            0.3 * edge_score
        )
        scores.append(step_score)

    return sum(scores) / len(scores)
```

## Integration Points

### 1. EvoSwarm → AgentGym-RL

**Data Flow:** Training job submission

```python
# EvoSwarm detects need for training
fitness_plateau = True  # No improvement in 5 generations

# Launch training
POST http://agentgym-rl-coordinator:8114/agentgym/train/start
{
  "environment": "pmoves-hirag",
  "population_id": "pop-67",
  "training_config": {
    "algorithm": "grpo",  # Exploration-focused for plateau
    "horizon": 10,
    "num_epochs": 25
  }
}

# Coordinator starts training, publishes event
NATS publish: agentgym.train.started.v1
{
  "training_run_id": "run-789",
  "population_id": "pop-67",
  "trigger_reason": "fitness_plateau"
}
```

### 2. AgentGym-RL → EvoSwarm

**Data Flow:** Training metrics and model checkpoints

```python
# AgentGym-RL completes epoch
NATS publish: agentgym.train.epoch.completed.v1
{
  "training_run_id": "run-789",
  "epoch": 10,
  "metrics": {
    "avg_reward": 0.74,
    "success_rate": 0.71,
    "geometry_coherence": 0.83
  },
  "checkpoint_path": "s3://agentgym-models/run-789/epoch-10.ckpt"
}

# EvoSwarm listens and incorporates metrics into fitness
# High geometry_coherence → update CGP builder parameters
```

### 3. Hi-RAG v2 → AgentGym-RL

**Data Flow:** Knowledge retrieval for environment

```python
# Agent in PMOVES-HiRAG environment takes action
action = {"type": "query_hirag", "query": "consciousness quantum mechanics"}

# Environment calls Hi-RAG v2
POST http://hi-rag-gateway-v2:8086/hirag/query
{
  "query": "consciousness quantum mechanics",
  "top_k": 10,
  "rerank": true,
  "namespace": "pmoves.consciousness"
}

# Hi-RAG returns results with scores
response = {
  "results": [
    {
      "text": "...",
      "entity_id": "penrose_orch_or",
      "rerank_score": 0.92,
      "centrality": 0.8,
      "constellation_id": "consciousness-quantum"
    },
    ...
  ]
}

# Environment computes reward using these scores
```

### 4. AgentGym-RL → Agent Zero

**Data Flow:** Trained agent deployment

```python
# Training completes
NATS publish: agentgym.train.completed.v1
{
  "training_run_id": "run-789",
  "final_metrics": {...},
  "best_checkpoint": "s3://agentgym-models/run-789/best.ckpt"
}

# Agent Zero subscribes, registers new agent policy
# Can deploy trained agent via MCP API
POST http://agent-zero:8080/mcp/agent/register
{
  "agent_id": "retrieval-specialist-v2",
  "model_path": "s3://agentgym-models/run-789/best.ckpt",
  "capabilities": ["hirag_query", "constellation_nav"]
}
```

## Database Schema

### agentgym_training_runs

```sql
CREATE TABLE agentgym_training_runs (
  run_id TEXT PRIMARY KEY,
  population_id TEXT,
  environment TEXT,
  algorithm TEXT,  -- ppo|grpo|rloo|reinforce++
  status TEXT,  -- queued|training|completed|failed
  trigger_reason TEXT,  -- fitness_plateau|new_constellation|scheduled

  -- Training config
  base_model TEXT,
  num_epochs INT,
  current_epoch INT,
  horizon INT,
  batch_size INT,
  learning_rate FLOAT,

  -- Geometry config
  parameter_pack_id TEXT REFERENCES geometry_parameter_packs(pack_id),
  cgp_fitness_weight FLOAT,
  retrieval_quality_weight FLOAT,
  task_success_weight FLOAT,

  -- Metrics
  avg_reward FLOAT,
  success_rate FLOAT,
  avg_episode_length FLOAT,
  geometry_coherence FLOAT,

  -- Timestamps
  started_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP,

  -- Metadata
  metadata JSONB
);

CREATE INDEX idx_training_runs_population ON agentgym_training_runs(population_id);
CREATE INDEX idx_training_runs_status ON agentgym_training_runs(status);
```

### agentgym_trajectories

```sql
CREATE TABLE agentgym_trajectories (
  trajectory_id TEXT PRIMARY KEY,
  run_id TEXT REFERENCES agentgym_training_runs(run_id),
  epoch INT,
  episode_id INT,

  -- Task info
  task_description TEXT,
  constellation_id TEXT,
  cgp_id TEXT REFERENCES geometry_cgp_v1(cgp_id),
  difficulty TEXT,

  -- Episode data
  steps JSONB,  -- [{action, observation, reward}, ...]
  total_reward FLOAT,
  success BOOLEAN,
  episode_length INT,

  -- Metrics
  geometry_coherence FLOAT,
  retrieval_quality FLOAT,

  -- Storage
  full_trajectory_path TEXT,  -- MinIO path for detailed data

  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_trajectories_run ON agentgym_trajectories(run_id);
CREATE INDEX idx_trajectories_constellation ON agentgym_trajectories(constellation_id);
```

### agentgym_checkpoints

```sql
CREATE TABLE agentgym_checkpoints (
  checkpoint_id TEXT PRIMARY KEY,
  run_id TEXT REFERENCES agentgym_training_runs(run_id),
  epoch INT,

  -- Model info
  model_path TEXT,  -- MinIO path
  model_size_bytes BIGINT,

  -- Performance
  avg_reward FLOAT,
  success_rate FLOAT,
  is_best BOOLEAN DEFAULT FALSE,

  -- Versioning
  version TEXT,
  parent_checkpoint_id TEXT REFERENCES agentgym_checkpoints(checkpoint_id),

  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_checkpoints_run ON agentgym_checkpoints(run_id);
CREATE INDEX idx_checkpoints_best ON agentgym_checkpoints(is_best) WHERE is_best = TRUE;
```

## NATS Event Subjects

Add to `pmoves/contracts/topics.json`:

```json
{
  "agentgym.train.started.v1": {
    "schema": "schemas/agentgym/train.started.v1.schema.json",
    "description": "AgentGym-RL training run started"
  },
  "agentgym.train.epoch.completed.v1": {
    "schema": "schemas/agentgym/train.epoch.completed.v1.schema.json",
    "description": "AgentGym-RL training epoch completed"
  },
  "agentgym.train.completed.v1": {
    "schema": "schemas/agentgym/train.completed.v1.schema.json",
    "description": "AgentGym-RL training run completed"
  },
  "agentgym.train.failed.v1": {
    "schema": "schemas/agentgym/train.failed.v1.schema.json",
    "description": "AgentGym-RL training run failed"
  },
  "agentgym.trajectory.collected.v1": {
    "schema": "schemas/agentgym/trajectory.collected.v1.schema.json",
    "description": "Agent trajectory collected during training"
  }
}
```

## Docker Compose Additions

Add to `pmoves/docker-compose.yml`:

```yaml
services:
  agentgym-rl-coordinator:
    build:
      context: ./services/agentgym-rl-coordinator
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file: [env.shared.generated, env.shared, .env.generated, .env.local]
    environment:
      - AGENTGYM_BASE_MODEL=${AGENTGYM_BASE_MODEL:-Qwen2.5-7B-Instruct}
      - AGENTGYM_MODEL_PATH=/models
      - HIRAG_URL=${HIRAG_URL:-http://hi-rag-gateway-v2:8086}
      - SUPABASE_REST_URL=${SUPA_REST_URL}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      - MINIO_ENDPOINT=${MINIO_ENDPOINT}
      - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
      - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
      - NATS_URL=${NATS_URL:-nats://nats:4222}
      - TENSORZERO_BASE_URL=${TENSORZERO_BASE_URL}
    ports:
      - "8114:8114"
    volumes:
      - ./vendor/agentgym-rl:/agentgym-rl:ro
      - agentgym-models:/models
      - agentgym-logs:/logs
    depends_on:
      - nats
      - hi-rag-gateway-v2
      - evo-controller
    profiles: ["agents", "agentgym"]
    networks: [app_tier, api_tier, data_tier, monitoring_tier]
    extra_hosts:
      - "host.docker.internal:host-gateway"

  agentgym-env-pmoves:
    build:
      context: ./vendor/agentgym-rl
      dockerfile: environments/pmoves_hirag/Dockerfile
    restart: unless-stopped
    env_file: [env.shared.generated, env.shared, .env.generated, .env.local]
    environment:
      - HIRAG_URL=${HIRAG_URL:-http://hi-rag-gateway-v2:8086}
      - ENVIRONMENT_PORT=36000
      - SUPABASE_REST_URL=${SUPA_REST_URL}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
    ports:
      - "36000:36000"
    depends_on:
      - hi-rag-gateway-v2
    profiles: ["agents", "agentgym"]
    networks: [app_tier, data_tier]

volumes:
  agentgym-models:
  agentgym-logs:
```

## Environment Variables

Add to `pmoves/env.shared`:

```bash
# AgentGym-RL Configuration
AGENTGYM_COORDINATOR_URL=http://agentgym-rl-coordinator:8114
AGENTGYM_BASE_MODEL=Qwen2.5-7B-Instruct
AGENTGYM_MODEL_PATH=/models
AGENTGYM_ENABLE=true

# Training defaults
AGENTGYM_DEFAULT_ALGORITHM=ppo  # ppo|grpo|rloo|reinforce++
AGENTGYM_DEFAULT_HORIZON=10
AGENTGYM_DEFAULT_EPOCHS=25
AGENTGYM_DEFAULT_BATCH_SIZE=32
AGENTGYM_DEFAULT_LR=1e-6
AGENTGYM_DEFAULT_KL_COEF=0.001

# Geometry-aware reward weights
AGENTGYM_TASK_SUCCESS_WEIGHT=0.4
AGENTGYM_RETRIEVAL_QUALITY_WEIGHT=0.3
AGENTGYM_CGP_FITNESS_WEIGHT=0.2
AGENTGYM_EFFICIENCY_WEIGHT=0.1

# Training triggers (EvoSwarm)
AGENTGYM_TRIGGER_ON_PLATEAU=true
AGENTGYM_PLATEAU_WINDOW=5  # generations
AGENTGYM_TRIGGER_ON_NEW_CONSTELLATION=true
AGENTGYM_PERIODIC_TRAINING_INTERVAL=100  # epochs

# ScalingInter-RL progressive horizon
AGENTGYM_HORIZON_SCHEDULE=5,10,15  # comma-separated
AGENTGYM_HORIZON_EPOCH_THRESHOLDS=0,10,20  # when to switch

# Environment config
AGENTGYM_ENV_MAX_TURNS=15
AGENTGYM_ENV_TIMEOUT=600  # seconds
AGENTGYM_ENV_NAMESPACE=pmoves.consciousness

# Monitoring
AGENTGYM_WANDB_PROJECT=pmoves-agentgym-rl
AGENTGYM_WANDB_ENTITY=pmoves-ai
AGENTGYM_LOG_TRAJECTORIES=true
AGENTGYM_SAVE_FREQ=5  # epochs

# GPU allocation (if different from main services)
AGENTGYM_GPU_MEMORY_UTILIZATION=0.7
AGENTGYM_TENSOR_PARALLEL_SIZE=1
```

## Implementation Roadmap

### Phase 1: Basic Integration (Weeks 1-2)

**Goal:** Trajectory logging and basic environment

**Tasks:**
1. Create AgentGym-RL coordinator service skeleton
   - FastAPI app with `/train/start`, `/train/status` endpoints
   - NATS publisher for training events
   - Supabase client for trajectory storage

2. Implement PMOVES-HiRAG environment stub
   - Basic `reset()` and `step()` methods
   - Static task generator (hand-crafted questions)
   - Hi-RAG v2 API client

3. Add trajectory logging to Supabase
   - Create database tables
   - Store episode data in `agentgym_trajectories`
   - MinIO integration for full trajectory storage

4. EvoSwarm controller: Add training event publisher
   - NATS client in `_tick()` method
   - Publish `agentgym.train.started.v1` on demand

**Deliverables:**
- AgentGym-RL coordinator service running on port 8114
- Basic PMOVES-HiRAG environment
- Trajectory data flowing to Supabase
- Docker compose integration

**Validation:**
```bash
# Start training manually
curl -X POST http://localhost:8114/agentgym/train/start -H "Content-Type: application/json" -d '{
  "environment": "pmoves-hirag",
  "base_model": "Qwen2.5-7B-Instruct",
  "training_config": {"algorithm": "ppo", "num_epochs": 1}
}'

# Check trajectory logging
psql $SUPABASE_DB_URL -c "SELECT COUNT(*) FROM agentgym_trajectories;"
```

### Phase 2: Geometry-Aware Rewards (Weeks 3-4)

**Goal:** Integrate CGP fitness into reward function

**Tasks:**
1. Implement `compute_cgp_alignment()` function
   - Fetch CGP for current task from Supabase
   - Compare retrieval path to constellation structure
   - Return alignment score

2. Implement `compute_geometry_aware_reward()`
   - Multi-component reward (task + retrieval + geometry + efficiency)
   - Configurable weights via environment variables

3. Add `ConstellationTaskGenerator`
   - Sample CGPs from Supabase
   - Generate single-hop, multi-hop, synthesis tasks
   - Difficulty progression

4. Update PMOVES-HiRAG environment
   - Use geometry-aware reward
   - Track geometry coherence metric
   - Publish coherence to NATS

**Deliverables:**
- Geometry-aware reward function working
- Task generator producing constellation-based challenges
- Metrics showing geometry coherence improving during training

**Validation:**
```python
# Run training with geometry rewards enabled
result = coordinator.start_training(
    environment="pmoves-hirag",
    geometry_config={
        "cgp_fitness_weight": 0.3,
        "retrieval_quality_weight": 0.5
    }
)

# Check that geometry_coherence metric is populated
trajectories = fetch_trajectories(result["training_run_id"])
assert all(t["geometry_coherence"] > 0 for t in trajectories)
```

### Phase 3: Full PBT with CGP Evolution (Weeks 5-6)

**Goal:** Population-based training coordinated by EvoSwarm

**Tasks:**
1. Extend EvoSwarm controller with training triggers
   - Implement `_evaluate_training_trigger()`
   - Detect fitness plateau, new constellations, scheduled intervals
   - Call AgentGym coordinator API

2. Implement ScalingInter-RL horizon progression
   - `_get_current_horizon()` method in EvoSwarm
   - Progressive schedule: 5 → 10 → 15 turns
   - Adjust based on training epoch

3. Add population-based training
   - Multiple training runs with different hyperparameters
   - Track population fitness in `geometry_swarm_runs`
   - Select best performers for next generation

4. Checkpoint management
   - Store models in MinIO
   - Register best checkpoints in `agentgym_checkpoints`
   - Enable model versioning and rollback

5. Integrate with TensorZero Gateway
   - Route agent policy inference through TensorZero
   - Track token usage and latency
   - A/B test different agent policies

**Deliverables:**
- EvoSwarm automatically triggers training on plateau
- ScalingInter-RL working with progressive horizons
- Population-based training with multiple variants
- Model checkpoints versioned and stored

**Validation:**
```bash
# Simulate fitness plateau
# EvoSwarm should auto-trigger training

# Check NATS for training event
nats sub "agentgym.train.started.v1"

# Verify horizon progression
curl http://localhost:8114/agentgym/train/run-123/status | jq .current_horizon
# Should increase: 5 (epoch 0-10) → 10 (epoch 11-20) → 15 (epoch 21+)

# Check population tracking
psql $SUPABASE_DB_URL -c "SELECT population_id, COUNT(*) FROM agentgym_training_runs GROUP BY population_id;"
```

## Monitoring and Observability

### Grafana Dashboard

Create `pmoves/monitoring/grafana/dashboards/agentgym-rl.json`:

**Panels:**
1. Training runs (status breakdown)
2. Average reward over time
3. Success rate by environment
4. Geometry coherence trend
5. Training duration distribution
6. Model checkpoint frequency
7. GPU utilization during training
8. NATS event rate (training events)

**Queries:**
```promql
# Average reward
avg(agentgym_training_avg_reward{status="training"})

# Success rate
agentgym_training_success_rate{environment="pmoves-hirag"}

# Geometry coherence
avg(agentgym_trajectory_geometry_coherence)

# Training duration
histogram_quantile(0.95, agentgym_training_duration_seconds_bucket)
```

### Prometheus Metrics

Add to AgentGym-RL coordinator:

```python
from prometheus_client import Counter, Gauge, Histogram

# Counters
training_runs_started = Counter(
    "agentgym_training_runs_started_total",
    "Total training runs started",
    ["environment", "algorithm"]
)

training_runs_completed = Counter(
    "agentgym_training_runs_completed_total",
    "Total training runs completed",
    ["environment", "algorithm", "status"]  # success|failed
)

trajectories_collected = Counter(
    "agentgym_trajectories_collected_total",
    "Total trajectories collected",
    ["run_id", "success"]
)

# Gauges
active_training_runs = Gauge(
    "agentgym_training_runs_active",
    "Number of active training runs",
    ["environment"]
)

avg_reward = Gauge(
    "agentgym_training_avg_reward",
    "Average reward for training run",
    ["run_id", "epoch"]
)

geometry_coherence = Gauge(
    "agentgym_trajectory_geometry_coherence",
    "Geometry coherence score",
    ["run_id", "constellation_id"]
)

# Histograms
training_duration = Histogram(
    "agentgym_training_duration_seconds",
    "Training run duration in seconds",
    ["environment", "algorithm"]
)

episode_length = Histogram(
    "agentgym_episode_length",
    "Episode length (number of steps)",
    ["environment", "difficulty"]
)
```

## Security Considerations

1. **Model access control**
   - Restrict MinIO bucket access to coordinator only
   - Require authentication for checkpoint downloads
   - Sign model files with GPG

2. **Training resource limits**
   - Set max concurrent training runs
   - GPU memory quotas per run
   - Timeout for stuck training jobs

3. **Trajectory data privacy**
   - Redact sensitive information from trajectories
   - Encrypt trajectory files in MinIO
   - Retention policy: delete after 90 days

4. **NATS subject ACLs**
   - Only EvoSwarm can publish `agentgym.train.*`
   - Only coordinator can publish trajectory events

## Testing Strategy

### Unit Tests

```python
# Test geometry-aware reward
def test_geometry_aware_reward():
    cgp = load_fixture("consciousness-quantum.cgp")
    trajectory = [
        {"entity_id": "consciousness", "rerank_score": 0.9},
        {"entity_id": "quantum_theory", "rerank_score": 0.85}
    ]

    reward = compute_geometry_aware_reward(
        task={"ground_truth": "correct answer"},
        action={"type": "answer", "answer": "correct answer"},
        observation={},
        trajectory_history=trajectory,
        cgp=cgp,
        config={
            "task_success_weight": 0.4,
            "cgp_fitness_weight": 0.3
        }
    )

    assert 0.0 <= reward <= 1.0
    assert reward > 0.5  # Should be high for correct answer + good alignment

# Test constellation task generator
def test_task_generator():
    generator = ConstellationTaskGenerator("pmoves.consciousness")
    task = generator.sample_task(difficulty="medium")

    assert "description" in task
    assert "constellation_id" in task
    assert "target_concepts" in task
    assert len(task["target_concepts"]) >= 2  # Multi-hop for medium
```

### Integration Tests

```python
# Test end-to-end training flow
@pytest.mark.integration
async def test_training_flow():
    # Start training
    resp = await coordinator_client.post("/agentgym/train/start", json={
        "environment": "pmoves-hirag",
        "training_config": {"num_epochs": 2}
    })
    run_id = resp.json()["training_run_id"]

    # Wait for completion (with timeout)
    await wait_for_training_completion(run_id, timeout=600)

    # Check trajectories logged
    trajectories = await db.fetch(
        "SELECT * FROM agentgym_trajectories WHERE run_id = $1",
        run_id
    )
    assert len(trajectories) > 0

    # Check checkpoint created
    checkpoint = await db.fetchrow(
        "SELECT * FROM agentgym_checkpoints WHERE run_id = $1 AND is_best = TRUE",
        run_id
    )
    assert checkpoint is not None
    assert checkpoint["model_path"].startswith("s3://")
```

### Load Tests

```bash
# Simulate multiple concurrent training runs
hey -n 10 -c 3 -m POST -H "Content-Type: application/json" \
  -d '{"environment":"pmoves-hirag","training_config":{"num_epochs":5}}' \
  http://localhost:8114/agentgym/train/start

# Check system stability
curl http://localhost:8114/healthz
curl http://localhost:9090/api/v1/query?query=agentgym_training_runs_active
```

## Future Enhancements

1. **Multi-environment training**
   - Train agents across WebArena, TextCraft, BabyAI simultaneously
   - Transfer learning between environments
   - Unified policy for diverse tasks

2. **Curriculum learning**
   - Start with easy tasks, progress to hard
   - Automatically adjust difficulty based on success rate
   - Multi-stage training pipeline

3. **Meta-learning**
   - Train agent to learn how to learn
   - Few-shot adaptation to new constellations
   - Rapid fine-tuning on novel namespaces

4. **Distributed training**
   - Multi-GPU training across cluster
   - Parameter server for large models
   - Ray integration for scaling

5. **Human feedback integration**
   - RLHF loop for trajectory refinement
   - Expert demonstrations for imitation learning
   - Active learning to query humans on hard cases

6. **Model compression**
   - Distill large agent into smaller model
   - Quantization for faster inference
   - Deploy to edge devices (TensorRT)

## References

- **AgentGym-RL paper:** [Training LLM Agents for Long-Horizon Decision Making](https://arxiv.org/abs/2509.08755)
- **EvoSwarm context:** `.claude/context/evoswarm.md`
- **CONCH execution guide:** `pmoves/docs/PMOVESCHIT/PMOVES-CONCHexecution_guide.md`
- **Hi-RAG v2 service:** `pmoves/services/hi-rag-gateway-v2/`
- **NATS subjects:** `pmoves/contracts/topics.json`

## Developer Notes

**For Claude Code CLI users:**

This integration enables agents to learn retrieval strategies guided by CHIT geometry. Key points:

- EvoSwarm automatically triggers training when geometry fitness plateaus
- Agents train on Hi-RAG query tasks with constellation structure as guidance
- Trained agents can be deployed via Agent Zero MCP API
- All training metadata flows through Supabase for observability
- Use test namespace for development: `AGENTGYM_ENV_NAMESPACE=test`

**Quick start:**
```bash
# Enable AgentGym-RL profile
docker compose --profile agentgym up -d

# Trigger training manually
curl -X POST http://localhost:8114/agentgym/train/start -H "Content-Type: application/json" -d '{
  "environment": "pmoves-hirag",
  "training_config": {"algorithm": "ppo", "num_epochs": 5}
}'

# Monitor progress
curl http://localhost:8114/agentgym/train/{run_id}/status

# View Grafana dashboard
open http://localhost:3002/d/agentgym-rl
```
