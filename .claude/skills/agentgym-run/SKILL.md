---
name: agentgym:run
description: >
  Launch an AgentGym RL training session on this node using the 4090 field
  runner config (pmoves/configs/agentgym/field-runner-4090.yaml).
  Agent model: Qwen 3.5 9B via TensorZero (localhost:3030).
  Publishes episode results to agentgym.episode.completed.v1 on NATS.
  Environments: BabyAI, TextCraft, Maze, Wordle (lightweight);
  ALFWorld, SQLGym, WebShop (moderate). Max 300s/15 rounds, concurrency=1.
  Shift Crew style: NATS event publishing after each episode.
disable-model-invocation: true
---

# agentgym:run — AgentGym RL Field Runner (4090)

Launches an AgentGym reinforcement learning session using the 4090 node configuration.

## Pre-flight

```bash
# Verify TensorZero is running (required for Qwen 3.5 9B)
curl -sf http://localhost:3030/health && echo "TensorZero: OK" || echo "TensorZero: DOWN"

# Verify NATS is reachable (for episode event publishing)
curl -sf http://localhost:8222/healthz && echo "NATS: OK" || echo "NATS: unreachable"

# Check Ollama fallback available
ollama list | grep qwen3 || echo "Ollama qwen3 models not found"
```

## Run — Single Environment

```bash
# BabyAI (fastest, < 1GB RAM, no external deps)
make -C pmoves agentgym-run ENV=BabyAI EPISODES=5

# Wordle (good for language model eval)
make -C pmoves agentgym-run ENV=Wordle EPISODES=10

# ALFWorld (embodied task planning, ~2GB RAM)
make -C pmoves agentgym-run ENV=ALFWorld EPISODES=5
```

## Run — Full Lightweight Battery

```bash
make -C pmoves agentgym-run-lightweight
# Runs: BabyAI → TextCraft → Maze → Wordle (sequential, concurrency=1)
```

## Direct Python (without Make)

```bash
uv run python -m pmoves.services.agentgym_rl_coordinator.runner \
  --config pmoves/configs/agentgym/field-runner-4090.yaml \
  --env BabyAI \
  --episodes 5
```

## NATS Events Published

| Subject | When | Payload |
|---------|------|---------|
| `agentgym.episode.completed.v1` | After each episode | episode_id, env, reward, rounds, duration_s |
| `agentgym.eval.batch.completed.v1` | After full batch | batch_id, env, n_episodes, mean_reward |
| `agentgym.field.status.v1` | On runner start/stop | node, config, status |

## Environment Reference

| Name | Category | RAM | External Deps | Port |
|------|----------|-----|---------------|------|
| BabyAI | lightweight | < 1GB | None | 36001 |
| TextCraft | lightweight | < 1GB | None | 36002 |
| Maze | lightweight | < 1GB | None | 36003 |
| Wordle | lightweight | < 1GB | None | 36004 |
| ALFWorld | moderate | 1-4GB | ALFWorld data | 36005 |
| SQLGym | moderate | 1-4GB | SQLite | 36006 |
| WebShop | moderate | 1-4GB | Web scraper | 36007 |

**Skipped on 4090:** WebArena (needs full browser), SciWorld (needs Java)

## Notes

- Concurrency is 1 — episodes run sequentially (16GB VRAM budget)
- Model: `qwen35_9b` (registered in tensorzero.toml) with `qwen3:8b` Ollama fallback
- Max episode: 300s / 15 rounds — hard limits in field-runner-4090.yaml
- Capture results for AGNOTE4482 handoff: `make -C pmoves agentgym-results`
- See: `pmoves/configs/agentgym/field-runner-4090.yaml` for full config
- See: `pmoves/services/agentgym-rl-coordinator/` for the runner service
