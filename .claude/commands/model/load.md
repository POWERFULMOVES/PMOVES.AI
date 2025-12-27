# Model Load

Load a specific model into GPU memory.

## Arguments

- `$ARGUMENTS` - Model identifier (e.g., `qwen3:8b`, `ollama/qwen3:8b`, `--priority high`)

## Usage Examples

```
/model:load qwen3:8b
/model:load ollama/qwen3:32b --priority high
/model:load nomic-embed-text
```

## Instructions

1. Parse the model identifier from arguments:
   - If format is `provider/model`, use as-is
   - If just `model`, default to `ollama` provider

2. Parse priority if specified:
   - `--priority high` → priority 3
   - `--priority normal` → priority 5 (default)
   - `--priority low` → priority 7

3. Check available VRAM:
   ```bash
   curl -s http://localhost:8200/api/gpu/metrics/summary | jq '.free_vram_mb'
   ```

4. Get model's VRAM requirement from registry:
   ```bash
   curl -s http://localhost:8200/api/gpu/registry | jq '.models[] | select(.id == "MODEL_ID")'
   ```

5. If insufficient VRAM:
   - Show current usage
   - List idle models that could be unloaded
   - Suggest running `/gpu:optimize` first
   - Ask user if they want to proceed (will auto-evict idle models)

6. Queue the load request:
   ```bash
   curl -s -X POST http://localhost:8200/api/gpu/models/load \
     -H "Content-Type: application/json" \
     -d '{"model_id": "MODEL_ID", "provider": "PROVIDER", "priority": PRIORITY}'
   ```

7. Report result:
   - If already loaded: "Model [model] is already loaded"
   - If queued: "Model [model] queued for loading (request_id: [id])"
   - Monitor load progress if needed

8. For Ollama models, verify loading:
   ```bash
   curl -s http://localhost:11434/api/ps | jq '.models[] | select(.name == "MODEL")'
   ```
