# EvoSwarm + AgentGym-RL Quick Start Guide

**For developers implementing the integration**

## Overview

This guide provides a quick reference for implementing the EvoSwarm + AgentGym-RL integration. For full architecture details, see `evoswarm-agentgym-rl-integration.md`.

## Files Created

### 1. Architecture Document
**Path:** `/home/pmoves/PMOVES.AI/pmoves/docs/architecture/evoswarm-agentgym-rl-integration.md`

Complete integration design including:
- Component architecture
- API specifications
- Database schema
- NATS event subjects
- Reward function design
- Implementation roadmap (3 phases)

### 2. EvoSwarm Controller Extensions
**Path:** `/home/pmoves/PMOVES.AI/pmoves/services/evo-controller/agentgym_integration.py`

Python module providing:
- `AgentGymIntegration` mixin class
- Training trigger evaluation
- ScalingInterRL horizon scheduling
- AgentGym coordinator API client
- NATS event publishing

### 3. Docker Compose Configuration
**Path:** `/home/pmoves/PMOVES.AI/pmoves/docker-compose.agentgym.yml`

Services:
- `agentgym-rl-coordinator`: Training orchestrator (port 8114)
- `agentgym-env-pmoves`: PMOVES-HiRAG environment (port 36000)

Volumes:
- `agentgym-models`: Model checkpoints
- `agentgym-logs`: Training logs
- `agentgym-task-cache`: Cached constellation tasks

### 4. Environment Variables
**Path:** `/home/pmoves/PMOVES.AI/pmoves/env.agentgym.example`

Configuration for:
- Training defaults (algorithm, horizon, epochs)
- Reward weights (task success, retrieval quality, CGP fitness)
- Training triggers (plateau, new constellation, scheduled)
- ScalingInter-RL horizon progression
- GPU allocation
- Monitoring (W&B, Prometheus)

## Implementation Steps

### Phase 1: Basic Integration (Weeks 1-2)

**Goal:** Get training running and trajectories logging

1. **Create service directories**
   ```bash
   mkdir -p pmoves/services/agentgym-rl-coordinator
   mkdir -p pmoves/vendor/agentgym-rl/environments/pmoves_hirag
   ```

2. **Implement AgentGym coordinator service**
   ```python
   # pmoves/services/agentgym-rl-coordinator/app.py
   from fastapi import FastAPI
   import httpx

   app = FastAPI(title="AgentGym-RL Coordinator")

   @app.post("/agentgym/train/start")
   async def start_training(request: TrainingRequest):
       # 1. Validate request
       # 2. Launch training process
       # 3. Store metadata in Supabase
       # 4. Publish NATS event
       # 5. Return training_run_id
       pass

   @app.get("/agentgym/train/{run_id}/status")
   async def get_status(run_id: str):
       # Query Supabase for run status
       pass
   ```

3. **Implement PMOVES-HiRAG environment stub**
   ```python
   # pmoves/vendor/agentgym-rl/environments/pmoves_hirag/env.py
   class PMOVESHiRAGEnv:
       def reset(self) -> dict:
           # Generate task from constellation
           task = self.task_generator.sample_task()
           return {
               "task_description": task["description"],
               "constellation_id": task["constellation_id"]
           }

       def step(self, action: dict) -> tuple:
           if action["type"] == "query_hirag":
               results = self._query_hirag(action["query"])
               reward = self._compute_retrieval_reward(results)
               done = False
           elif action["type"] == "answer":
               correctness = self._evaluate_answer(action["answer"])
               reward = correctness["score"]
               done = True

           return observation, reward, done, info
   ```

4. **Add trajectory logging**
   ```sql
   -- Run migrations in Supabase
   CREATE TABLE agentgym_training_runs (...);
   CREATE TABLE agentgym_trajectories (...);
   CREATE TABLE agentgym_checkpoints (...);
   ```

