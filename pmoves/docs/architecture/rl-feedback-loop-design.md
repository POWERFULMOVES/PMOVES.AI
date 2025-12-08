# AgentGym-RL Feedback Loop Design for Agent Zero Integration

**Version:** 1.0
**Date:** 2025-12-08
**Status:** Design Specification

## Executive Summary

This document specifies the event-driven reinforcement learning (RL) feedback loop for integrating Agent Zero with AgentGym-RL. The system enables continuous learning from agent interactions, automated reward signal collection, and model improvement through online RL training.

## Architecture Overview

The RL feedback loop creates a closed-loop system where:
1. Agent Zero executes tasks and publishes trajectory data to NATS
2. RL Trainer subordinate collects trajectories and computes rewards
3. AgentGym-RL training service processes trajectories for model updates
4. Updated model checkpoints propagate back to Agent Zero
5. Performance metrics flow to observability stack (Prometheus/Grafana)

### Key Components

- **Agent Zero**: Primary orchestrator executing tasks and collecting interaction data
- **RL Trainer Subordinate**: Specialized agent coordinating RL training lifecycle
- **AgentGym-RL Service**: Training infrastructure (external service, port TBD)
- **NATS JetStream**: Event bus for trajectory and reward streaming
- **TensorZero Gateway**: Model serving infrastructure for A/B testing
- **ClickHouse**: Trajectory data warehouse (via TensorZero)

## NATS Subject Design

### 1. Trajectory Collection

**Subject:** `agent.rl.trajectory.v1`

**Purpose:** Stream multi-turn interaction sequences from agent execution

**Publisher:** Agent Zero (main agent and subordinates)

**Subscribers:**
- RL Trainer Subordinate
- ClickHouse ingestion pipeline
- Analytics dashboards

**Payload Structure:**
```json
{
  "trajectory_id": "uuid-v4",
  "session_id": "agent-session-id",
  "agent_id": "agent-zero-main",
  "subordinate_profile": "researcher|developer|rl-trainer|null",
  "start_timestamp": "2025-12-08T12:00:00Z",
  "end_timestamp": "2025-12-08T12:05:30Z",
  "turns": [
    {
      "turn_id": 1,
      "timestamp": "2025-12-08T12:00:00Z",
      "observation": {
        "type": "user_message|tool_result|subordinate_response",
        "content": "string or object",
        "context": {
          "memory_state": {},
          "available_tools": [],
          "subordinates_active": 2
        }
      },
      "thought_process": ["thought 1", "thought 2"],
      "action": {
        "type": "tool_call|subordinate_call|response",
        "tool_name": "code_exe|call_subordinate|memory|etc",
        "tool_args": {},
        "raw_response": "full LLM response"
      },
      "result": {
        "success": true,
        "output": "tool execution result",
        "error": null,
        "execution_time_ms": 1500
      }
    }
  ],
  "task_context": {
    "task_id": "original-task-id",
    "instructions": "user's original request",
    "complexity_score": 0.75,
    "domain": "coding|research|data_analysis|general"
  },
  "metadata": {
    "model": "qwen2.5-32b-instruct",
    "temperature": 0.7,
    "total_tokens": 5000,
    "total_cost_usd": 0.025
  }
}
```

**JetStream Configuration:**
```bash
nats stream add RL_TRAJECTORIES \
  --subjects "agent.rl.trajectory.v1" \
  --retention limits \
  --max-age 30d \
  --max-msgs 1000000 \
  --storage file
```

### 2. Reward Signals

**Subject:** `agent.rl.reward.v1`

**Purpose:** Publish computed reward signals for trajectory evaluation

**Publisher:**
- RL Trainer Subordinate
- User feedback mechanisms
- Automated evaluation services

**Subscribers:**
- AgentGym-RL training service
- Analytics dashboards
- ClickHouse ingestion

