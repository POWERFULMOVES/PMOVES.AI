# AgentGym-RL Feedback Loop Integration - Summary

**Date:** 2025-12-08
**Status:** Design Complete - Ready for Implementation
**Version:** 1.0

## Overview

This document provides a comprehensive design for integrating Agent Zero with AgentGym-RL through an event-driven reinforcement learning feedback loop. The system enables continuous learning from agent interactions, automated reward signal collection, and iterative model improvement.

## Deliverables

### 1. Architecture Documentation

**Main Design Document:** `/home/pmoves/PMOVES.AI/docs/rl-feedback-loop-design.md`

Comprehensive 500+ line specification covering:
- Architecture overview and component interactions
- NATS subject design (5 new subjects)
- Data flow diagrams (ASCII art)
- Reward computation strategies
- Model update propagation workflows
- Integration requirements for Agent Zero and AgentGym-RL
- Performance metrics and monitoring
- Security and privacy considerations
- Future enhancement roadmap

### 2. NATS Subject Definitions

**Updated Topics Registry:** `/home/pmoves/PMOVES.AI/pmoves/contracts/topics.json`

Added 5 new RL-specific subjects:
- `agent.rl.trajectory.v1` - Multi-turn interaction sequences
- `agent.rl.reward.v1` - Computed reward signals
- `agent.rl.training.request.v1` - Training job requests
- `agent.rl.training.status.v1` - Training progress updates
- `agent.rl.model.deployed.v1` - Model deployment notifications

### 3. JSON Schemas

**Location:** `/home/pmoves/PMOVES.AI/pmoves/contracts/schemas/agent-rl/`

Created 5 production-ready JSON schemas:

1. **trajectory.v1.schema.json** (150 lines)
   - Multi-turn agent interaction structure
   - Observation, action, result tuples
   - Task context and metadata
   - Supports all subordinate agent types

2. **reward.v1.schema.json** (110 lines)
   - Multi-component reward structure
   - Task completion, efficiency, code quality, user feedback
   - Normalization parameters (z-score, min-max)
   - Confidence and evaluation metadata

3. **training.request.v1.schema.json** (130 lines)
   - Training job configuration
   - Dataset filtering parameters
   - Hyperparameters for PPO/DPO/RLOO algorithms
   - Compute resource requirements
   - Evaluation and checkpointing config

4. **training.status.v1.schema.json** (100 lines)
   - Job status (queued, running, completed, failed)
   - Progress tracking (epochs, steps, ETA)
   - Training metrics (loss, reward, KL divergence)
   - Evaluation results and artifacts
   - Error details for failures

5. **model.deployed.v1.schema.json** (90 lines)
   - Model deployment metadata
   - Serving platform configuration
   - Canary rollout schedule
   - Validation results
   - Traffic routing parameters

All schemas include:
- Full JSON Schema 2020-12 compliance
- Required field validation
- Type constraints and enums
- Detailed descriptions
- Example values

### 4. Subordinate Agent Profile

**Profile Document:** `/home/pmoves/PMOVES.AI/docs/subordinate-profile-rl-trainer.md`

Comprehensive 400+ line agent role specification for `rl-trainer` subordinate covering:

#### Core Responsibilities
- Trajectory collection and validation
- Multi-component reward computation
- Training job orchestration
- Model validation and deployment
- Canary rollout management
- Automatic rollback on degradation

#### NATS Integration
- Subscribes to: trajectory, training status, model deployment events
- Publishes to: rewards, training requests, deployment notifications
- Queue groups and consumer configurations

#### Operational Procedures
- 6-phase RL lifecycle management
- Reward computation algorithms with code examples
- Training trigger logic (threshold, scheduled, manual)
- Multi-stage validation pipeline
- Canary deployment strategy
- Emergency rollback procedures

#### Tool Specifications
- NATS interaction APIs
- Data processing utilities
- Model management tools
- TensorZero Gateway integration
- AgentGym-RL service endpoints

#### Decision-Making Framework
- Training job prioritization logic
- Deployment strategy selection
- Automatic rollback conditions
- Error handling and recovery

#### Performance Targets
- Latency requirements for each phase
- Throughput expectations
- Resource utilization limits

#### Reporting & Alerts
- Daily training summaries
- Job completion reports
- Alert escalation rules

## Key Design Decisions

