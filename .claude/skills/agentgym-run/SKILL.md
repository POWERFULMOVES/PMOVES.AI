---
name: agentgym-run
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

# agentgym-run — AgentGym RL Field Runner (4090)

Launches an AgentGym reinforcement learning session using the 4090 node configuration.

## Pre-flight

```bash
# Verify TensorZero is running (required for Qwen 3.5 9B)
curl -sf http://localhost:3030/health && echo "TensorZero: OK" || echo "TensorZero: DOWN"

  # One derivation, one place. `8222` is the CONTAINER-side port; the host half
  # AND the port vary per node (compose default 9223, Z890 8222, and
  # NATS_MONITORING_BIND can move the host off loopback). See nats-endpoint.sh.
  NATS_URL=$(bash .claude/scripts/nats-endpoint.sh)
  curl -sf "$NATS_URL/healthz" >/dev/null 2>&1 && echo "NATS: OK ($NATS_URL)" || echo "NATS: DOWN ($NATS_URL)"

# Check Ollama fallback available
ollama list | grep qwen3 || echo "Ollama qwen3 models not found"
```

## Run — Single Episode

The current field runner (`pmoves/tools/agentgym_field_runner.py`) runs ONE episode per invocation; batch by looping in shell. CLI accepts `--run <env>`, `--config <profile>`, `--dry-run`, `--list-envs`.

```bash
# Validate config + env connectivity without running an episode
python pmoves/tools/agentgym_field_runner.py --dry-run --run BabyAI

# BabyAI (fastest, < 1GB RAM, no external deps)
python pmoves/tools/agentgym_field_runner.py --run BabyAI

# Wordle (good for language model eval)
python pmoves/tools/agentgym_field_runner.py --run Wordle

# ALFWorld (embodied task planning, ~2GB RAM)
python pmoves/tools/agentgym_field_runner.py --run ALFWorld

# List configured environments with health status
python pmoves/tools/agentgym_field_runner.py --list-envs
```

## Run — Full Lightweight Battery

Until a `make agentgym-run-lightweight` wrapper lands, batch via shell:

```bash
for env in BabyAI TextCraft Maze Wordle; do
  python pmoves/tools/agentgym_field_runner.py --run "$env"
done
```

> **TODO (follow-up PR)**: Wrap as `make -C pmoves agentgym-run ENV=X` + `make -C pmoves agentgym-run-lightweight` Make targets so this skill routes through the canonical `with-env.sh` chain. Also: add a `--repeat N` flag to the runner for episode batching without shell looping.

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
- Capture results for AGNOTE4482 handoff: episode JSON written to `pmoves/data/agentgym/runs/` (a `make -C pmoves agentgym-results` summary target is a pending follow-up)
- See: `pmoves/configs/agentgym/field-runner-4090.yaml` for full config
- See: `pmoves/services/agentgym-rl-coordinator/` for the runner service
