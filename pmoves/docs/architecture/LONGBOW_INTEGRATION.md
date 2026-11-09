# Longbow Integration Scaffold

**Status:** v1.1 deferral — Milestone M6  
**TAC Ref:** `pmoves/configs/tac_trees/pmoves-launch-readiness.tac.yaml` stage-4.longbow-or-deprecated  
**Decision:** Deprecated — see `PMOVES_LONGBOW_DEPRECATED.md`. BM25/hybrid capability delivered via Qdrant sparse + Meilisearch instead.

## Purpose

Longbow is the learned-pattern router for PMOVES.AI. It sits between agents and models, using contextual-bandit reinforcement learning to route requests to the optimal model suit based on historical performance.

## Architecture

```
Agent Request → Longbow Router → Model Suit Selection → Inference → Feedback
                    ↑___________________________________________|
```

### Components

1. **Pattern Extractor** — Embeds request features (task type, context length, agent class)
2. **Bandit Core** — Contextual bandit with Thompson sampling
3. **Model Registry** — Reads `pmoves/configs/model-suits/` + live HF collection
4. **Feedback Loop** — Consumes `model.fitness.recorded.v1` for reward signal

## Interface

### NATS Subjects

| Subject | Direction | Payload |
|---------|-----------|---------|
| `longbow.route.request.v1` | In | `{agent_id, task_type, context_length, preferred_model}` |
| `longbow.route.response.v1` | Out | `{selected_suit, confidence, exploration}` |
| `longbow.feedback.v1` | In | `{route_id, latency, quality_score, tokens_used}` |

### Files (Target)

- `PMOVES-Longbow/services/longbow-router/app.py` — FastAPI router service
- `PMOVES-Longbow/longbow/bandit.py` — Thompson sampling implementation
- `PMOVES-Longbow/longbow/registry.py` — Model suit registry client

## Integration with Darkmatter Factory

Fine-tuned models from the Darkmatter Factory are first-class citizens in Longbow:
- Each minted model registers its suit profile
- Longbow learns which agents benefit from which fine-tunes
- Adapter hot-swap is triggered by `longbow.route.response.v1`

## Status

| Item | State |
|------|-------|
| Submodule `PMOVES-Longbow` | MISSING — needs creation or external integration |
| TAC tree stage-4 task | ❌ Not started |
| Router service | ❌ Not started |
| Bandit core | ❌ Not started |
| NATS subject schema | ⏳ Defined above, not deployed |

## Claim

**Lane:** `feat/longbow-router-scaffold`  
**Owner:** TBD (recommend 4090-CLAUDE or z890-CLAUDE)  
**Scope:** Create submodule scaffold, implement basic bandit, wire to model suits  
**Blocked by:** Darkmatter Factory Lane C (model registry schema)

<!-- GRAPHITI_MARK: LONGBOW-INTEGRATION::SCAFFOLD::2026-06-01 -->