5. **Integrate with EvoSwarm controller**
   ```python
   # pmoves/services/evo-controller/app.py
   from agentgym_integration import AgentGymIntegration

   class EvoSwarmController(AgentGymIntegration):
       async def _tick(self) -> None:
           # Existing: Fetch CGPs, evaluate fitness
           payload = await self._fetch_recent_cgps()

           # NEW: Check if training should be triggered
           decision = await self.evaluate_training_trigger(payload)
           if decision["should_train"]:
               pack = await self._get_latest_pack()
               result = await self.launch_agentgym_training(decision, pack)
               if result:
                   await self.publish_training_event(result, decision)

           # Existing: Upsert parameter pack, publish swarm meta
           ...

           # NEW: Increment epoch for ScalingInter-RL
           self.increment_epoch()
   ```

6. **Test manually**
   ```bash
   # Start services
   docker compose -f docker-compose.yml -f docker-compose.agentgym.yml --profile agentgym up -d

   # Trigger training
   curl -X POST http://localhost:8114/agentgym/train/start \
     -H "Content-Type: application/json" \
     -d '{
       "environment": "pmoves-hirag",
       "base_model": "Qwen2.5-7B-Instruct",
       "training_config": {
         "algorithm": "ppo",
         "num_epochs": 2
       }
     }'

   # Check status
   curl http://localhost:8114/agentgym/train/{run_id}/status

   # Verify trajectory logging
   docker compose exec postgres psql -U pmoves -d pmoves \
     -c "SELECT COUNT(*) FROM agentgym_trajectories;"
   ```

**Deliverables:**
- ✅ AgentGym coordinator responds on port 8114
- ✅ Training can be triggered via API
- ✅ Trajectories logged to Supabase
- ✅ NATS events published

### Phase 2: Geometry-Aware Rewards (Weeks 3-4)

**Goal:** Integrate CGP fitness into reward function

1. **Implement geometry alignment computation**
   ```python
   # pmoves/vendor/agentgym-rl/environments/pmoves_hirag/rewards.py
   def compute_cgp_alignment(retrieval_path, cgp_structure):
       # Check if retrieved nodes are in constellation
       # Measure centrality of retrieved nodes
       # Score edge traversal
       return alignment_score  # 0.0 to 1.0
   ```

2. **Implement multi-component reward**
   ```python
   def compute_geometry_aware_reward(task, action, observation, trajectory, cgp, config):
       task_reward = evaluate_answer(action["answer"], task["ground_truth"])
       retrieval_reward = observation.get("retrieval_quality", 0.0)
       geometry_reward = compute_cgp_alignment(trajectory, cgp["geometry"]["constellation"])
       efficiency_penalty = max(0, (len(trajectory) - task["optimal_steps"]) / 10)

       return (
           config["task_success_weight"] * task_reward +
           config["retrieval_quality_weight"] * retrieval_reward +
           config["cgp_fitness_weight"] * geometry_reward -
           config["efficiency_weight"] * efficiency_penalty
       )
   ```

3. **Add constellation task generator**
   ```python
   # pmoves/vendor/agentgym-rl/environments/pmoves_hirag/task_generator.py
   class ConstellationTaskGenerator:
       def sample_task(self, difficulty="medium"):
           # Fetch recent CGPs from Supabase
           cgp = random.choice(self.cgp_cache)
           constellation = cgp["geometry"]["constellation"]

           if difficulty == "medium":
               # Generate multi-hop question
               path = self._sample_graph_path(constellation, max_hops=3)
               question = self._path_to_question(path, constellation)
               return {
                   "description": question,
                   "constellation_id": constellation["id"],
                   "cgp_id": cgp["cgp_id"],
                   "target_concepts": path,
                   "optimal_path": path
               }
   ```

4. **Test geometry rewards**
   ```python
   # Test script
   cgp = fetch_cgp("consciousness-quantum")
   task = generate_task_from_cgp(cgp)
   trajectory = simulate_agent_episode(task)

   reward = compute_geometry_aware_reward(
       task=task,
       action={"type": "answer", "answer": "correct"},
       observation={},
       trajectory_history=trajectory,
       cgp=cgp,
       config={"cgp_fitness_weight": 0.3}
   )

   assert reward > 0.5  # Should be high for good alignment
   ```

