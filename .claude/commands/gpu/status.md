# GPU Status

Show VRAM usage, loaded models, and running GPU processes using Pmoves-Glancer.

## Arguments

- `$ARGUMENTS` - Optional: "summary" for brief output, "full" for detailed output (default: summary)

## Instructions

1. **Primary: Query Pmoves-Glancer for GPU metrics** (port 9105 or 61208):
   ```bash
   # Glancer GPU endpoint
   curl -s http://localhost:9105/api/4/gpu | jq '.'
   # Alternative if different port
   curl -s http://localhost:61208/api/4/gpu | jq '.'
   ```

   Glancer returns:
   ```json
   [
     {
       "gpu_id": "nvidia0",
       "name": "NVIDIA GeForce RTX 5090",
       "mem": 76.5,           # Memory usage %
       "proc": 45,            # GPU utilization %
       "temperature": 55,     # Temperature °C
       "fan_speed": 30        # Fan speed %
     }
   ]
   ```

2. **Fallback: If Glancer unavailable, use nvidia-smi directly:**
   ```bash
   nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu --format=csv,noheader,nounits
   ```

3. **Get loaded models from GPU Orchestrator** (for model-level detail):
   ```bash
   curl -s http://localhost:8200/api/gpu/status | jq '.loaded_models'
   ```

4. **For processes, use Glancer's processlist with GPU filter:**
   ```bash
   curl -s "http://localhost:9105/api/4/processlist?sort=gpu_memory" | jq '.[:10]'
   ```

5. **Display results formatted as:**

   **GPU Status (via Glancer):**
   - GPU: [name]
   - VRAM: [mem]% used ([used_mb]/[total_mb] MB)
   - Temperature: [temperature]°C
   - Utilization: [proc]%
   - Fan Speed: [fan_speed]%

   **Loaded Models (via GPU Orchestrator):**
   | Model | Provider | VRAM (MB) | Idle Time |
   |-------|----------|-----------|-----------|

   **Top GPU Processes:** (if full output requested)
   | PID | Name | GPU Mem (MB) | Container |
   |-----|------|--------------|-----------|

6. **Add recommendations if:**
   - mem > 80%: Suggest running `/gpu:optimize`
   - Idle models > 5 min: List candidates for unloading
   - Temperature > 80°C: Warn about thermal throttling

7. **If orchestrator not running but Glancer works:**
   Report GPU metrics only, note that model tracking is unavailable.
