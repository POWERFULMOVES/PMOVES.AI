# GPU Optimize

Auto-optimize GPU by unloading idle models to free VRAM.

## Arguments

- `$ARGUMENTS` - Optional: "dry-run" to preview without unloading, "aggressive" to force unload all except active

## Instructions

1. Check current GPU status:
   ```bash
   curl -s http://localhost:8200/api/gpu/status | jq '.loaded_models'
   ```

2. If dry-run mode:
   - List models that would be unloaded (idle > 5 minutes)
   - Show estimated VRAM to be freed
   - Exit without making changes

3. Call the optimize endpoint:
   ```bash
   curl -s -X POST http://localhost:8200/api/gpu/optimize | jq '.'
   ```

4. For aggressive mode (if specified):
   - Unload ALL idle models regardless of timeout
   - Use force=true parameter

5. Report results:

   **Optimization Results:**
   - Models unloaded: [count]
   - VRAM freed: [amount] MB
   - Errors: [list if any]

   **Current Status:**
   - VRAM now: [used]/[total] MB ([percent]%)
   - Remaining models: [count]

6. If no models were unloaded:
   - Explain why (no idle models, or all models in active sessions)
   - Suggest manual unload if needed: `/model:unload ollama/qwen3:8b`