**Deliverables:**
- ✅ Geometry alignment scoring works
- ✅ Multi-component reward implemented
- ✅ Task generator produces constellation-based challenges
- ✅ Metrics show geometry_coherence improving

### Phase 3: Full PBT with CGP Evolution (Weeks 5-6)

**Goal:** Automatic training triggered by EvoSwarm

1. **Add training triggers to EvoSwarm**
   ```python
   # Already implemented in agentgym_integration.py
   # Just enable in environment variables:
   AGENTGYM_ENABLE=true
   AGENTGYM_TRIGGER_ON_PLATEAU=true
   AGENTGYM_PLATEAU_WINDOW=5
   ```

2. **Implement ScalingInter-RL horizon progression**
   ```bash
   # Configure horizon schedule
   AGENTGYM_HORIZON_SCHEDULE=5,10,15
   AGENTGYM_HORIZON_EPOCH_THRESHOLDS=0,10,20

   # EvoSwarm will automatically use:
   # - Epochs 0-10: horizon=5
   # - Epochs 11-20: horizon=10
   # - Epochs 21+: horizon=15
   ```

3. **Add checkpoint management**
   ```python
   # In coordinator after each epoch
   async def save_checkpoint(run_id, epoch, model, metrics):
       # Save to MinIO
       model_path = f"s3://agentgym-models/{run_id}/epoch-{epoch}.ckpt"
       await minio_client.upload(model, model_path)

       # Record in Supabase
       await db.execute(
           "INSERT INTO agentgym_checkpoints (run_id, epoch, model_path, avg_reward, is_best) VALUES ($1, $2, $3, $4, $5)",
           run_id, epoch, model_path, metrics["avg_reward"], is_best
       )
   ```

4. **Test automatic training**
   ```bash
   # Simulate fitness plateau by adding low-fitness CGPs
   # EvoSwarm should auto-trigger training

   # Monitor NATS events
   nats sub "agentgym.train.started.v1"

   # Check EvoSwarm logs
   docker compose logs -f evo-controller | grep "AgentGym"

   # Verify training launched
   curl http://localhost:8114/agentgym/train/{run_id}/status
   ```

**Deliverables:**
- ✅ EvoSwarm auto-triggers training on plateau
- ✅ ScalingInter-RL horizon progression works
- ✅ Checkpoints saved and versioned
- ✅ Population tracking in database

## Configuration Quick Reference

### Minimal Configuration (Quick Test)
```bash
# Add to env.shared
AGENTGYM_ENABLE=true
AGENTGYM_DEFAULT_EPOCHS=2
AGENTGYM_DEFAULT_BATCH_SIZE=8
AGENTGYM_DEFAULT_HORIZON=5
AGENTGYM_ENV_MAX_TURNS=5
```

### Production Configuration
```bash
# Add to env.shared
AGENTGYM_ENABLE=true
AGENTGYM_DEFAULT_ALGORITHM=ppo
AGENTGYM_DEFAULT_EPOCHS=50
AGENTGYM_DEFAULT_BATCH_SIZE=64
AGENTGYM_DEFAULT_HORIZON=15
AGENTGYM_ENV_MAX_TURNS=20

# Reward weights
AGENTGYM_TASK_SUCCESS_WEIGHT=0.4
AGENTGYM_RETRIEVAL_QUALITY_WEIGHT=0.3
AGENTGYM_CGP_FITNESS_WEIGHT=0.2
AGENTGYM_EFFICIENCY_WEIGHT=0.1

# Training triggers
AGENTGYM_TRIGGER_ON_PLATEAU=true
AGENTGYM_PLATEAU_WINDOW=5
AGENTGYM_TRIGGER_ON_NEW_CONSTELLATION=true
AGENTGYM_PERIODIC_TRAINING_INTERVAL=100

# ScalingInter-RL
AGENTGYM_HORIZON_SCHEDULE=5,10,15
AGENTGYM_HORIZON_EPOCH_THRESHOLDS=0,10,20
```