**Payload Structure:**
```json
{
  "reward_id": "uuid-v4",
  "trajectory_id": "matching-trajectory-uuid",
  "session_id": "agent-session-id",
  "timestamp": "2025-12-08T12:06:00Z",
  "reward_components": {
    "task_completion": {
      "score": 0.9,
      "weight": 0.4,
      "source": "automated",
      "reasoning": "task completed successfully with all requirements met"
    },
    "efficiency": {
      "score": 0.7,
      "weight": 0.2,
      "source": "automated",
      "reasoning": "completed in 5 turns, avg is 7 turns for this task type"
    },
    "code_quality": {
      "score": 0.85,
      "weight": 0.15,
      "source": "linter",
      "reasoning": "pylint score 8.5/10, no critical issues"
    },
    "user_feedback": {
      "score": 1.0,
      "weight": 0.25,
      "source": "human",
      "reasoning": "user marked as helpful"
    }
  },
  "total_reward": 0.8625,
  "reward_type": "dense|sparse",
  "normalization": {
    "method": "z-score",
    "mean": 0.75,
    "std": 0.15
  },
  "metadata": {
    "evaluator": "rl-trainer-subordinate",
    "evaluation_method": "hybrid",
    "confidence": 0.92
  }
}
```

**JetStream Configuration:**
```bash
nats stream add RL_REWARDS \
  --subjects "agent.rl.reward.v1" \
  --retention limits \
  --max-age 30d \
  --max-msgs 500000 \
  --storage file
```

### 3. Training Requests

**Subject:** `agent.rl.training.request.v1`

**Purpose:** Trigger RL training jobs with specified parameters

**Publisher:** RL Trainer Subordinate

**Subscribers:** AgentGym-RL training service

**Payload Structure:**
```json
{
  "training_job_id": "uuid-v4",
  "timestamp": "2025-12-08T13:00:00Z",
  "requester": "rl-trainer-subordinate",
  "trigger_reason": "scheduled|threshold_reached|manual",
  "training_config": {
    "algorithm": "ppo|dpo|rloo|grpo",
    "base_model": "qwen2.5-32b-instruct",
    "dataset": {
      "source": "nats_stream",
      "stream_name": "RL_TRAJECTORIES",
      "filter": {
        "min_reward": 0.5,
        "max_trajectory_length": 50,
        "date_range": {
          "start": "2025-12-01T00:00:00Z",
          "end": "2025-12-08T12:59:59Z"
        },
        "task_domains": ["coding", "research"],
        "exclude_subordinate_profiles": []
      },
      "sample_size": 10000
    },
    "hyperparameters": {
      "learning_rate": 1e-5,
      "batch_size": 32,
      "epochs": 3,
      "clip_epsilon": 0.2,
      "gamma": 0.99,
      "gae_lambda": 0.95
    },
    "compute": {
      "gpu_count": 2,
      "gpu_type": "a100",
      "distributed": true,
      "mixed_precision": "bf16"
    },
    "checkpointing": {
      "save_interval": 1000,
      "max_checkpoints": 5,
      "storage_path": "s3://pmoves-models/rl-checkpoints/"
    }
  },
  "evaluation": {
    "enabled": true,
    "holdout_size": 0.1,
    "metrics": ["reward", "task_completion", "efficiency"],
    "benchmark_tasks": ["code_generation", "data_analysis", "research_synthesis"]
  },
  "priority": "normal|high|low",
  "metadata": {
    "requested_by": "user-id or system",
    "previous_training_job": "uuid-v4 or null",
    "notes": "optional description"
  }
}
```

### 4. Training Status Updates

**Subject:** `agent.rl.training.status.v1`

**Purpose:** Broadcast training progress and results

**Publisher:** AgentGym-RL training service

**Subscribers:**
- RL Trainer Subordinate
- Monitoring dashboards
- Agent Zero (for model update awareness)

