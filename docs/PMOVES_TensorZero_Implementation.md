# PMOVES.AI TensorZero Implementation Guide
**Gateway Architecture & Robustness Enhancement**

This document details the implementation of **TensorZero** within the PMOVES.AI stack. TensorZero serves as the unified Model Gateway, providing a single, high-performance interface for all LLM interactions, ensuring robustness, standardized observability, and seamless model fallbacks.

---

## 1. Gateway Architecture

The TensorZero Gateway acts as a localized proxy that sits between our applications (Agent Zero, Archon, Hi-RAG) and the underlying Model Providers.

### The "Local-First" Routing Philosophy
PMOVES prioritizes models in this strict order to optimize cost and credit usage:
1.  **Tier 1: Local / Free** (Ollama, Cloudflare Workers AI) - *Always try first.*
2.  **Tier 2: Specific Plans** (Claude Code, OpenRouter, GLM Coding) - *Use for complex tasks.*
3.  **Tier 3: Cloud Fallback** (Based on API Credit Availability):
    *   **Priority 1**: Google Gemini (Deep budget)
    *   **Priority 2**: Anthropic (Secondary budget)
    *   **Priority 3**: OpenAI (Emergency backup)

---

## 2. Configuration (`tensorzero.toml`)

The core configuration defines how models are routed. We use **Variant-Based Routing** to implement the hierarchy.

### 2.1 Provider Configuration
Define all available providers, mapping them to their specific API keys (loaded from env).

```toml
[gateway]
bind_address = "0.0.0.0:3000"

# --- Tier 1: Local & Free ---
[providers.ollama]
type = "ollama"
url = "http://host.docker.internal:11434"

[providers.cloudflare]
type = "cloudflare"
url = "https://api.cloudflare.com/client/v4/accounts/${env.CF_ACCOUNT_ID}/ai/v1"
api_key = "${env.CF_API_TOKEN}"

# --- Tier 2: Specific Plans ---
[providers.openrouter]
type = "openai"
url = "https://openrouter.ai/api/v1"
api_key = "${env.OPENROUTER_API_KEY}"

[providers.glm]
type = "openai"
url = "https://open.bigmodel.cn/api/paas/v4/"
api_key = "${env.GLM_API_KEY}"

# --- Tier 3: Cloud Fallback ---
[providers.google_gemini]
type = "google" # TensorZero supports Google Vertex/Gemini
api_key = "${env.GOOGLE_API_KEY}"

[providers.anthropic]
type = "anthropic"
api_key = "${env.ANTHROPIC_API_KEY}"

[providers.openai]
type = "openai"
api_key = "${env.OPENAI_API_KEY}"
```

### 2.2 Model Definitions
Map abstract model names to provider-specific strings.

```toml
[models.qwen-local]
provider = "ollama"
model = "qwen2.5:32b"

[models.llama-cf]
provider = "cloudflare"
model = "@cf/meta/llama-3-8b-instruct"

[models.gemini-pro]
provider = "google_gemini"
model = "gemini-1.5-pro"

[models.claude-sonnet]
provider = "anthropic"
model = "claude-3-5-sonnet-20240620"

[models.gpt-4o]
provider = "openai"
model = "gpt-4o"
```

### 2.3 Function Routing (The Logic)
Define "Functions" (business capabilities) and route them through the tiers.

```toml
# General Chat Routing
[functions.chat]
type = "chat"
variants = ["local", "free_tier", "cloud_gemini", "cloud_anthropic", "cloud_openai"]

[functions.chat.variants.local]
model = "models.qwen-local"
weight = 1.0

[functions.chat.variants.free_tier]
model = "models.llama-cf"
weight = 0.5

# Cloud Fallback Chain
[functions.chat.variants.cloud_gemini]
model = "models.gemini-pro"
weight = 0.4  # Primary Cloud

[functions.chat.variants.cloud_anthropic]
model = "models.claude-sonnet"
weight = 0.3  # Secondary

[functions.chat.variants.cloud_openai]
model = "models.gpt-4o"
weight = 0.1  # Last Resort
```

```toml
# Embedding: Local First
[functions.embed]
type = "embedding"
variants = ["local_embed"]

[functions.embed.variants.local_embed]
provider = "ollama"
model = "qwen3-embedding:4b"
```

---

## 3. Inference API Reference

The Gateway exposes a standardized `/inference` endpoint.

### 3.1 Python SDK Example
```python
from tensorzero import AsyncTensorZeroGateway

async with await AsyncTensorZeroGateway.build_http(gateway_url="http://localhost:3000") as client:
    # This call tries: Local -> Cloudflare -> Gemini -> Anthropic -> OpenAI
    result = await client.inference(
        function_name="chat",
        input={
            "messages": [{"role": "user", "content": "Explain quantum computing."}]
        }
    )
```

---