### 1. Event-Driven Architecture
- **Why:** Decouples Agent Zero from training infrastructure, enables async processing, supports distributed scaling
- **Trade-off:** Adds NATS dependency, requires message schema management
- **Mitigation:** JetStream persistence ensures no data loss, schema validation prevents corruption

### 2. Multi-Component Reward Function
- **Components:** Task completion (40%), Efficiency (20%), Code quality (15%), User feedback (25%)
- **Why:** Balances automated metrics with human preferences, prevents reward hacking
- **Trade-off:** Complex to tune, requires baseline tracking
- **Mitigation:** Configurable weights, normalization, historical comparison

### 3. Canary Deployment Strategy
- **Rollout:** 10% → 25% → 50% → 100% over 4 hours
- **Why:** Minimizes risk of deploying degraded models, enables quick rollback
- **Trade-off:** Slower deployment than blue-green
- **Mitigation:** Automatic rollback on error/performance thresholds, monitoring

### 4. Subordinate Agent Coordinator
- **Why:** Centralizes RL logic, isolates main agent from training complexity, enables reuse
- **Trade-off:** Additional agent overhead, coordination latency
- **Mitigation:** Async processing, efficient NATS subscriptions, stateless design

### 5. TensorZero Gateway Integration
- **Why:** Leverages existing model serving, A/B testing, observability infrastructure
- **Trade-off:** Adds dependency on TensorZero
- **Mitigation:** Fallback to direct Ollama serving, TensorZero is already production critical

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Implement trajectory collection hooks in Agent Zero
- [ ] Create NATS stream configurations
- [ ] Deploy JSON schemas to validation pipeline
- [ ] Set up ClickHouse trajectory storage

### Phase 2: RL Trainer Subordinate (Week 3-4)
- [ ] Implement subordinate agent with role from profile doc
- [ ] Build reward computation pipeline
- [ ] Create training job request generator
- [ ] Add NATS pub/sub integration

### Phase 3: AgentGym-RL Service (Week 5-6)
- [ ] Build NATS subscriber for training requests
- [ ] Implement dataset loader from NATS/ClickHouse
- [ ] Integrate PPO/DPO training algorithms
- [ ] Create checkpoint management system
- [ ] Build status update publisher

### Phase 4: Model Deployment (Week 7-8)
- [ ] Implement validation pipeline
- [ ] Build TensorZero Gateway integration
- [ ] Create canary rollout controller
- [ ] Add automatic rollback logic
- [ ] Deploy Prometheus metrics

### Phase 5: Monitoring & Testing (Week 9-10)
- [ ] Create Grafana dashboards for RL pipeline
- [ ] Set up Loki log aggregation
- [ ] Build integration tests
- [ ] Conduct end-to-end testing
- [ ] Performance benchmarking

### Phase 6: Production Rollout (Week 11-12)
- [ ] Deploy to staging environment
- [ ] Run shadow training jobs
- [ ] Collect baseline metrics
- [ ] Gradual production rollout
- [ ] Documentation and training

## Integration Points

### Agent Zero Modifications Required
1. **Trajectory Collection Hook**
   - Location: `python/agent.py` in message loop
   - Action: Publish to `agent.rl.trajectory.v1` after task completion
   - Data: Serialize turn-by-turn interaction history

2. **User Feedback Capture**
   - Location: WebUI components
   - Action: Add thumbs up/down buttons, star ratings
   - Backend: Store feedback linked to trajectory_id

3. **Model Version Tracking**
   - Location: Agent initialization
   - Action: Read current model from TensorZero, include in trajectory metadata
   - Purpose: Enable version-specific performance analysis

### AgentGym-RL Service Requirements
1. **NATS Client Integration**
   - Subscribe to training requests
   - Publish status updates
   - Handle connection resilience

2. **Dataset Loader**
   - Query NATS JetStream or ClickHouse
   - Apply filtering logic from request
   - Batch preparation for training

3. **Training Pipeline**
   - Support PPO, DPO, RLOO algorithms
   - GPU multi-node training
   - Checkpoint management
   - Evaluation on holdout set

4. **API Endpoints**
   - Health checks
   - Manual training triggers
   - Job status queries
   - Model listing

### Infrastructure Dependencies
1. **NATS JetStream**
   - 3 new streams (trajectories, rewards, training)
   - 30-day retention for trajectories/rewards
   - 7-day retention for training events