**Payload Structure:**
```json
{
  "training_job_id": "matching-request-uuid",
  "timestamp": "2025-12-08T13:15:00Z",
  "status": "queued|running|completed|failed|cancelled",
  "progress": {
    "current_epoch": 2,
    "total_epochs": 3,
    "current_step": 5000,
    "total_steps": 7500,
    "percent_complete": 66.67,
    "eta_seconds": 1800
  },
  "metrics": {
    "current": {
      "loss": 0.234,
      "reward_mean": 0.82,
      "reward_std": 0.12,
      "policy_entropy": 2.34,
      "kl_divergence": 0.015,
      "learning_rate": 9.5e-6
    },
    "best": {
      "epoch": 1,
      "step": 3000,
      "reward_mean": 0.85,
      "checkpoint_path": "s3://pmoves-models/rl-checkpoints/job-123/best.pt"
    }
  },
  "evaluation_results": {
    "holdout_reward": 0.83,
    "benchmark_scores": {
      "code_generation": 0.88,
      "data_analysis": 0.79,
      "research_synthesis": 0.81
    },
    "improvement_over_baseline": 0.08
  },
  "artifacts": {
    "final_checkpoint": "s3://pmoves-models/rl-checkpoints/job-123/final.pt",
    "tensorboard_logs": "s3://pmoves-models/rl-logs/job-123/",
    "training_curves": "s3://pmoves-models/rl-viz/job-123/curves.png",
    "model_card": "s3://pmoves-models/rl-checkpoints/job-123/README.md"
  },
  "resource_usage": {
    "gpu_hours": 12.5,
    "cost_usd": 45.30,
    "peak_memory_gb": 78.4,
    "total_training_time_seconds": 3600
  },
  "error": {
    "code": "OOM|CONVERGENCE|DATA|INFRA",
    "message": "optional error description",
    "traceback": "full error trace if failed"
  },
  "metadata": {
    "training_platform": "agentgym-rl-v1",
    "cuda_version": "12.1",
    "pytorch_version": "2.3.0"
  }
}
```

### 5. Model Deployment Events

**Subject:** `agent.rl.model.deployed.v1`

**Purpose:** Notify when new RL-trained model is deployed to serving

**Publisher:** RL Trainer Subordinate (after validation)

**Subscribers:** Agent Zero, TensorZero Gateway, monitoring

**Payload Structure:**
```json
{
  "deployment_id": "uuid-v4",
  "training_job_id": "source-training-job-uuid",
  "timestamp": "2025-12-08T14:00:00Z",
  "model_info": {
    "model_id": "agent-zero-rl-v2.3",
    "base_model": "qwen2.5-32b-instruct",
    "checkpoint_path": "s3://pmoves-models/deployed/agent-zero-rl-v2.3/",
    "training_date": "2025-12-08T13:30:00Z",
    "training_samples": 10000,
    "final_reward": 0.85
  },
  "deployment_config": {
    "serving_platform": "tensorzero",
    "endpoint": "http://tensorzero-gateway:3000/v1/chat/completions",
    "model_name": "agent-zero-rl-v2.3",
    "rollout_strategy": "canary|blue_green|immediate",
    "traffic_percentage": 10,
    "ramp_schedule": [
      {"timestamp": "2025-12-08T14:00:00Z", "percentage": 10},
      {"timestamp": "2025-12-08T16:00:00Z", "percentage": 50},
      {"timestamp": "2025-12-08T20:00:00Z", "percentage": 100}
    ]
  },
  "validation_results": {
    "benchmark_passed": true,
    "safety_checks_passed": true,
    "performance_regression": false,
    "human_eval_score": 0.87
  },
  "metadata": {
    "deployed_by": "rl-trainer-subordinate",
    "approval_status": "automated|manual_approved",
    "previous_model": "agent-zero-rl-v2.2"
  }
}
```

## Feedback Loop Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AGENT ZERO EXECUTION LAYER                      │
│                                                                         │
│  ┌───────────┐     ┌──────────────┐     ┌──────────────┐             │
│  │  Agent    │────▶│ Subordinate  │────▶│ Subordinate  │             │
│  │  Zero     │     │  (Research)  │     │  (Coder)     │             │
│  │  (Main)   │     └──────────────┘     └──────────────┘             │
│  └─────┬─────┘                                                        │
│        │                                                              │
│        │ Execution Traces                                            │
└────────┼──────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    TRAJECTORY COLLECTION PIPELINE                       │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  NATS JetStream: agent.rl.trajectory.v1                          │  │
│  │                                                                  │  │
│  │  {session, turns[], actions, results, context, metadata}        │  │
│  └────┬──────────────────────────┬──────────────────────────────────┘  │
│       │                          │                                     │
│       │                          │                                     │
└───────┼──────────────────────────┼─────────────────────────────────────┘
        │                          │
        │                          └─────────────┐
        ▼                                        ▼