## 3. Exhaustive Service Integration Matrix

This matrix encompasses all 55+ services in the PMOVES.AI ecosystem, defining their integration path into the TensorZero/Geometry architecture.

### Legend
- **MIGRATE**: Service logic must change to use TensorZero Gateway.
- **INTEGRATE**: Service must emit/consume Geometry Bus (NATS) events.
- **NETWORK**: Service only needs network tier reassignment (no logic change).
- **OBSERVE**: Service is a passive component; no action required.

### 3.1 Core Infrastructure
| Service | Current Status | Integration Strategy | Action Item |
| :--- | :--- | :--- | :--- |
| `tensorzero-gateway` | **NEW** | **CORE**: The central hub. | Deploy & Secure |
| `tensorzero-clickhouse` | **NEW** | **CORE**: Observability backend. | Deploy in `data_tier` |
| `tensorzero-ui` | **NEW** | **CORE**: Admin dashboard. | Deploy in `monitoring_tier` |
| `nats` | **EXISTING** | **CORE**: The Geometry Bus carrier. | Ensure `bus_tier` isolation |

### 3.2 Agent Orchestration
| Service | Integration Strategy | Action Item |
| :--- | :--- | :--- |
| `agent-zero` | **MIGRATE** | Point `OPENAI_BASE_URL` to Gateway. Use `tensorzero::model` names. | Update `.env` |
| `archon` | **MIGRATE** | Same as Agent Zero. Ensure all sub-agents route through Gateway. | Update `.env` |
| `mesh-agent` | **NETWORK** | Ensure connectivity to Gateway for health checks. | Verify Network |
| `channel-monitor` | **INTEGRATE** | Publish `content.new.v1` as Geometry Packet. | Add NATS logic |

### 3.3 Knowledge & Retrieval
| Service | Integration Strategy | Action Item |
| :--- | :--- | :--- |
| `hi-rag-gateway-v2` | **ENHANCE** | Use `tensorzero::embedding` for vectorization. | Update `config.yaml` |
| `hi-rag-gateway-v2-gpu` | **ENHANCE** | Same as v2. | Update `config.yaml` |
| `hi-rag-gateway` (v1) | **DEPRECATE** | Legacy. Route traffic to v2 or Gateway. | Audit usage |
| `deepresearch` | **MIGRATE** | **Critical**: Move high-volume queries to Gateway to use Semantic Caching. | Update `.env` |
| `supaserch` | **INTEGRATE** | Ensure outputs are valid `geometry.visualization.ready.v1` packets. | Verify Schema |
| `notebook-sync` | **NETWORK** | Isolated in `app_tier`. | Network Config |

### 3.4 Media Ingestion & Processing
| Service | Integration Strategy | Action Item |
| :--- | :--- | :--- |
| `pmoves-yt` | **INTEGRATE** | Emit `video.ingested.v1` events to Bus. | Verify NATS |
| `ffmpeg-whisper` | **NETWORK** | Compute heavy. Isolate in `app_tier` + GPU access. | Verify Resources |
| `media-video` | **INTEGRATE** | Analysis results must be Geometry Packets. | Update Output Logic |
| `media-audio` | **INTEGRATE** | Emotion analysis results must be Geometry Packets. | Update Output Logic |
| `extract-worker` | **ENHANCE** | Use TensorZero for `json_mode` extraction tasks. | Update LLM Client |
| `pdf-ingest` | **NETWORK** | Standard isolation. | Network Config |
| `langextract` | **NETWORK** | Standard isolation. | Network Config |
| `bgutil-pot-provider` | **OBSERVE** | Helper utility. | No Change |

### 3.5 Utilities & Integration
| Service | Integration Strategy | Action Item |
| :--- | :--- | :--- |
| `presign` | **OBSERVE** | Essential for serving artifact URLs to UI. | No Change |
| `render-webhook` | **INTEGRATE** | ComfyUI images should be emitted as Visual Geometry Packets. | Add NATS Publish |
| `publisher-discord` | **INTEGRATE** | Consume Geometry Packets and render rich embeds. | Update Consumer |
| `jellyfin-bridge` | **NETWORK** | Isolated in `api_tier` (ingress) / `app_tier`. | Network Config |
| `retrieval-eval` | **MIGRATE** | Use TensorZero as the "Judge" model for evals. | Update LLM Client |
| `flute-gateway` | **INTEGRATE** | Voice streams emit `geometry.event.v1`. | Add NATS Publish |
| `n8n` | **MIGRATE** | Configure N8N AI nodes to use TensorZero Gateway. | Update N8N Creds |
| `cloudflared` | **NETWORK** | Strict egress control. | Network Config |

