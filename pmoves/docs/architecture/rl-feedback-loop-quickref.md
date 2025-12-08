# AgentGym-RL Feedback Loop - Quick Reference

## NATS Subjects

### Trajectory Collection
```bash
# Subject: agent.rl.trajectory.v1
# Publisher: Agent Zero (main + subordinates)
# Subscriber: RL Trainer Subordinate, ClickHouse

nats sub "agent.rl.trajectory.v1" --queue rl-workers
```

### Reward Signals
```bash
# Subject: agent.rl.reward.v1
# Publisher: RL Trainer Subordinate
# Subscriber: AgentGym-RL, Analytics

nats sub "agent.rl.reward.v1"
```

### Training Control
```bash
# Subject: agent.rl.training.request.v1
# Publisher: RL Trainer Subordinate
# Subscriber: AgentGym-RL Service

nats pub "agent.rl.training.request.v1" '{
  "training_job_id": "uuid",
  "timestamp": "2025-12-08T13:00:00Z",
  "requester": "rl-trainer-subordinate",
  "trigger_reason": "threshold_reached",
  "training_config": { ... }
}'
```

### Training Status
```bash
# Subject: agent.rl.training.status.v1
# Publisher: AgentGym-RL Service
# Subscriber: RL Trainer Subordinate

nats sub "agent.rl.training.status.v1"
```

### Model Deployment
```bash
# Subject: agent.rl.model.deployed.v1
# Publisher: RL Trainer Subordinate
# Subscriber: Agent Zero, TensorZero, Monitoring

nats sub "agent.rl.model.deployed.v1"
```

## Reward Computation

### Component Weights
- **Task Completion:** 40% (binary + partial credit)
- **Efficiency:** 20% (turns/time vs baseline)
- **Code Quality:** 15% (linters, tests, security)
- **User Feedback:** 25% (explicit + implicit signals)

### Total Reward Formula
```python
total_reward = (
    normalize(task_completion) * 0.40 +
    normalize(efficiency) * 0.20 +
    normalize(code_quality) * 0.15 +
    normalize(user_feedback) * 0.25
)
```

### Normalization
```python
# Z-score across trailing 1000 trajectories
z_score = (score - mean) / std
normalized = (z_score + 2.0) / 4.0  # Map to [0, 1]
```

## Training Triggers

### Threshold-Based
```python
if trajectory_count >= 5000:
    trigger_training(reason="threshold_reached")
```

### Scheduled
```bash
# Daily at 02:00 UTC
CRON: "0 2 * * *"
```

### Manual
```python
# Via Agent Zero command
agent.call_subordinate(
    profile="rl-trainer",
    message="Trigger training job with 10K samples from last 30 days"
)
```

### Performance Degradation
```python
if current_model_reward < baseline - 0.10:
    trigger_training(reason="performance_degradation", priority="urgent")
```

## Deployment Workflow

### Canary Rollout Schedule
```
T+0h:   10% traffic to new model
T+1h:   25% traffic
T+2h:   50% traffic
T+4h:   100% traffic (full deployment)
```

### Rollback Conditions
```python
# Automatic rollback if:
error_rate > 0.05 (5%)
avg_reward < baseline - 0.05
user_negative_feedback > 2x baseline
```

### Rollback Execution
```bash
# Immediate switch to previous model
curl -X PUT http://tensorzero-gateway:3000/admin/traffic \
  -d '{"model_id": "agent-zero-rl-v2.3", "traffic_percentage": 100}'
```

## Key Commands

### Check Training Job Status
```bash
# Via NATS
nats req "agent.rl.training.status.request" '{"job_id": "uuid"}'

# Via HTTP
curl http://agentgym-rl:8100/training/{job_id}/status
```

### Query Model Performance
```bash
# TensorZero metrics
curl http://tensorzero-gateway:3000/admin/models/agent-zero-rl-v2.3/metrics

# Prometheus query
curl 'http://prometheus:9090/api/v1/query?query=agent_rl_model_reward_mean'
```

### List Available Models
```bash
curl http://agentgym-rl:8100/models
```

### Manual Training Trigger
```bash
nats pub "agent.rl.training.request.v1" "$(cat <<EOF
{
  "training_job_id": "manual-$(uuidgen)",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "requester": "admin-manual",
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
}
EOF
)"
```

## JetStream Stream Creation

```bash
# Trajectories (30-day retention, 1M msgs)
nats stream add RL_TRAJECTORIES \
  --subjects "agent.rl.trajectory.v1" \
  --retention limits \
  --max-age 30d \
  --max-msgs 1000000 \
  --storage file

# Rewards (30-day retention, 500K msgs)
nats stream add RL_REWARDS \
  --subjects "agent.rl.reward.v1" \
  --retention limits \
  --max-age 30d \
  --max-msgs 500000 \
  --storage file

# Training (7-day retention, 10K msgs)
nats stream add RL_TRAINING \
  --subjects "agent.rl.training.>" \
  --retention limits \
  --max-age 7d \
  --max-msgs 10000 \
  --storage file
```

## Prometheus Queries