┌─────────────────────────────┐      ┌─────────────────────────────┐
│   RL TRAINER SUBORDINATE    │      │   CLICKHOUSE WAREHOUSE      │
│                             │      │                             │
│  ┌────────────────────┐     │      │  - Trajectory storage       │
│  │  Trajectory        │     │      │  - Analytics queries        │
│  │  Collector         │     │      │  - Historical data          │
│  └────────┬───────────┘     │      │  - Model versioning         │
│           │                 │      └─────────────────────────────┘
│           ▼                 │
│  ┌────────────────────┐     │
│  │  Reward            │     │
│  │  Calculator        │     │
│  │                    │     │
│  │  - Task completion │     │
│  │  - Efficiency      │     │
│  │  - Quality metrics │     │
│  │  - User feedback   │     │
│  └────────┬───────────┘     │
│           │                 │
└───────────┼─────────────────┘
            │ agent.rl.reward.v1
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    REWARD AGGREGATION & STORAGE                         │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  NATS JetStream: agent.rl.reward.v1                              │  │
│  │                                                                  │  │
│  │  {trajectory_id, components, total_reward, metadata}            │  │
│  └────┬─────────────────────────────────────────────────────────────┘  │
│       │                                                                │
└───────┼────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               RL TRAINER: TRAINING ORCHESTRATION                        │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │  Training Trigger Logic                                       │     │
│  │  - Threshold: 5000 new trajectories                           │     │
│  │  - Schedule: Daily at 02:00 UTC                               │     │
│  │  - Manual: Via Agent Zero command                             │     │
│  └───────┬───────────────────────────────────────────────────────┘     │
│          │                                                             │
│          │ agent.rl.training.request.v1                               │
│          ▼                                                             │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │  NATS: Training Job Request                                   │     │
│  │  {config, dataset, hyperparams, compute, eval}                │     │
│  └───────┬───────────────────────────────────────────────────────┘     │
└──────────┼─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENTGYM-RL TRAINING SERVICE                         │
│                           (External Service)                            │
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐           │
│  │  Data Loader │────▶│  RL Trainer  │────▶│  Evaluator   │           │
│  │              │     │              │     │              │           │
│  │  - NATS Sub  │     │  - PPO/DPO   │     │  - Benchmarks│           │
│  │  - Filtering │     │  - GPU Train │     │  - Validation│           │
│  │  - Batching  │     │  - Checkpt   │     │  - Safety    │           │
│  └──────────────┘     └──────┬───────┘     └──────────────┘           │
│                               │                                        │
│                               │ agent.rl.training.status.v1           │
│                               │ (periodic updates)                     │
│                               ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │  Checkpoint Storage (S3/MinIO)                               │     │
│  │  - Epoch checkpoints                                         │     │
│  │  - Best model                                                │     │
│  │  - Final model                                               │     │
│  └──────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
           │
           │ Training Complete
           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                 MODEL VALIDATION & DEPLOYMENT                           │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │  RL Trainer Subordinate: Validation                           │     │
│  │  - Performance benchmarks                                     │     │
│  │  - Safety checks                                              │     │
│  │  - Regression detection                                       │     │
│  │  - Human evaluation (optional)                                │     │
│  └───────┬───────────────────────────────────────────────────────┘     │
│          │                                                             │
│          │ agent.rl.model.deployed.v1                                 │
│          ▼                                                             │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │  TensorZero Gateway: Model Update                             │     │
│  │  - Register new model                                         │     │
│  │  - Canary deployment (10% → 50% → 100%)                       │     │
│  │  - A/B testing metrics                                        │     │
│  │  - Automatic rollback on failure                              │     │
│  └───────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
           │
           │ Model Active
           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  AGENT ZERO: UPDATED MODEL IN USE                       │
│                                                                         │
│  - Executes tasks with RL-improved policy                              │
│  - Generates new trajectories                                          │
│  - Continuous feedback loop                                            │
│  - Performance monitoring via Prometheus/Grafana                       │
└─────────────────────────────────────────────────────────────────────────┘
           │
           └──────────────┐
                          │ Loop continues...
                          ▼
                    [Back to top]


