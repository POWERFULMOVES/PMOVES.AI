# SKILL.md — B850 Llama Server

> **Node:** B850 (Knuckles) — AMD Ryzen 9850X3D + Dual Radeon AI Pro R9700
> **Backend:** llama.cpp HIP via `tlee933/llama.cpp-rdna4-gfx1201`
> **API:** OpenAI-compatible at `http://localhost:8080/v1`

---

## Discovery

Pinokio Agent Interpreter can auto-discover this service via the built-in `pinokio` skill.

```bash
# Verify discovery
pterm which llama-server

# List available models
pterm list | grep llama
```

---

## Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/v1/chat/completions` | Chat completions (OpenAI-compatible) |
| GET | `/v1/models` | List available models |
| GET | `/health` | Server health check |

---

## Models

| Model ID | VRAM | Description |
|----------|------|-------------|
| `gemma-4-31b-q4km` | 32GB | Single-GPU fit, fast inference |
| `gemma-4-26b-a4b-dual` | 64GB | Dual-GPU row-split, higher quality |

---

## Usage Examples

### Via Pterm CLI

```bash
# Start llama-server
pterm start llama-server

# Check health
curl http://localhost:8080/health

# List models
curl -s http://localhost:8080/v1/models | jq '.data[].id'
```

### Via Claude Code / JavaScript

```javascript
// Chat completion
const response = await fetch('http://localhost:8080/v1/chat/completions', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    model: 'gemma-4-31b-q4km',
    messages: [
      {role: 'system', content: 'You are a helpful AI assistant on B850.'},
      {role: 'user', content: 'Explain RDNA4 architecture.'}
    ],
    max_tokens: 1024,
    temperature: 0.7
  })
});

const data = await response.json();
console.log(data.choices[0].message.content);
```

### Via Curl

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma-4-31b-q4km",
    "messages": [{"role": "user", "content": "Hello from B850!"}],
    "max_tokens": 512
  }' | jq '.choices[0].message.content'
```

### Via Python (OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="sk-b850-local"  # Required but unused
)

response = client.chat.completions.create(
    model="gemma-4-31b-q4km",
    messages=[
        {"role": "system", "content": "You are a helpful AI assistant on B850."},
        {"role": "user", "content": "Explain AMD 3D V-Cache technology."}
    ],
    max_tokens=1024
)

print(response.choices[0].message.content)
```

---

## Hardware Configuration

```
CPU: AMD Ryzen 9850X3D (8C / 3D V-Cache)
GPU: 2x Radeon AI Pro R9700 (gfx1201)
VRAM: 64GB total (2x 32GB)
Backend: llama.cpp HIP (ROCm 7.1)
Fork: tlee933/llama.cpp-rdna4-gfx1201
```

**Note:** Stock Ollama ROCm v6 libs do NOT include gfx1201 kernels. This custom fork is required for RDNA4 support.

---

## Dual-GPU Mode

For models requiring >32GB VRAM:

```bash
llama-server \
  --model gemma-4-26b-a4b-dual.gguf \
  --tensor-split 0.5,0.5 \
  --split-mode row \
  --port 8080
```

---

## Metrics & Monitoring

Prometheus metrics available at `http://localhost:9835/metrics`:

```bash
# Scrape GPU metrics
curl -s http://localhost:9835/metrics | grep rocm_

# View in Grafana
# Dashboard: PMOVES GPU Metrics (datasource: prometheus:9835)
```

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLAMA_SERVER_PORT` | 8080 | API port |
| `LLAMA_SERVER_HOST` | 127.0.0.1 | Bind address |
| `LLAMA_GPU_LAYERS` | -1 | GPU offload (-1 = all) |
| `TENSOR_SPLIT` | - | Dual-GPU split (e.g., "0.5,0.5") |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Connection refused` | Start server: `pterm start llama-server` |
| `CUDA error` | Wrong backend — use `llama.cpp HIP` not CUDA |
| `Out of memory` | Use smaller model or enable dual-GPU mode |
| `Slow inference` | Check GPU utilization: `curl http://localhost:9835/metrics` |

---

## Related Files

- `pmoves/config/profiles/workstation-9850x3d-dual-r9700.yaml` — Hardware profile
- `pmoves/config/rooms/9850x3d-rdna4.room.studio.json` — Room manifest
- `pmoves/docs/P7_VSCODE_INTEGRATION.md` — VS Code integration guide
