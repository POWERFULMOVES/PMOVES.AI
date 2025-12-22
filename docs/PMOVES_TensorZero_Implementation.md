# PMOVES.AI TensorZero Implementation Guide
**Gateway Architecture & Robustness Enhancement**

This document details the implementation of **TensorZero** within the PMOVES.AI stack. TensorZero serves as the unified Model Gateway, providing a single, high-performance interface for all LLM interactions, ensuring robustness, standardized observability, and seamless model fallbacks.

---

## 1. Gateway Architecture

The TensorZero Gateway acts as a localized proxy that sits between our applications (Agent Zero, Archon, Hi-RAG) and the underlying Model Providers (OpenAI, Anthropic, vLLM, Ollama).

### Key Benefits
-   **Unified API:** Write code once using the standardized `/inference` endpoint; switch models via configuration.
-   **Low Latency:** Written in Rust, adding <1ms overhead.
-   **Robustness:** Automatic fallbacks (e.g., if `gpt-4` fails, transparently route to `claude-3-opus`).
-   **Observability:** All inference inputs, outputs, and latency metrics are structured and stored in **ClickHouse** (configured via environment variables), with OpenTelemetry tracing enabled.

---

## 2. Configuration (`tensorzero.toml`)

The core configuration defines how models are routed and how tools are structured.

### 2.1 Model & Provider Definition
Define abstract "Functions" (business logic) that map to specific "Models" and "Providers".

```toml
[gateway]
bind_address = "0.0.0.0:3000"

[functions.chat]
type = "chat"

[models.gpt-4o]
routing = ["openai-gpt-4o"]

[providers.openai-gpt-4o]
type = "openai"
model = "gpt-4o"
api_key = "${env.OPENAI_API_KEY}"
```

### 2.2 Tool Definitions (Crucial for Robustness)
Defining tools in configuration ensures strictly typed schemas, reducing hallucinated function calls.

```toml
# Define the tool globally
[tools.get_weather]
description = "Get the current weather for a location"
parameters = { type = "object", properties = { location = { type = "string" }, unit = { type = "string", enum = ["celsius", "fahrenheit"] } }, required = ["location"] }

# Attach tool to a function
[functions.agent_chat]
type = "chat"
tools = ["get_weather"]
```

---

## 3. Inference API Reference

The Gateway exposes a standardized `/inference` endpoint.

### 3.1 Python SDK Example
```python
from tensorzero import AsyncTensorZeroGateway

async with await AsyncTensorZeroGateway.build_http(gateway_url="http://localhost:3000") as client:
    result = await client.inference(
        function_name="agent_chat",
        input={
            "system": "You are a helpful assistant.",
            "messages": [
                {"role": "user", "content": "What's the weather in New York?"}
            ]
        }
    )
    print(result)
```

### 3.2 HTTP/cURL Example
```bash
curl -X POST http://localhost:3000/inference \
  -H "Content-Type: application/json" \
  -d '{
    "function_name": "agent_chat",
    "input": {
      "system": "You are a helpful assistant.",
      "messages": [
        {"role": "user", "content": "Draft an email to the team."}
      ]
    },
    "stream": true
  }'
```

### 3.3 Response Structure
Responses are standardized, regardless of the underlying provider.

```json
{
  "inference_id": "uuid-...",
  "content": [
    {
      "type": "text",
      "text": "Here is the draft email..."
    }
  ],
  "usage": {
    "input_tokens": 50,
    "output_tokens": 120
  }
}
```

---

## 4. Best Practices for Robustness

### 4.1 Fallbacks
Configure generic functions to fallback to cheaper or more reliable models on failure.

```toml
[functions.summarize]
type = "chat"
fallback_variants = ["haiku-3.5", "llama-3-8b"]
```

### 4.2 Semantic Caching
Enable caching to serve identical queries instantly without hitting the provider, saving cost and latency.

```toml
[gateway]
cache_enabled = true
```

### 4.3 Observability
Leverage the built-in ClickHouse integration to specific queries like:
-   "Which tools are failing most often?"
-   "What is the P99 latency of the `agent_chat` function?"

---

*For full configuration options, refer to the [TensorZero Documentation](https://www.tensorzero.com/docs).*