OBSERVABILITY CROSS-CUTS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌─────────────────────────────────────────────────────────────────┐
  │  Prometheus Metrics                                             │
  │  - agent_rl_trajectories_total                                  │
  │  - agent_rl_reward_mean                                         │
  │  - agent_rl_training_duration_seconds                           │
  │  - agent_rl_model_performance_score                             │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │  Grafana Dashboards                                             │
  │  - RL Training Overview                                         │
  │  - Model Performance Comparison                                 │
  │  - Trajectory Quality Metrics                                   │
  │  - Reward Distribution                                          │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │  Loki Logs                                                      │
  │  - Trajectory collection events                                 │
  │  - Reward calculation logs                                      │
  │  - Training job execution                                       │
  │  - Model deployment audit trail                                 │
  └─────────────────────────────────────────────────────────────────┘
```

## Reward Computation Strategy

### Automated Reward Components

#### 1. Task Completion (Weight: 0.40)

**Calculation:**
```python
def compute_task_completion_reward(trajectory):
    """
    Binary success indicator with partial credit for progress.
    """
    if trajectory.task_status == "completed_successfully":
        return 1.0
    elif trajectory.task_status == "partial_completion":
        return 0.5 + (trajectory.completion_percentage * 0.5)
    else:
        return 0.0
```

**Signals:**
- Task marked complete by user
- All subtasks successfully executed
- No critical errors in final output
- User did not request retry or correction

#### 2. Efficiency (Weight: 0.20)

**Calculation:**
```python
def compute_efficiency_reward(trajectory, task_type_stats):
    """
    Reward for completing task in fewer turns/time than average.
    """
    turns_taken = len(trajectory.turns)
    avg_turns = task_type_stats[trajectory.task_type].mean_turns
    std_turns = task_type_stats[trajectory.task_type].std_turns

    # Z-score normalization, capped at [-2, 2]
    z_score = (avg_turns - turns_taken) / std_turns
    z_score = max(-2.0, min(2.0, z_score))

    # Map to [0, 1] range
    return (z_score + 2.0) / 4.0
```

**Signals:**
- Number of turns/interactions
- Total execution time
- Token usage (cost efficiency)
- Tool call efficiency (minimize redundant calls)

#### 3. Code Quality (Weight: 0.15)

**Calculation (for coding tasks):**
```python
def compute_code_quality_reward(trajectory):
    """
    Automated code quality assessment via linters and tests.
    """
    if not trajectory.contains_code:
        return None  # Not applicable

    scores = []

    # Linter score
    if trajectory.linter_results:
        pylint_score = trajectory.linter_results.score / 10.0
        scores.append(pylint_score)

    # Test pass rate
    if trajectory.test_results:
        pass_rate = trajectory.test_results.passed / trajectory.test_results.total
        scores.append(pass_rate)

    # Security scan
    if trajectory.security_scan:
        security_score = 1.0 - (trajectory.security_scan.critical_issues * 0.5)
        security_score = max(0.0, security_score)
        scores.append(security_score)

    return sum(scores) / len(scores) if scores else 0.5
```

**Signals:**
- Pylint/flake8/mypy scores
- Test pass rates
- Security vulnerability scans
- Code complexity metrics

#### 4. User Feedback (Weight: 0.25)

**Collection Methods:**
- Explicit thumbs up/down in Agent Zero UI
- Task rating (1-5 stars)
- Follow-up correction requests (negative signal)
- No response = neutral (0.5 reward)

**Calculation:**
```python
def compute_user_feedback_reward(trajectory):
    """
    Direct user satisfaction signal.
    """
    if trajectory.user_feedback:
        if trajectory.user_feedback.type == "thumbs_up":
            return 1.0
        elif trajectory.user_feedback.type == "thumbs_down":
            return 0.0
        elif trajectory.user_feedback.type == "rating":
            return trajectory.user_feedback.rating / 5.0

    # Implicit signals
    if trajectory.correction_requested:
        return 0.2  # Task needed rework
    elif trajectory.task_abandoned:
        return 0.0  # User gave up
    else:
        return 0.5  # Neutral (no explicit feedback)
```

### Reward Normalization

All component rewards are z-score normalized across recent trajectories (trailing 1000) before weighting:

```python
def normalize_reward_component(score, component_name, reward_history):
    """
    Z-score normalization to handle distribution shifts.
    """
    recent_scores = reward_history[component_name][-1000:]
    mean = np.mean(recent_scores)
    std = np.std(recent_scores) + 1e-8  # Avoid division by zero

    z_score = (score - mean) / std
    return z_score
