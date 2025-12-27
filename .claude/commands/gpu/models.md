# GPU Models

List models and their memory requirements.

## Arguments

- `$ARGUMENTS` - Optional: "loaded" for only loaded models, "registry" for known models, "all" for both (default: all)

## Instructions

1. Query the GPU orchestrator models endpoint:
   ```bash
   curl -s "http://localhost:8200/api/gpu/models?include_unloaded=true" | jq '.'
   ```

2. For Ollama specifically:
   ```bash
   curl -s http://localhost:11434/api/ps | jq '.'  # Running models
   curl -s http://localhost:11434/api/tags | jq '.'  # Available models
   ```

3. Display results formatted as:

   **Currently Loaded Models:**
   | Model | Provider | VRAM (MB) | State | Last Used |
   |-------|----------|-----------|-------|-----------|

   **Available in Registry:**
   | Model | Provider | Est. VRAM (MB) | Description |
   |-------|----------|----------------|-------------|

4. Show VRAM summary:
   - Total VRAM: [total] MB
   - Used by models: [used] MB
   - Available for loading: [free] MB

5. If a model is requested in $ARGUMENTS that's not found, suggest similar models from registry.
