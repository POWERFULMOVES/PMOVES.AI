# TAC Tree: autoresearch

> Technology-Architecture-Context tree for the autoresearch autonomous ML training loop — an AI agent-driven experiment runner that modifies, trains, and evaluates LLMs overnight.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | autoresearch |
| **Port** | None (CLI tool, not a service) |
| **Health** | N/A |
| **Metrics** | N/A |
| **Submodule** | `PMOVES-autoresearch` |
| **Docker Profile** | N/A (runs directly on GPU host) |
| **Tier** | llm |
| **Class** | Specialized |
| **Evolution** | Pre-Stage |

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| GPU hardware (H100/4090/5090) | NVIDIA CUDA compute | Yes |
| PyTorch | Training framework | Yes |
| `uv` | Package manager and runner | Yes |
| AI coding agent (Claude/Codex) | Experiment pilot — reads `program.md`, modifies `train.py` | Yes |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| Agent Zero (planned) | NATS task delegation | Orchestrate experiment runs remotely |
| Supabase (planned) | REST API | Store experiment results for analysis |
| AgentGym RL (planned) | NATS / shared storage | Feed training results into RL pipeline |
| Hi-RAG v2 (planned) | Ingest API | Index experiment findings for retrieval |

## Key Endpoints

_None — autoresearch is a CLI tool, not a network service._

## NATS Subjects

_All subjects are **planned** — autoresearch currently has no NATS integration._

| Subject | Direction | Description |
|---------|-----------|-------------|
| `research.autoresearch.experiment.v1` | Publishes (planned) | Experiment started/completed events |
| `research.autoresearch.result.v1` | Publishes (planned) | val_bpb results for each experiment |

> **TODO:** When implemented, register these subjects in `.claude/context/nats-subjects.md` and `pmoves/contracts/topics.json`.

## CHIT Integration Status

| Capability | Status | Notes |
|------------|--------|-------|
| CGP packet generation | None | Not CHIT-enabled |
| Attribution | None | Potential for training-objective CHIT weighting |
| Swarm participant | No | Standalone CLI tool |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/healthz` endpoint | N/A | CLI tool, not a service |
| `/metrics` (Prometheus) | N/A | No metrics endpoint |
| Auth (JWT/Bearer) | N/A | Local CLI execution |
| Docker hardening | N/A | Not containerized |
| NATS auth | N/A | No NATS integration yet |
| `env.shared` format | N/A | Uses `pyproject.toml` + `uv` |

## Experiment Loop Architecture

autoresearch implements an autonomous research loop inspired by Karpathy's vision of AI-driven ML research:

```
┌─────────────────────────────────────────────────┐
│                  program.md                      │
│          (human-authored research org)            │
└──────────────────┬──────────────────────────────┘
                   │ AI agent reads instructions
                   ▼
┌─────────────────────────────────────────────────┐
│              train.py (agent-modified)            │
│  GPT model + Muon/AdamW optimizer + training loop│
└──────────────────┬──────────────────────────────┘
                   │ uv run train.py (5-min budget)
                   ▼
┌─────────────────────────────────────────────────┐
│              prepare.py (fixed)                   │
│  Data prep, tokenizer, dataloader, evaluation    │
│  Metric: val_bpb (validation bits per byte)      │
└──────────────────┬──────────────────────────────┘
                   │ result comparison
                   ▼
            ┌──────┴──────┐
            │  Improved?   │
            ├──Yes──► Keep │
            └──No───► Discard, try new approach
```

### Key Design Choices

| Property | Value |
|----------|-------|
| Time budget | Fixed 5 minutes per experiment (~12 experiments/hour) |
| Metric | `val_bpb` (validation bits per byte) — lower is better |
| Agent-editable files | Only `train.py` |
| Human-editable files | Only `program.md` |
| Fixed files | `prepare.py` (constants, data prep, evaluation) |
| Platform | Single NVIDIA GPU (H100 tested, 4090/5090 viable) |

### Project Structure

```
PMOVES-autoresearch/
├── prepare.py      — Constants, data prep, runtime utilities (DO NOT modify)
├── train.py        — Model, optimizer, training loop (agent modifies this)
├── program.md      — Agent instructions (human modifies this)
├── pyproject.toml   — Dependencies (PyTorch, etc.)
├── analysis.ipynb   — Experiment analysis notebook
├── progress.png     — Training progress visualization
└── uv.lock          — Locked dependencies
```

## Cross-Links

- **Submodule:** `PMOVES-autoresearch/`
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)
- **AgentGym RL:** `Pmoves-AgentGym-RL/` — potential training pipeline integration
- **DeepResearch TAC:** Related research automation (LLM-based planning vs ML training)
- **Upstream:** [karpathy/autoresearch](https://github.com/karpathy/autoresearch) (fork origin)

## Open Items

- No NATS integration — experiment events are local-only
- No Supabase/storage for experiment results (results exist only on GPU host)
- No Agent Zero orchestration path for remote experiment delegation
- No Docker containerization — manual GPU host setup required
- Could feed experiment results to Hi-RAG v2 for research retrieval
- Integration with AgentGym RL for training pipeline continuity
- Platform support limited to NVIDIA GPUs (no MPS/CPU)

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-DEEP-DIVE::2026-03-15 -->
