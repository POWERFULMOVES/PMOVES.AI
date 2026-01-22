# AgentGym-RL Feedback Loop - Documentation Index

**Project:** Agent Zero RL Integration with AgentGym-RL
**Status:** Design Complete
**Date:** 2025-12-08
**Version:** 1.0

## Quick Navigation

### For Developers
Start here: [Quick Reference](/home/pmoves/PMOVES.AI/docs/rl-feedback-loop-quickref.md)
- NATS commands
- Common operations
- Troubleshooting
- Environment variables

### For Architects
Start here: [Design Document](/home/pmoves/PMOVES.AI/docs/rl-feedback-loop-design.md)
- Architecture overview
- Data flow diagrams
- Integration requirements
- Performance metrics

### For Project Managers
Start here: [Summary](/home/pmoves/PMOVES.AI/docs/rl-feedback-loop-summary.md)
- Deliverables overview
- Implementation roadmap (12 weeks)
- Success metrics
- Resource requirements

### For Agent Developers
Start here: [RL Trainer Profile](/home/pmoves/PMOVES.AI/docs/subordinate-profile-rl-trainer.md)
- Subordinate agent role specification
- Operational procedures
- Tool specifications
- Example interactions

## Document Structure

```
docs/
├── INDEX-rl-feedback-loop.md              [THIS FILE]
│   └── Master index and navigation
│
├── rl-feedback-loop-design.md             [MAIN SPEC - 43KB]
│   ├── Architecture overview
│   ├── NATS subject design (5 subjects)
│   ├── ASCII data flow diagrams
│   ├── Reward computation algorithms
│   ├── Model update propagation
│   ├── Integration requirements
│   ├── Performance metrics
│   ├── Security considerations
│   └── Future enhancements
│
├── rl-feedback-loop-summary.md            [EXEC SUMMARY - 13KB]
│   ├── Deliverables checklist
│   ├── Key design decisions
│   ├── Implementation roadmap (12 weeks)
│   ├── Integration points
│   ├── Performance expectations
│   ├── Monitoring strategy
│   └── Success metrics
│
├── rl-feedback-loop-quickref.md           [CHEATSHEET - 9KB]
│   ├── NATS subject quick reference
│   ├── Reward computation formulas
│   ├── Training trigger conditions
│   ├── Deployment workflow
│   ├── Key commands
│   ├── JetStream setup
│   ├── Prometheus queries
│   └── Troubleshooting guide
│
└── subordinate-profile-rl-trainer.md      [AGENT ROLE - 20KB]
    ├── Core responsibilities
    ├── NATS integration details
    ├── 6-phase RL methodology
    ├── Reward computation code
    ├── Training orchestration logic
    ├── Validation procedures
    ├── Deployment strategies
    ├── Tool specifications
    ├── Decision-making framework
    ├── Performance targets
    ├── Reporting templates
    ├── Example interactions
    └── Configuration reference

pmoves/contracts/
├── topics.json                             [REGISTRY - 5.2KB]
│   └── 5 new RL subjects registered
│
└── schemas/agent-rl/
    ├── trajectory.v1.schema.json           [SCHEMA - 6.7KB]
    │   └── Multi-turn agent interaction structure
    │
    ├── reward.v1.schema.json               [SCHEMA - 4.4KB]
    │   └── Multi-component reward signals
    │
    ├── training.request.v1.schema.json     [SCHEMA - 7.8KB]
    │   └── Training job configuration
    │
    ├── training.status.v1.schema.json      [SCHEMA - 6.2KB]
    │   └── Training progress updates
    │
    └── model.deployed.v1.schema.json       [SCHEMA - 5.0KB]
        └── Model deployment notifications
```

## File Sizes
- **Total Documentation:** 85KB (4 markdown files)
- **Total Schemas:** 30KB (5 JSON schemas)
- **Total Deliverables:** 115KB
- **Line Count:** ~2,500 lines of comprehensive specification

## Component Summary

### 1. NATS Subjects (5 new)
- `agent.rl.trajectory.v1` - Agent interaction sequences
- `agent.rl.reward.v1` - Computed reward signals
- `agent.rl.training.request.v1` - Training job requests
- `agent.rl.training.status.v1` - Training progress updates
- `agent.rl.model.deployed.v1` - Model deployment events

