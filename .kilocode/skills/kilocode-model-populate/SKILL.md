---
name: kilocode-model-populate
description: Pull and register Ollama models on the 5090 GPU node, sync with TensorZero config, and manage model availability for the PMOVES fleet. Use when adding new local models or updating model routing.
keywords: [model, ollama, pull, register, tensorzero, sync]
version: 1.0.0
category: PMOVES/KiloCode-GLM
---

# KiloCode Model Populate

Model pulling, registration, and TensorZero sync using GLM-5.2 for model card analysis and routing decisions.

## Purpose

Pull new models to the 5090's Ollama instance, register them in TensorZero, and sync the model routing configuration across the PMOVES fleet.

## Capabilities

- 📦 Pull models via `ollama pull`
- 🗒️ Analyze model cards via HuggingFace MCP
- 🔀 Register models in TensorZero config
- 📊 Sync model profiles via `models_sync.py`
- 🏷️ Tag models with PMOVES-specific metadata

## Integration Points

- **Ollama**: `http://localhost:11434`
- **TensorZero Gateway**: `http://localhost:3030`
- **Model Sync Tool**: `pmoves/tools/models/models_sync.py`
- **Provider Catalog**: `pmoves/config/provider_catalog.yaml`
- **Model Suits**: `pmoves/configs/model-suits/`
- **HuggingFace MCP**: For model card research

## Workflow

### Step 1: Research Model

```
# Use HuggingFace MCP to study the model card
# Check VRAM requirements vs available GPU memory
# Verify license compatibility
```

### Step 2: Pull Model

```bash
ollama pull <model-name>
```

### Step 3: Verify Pull

```bash
ollama list
ollama show <model-name>
```

### Step 4: Sync to TensorZero

```bash
# Sync model profiles
python pmoves/tools/models/models_sync.py sync

# Or dynamic sync from Supabase registry
python pmoves/tools/models/models_sync.py sync-dynamic
```

### Step 5: Publish Mesh Event

```bash
# Notify fleet of new model availability
nats pub mesh.gpu.model.loaded.v1 '{"model":"<name>","node":"5090","vram_gb":<n>}'
```

## Trigger Phrases

- "pull model"
- "register model"
- "model populate"
- "sync models"
- "add ollama model"