## Common Commands

```bash
# Start AgentGym services
docker compose -f docker-compose.yml -f docker-compose.agentgym.yml --profile agentgym up -d

# Check service health
curl http://localhost:8114/healthz
curl http://localhost:36000/healthz

# Trigger training manually
curl -X POST http://localhost:8114/agentgym/train/start \
  -H "Content-Type: application/json" \
  -d @pmoves/examples/agentgym-training-request.json

# Check training status
curl http://localhost:8114/agentgym/train/{run_id}/status | jq

# Monitor NATS events
nats sub "agentgym.train.*"

# Check EvoSwarm status
curl http://localhost:8113/config | jq .agentgym

# View trajectories
docker compose exec postgres psql -U pmoves -d pmoves \
  -c "SELECT run_id, COUNT(*) as episodes, AVG(total_reward) as avg_reward FROM agentgym_trajectories GROUP BY run_id ORDER BY run_id DESC LIMIT 10;"

# Check model checkpoints
docker compose exec postgres psql -U pmoves -d pmoves \
  -c "SELECT run_id, epoch, avg_reward, is_best FROM agentgym_checkpoints ORDER BY run_id DESC, epoch DESC LIMIT 10;"

# View Grafana dashboard
open http://localhost:3002/d/agentgym-rl

# Stop services
docker compose -f docker-compose.yml -f docker-compose.agentgym.yml --profile agentgym down
```

## Debugging Tips

### Training not starting
```bash
# Check EvoSwarm logs
docker compose logs evo-controller | grep -i agentgym

# Verify AgentGym enabled
curl http://localhost:8113/config | jq .agentgym.enabled

# Check coordinator reachable
curl http://localhost:8114/healthz
```

### No trajectories logged
```bash
# Check environment server
curl http://localhost:36000/healthz

# Check Supabase connection
docker compose exec agentgym-rl-coordinator env | grep SUPABASE

# Check database tables exist
docker compose exec postgres psql -U pmoves -d pmoves -c "\dt agentgym*"
```

### Geometry rewards always zero
```bash
# Verify CGPs available
curl "$SUPA_REST_URL/geometry_cgp_v1?limit=5" \
  -H "apikey: $SUPABASE_SERVICE_KEY" | jq

# Check Hi-RAG v2 accessible
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 5}'

# Enable debug logging
docker compose exec agentgym-env-pmoves env LOG_LEVEL=DEBUG
docker compose restart agentgym-env-pmoves
```

## Next Steps

After completing Phase 3:

1. **Monitor production performance**
   - View Grafana dashboard at http://localhost:3002/d/agentgym-rl
   - Track geometry_coherence metric over time
   - Compare success rates before/after training

2. **Deploy trained agents**
   - Register best checkpoint in TensorZero Gateway
   - Integrate with Agent Zero via MCP API
   - Enable A/B testing of policies

3. **Expand to other environments**
   - Add WebArena environment
   - Add TextCraft environment
   - Train unified multi-environment policy

4. **Implement advanced features**
   - Curriculum learning with difficulty progression
   - Population-based training (PBT)
   - Meta-learning for fast adaptation
   - Distributed training across cluster

## References

- Full architecture doc: `pmoves/docs/architecture/evoswarm-agentgym-rl-integration.md`
- EvoSwarm context: `.claude/context/evoswarm.md`
- AgentGym-RL paper: https://arxiv.org/abs/2509.08755
- CONCH execution guide: `pmoves/docs/PMOVESCHIT/PMOVES-CONCHexecution_guide.md`

## Support

For questions or issues:
1. Check architecture doc for detailed specifications
2. Review AgentGym-RL README at `pmoves/vendor/agentgym-rl/README.md`
3. Examine test cases in `pmoves/services/agentgym-rl-coordinator/tests/`
4. Consult CLAUDE.md for PMOVES.AI integration patterns