### 2. JSON Schemas (5 files)
All schemas include:
- JSON Schema 2020-12 compliance
- Required field validation
- Type constraints and enums
- Detailed descriptions
- Example values

### 3. Subordinate Agent Profile
- Profile name: `rl-trainer`
- 6-phase RL lifecycle management
- NATS pub/sub integration
- Multi-component reward computation
- Canary deployment orchestration
- Automatic rollback mechanisms

### 4. Integration Components
- Agent Zero trajectory collection hooks
- AgentGym-RL NATS subscriber
- TensorZero Gateway deployment
- ClickHouse trajectory warehouse
- Prometheus/Grafana monitoring

## Key Features

### Event-Driven Architecture
- Decoupled components via NATS
- Async processing for scalability
- JetStream persistence (30-day retention)
- Queue groups for load balancing

### Multi-Component Rewards
- Task completion: 40%
- Efficiency: 20%
- Code quality: 15%
- User feedback: 25%
- Z-score normalization

### Canary Deployment
- 10% → 25% → 50% → 100% over 4 hours
- Automatic rollback on degradation
- A/B testing via TensorZero
- Performance monitoring

### Observability
- 8+ Prometheus metrics
- 3 Grafana dashboards
- Loki log aggregation
- Alert rules for failures

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
- Trajectory collection in Agent Zero
- NATS stream setup
- Schema deployment
- ClickHouse storage

### Phase 2: RL Trainer (Weeks 3-4)
- Subordinate agent implementation
- Reward computation pipeline
- Training request generator
- NATS integration

### Phase 3: AgentGym-RL (Weeks 5-6)
- NATS subscriber
- Dataset loader
- PPO/DPO training
- Checkpoint management

### Phase 4: Deployment (Weeks 7-8)
- Validation pipeline
- TensorZero integration
- Canary controller
- Rollback logic

### Phase 5: Monitoring (Weeks 9-10)
- Grafana dashboards
- Loki setup
- Integration tests
- Performance benchmarks

### Phase 6: Production (Weeks 11-12)
- Staging deployment
- Shadow training
- Baseline collection
- Production rollout

## Performance Targets

### Latency
- Trajectory collection: < 100ms
- Reward computation: < 500ms
- Training queue: < 5 minutes
- Model validation: < 30 minutes
- Deployment: < 5 minutes
- Rollback: < 60 seconds

### Throughput
- Trajectories: 1000/day
- Training jobs: 1/day
- Deployments: 1-2/week

### Resource Usage
- NATS storage: ~100GB/month
- ClickHouse: ~200GB/month
- Training: 8 GPU-hours/job
- Cost: ~$50/job

## Usage Examples

### Publish Test Trajectory
```bash
nats pub "agent.rl.trajectory.v1" "$(cat test_trajectory.json)"
```

### Trigger Training Job
```bash
nats pub "agent.rl.training.request.v1" "$(cat training_config.json)"
```

### Monitor Training Status
```bash
nats sub "agent.rl.training.status.v1"
```

### Deploy Model
```bash
# Via subordinate agent
agent.call_subordinate(
    profile="rl-trainer",
    message="Deploy model v2.4 with canary rollout"
)
```

## Testing Strategy

### Unit Tests
- Trajectory validation
- Reward computation
- Schema validation
- NATS pub/sub

### Integration Tests
- End-to-end trajectory flow
- Training job lifecycle
- Deployment workflow
- Rollback procedures

### Load Tests
- 1000 trajectories/day sustained
- Concurrent training jobs
- Deployment under load
- Rollback latency

### Shadow Tests
- Run training on production data
- Don't deploy models
- Validate pipeline
- Collect baselines

## Success Criteria

### Technical
- Model performance: +5-10% per cycle
- Training success rate: > 90%
- Deployment success rate: > 95%
- Rollback time: < 60 seconds
- False rollback rate: < 5%

### Business
- Task completion: +10-15%
- User satisfaction: +20%
- Agent efficiency: -15% turns
- Code quality: +10% linter scores
- Support tickets: -25%