2. **ClickHouse**
   - Trajectory warehouse (via TensorZero existing setup)
   - Analytics queries
   - Historical baseline tracking

3. **S3/MinIO**
   - Model checkpoint storage (90-day retention)
   - Training logs and artifacts
   - Validation results

4. **TensorZero Gateway**
   - Model registration API
   - Traffic routing configuration
   - Metrics export

## Performance Expectations

### Latency Targets
- Trajectory collection: < 100ms
- Reward computation: < 500ms per trajectory
- Training job queue: < 5 minutes
- Model validation: < 30 minutes
- Deployment: < 5 minutes
- Rollback: < 60 seconds

### Throughput Targets
- Trajectories: 1000/day sustained
- Training jobs: 1/day (threshold-triggered)
- Model deployments: 1-2/week

### Resource Requirements
- NATS storage: ~100GB/month for trajectories
- ClickHouse: ~200GB/month with compression
- Training GPU: 2x A100 x 4 hours = 8 GPU-hours/job
- Training cost: ~$50/job at cloud rates

## Monitoring Strategy

### Prometheus Metrics
- `agent_rl_trajectories_collected_total` (counter)
- `agent_rl_trajectory_reward` (histogram)
- `agent_rl_training_jobs_total` (counter)
- `agent_rl_training_duration_seconds` (histogram)
- `agent_rl_model_reward_mean` (gauge)
- `agent_rl_model_error_rate` (gauge)

### Grafana Dashboards
1. **RL Training Overview**
   - Trajectory collection rates
   - Reward distribution
   - Training job status
   - Resource utilization

2. **Model Performance**
   - Reward trends over time
   - A/B test results
   - Error rates by model version
   - User feedback metrics

3. **Deployment Health**
   - Canary rollout progress
   - Traffic distribution
   - Rollback history
   - Validation pass rates

### Alerts
- Training job failures (3 consecutive)
- Model validation failures
- Deployment rollbacks
- Trajectory collection errors > 10%
- NATS connectivity loss > 5 minutes

## Security & Privacy

### Data Protection
- Automatic PII redaction from trajectories
- API keys, passwords, emails scrubbed
- User opt-out mechanism for data collection
- NATS subject ACLs by service account

### Model Safety
- Red-teaming before deployment
- Toxicity/bias evaluation
- Refusal behavior verification
- Human-in-the-loop for critical decisions

### Audit Trail
- All model deployments logged
- Training data provenance tracked
- Rollback decisions recorded
- Loki log retention: 30 days

## Success Metrics

### Technical Metrics
- Model performance improvement: +5-10% per training cycle
- Training success rate: > 90%
- Deployment success rate: > 95%
- Mean time to rollback: < 60 seconds
- False rollback rate: < 5%

### Business Metrics
- Task completion rate improvement: +10-15%
- User satisfaction increase: +20%
- Agent efficiency gain: -15% fewer turns
- Code quality improvement: +10% linter scores
- Support ticket reduction: -25%

## Next Steps

1. **Review Design** - Stakeholder review and approval of architecture
2. **Resource Allocation** - Assign engineering team and GPU resources
3. **Phase 1 Kickoff** - Begin trajectory collection implementation
4. **AgentGym-RL Service** - Select/build training service infrastructure
5. **Pilot Testing** - Run with synthetic data before production
6. **Production Rollout** - Gradual deployment following roadmap

## References

All detailed documentation and schemas are located in:
- `/home/pmoves/PMOVES.AI/docs/rl-feedback-loop-design.md` - Full design spec
- `/home/pmoves/PMOVES.AI/docs/subordinate-profile-rl-trainer.md` - Agent profile
- `/home/pmoves/PMOVES.AI/pmoves/contracts/schemas/agent-rl/` - JSON schemas
- `/home/pmoves/PMOVES.AI/pmoves/contracts/topics.json` - NATS subject registry

## Contact & Support

For questions about this design:
- Architecture: Review main design document
- Implementation: Reference subordinate agent profile
- Schema validation: Check JSON schemas
- NATS integration: Consult `.claude/context/nats-subjects.md`

---

**Design Status:** ✅ Complete
**Implementation Status:** 🔄 Ready to Begin
**Target Completion:** 12 weeks from kickoff
**Risk Level:** Medium (new ML infrastructure, distributed coordination)
**Business Impact:** High (enables continuous agent improvement)
