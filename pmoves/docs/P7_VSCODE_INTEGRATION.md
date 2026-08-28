# P7 VS Code Claude Code Integration Guide

> **For:** B850 (Knuckles) and other PMOVES nodes
> **Purpose:** Document the integration path between VS Code Claude Code and Pinokio 7
> **Last updated:** 2026-05-19

---

## Overview

Pinokio 7 (P7) provides built-in agent capabilities that integrate with VS Code Claude Code through:
1. **Auto-Discovery:** The built-in `pinokio` skill discovers installed apps
2. **Pterm CLI:** Command-line interface to trigger Pinokio app launches
3. **OpenAI-Compatible APIs:** Local inference via llama-server

---

## Integration Paths

### 1. P7 Auto-Discovery (Built-in)

P7's Agent Interpreter automatically discovers apps installed in Pinokio. No additional configuration needed.

```bash
# List discoverable apps
pterm list

# Check if llama-server is available
pterm which llama-server
```

### 2. Claude Code → P7 Launcher

Trigger Pinokio app launches from within VS Code Claude Code sessions:

```javascript
// Via shell commands
!pterm start llama-server

// Check app status
!pterm status llama-server
```

### 3. Llama-Server Bridge (B850 Local Inference)

Configure Claude Code to use B850's local llama-server for inference:

**Option A: Environment Variables (Recommended)**
```bash
export OPENAI_BASE_URL="http://localhost:8080/v1"
export OPENAI_API_KEY="sk-b850-local"
```

**Option B: .claude/settings.json**
```json
{
  "env": {
    "OPENAI_BASE_URL": "http://localhost:8080/v1",
    "OPENAI_API_KEY": "sk-b850-local"
  }
}
```

**Option C: Per-Session (Claude Code)**
```
When prompted for API endpoint, use:
Base URL: http://localhost:8080/v1
API Key: sk-b850-local (or any value)
```

---

## B850-Specific Endpoints

| Service | Endpoint | Purpose |
|---------|----------|---------|
| Llama Server | `http://localhost:8080/v1` | OpenAI-compatible inference |
| Models List | `http://localhost:8080/v1/models` | Available models |
| Health Check | `http://localhost:8080/health` | Server status |
| ROCm Metrics | `http://localhost:9835/metrics` | Prometheus GPU metrics |

---

## Available Models (B850)

- `gemma-4-31b-q4km` — Single-GPU fit (32GB)
- `gemma-4-26b-a4b-dual` — Dual-GPU row-split (64GB total)

---

## Usage Examples

### Chat Completions via Fetch

```javascript
const response = await fetch('http://localhost:8080/v1/chat/completions', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    model: 'gemma-4-31b-q4km',
    messages: [
      {role: 'system', content: 'You are a helpful assistant on B850.'},
      {role: 'user', content: 'Hello from B850!'}
    ],
    max_tokens: 512
  })
});

const data = await response.json();
console.log(data.choices[0].message.content);
```

### Via Pterm Start

```bash
# Start llama-server
pterm start llama-server

# Check server health
curl -s http://localhost:8080/v1/models | jq '.data[].id'

# Run inference
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma-4-31b-q4km",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' | jq '.choices[0].message.content'
```

---

## TTS Integration (Cross-Node)

Route text-to-speech requests through Pinokio to remote TTS services:

```javascript
// Via P7's built-in routing
speak hello

// This routes through Pinokio to Ultimate-TTS-Studio on 5090
```

---

## Verification Steps

After setup, verify the integration:

```bash
# 1. Check Pinokio version
cat ~/.pinokio/config.json | jq '.version'

# 2. Verify llama-server is running
curl -s http://localhost:8080/v1/models | jq '.data[].id'

# 3. Test inference
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemma-4-31b-q4km","messages":[{"role":"user","content":"test"}]}' \
  | jq '.choices[0].message.content'

# 4. Check P7 discovery
pterm which llama-server
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Connection refused` on :8080 | Start llama-server: `pterm start llama-server` |
| `pterm: command not found` | Pinokio not in PATH — use full path to `~/.pinokio/bin/pterm` |
| Model not found | Check available models: `curl http://localhost:8080/v1/models` |
| CORS errors | Claude Code may need `localhost` → `127.0.0.1` or vice versa |

---

## Related Documentation

- `pmoves/configs/tac_trees/pinokio-p7.tac.yaml` — P7 integration tracking
- `pmoves/config/rooms/catalog.json` — Room registry
- `pmoves/config/profiles/workstation-9850x3d-dual-r9700.yaml` — B850 hardware profile
- `.claude/settings.json` — VS Code Claude Code configuration

---

## Next Steps

1. ✅ B850 added to P7 TAC tree
2. ✅ Room manifest created and registered
3. ✅ Integration guide created (this file)
4. ⏳ Create SKILL.md for P7 auto-discovery
5. ⏳ Document Hermes deprecation