## Security & Privacy

### Data Protection
- Automatic PII redaction
- API key scrubbing
- User opt-out support
- NATS ACLs

### Model Safety
- Red-teaming validation
- Toxicity evaluation
- Refusal testing
- Human oversight

### Audit Trail
- All deployments logged
- Training provenance tracked
- Rollback decisions recorded
- 30-day log retention

## Support & Maintenance

### Daily Operations
- Monitor trajectory collection
- Review training job status
- Check model performance
- Respond to alerts

### Weekly Tasks
- Review training reports
- Analyze performance trends
- Update reward weights
- Audit deployment history

### Monthly Tasks
- Capacity planning
- Cost optimization
- Security review
- Documentation updates

## References

### Internal Documentation
- `.claude/CLAUDE.md` - PMOVES.AI architecture
- `.claude/context/nats-subjects.md` - NATS catalog
- `.claude/context/tensorzero.md` - TensorZero docs
- `.claude/context/services-catalog.md` - Service registry

### External Resources
- [AgentGym Paper](https://arxiv.org/abs/2406.04151)
- [PPO Algorithm](https://arxiv.org/abs/1707.06347)
- [DPO Algorithm](https://arxiv.org/abs/2305.18290)
- [NATS JetStream](https://docs.nats.io/nats-concepts/jetstream)
- [TensorZero Docs](https://tensorzero.com/docs)

## FAQ

**Q: Why event-driven architecture via NATS?**
A: Decouples Agent Zero from training infrastructure, enables async processing, supports distributed scaling, provides reliable message delivery via JetStream.

**Q: Why multi-component rewards vs single metric?**
A: Prevents reward hacking, balances automated metrics with human preferences, enables fine-grained optimization, supports domain-specific tuning.

**Q: Why canary deployment instead of blue-green?**
A: Minimizes risk of deploying degraded models, enables gradual validation, supports automatic rollback, provides A/B testing capability.

**Q: Why subordinate agent vs main agent logic?**
A: Isolates RL complexity from main agent, enables reuse across instances, simplifies testing, centralizes coordination logic.

**Q: What if training fails repeatedly?**
A: Automatic retry with adjusted hyperparameters, human operator alerts after 3 failures, fallback to previous model, investigation workflow.

**Q: What if NATS is unavailable?**
A: Trajectories buffered locally, retry with backoff, fallback to HTTP APIs, alert operators, graceful degradation.

**Q: How to handle model regression?**
A: Automatic validation before deployment, multi-stage benchmarking, regression detection thresholds, automatic rollback, human review.

## Contact & Questions

For assistance with this design:
- **Architecture Questions:** Review `/home/pmoves/PMOVES.AI/docs/rl-feedback-loop-design.md`
- **Implementation Help:** See `/home/pmoves/PMOVES.AI/docs/subordinate-profile-rl-trainer.md`
- **Quick Reference:** Check `/home/pmoves/PMOVES.AI/docs/rl-feedback-loop-quickref.md`
- **Schema Issues:** Validate against `/home/pmoves/PMOVES.AI/pmoves/contracts/schemas/agent-rl/`
- **NATS Questions:** Consult `.claude/context/nats-subjects.md`

## Version History

- **v1.0** (2025-12-08): Initial design complete
  - 5 NATS subjects defined
  - 5 JSON schemas created
  - Subordinate agent profile documented
  - Architecture and data flow specified
  - 12-week implementation roadmap
  - Monitoring and observability strategy
  - Security and privacy considerations

## Next Steps

1. **Stakeholder Review** - Present design for approval
2. **Resource Allocation** - Assign team and GPU resources
3. **Phase 1 Kickoff** - Begin trajectory collection implementation
4. **AgentGym-RL Selection** - Choose/build training service
5. **Pilot Testing** - Synthetic data validation
6. **Production Rollout** - Follow 12-week roadmap

---

**Status:** ✅ Design Complete | 🔄 Ready for Implementation
**Risk Level:** Medium | **Business Impact:** High
**Target Completion:** 12 weeks from kickoff