```

### Total Reward Calculation

```python
def compute_total_reward(trajectory, reward_history, weights):
    """
    Weighted sum of normalized component rewards.
    """
    components = {
        "task_completion": compute_task_completion_reward(trajectory),
        "efficiency": compute_efficiency_reward(trajectory, task_stats),
        "code_quality": compute_code_quality_reward(trajectory),
        "user_feedback": compute_user_feedback_reward(trajectory)
    }

    # Normalize each component
    normalized = {}
    for name, score in components.items():
        if score is not None:
            normalized[name] = normalize_reward_component(score, name, reward_history)
        else:
            normalized[name] = 0.0

    # Weighted sum
    total = sum(normalized[name] * weights[name] for name in weights)

    return {
        "components": components,
        "normalized": normalized,
        "total_reward": total,
        "weights": weights
    }
```

## Model Update Propagation

### 1. Training Completion

When AgentGym-RL completes training:
1. Publish `agent.rl.training.status.v1` with status="completed"
2. Include checkpoint paths and metrics
3. RL Trainer Subordinate receives event

### 2. Validation Phase

RL Trainer Subordinate validates new model:
```python
async def validate_model(checkpoint_path):
    """
    Multi-stage validation before deployment.
    """
    validation_results = {
        "benchmark_passed": False,
        "safety_passed": False,
        "performance_regression": False
    }

    # 1. Run benchmark suite
    benchmark_scores = await run_benchmarks(checkpoint_path, tasks=[
        "code_generation",
        "data_analysis",
        "research_synthesis",
        "tool_usage"
    ])
    validation_results["benchmark_passed"] = (
        benchmark_scores.mean() >= BENCHMARK_THRESHOLD
    )

    # 2. Safety checks
    safety_results = await run_safety_checks(checkpoint_path, checks=[
        "refusal_behavior",
        "toxicity_test",
        "jailbreak_resistance"
    ])
    validation_results["safety_passed"] = safety_results.all_passed

    # 3. Regression detection
    current_model_performance = get_current_model_metrics()
    performance_delta = benchmark_scores.mean() - current_model_performance
    validation_results["performance_regression"] = (performance_delta < -0.05)

    return validation_results
```

### 3. Deployment to TensorZero

If validation passes:
```python
async def deploy_model_to_tensorzero(checkpoint_path, validation_results):
    """
    Register model in TensorZero with canary deployment.
    """
    # 1. Upload to model storage
    model_id = f"agent-zero-rl-v{get_next_version()}"
    deployed_path = await upload_to_storage(checkpoint_path, model_id)

    # 2. Register in TensorZero
    await tensorzero_client.register_model(
        model_id=model_id,
        model_path=deployed_path,
        base_model="qwen2.5-32b-instruct",
        metadata={
            "training_job": training_job_id,
            "validation_results": validation_results,
            "deployment_timestamp": datetime.utcnow().isoformat()
        }
    )

    # 3. Canary deployment (gradual rollout)
    await tensorzero_client.update_traffic_split(
        model_id=model_id,
        traffic_percentage=10,  # Start with 10%
        ramp_schedule=[
            {"delay_minutes": 60, "percentage": 25},
            {"delay_minutes": 120, "percentage": 50},
            {"delay_minutes": 240, "percentage": 100}
        ]
    )

    # 4. Publish deployment event
    await nats_client.publish(
        "agent.rl.model.deployed.v1",
        deployment_payload
    )
```

### 4. Agent Zero Model Reload

Agent Zero listens for deployment events:
```python
async def handle_model_deployment(msg):
    """
    React to new model deployment.
    """
    deployment = json.loads(msg.data)

    # Update model configuration
    if deployment["deployment_config"]["rollout_strategy"] == "canary":
        # TensorZero handles traffic routing
        logger.info(f"New model {deployment['model_info']['model_id']} "
                   f"deployed with canary rollout")
    else:
        # Immediate switch
        await update_agent_model(deployment["model_info"]["model_id"])

    # Update metrics tracking
    metrics.update_model_version(deployment["model_info"]["model_id"])