```promql
# Trajectory collection rate (per minute)
rate(agent_rl_trajectories_collected_total[5m]) * 60

# Average trajectory reward
avg_over_time(agent_rl_trajectory_reward[1h])

# Training job success rate
sum(rate(agent_rl_training_jobs_total{status="completed"}[24h])) /
sum(rate(agent_rl_training_jobs_total[24h]))

# Model performance comparison
agent_rl_model_reward_mean{model_version=~".*"}

# Error rate by model version
rate(agent_rl_model_errors_total[5m])
```

## Grafana Dashboard Queries

### RL Training Overview Panel
```json
{
  "title": "Trajectories Collected (24h)",
  "targets": [{
    "expr": "sum(increase(agent_rl_trajectories_collected_total[24h]))"
  }]
}
```

### Model Performance Panel
```json
{
  "title": "Model Reward Over Time",
  "targets": [{
    "expr": "agent_rl_model_reward_mean",
    "legendFormat": "{{model_version}}"
  }]
}
```

## Environment Variables

```bash
# NATS
NATS_URL=nats://nats:4222
AGENTZERO_JETSTREAM=true

# AgentGym-RL
AGENTGYM_RL_URL=http://agentgym-rl:8100
AGENTGYM_RL_API_KEY=${SECRET}

# TensorZero
TENSORZERO_BASE_URL=http://tensorzero-gateway:3000
TENSORZERO_ADMIN_TOKEN=${SECRET}

# Training
RL_ALGORITHM=ppo
RL_BASE_MODEL=qwen2.5-32b-instruct
RL_TRAINING_THRESHOLD=5000

# Rewards
REWARD_WEIGHT_TASK_COMPLETION=0.40
REWARD_WEIGHT_EFFICIENCY=0.20
REWARD_WEIGHT_CODE_QUALITY=0.15
REWARD_WEIGHT_USER_FEEDBACK=0.25

# Deployment
CANARY_INITIAL_TRAFFIC=0.10
CANARY_RAMP_HOURS=4
```

## Troubleshooting

### Training Job Stuck in Queue
```bash
# Check AgentGym-RL service health
curl http://agentgym-rl:8100/health

# Check GPU availability
nvidia-smi

# Review training logs
docker logs agentgym-rl-service
```

### Trajectories Not Collecting
```bash
# Verify NATS stream exists
nats stream info RL_TRAJECTORIES

# Check Agent Zero NATS connectivity
docker logs agent-zero | grep -i nats

# Monitor trajectory subject
nats sub "agent.rl.trajectory.v1" --count 10
```

### Model Deployment Failed
```bash
# Check TensorZero Gateway status
curl http://tensorzero-gateway:3000/health

# Review deployment logs
nats sub "agent.rl.model.deployed.v1"

# Check model storage
aws s3 ls s3://pmoves-models/rl-checkpoints/
```

### High Rollback Rate
```bash
# Query rollback reasons
nats sub "agent.rl.model.deployed.v1" | grep -i rollback

# Check model validation logs
grep "validation" /var/log/rl-trainer.log

# Review error metrics
curl 'http://prometheus:9090/api/v1/query?query=agent_rl_model_error_rate'
```

## File Locations

```
/home/pmoves/PMOVES.AI/
├── docs/
│   ├── rl-feedback-loop-design.md          # Full design spec
│   ├── rl-feedback-loop-summary.md         # Implementation summary
│   ├── rl-feedback-loop-quickref.md        # This file
│   └── subordinate-profile-rl-trainer.md   # Agent role spec
├── pmoves/contracts/
│   ├── topics.json                         # NATS subject registry
│   └── schemas/agent-rl/
│       ├── trajectory.v1.schema.json
│       ├── reward.v1.schema.json
│       ├── training.request.v1.schema.json
│       ├── training.status.v1.schema.json
│       └── model.deployed.v1.schema.json
└── PMOVES-Agent-Zero/agents/rl-trainer/    # Deploy profile here
    └── prompts/agent.system.main.role.md
```

## Common Operations

### Daily Health Check
```bash
# Check trajectory collection
nats stream info RL_TRAJECTORIES | grep Messages

# Check training job history
curl http://agentgym-rl:8100/jobs?status=completed&limit=10

# Check current model performance
curl http://tensorzero-gateway:3000/admin/models/current/metrics

# Review alerts
curl http://prometheus:9090/api/v1/alerts
```

### Weekly Training Report
```bash
# Trajectories collected
nats stream info RL_TRAJECTORIES

# Training jobs completed
curl http://agentgym-rl:8100/jobs?status=completed&since=7d

# Model deployments
curl http://agentgym-rl:8100/models?deployed_since=7d

# Performance trend
curl 'http://prometheus:9090/api/v1/query_range?query=agent_rl_model_reward_mean&start=-7d&step=1h'
```

## Support

- **Design Questions:** See `/home/pmoves/PMOVES.AI/docs/rl-feedback-loop-design.md`
- **Implementation Help:** See `/home/pmoves/PMOVES.AI/docs/subordinate-profile-rl-trainer.md`
- **Schema Validation:** Check `/home/pmoves/PMOVES.AI/pmoves/contracts/schemas/agent-rl/`
- **NATS Integration:** Consult `.claude/context/nats-subjects.md`
- **Architecture Context:** Review `.claude/CLAUDE.md`