### 3.6 Data Storage (Supabase/Internal)
| Service | Integration Strategy | Action Item |
| :--- | :--- | :--- |
| `postgres` | **NETWORK** | Strict `data_tier`. No direct external access. | Network Config |
| `postgrest` | **NETWORK** | Expose only to `api_tier` and `app_tier`. | Network Config |
| `qdrant` | **NETWORK** | Strict `data_tier`. | Network Config |
| `neo4j` | **NETWORK** | Strict `data_tier`. | Network Config |
| `meilisearch` | **NETWORK** | Strict `data_tier`. | Network Config |
| `minio` | **NETWORK** | Strict `data_tier` (API exposed to App/API tiers). | Network Config |
| `pmoves-ollama` | **NETWORK** | Local LLM. Keep in `app_tier`. | Network Config |

### 3.7 Monitoring Stack
| Service | Integration Strategy | Action Item |
| :--- | :--- | :--- |
| `prometheus` | **INTEGRATE** | Scrape TensorZero `/metrics`. | Add Scrape Config |
| `grafana` | **ENHANCE** | Import TensorZero dashboards. | Dashboard Import |
| `loki` | **OBSERVE** | TensorZero logs via stdout. | No Change |
| `promtail` | **OBSERVE** | Log shipping. | No Change |
| `cadvisor` | **OBSERVE** | Container metrics. | No Change |
| `blackbox` | **OBSERVE** | Health checks. | No Change |
| `node-exporter`| **OBSERVE** | Host metrics. | No Change |

### 3.8 Additional Services (Invidious/Grayjay/Etc)
| Service | Integration Strategy | Action Item |
| :--- | :--- | :--- |
| `invidious-stack` | **NETWORK** | Isolated group. | Network Config |
| `grayjay-stack` | **NETWORK** | Isolated group. | Network Config |
| `nats-echo-*` | **OBSERVE** | Debug tools. | No Change |

---

## 4. Security Hardening Compliance

In alignment with `docs/PMOVES.AI-Edition-Hardened-Full.md`, all new components must adhere to the following **Production Hardening Guidelines**:

1.  **User Context**:
    -   **TensorZero/AgentGym**: `user: "65532:65532"` (Distroless non-root).
    -   **Nginx/ClickHouse**: `user: "101:101"` (Service specific non-root).
2.  **Filesystem**:
    -   `read_only: true` by default.
    -   Writable volumes mounted only at specific paths (e.g., `/var/lib/clickhouse`).
3.  **Capability Dropping**:
    -   `cap_drop: [ALL]` for standard containers.
    -   `security_opt: [no-new-privileges:true]`.
4.  **Network Isolation**:
    -   No service sits on the "legacy" flat network.
    -   All services must explicitly declare `api_tier`, `app_tier`, `data_tier`, or `bus_tier`.

---

## 6. Hugging Face Training & Publishing Pipeline

PMOVES leverages the Hugging Face ecosystem to close the "Simulation to Reality" loop by publishing high-quality datasets and fine-tuned models.

### 6.1 Dataset Creation (The "Memory" Loop)
**Source**: All agent actions emitted to the **Geometry Bus** (NATS `geometry.event.v1`) are captured.
**Process**:
1.  **Accumulation**: `agentgym-rl-coordinator` buffers "CHIT" packets (successful trajectories).
2.  **Filtering**: Only high-fitness trajectories (verified code, successful research) are kept.
3.  **Publishing**:
    *   **Format**: Parquet / JSONL.
    *   **Destination**: `HuggingFace Hub` (e.g., `PMOVES/geometry-trajectories-v1`).
    *   **Frequency**: Batch updates (e.g., every 1000 successful episodes).

### 6.2 Model Training & Publishing (The "Skill" Loop)
**Engine**: **AgentGym-RL** performs PPO/RLHF training on the collected datasets.
**Artifacts**:
1.  **LoRA Adapters**: Lightweight fine-tunes on top of base models (e.g., `qwen2.5-32b-pmoves-lora`).
2.  **Full Finetunes**: Merged models for edge deployment.
3.  **Publishing**:
    *   Automatic push to HF Hub via `huggingface_hub` Python SDK.
    *   Versioning tagged with Git SHA and Training Run ID.

### 6.3 Authentication & Configuration
**Requirements**:
*   `HF_TOKEN` (Write access) in specific service environments.
*   **Infrastructure**: Persistent volume for `~/.cache/huggingface` to speed up training starts.

---

## 7. Next Steps

1.  **Deploy Infrastructure**: Run the updated `docker-compose` stack with TensorZero + ClickHouse + AgentGym.
2.  **Migrate Agent Zero**: Update environment variables to point to the Gateway.
3.  **Verify Observability**: access the TensorZero UI and confirm Agent Zero traces are appearing.
4.  **Launch Math UI**: Verify Hyperdimensions is accessible and rendering default geometry.
5.  **Authenticate HF**: Set `HF_TOKEN` in `.env.local` and verify `agentgym-rl-coordinator` can push a test dataset.