```

### 5. A/B Testing & Rollback

TensorZero automatically tracks performance:
```python
async def monitor_deployment(deployment_id):
    """
    Monitor new model performance and auto-rollback on degradation.
    """
    while deployment_active(deployment_id):
        await asyncio.sleep(300)  # Check every 5 minutes

        metrics = await tensorzero_client.get_model_metrics(
            deployment_id=deployment_id,
            time_window_minutes=30
        )

        # Check for performance degradation
        if metrics.error_rate > ERROR_THRESHOLD:
            logger.warning(f"High error rate detected: {metrics.error_rate}")
            await rollback_deployment(deployment_id)

        if metrics.avg_reward < REWARD_THRESHOLD:
            logger.warning(f"Low reward detected: {metrics.avg_reward}")
            await rollback_deployment(deployment_id)
```

## Integration Requirements

### Agent Zero Modifications

1. **Trajectory Collection Hook**
   - Location: `python/agent.py` in message loop
   - Collect turn data: observation, thought, action, result
   - Publish to `agent.rl.trajectory.v1` at task completion

2. **User Feedback Capture**
   - Add thumbs up/down buttons to WebUI
   - Capture implicit signals (corrections, abandonment)
   - Link feedback to trajectory_id

3. **Model Version Tracking**
   - Store current model version in agent context
   - Include in trajectory metadata
   - Enable version-specific performance analysis

### AgentGym-RL Service Requirements

1. **NATS Integration**
   - Subscribe to training requests
   - Publish status updates
   - Stream trajectory data for training

2. **Dataset Management**
   - Load trajectories from NATS/ClickHouse
   - Apply filtering and sampling
   - Batch preparation for training

3. **Checkpoint Management**
   - Save to S3/MinIO
   - Version tracking
   - Automatic cleanup of old checkpoints

4. **API Endpoints**
   - `POST /training/start` - Manual training trigger
   - `GET /training/{job_id}/status` - Job status
   - `POST /training/{job_id}/cancel` - Cancel job
   - `GET /models` - List available models

### Infrastructure Requirements

1. **NATS JetStream Streams**
   - RL_TRAJECTORIES (30 day retention, 1M msgs)
   - RL_REWARDS (30 day retention, 500K msgs)
   - RL_TRAINING (7 day retention, 10K msgs)

2. **Storage**
   - S3/MinIO bucket: `pmoves-models`
   - Subdirectories: `rl-checkpoints/`, `rl-logs/`, `rl-viz/`
   - Retention policy: 90 days for checkpoints

3. **Compute**
   - GPU cluster for training (2x A100 recommended)
   - CPU instances for data processing
   - Auto-scaling based on training queue

4. **Monitoring**
   - Prometheus metrics from all components
   - Grafana dashboard for RL pipeline
   - Alerts for training failures, model degradation

## Performance Metrics

### Training Metrics (Published to Prometheus)

```python
# Training job metrics
agent_rl_training_jobs_total = Counter(
    "agent_rl_training_jobs_total",
    "Total RL training jobs",
    ["status"]
)

agent_rl_training_duration_seconds = Histogram(
    "agent_rl_training_duration_seconds",
    "Training job duration",
    buckets=[300, 600, 1800, 3600, 7200, 14400]
)

agent_rl_training_samples = Histogram(
    "agent_rl_training_samples",
    "Number of samples used in training",
    buckets=[1000, 5000, 10000, 50000, 100000]
)

# Model performance metrics
agent_rl_model_reward_mean = Gauge(
    "agent_rl_model_reward_mean",
    "Mean reward of deployed model",
    ["model_version"]
)

agent_rl_model_benchmark_score = Gauge(
    "agent_rl_model_benchmark_score",
    "Benchmark score by task type",
    ["model_version", "task_type"]
)
```

### Trajectory Metrics

```python
agent_rl_trajectories_collected_total = Counter(
    "agent_rl_trajectories_collected_total",
    "Total trajectories collected",
    ["agent_type", "task_domain"]
)

agent_rl_trajectory_length = Histogram(
    "agent_rl_trajectory_length",
    "Number of turns in trajectory",
    buckets=[1, 3, 5, 10, 20, 50]
)

agent_rl_trajectory_reward = Histogram(
    "agent_rl_trajectory_reward",
    "Trajectory total reward",
    buckets=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
)
```

### Deployment Metrics

```python
agent_rl_model_deployments_total = Counter(
    "agent_rl_model_deployments_total",
    "Total model deployments",
    ["status"]
)

