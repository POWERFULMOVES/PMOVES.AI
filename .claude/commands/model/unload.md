# Model Unload

Unload a specific model to free GPU VRAM.

## Arguments

- `$ARGUMENTS` - Model identifier (e.g., `qwen3:8b`, `ollama/qwen3:8b`, `--force`)

## Usage Examples

```
/model:unload qwen3:8b
/model:unload ollama/qwen3:32b --force
/model:unload tts/kokoro
```

## Instructions

1. Parse the model identifier from arguments:
   - If format is `provider/model`, use as-is
   - If just `model`, default to `ollama` provider

2. Check if `--force` flag is present (unload even if in active session)

3. Check if model is currently loaded:
   ```bash
   curl -s http://localhost:8200/api/gpu/models/loaded | jq '.models'
   ```

4. If model is not loaded:
   - Report "Model [model] is not currently loaded"
   - List currently loaded models as reference
   - Exit

5. Check for provider limitations:
   - **Ollama**: Supports dynamic unload via keep_alive=0
   - **vLLM**: Does NOT support dynamic unload - warn user to stop container
   - **TTS**: Does NOT support individual engine unload - warn about container

6. For Ollama models, proceed with unload:
   ```bash
   curl -s -X POST "http://localhost:8200/api/gpu/models/unload/PROVIDER/MODEL_ID?force=FORCE"
   ```

7. For vLLM/TTS, provide guidance:
   ```
   vLLM and Ultimate TTS Studio do not support dynamic model unloading.
   To free VRAM, stop the container:
   - vLLM: docker stop pmoves-vllm-1
   - TTS: docker stop pmoves-ultimate-tts-studio-1
   ```

8. Report result:
   - Success: "Unloaded [model], freed approximately [vram] MB"
   - Failure: "Failed to unload [model]: [reason]"
   - If in active session without --force: "Model is in active session. Use --force to override."

9. Show updated VRAM status:
   ```bash
   curl -s http://localhost:8200/api/gpu/metrics/summary | jq '.'
   ```
