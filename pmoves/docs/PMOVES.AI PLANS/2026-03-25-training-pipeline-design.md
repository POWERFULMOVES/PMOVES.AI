# PMOVES Training Pipeline Design

**Date:** 2026-03-25
**Author:** 5090-claude + DARKXSIDE
**Status:** Design approved

## Purpose

Fine-tune models on PMOVES-specific content using Unsloth Studio (already running on 5090). Three phases: embeddings for better retrieval, agentic models for local tool-use, voice adaptation for persona synthesis. All trained on PMOVES content first — eat your own cooking.

## Architecture

```text
PMOVES Content (MinIO/Supabase)
  → Data Prep (JSONL formatting)
  → Unsloth Studio (LoRA/QLoRA on 5090 GPU)
  → HuggingFace (POWERFULMOVES org)
  → TensorZero (model routing)
  → Consumers (Hi-RAG, Agent Zero, Flute-Gateway)
```

## Multi-Node Coordination

| Node | During Training | During Serving |
|------|----------------|----------------|
| 5090 (32GB) | Unsloth training | TTS + inference |
| z890 (24GB) | TTS + data services | Data services |
| VPS/KVM | E2B eval sandboxes | API gateway |

VRAM swap protocol: stop TTS on 5090 → train → restart TTS. z890 covers TTS during the training window.

## Three Phases

### Phase 1: Embeddings (Crawl)
- Base: Qwen3-4b (3072d)
- Data: PMOVES transcripts, docs, CHIT packets, agent trails
- Output: `POWERFULMOVES/pmoves-qwen3-4b-embed`
- Impact: Hi-RAG retrieval quality jumps from generic to domain-aware

### Phase 2: Agentic Models (Walk)
- Base: Qwen2.5-7B or Llama 3.1-8B
- Data: Claude Code logs, MCP tool patterns, Known Roads
- Output: `POWERFULMOVES/pmoves-agent-7b`
- Impact: Local agent handles routine tasks without cloud LLMs

### Phase 3: Voice Adaptation (Run)
- Base: Fish S2 Pro, F5-TTS
- Data: Synthesized reference audio from existing engines
- Output: Persona-specific voice adapters
- Impact: Each agent has a unique, fine-tuned voice

## FlOO$ Skill Pairing

`training-eval-deploy`: data-prep → unsloth-train → e2b-eval → hf-publish → tz-register

NATS subject: `skills.pipeline.training-eval-deploy.v1`

## TAC Tree

See `pmoves/configs/tac_trees/training-pipeline.tac.yaml`