agent_rl_model_traffic_percentage = Gauge(
    "agent_rl_model_traffic_percentage",
    "Traffic percentage for deployed model",
    ["model_version"]
)

agent_rl_model_error_rate = Gauge(
    "agent_rl_model_error_rate",
    "Error rate by model version",
    ["model_version"]
)
```

## Security & Privacy Considerations

### Data Privacy

1. **PII Filtering**
   - Automatically detect and redact PII from trajectories
   - API keys, passwords, emails scrubbed before storage
   - User opt-out mechanism for trajectory collection

2. **Access Controls**
   - NATS subject permissions by service account
   - S3 bucket policies for checkpoint storage
   - Audit logging for data access

3. **Data Retention**
   - Trajectories: 30 days in hot storage, 90 days archived
   - Rewards: 30 days
   - Models: 90 days, best models indefinitely

### Model Safety

1. **Safety Validation**
   - Red-teaming before deployment
   - Toxicity/bias evaluation
   - Refusal behavior verification

2. **Rollback Mechanism**
   - Automatic rollback on safety violations
   - Human-in-the-loop for critical decisions
   - Manual override capability

3. **Audit Trail**
   - All model deployments logged
   - Training data provenance tracked
   - Decision explanations stored

## Future Enhancements

### Phase 2 Features

1. **Multi-Agent RL**
   - Train multiple subordinates collaboratively
   - Coordination rewards
   - Hierarchical RL policies

2. **Online RL**
   - Continuous learning during execution
   - Real-time model updates
   - Adaptive reward functions

3. **Human-in-the-Loop RL**
   - Interactive reward shaping
   - Preference learning from comparisons
   - Active learning for edge cases

4. **Meta-Learning**
   - Few-shot adaptation to new task types
   - Transfer learning across domains
   - Curriculum learning

### Phase 3 Features

1. **Distributed Training**
   - Multi-node training
   - Asynchronous PPO
   - Federation across PMOVES instances

2. **Advanced Reward Models**
   - Learned reward models (IRL)
   - Multi-objective optimization
   - Intrinsic motivation (curiosity)

3. **Explainability**
   - Policy visualization
   - Counterfactual analysis
   - Reward attribution

## References

- [AgentGym Paper](https://arxiv.org/abs/2406.04151)
- [PPO Algorithm](https://arxiv.org/abs/1707.06347)
- [DPO Algorithm](https://arxiv.org/abs/2305.18290)
- [Agent Zero Architecture](../PMOVES-Agent-Zero/docs/architecture.md)
- [NATS JetStream Docs](https://docs.nats.io/nats-concepts/jetstream)
- [TensorZero Docs](https://tensorzero.com/docs)

## Appendix: Example NATS Commands

### Subscribe to Trajectories
```bash
nats sub "agent.rl.trajectory.v1" --queue rl-workers
```

### Publish Test Reward
```bash
nats pub "agent.rl.reward.v1" '{
  "reward_id": "test-123",
  "trajectory_id": "traj-456",
  "session_id": "sess-789",
  "timestamp": "2025-12-08T12:00:00Z",
  "reward_components": {
    "task_completion": {"score": 1.0, "weight": 0.4, "source": "automated"},
    "efficiency": {"score": 0.8, "weight": 0.2, "source": "automated"},
    "user_feedback": {"score": 1.0, "weight": 0.4, "source": "human"}
  },
  "total_reward": 0.92
}'
```

### Trigger Training Job
```bash
nats pub "agent.rl.training.request.v1" '{
  "training_job_id": "job-001",
  "timestamp": "2025-12-08T13:00:00Z",
  "requester": "manual-trigger",
  "trigger_reason": "manual",
  "training_config": {
    "algorithm": "ppo",
    "base_model": "qwen2.5-32b-instruct",
    "dataset": {
      "source": "nats_stream",
      "stream_name": "RL_TRAJECTORIES",
      "sample_size": 5000
    },
    "hyperparameters": {
      "learning_rate": 1e-5,
      "batch_size": 32,
      "epochs": 3
    }
  }
}'
```

### Monitor Training Status
```bash
nats sub "agent.rl.training.status.v1"
```
