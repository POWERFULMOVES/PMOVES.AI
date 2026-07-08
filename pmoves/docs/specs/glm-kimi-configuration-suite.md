# GLM-4/KIMI-K2 Configuration Suite — Master Document

**Version:** 2.0.0  
**Date:** 2026-07-09  
**Author:** PMOVES Model Configuration Engineer  
**Scope:** Complete model suit specifications for GLM-4 family (air/flash/plus/4.7) and GLM-5 family (turbo/5.1) plus KIMI-K2 integration  
**Status:** PRODUCTION SPEC — ready for implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [GLM Hub Architecture](#2-glm-hub-architecture)
3. [GLM-4-Air](#3-glm-4-air)
4. [GLM-4-Flash](#4-glm-4-flash)
5. [GLM-4-Plus](#5-glm-4-plus)
6. [GLM-4.7](#6-glm-47)
7. [GLM-5-Turbo](#7-glm-5-turbo)
8. [GLM-5.1](#8-glm-51)
9. [KIMI-K2 Integration](#9-kimi-k2-integration)
10. [BGE-M3 Hybrid Caching](#10-bge-m3-hybrid-caching)
11. [Cross-Model Fallback Matrix](#11-cross-model-fallback-matrix)
12. [TensorZero Routing Configuration](#12-tensorzero-routing-configuration)
13. [Appendix A: Model Comparison Matrix](#appendix-a-model-comparison-matrix)
14. [Appendix B: Provider Cascade Configuration](#appendix-b-provider-cascade-configuration)
15. [Appendix C: Environment Variable Reference](#appendix-c-environment-variable-reference)

---

## 1. Executive Summary

This document defines the complete configuration suite for the **GLM-4/5 and KIMI-K2 model families** in the PMOVES.AI multi-agent orchestration platform. It specifies 7 production model suits (6 GLM variants + 1 KIMI), their harness mappings, CGP state vectors, fallback chains, and TensorZero routing configuration.

**Key architectural decisions:**
- **Hub-and-spoke model:** GLM-5.1 serves as the central hub; all other models are spokes with defined fallback paths
- **BGE-M3 hybrid caching:** Dense (1024d) + sparse + ColBERT vectors for semantic cache precision
- **KIMI-K2 as long-context specialist:** 256K context window with 8 variants for different use cases
- **CGP state vectors:** Every model carries a `{delta, Hz, kappa, A, F}` resonance signature
- **Three-layer fallback:** Local GLM → Cloud GLM → KIMI → OpenRouter (cascading degradation)

**Models covered:**

| Model | Family | Role | Context | Status |
|-------|--------|------|---------|--------|
| GLM-4-Air | GLM-4 | Lightweight, edge | 128K | PRODUCTION |
| GLM-4-Flash | GLM-4 | Fastest inference | 128K | PRODUCTION |
| GLM-4-Plus | GLM-4 | Premium quality | 128K | PRODUCTION |
| GLM-4.7 | GLM-4 | Balanced coding | 200K | PRODUCTION |
| GLM-5-Turbo | GLM-5 | High-throughput | 128K | PRODUCTION |
| GLM-5.1 | GLM-5 | Long-horizon autonomy | 202K | PRODUCTION |
| KIMI-K2 | KIMI | Long-context specialist | 256K | PRODUCTION |

---

## 2. GLM Hub Architecture

### Hub-and-Spoke Design

```
                    GLM-5.1 (HUB)
                   /    |    \
                  /     |     \
            GLM-5-Turbo |      KIMI-K2
                |       |         |
            GLM-4.7     |     (long-context
                |       |      specialist)
            GLM-4-Plus  |
                |       |
            GLM-4-Flash |
                |       |
            GLM-4-Air   |
                        |
                   OpenRouter
                   (universal fallback)
```

### Hub Responsibilities (GLM-5.1)

- Central routing decision point for all GLM-family requests
- Default model for complex multi-step reasoning
- Longest context window (202K) for deep document analysis
- Highest parameter count (744B total / 40B active)
- Fallback destination for all other GLM models

### Spoke Responsibilities

| Model | Primary Use Case | Fallback To |
|-------|-----------------|-------------|
| GLM-4-Air | High-volume edge inference | GLM-4-Flash |
| GLM-4-Flash | Low-latency streaming | GLM-4-Air |
| GLM-4-Plus | Critical accuracy tasks | GLM-4.7 |
| GLM-4.7 | Agentic coding, long docs | GLM-4-Plus |
| GLM-5-Turbo | Multi-step workflows | GLM-5.1 |
| KIMI-K2 | Long-context, Chinese | GLM-4.7 |

---

## 3. GLM-4-Air

### Model Specification

```yaml
model_suit:
  name: glm-4-air
  provider: zhipu_ai
  base_url: "https://api.z.ai/v1"
  api_key_env: ZAI_API_KEY
  
  architecture:
    type: dense
    total_params: "9B"
    active_params: "9B"
    attention: standard
    
  context:
    max_window: 128000
    effective_window: 32000
    working_window: 16000
    
  defaults:
    temperature: 0.7
    top_p: 0.95
    max_tokens: 4096
    frequency_penalty: 0.0
    presence_penalty: 0.0
    
  advanced:
    tool_call_parser: glm4
    enable_thinking: false
    mtp_steps: 1
```

### Harness Mappings

| Harness | Temperature | Top P | Max Tokens | System Prompt | Use Case |
|---------|-------------|-------|------------|---------------|----------|
| voice_synthesis | 0.7 | 0.95 | 256 | conversational_narrator | Prosodic voice output |
| documentation | 0.6 | 0.95 | 4096 | conversational_writer | Technical docs |
| lightweight_coding | 0.6 | 0.93 | 2048 | directive_engineer | Simple code tasks |
| monitoring | 0.2 | 0.85 | 1024 | directive_infrastructure | System alerts |
| quick_chat | 0.8 | 0.98 | 1024 | conversational_assistant | Casual interaction |

### CGP State Vector

```yaml
cgp_state_vector:
  delta: 0.4      # Variance - moderate exploration
  Hz: 0.1         # Frequency - low, grounding
  kappa: 1.5      # Coherence - medium-high
  A: 0.4          # Amplitude - moderate energy
  F: 0.05         # Form - stable, low volatility
```

### Fallback Chain

```
GLM-4-Air → GLM-4-Flash → GLM-4-Plus → GLM-5.1 → OpenRouter
```

---

## 4. GLM-4-Flash

### Model Specification

```yaml
model_suit:
  name: glm-4-flash
  provider: zhipu_ai
  base_url: "https://api.z.ai/v1"
  api_key_env: ZAI_API_KEY
  
  architecture:
    type: dense
    total_params: "9B"
    active_params: "9B"
    attention: standard
    
  context:
    max_window: 128000
    effective_window: 32000
    working_window: 8000
    
  defaults:
    temperature: 0.7
    top_p: 0.95
    max_tokens: 4096
    frequency_penalty: 0.0
    presence_penalty: 0.0
    
  advanced:
    tool_call_parser: glm4
    enable_thinking: false
    mtp_steps: 1
```

### Harness Mappings

| Harness | Temperature | Top P | Max Tokens | System Prompt | Use Case |
|---------|-------------|-------|------------|---------------|----------|
| quick_chat | 0.8 | 0.98 | 1024 | conversational_assistant | Fast responses |
| streaming_response | 0.7 | 0.95 | 2048 | conversational_narrator | Real-time output |
| lightweight_coding | 0.6 | 0.93 | 2048 | directive_engineer | Quick code |

### CGP State Vector

```yaml
cgp_state_vector:
  delta: 0.5      # Variance - higher exploration
  Hz: 0.2         # Frequency - slightly elevated
  kappa: 1.2      # Coherence - lower (faster = less precise)
  A: 0.5          # Amplitude - medium energy
  F: 0.1          # Form - moderate volatility
```

### Fallback Chain

```
GLM-4-Flash → GLM-4-Air → GLM-4-Plus → GLM-5.1 → OpenRouter
```

---

## 5. GLM-4-Plus

### Model Specification

```yaml
model_suit:
  name: glm-4-plus
  provider: zhipu_ai
  base_url: "https://api.z.ai/v1"
  api_key_env: ZAI_API_KEY
  
  architecture:
    type: moe
    total_params: "130B"
    active_params: "130B"
    attention: standard
    
  context:
    max_window: 128000
    effective_window: 64000
    working_window: 32000
    
  defaults:
    temperature: 1.0
    top_p: 0.95
    max_tokens: 4096
    frequency_penalty: 0.0
    presence_penalty: 0.0
    
  advanced:
    tool_call_parser: glm4
    enable_thinking: true
    mtp_steps: 1
```

### Harness Mappings

| Harness | Temperature | Top P | Max Tokens | System Prompt | Use Case |
|---------|-------------|-------|------------|---------------|----------|
| code_review | 0.15 | 0.80 | 16384 | directive_critical | Thorough review |
| complex_analysis | 0.3 | 0.90 | 8192 | directive_analytical | Deep analysis |
| documentation | 0.6 | 0.95 | 4096 | conversational_writer | Quality docs |

### CGP State Vector

```yaml
cgp_state_vector:
  delta: 0.2      # Variance - low (precise)
  Hz: 0.05        # Frequency - very low (grounding)
  kappa: 2.0      # Coherence - very high (premium quality)
  A: 0.3          # Amplitude - lower energy (deliberate)
  F: 0.03         # Form - very stable
```

### Fallback Chain

```
GLM-4-Plus → GLM-4.7 → GLM-5.1 → OpenRouter
```

---

## 6. GLM-4.7

### Model Specification

```yaml
model_suit:
  name: glm-4.7
  provider: zhipu_ai
  base_url: "https://api.z.ai/v1"
  api_key_env: ZAI_API_KEY
  
  architecture:
    type: moe
    total_params: "130B"
    active_params: "130B"
    attention: standard
    
  context:
    max_window: 200000
    effective_window: 128000
    working_window: 64000
    
  defaults:
    temperature: 0.7
    top_p: 0.95
    max_tokens: 16384
    frequency_penalty: 0.0
    presence_penalty: 0.0
    
  advanced:
    tool_call_parser: glm47
    enable_thinking: true
    mtp_steps: 1
```

### Harness Mappings

| Harness | Temperature | Top P | Max Tokens | System Prompt | Use Case |
|---------|-------------|-------|------------|---------------|----------|
| agentic_coding | 0.7 | 0.95 | 16384 | directive_engineer | Complex coding |
| long_context_analysis | 0.2 | 0.85 | 8192 | directive_analytical | Document analysis |
| debugging | 0.3 | 0.90 | 8192 | directive_debugger | Bug fixing |
| architecture_planning | 0.4 | 0.90 | 16384 | directive_architect | System design |

### CGP State Vector

```yaml
cgp_state_vector:
  delta: 0.3      # Variance - moderate-low
  Hz: 0.08        # Frequency - low (focus)
  kappa: 1.8      # Coherence - high (coding requires precision)
  A: 0.35         # Amplitude - moderate
  F: 0.04         # Form - stable
```

### Fallback Chain

```
GLM-4.7 → GLM-4-Plus → GLM-5.1 → OpenRouter
```

---

## 7. GLM-5-Turbo

### Model Specification

```yaml
model_suit:
  name: glm-5-turbo
  provider: zhipu_ai
  base_url: "https://api.z.ai/v1"
  api_key_env: ZAI_API_KEY
  
  architecture:
    type: moe
    total_params: "355B"
    active_params: "32B"
    attention: standard
    
  context:
    max_window: 128000
    effective_window: 32000
    working_window: 16000
    
  defaults:
    temperature: 1.0
    top_p: 0.95
    max_tokens: 8192
    frequency_penalty: 0.0
    presence_penalty: 0.0
    
  advanced:
    tool_call_parser: glm47
    enable_thinking: true
    mtp_steps: 1
```

### Harness Mappings

| Harness | Temperature | Top P | Max Tokens | System Prompt | Use Case |
|---------|-------------|-------|------------|---------------|----------|
| workflow_execution | 0.8 | 0.95 | 8192 | directive_engineer | Multi-step tasks |
| code_generation | 0.7 | 0.95 | 16384 | directive_engineer | Code writing |
| multi_step_reasoning | 1.0 | 0.95 | 8192 | directive_reasoner | Complex reasoning |

### CGP State Vector

```yaml
cgp_state_vector:
  delta: 0.5      # Variance - moderate-high (creative)
  Hz: 0.15        # Frequency - elevated (turbo)
  kappa: 1.4      # Coherence - medium (balance speed/quality)
  A: 0.5          # Amplitude - medium-high
  F: 0.08         # Form - moderate volatility
```

### Fallback Chain

```
GLM-5-Turbo → GLM-5.1 → GLM-4-Plus → OpenRouter
```

---

## 8. GLM-5.1

### Model Specification

```yaml
model_suit:
  name: glm-5.1
  provider: zhipu_ai
  base_url: "https://api.z.ai/v1"
  api_key_env: ZAI_API_KEY
  
  architecture:
    type: moe
    total_params: "744B"
    active_params: "40B"
    attention: standard
    
  context:
    max_window: 202752
    effective_window: 128000
    working_window: 64000
    
  defaults:
    temperature: 1.0
    top_p: 0.95
    max_tokens: 131072
    frequency_penalty: 0.0
    presence_penalty: 0.0
    
  advanced:
    tool_call_parser: glm47
    enable_thinking: true
    mtp_steps: shared
```

### Harness Mappings

| Harness | Temperature | Top P | Max Tokens | System Prompt | Use Case |
|---------|-------------|-------|------------|---------------|----------|
| deep_debugging | 0.3 | 0.90 | 131072 | directive_debugger | Deep debugging |
| system_engineering | 0.7 | 0.95 | 8192 | directive_engineer | System architecture |
| long_session | 1.0 | 0.95 | 131072 | directive_architect | Extended work |
| refactoring | 0.5 | 0.92 | 16384 | directive_refactorer | Code refactoring |

### CGP State Vector

```yaml
cgp_state_vector:
  delta: 0.35     # Variance - moderate (balanced)
  Hz: 0.1         # Frequency - moderate (sustained)
  kappa: 1.6      # Coherence - medium-high (quality)
  A: 0.4          # Amplitude - moderate
  F: 0.06         # Form - moderate stability
```

### Fallback Chain

```
GLM-5.1 → GLM-5-Turbo → GLM-4-Plus → OpenRouter
```

---

## 9. KIMI-K2 Integration

### Model Specification

```yaml
model_suit:
  name: kimi-k2
  provider: moonshot_ai
  base_url: "https://api.moonshot.cn/v1"
  api_key_env: MOONSHOT_API_KEY
  legacy_api_key_env: KIMI_API_KEY
  legacy_sunset_date: "2026-10-01"
  
  architecture:
    type: moe
    total_params: "1T"
    active_params: "32B"
    num_experts: 384
    selected_experts: 8
    shared_experts: 1
    attention: MLA
    layers: 61
    hidden_size: 7168
    heads: 64
    vocab_size: 160000
    
  context:
    max_window: 256000
    base_window: 128000
    effective_window: 200000
    working_window: 64000
    
  defaults:
    temperature: 0.7
    top_p: 0.95
    min_p: 0.01
    max_tokens: 4096
    frequency_penalty: 0.0
    presence_penalty: 0.0
    expert_topk: 8
```

### Variants (8 configurations)

| Variant | Context | Special Features | Use Case |
|---------|---------|------------------|----------|
| k2-instruct | 128K | General-purpose | Chat, tool use |
| k2-0905 | 256K | Extended context | Large documents |
| k2-thinking | 256K | Chain-of-thought | Deep reasoning |
| k2.5 | 256K | Multimodal, MoonViT | Vision + text |
| k2.6 | 256K | Enhanced reasoning | Complex analysis |
| k2.7-code | 256K | Code-specialized | Programming |
| dev-72b | 128K | Dense, Qwen2.5-72B base | Coding (efficient) |
| linear | 128K | KDA attention, 48B/3B | Efficient inference |

### Harness Mappings

| Harness | Variant | Temperature | Top P | Max Tokens | System Prompt |
|---------|---------|-------------|-------|------------|---------------|
| long_context_research | k2-0905 | 0.3 | 0.90 | 8192 | directive_researcher |
| chinese_language | k2-instruct | 0.5 | 0.93 | 4096 | directive_cultural_aware |
| agentic_coding | dev-72b | 0.7 | 0.95 | 16384 | directive_engineer |
| deep_reasoning | k2-thinking | 1.0 | 0.95 | 8192 | directive_reasoner |
| voice_synthesis | k2-instruct | 0.8 | 0.95 | 512 | conversational_emotive |

### CGP State Vector

```yaml
cgp_state_vector:
  delta: 0.45     # Variance - moderate (adaptable)
  Hz: 0.12        # Frequency - moderate (flexible)
  kappa: 1.3      # Coherence - medium (long context = more noise)
  A: 0.45         # Amplitude - moderate
  F: 0.06         # Form - moderate stability
```

### Fallback Chain

```
KIMI-K2 → GLM-4.7 → GLM-5.1 → OpenRouter
```

---

## 10. BGE-M3 Hybrid Caching

### Architecture

The BGE-M3 embedding model provides **three concurrent vector types** for semantic caching:

| Vector Type | Dimension | Purpose | Weight |
|-------------|-----------|---------|--------|
| Dense | 1024 | General semantic similarity | 0.5 |
| Sparse | vocabulary-sized | Keyword/BM25 overlap | 0.3 |
| ColBERT | 1024 × seq_len | Token-level fine-grained match | 0.2 |

### Hybrid Scoring Formula

```python
score = (0.5 * cosine_similarity(dense_query, dense_cache)) +
        (0.3 * sparse_overlap(sparse_query, sparse_cache)) +
        (0.2 * colbert_maxsim(colbert_query, colbert_cache))
```

### Cache Configuration

```yaml
semantic_cache:
  embedding_model: "BAAI/bge-m3"
  embedding_dim: 1024
  similarity_threshold: 0.90
  ttl_chat: 300      # 5 minutes
  ttl_embedding: 3600 # 1 hour
  max_entries: 10000
  eviction_policy: "lru"  # TTL + LRU hybrid
  
  vector_storage:
    dense: pgvector    # HNSW index
    sparse: jsonb      # PostgreSQL JSONB
    colbert: jsonb     # PostgreSQL JSONB
    
  hot_swap:
    enabled: true
    auto_invalidate: true  # Flush on model change
```

### Integration with Model Suits

| Model Suit | Embedding Trigger | Cache Hit Action |
|------------|-------------------|-----------------|
| GLM-4-Air | quick_chat, voice_synthesis | Return cached, publish token savings |
| GLM-4-Plus | code_review, complex_analysis | Validate response quality before cache |
| GLM-5.1 | deep_debugging, long_session | Cache with extended TTL (1 hour) |
| KIMI-K2 | long_context_research | Cache with 2-hour TTL (expensive) |

---

## 11. Cross-Model Fallback Matrix

### Complete Fallback Paths

```
Request comes in for:
├── GLM-4-Air
│   ├── Try: GLM-4-Air (local)
│   ├── Fallback 1: GLM-4-Flash
│   ├── Fallback 2: GLM-4-Plus
│   ├── Fallback 3: GLM-5.1
│   └── Final: OpenRouter
│
├── GLM-4-Flash
│   ├── Try: GLM-4-Flash (local)
│   ├── Fallback 1: GLM-4-Air
│   ├── Fallback 2: GLM-4-Plus
│   ├── Fallback 3: GLM-5.1
│   └── Final: OpenRouter
│
├── GLM-4-Plus
│   ├── Try: GLM-4-Plus (local/cloud)
│   ├── Fallback 1: GLM-4.7
│   ├── Fallback 2: GLM-5.1
│   └── Final: OpenRouter
│
├── GLM-4.7
│   ├── Try: GLM-4.7 (local/cloud)
│   ├── Fallback 1: GLM-4-Plus
│   ├── Fallback 2: GLM-5.1
│   └── Final: OpenRouter
│
├── GLM-5-Turbo
│   ├── Try: GLM-5-Turbo (cloud)
│   ├── Fallback 1: GLM-5.1
│   ├── Fallback 2: GLM-4-Plus
│   └── Final: OpenRouter
│
├── GLM-5.1 (HUB)
│   ├── Try: GLM-5.1 (cloud)
│   ├── Fallback 1: GLM-5-Turbo
│   ├── Fallback 2: GLM-4-Plus
│   └── Final: OpenRouter
│
└── KIMI-K2
    ├── Try: KIMI-K2 (cloud)
    ├── Fallback 1: GLM-4.7
    ├── Fallback 2: GLM-5.1
    └── Final: OpenRouter
```

### Fallback Decision Logic

```python
def route_with_fallback(request, primary_model):
    """Three-body routing with cascading fallback."""
    
    # Body 1: Delivery — attempt primary model
    result, status = try_model(request, primary_model)
    if status == "success":
        return result
    
    # Body 2: Control — verify fallback is appropriate
    fallback_chain = get_fallback_chain(primary_model)
    log_control_decision(request, primary_model, status, fallback_chain)
    
    # Body 3: Memory — CHIT trail records the routing decision
    chit_record = sign_routing_decision(request, primary_model, fallback_chain)
    
    # Execute fallback chain
    for fallback_model in fallback_chain:
        result, status = try_model(request, fallback_model)
        if status == "success":
            record_cache_hit(request, fallback_model, chit_record)
            return result
    
    # All fallbacks exhausted
    raise RoutingExhaustedError(f"All models failed for request: {request.id}")
```

---

## 12. TensorZero Routing Configuration

### Function Definitions

```yaml
# pmoves/functions/glm_routing.yml
functions:
  pmoves_orchestrator_coding:
    type: chat
    variants:
      glm-4.7-primary:
        weight: 0.6
        model: glm-4.7
      glm-5.1-backup:
        weight: 0.3
        model: glm-5.1
      kimi-k2-long:
        weight: 0.1
        model: kimi-k2
    fallback:
      - glm-4.7-primary
      - glm-5.1-backup
      - kimi-k2-long

  pmoves_worker_glm:
    type: chat
    variants:
      glm-4-air:
        weight: 0.5
        model: glm-4-air
      glm-4-flash:
        weight: 0.3
        model: glm-4-flash
      glm-4-plus:
        weight: 0.2
        model: glm-4-plus

  pmoves_worker_kimi:
    type: chat
    variants:
      kimi-k2-instruct:
        weight: 0.7
        model: kimi-k2-instruct
      kimi-k2-thinking:
        weight: 0.3
        model: kimi-k2-thinking
```

### Metric-Based Routing

```yaml
# Auto-switch based on observed metrics
routing_rules:
  - condition: "latency_p95 > 5000ms"
    action: "reduce_weight by 0.2"
    target: "slow_model"
    
  - condition: "error_rate > 0.05"
    action: "trigger_fallback"
    target: "unreliable_model"
    
  - condition: "cache_hit_rate < 0.20"
    action: "lower_similarity_threshold by 0.05"
    target: "semantic_cache"
    
  - condition: "token_cost_per_request > $0.10"
    action: "prefer_cached_responses"
    target: "expensive_models"
```

---

## Appendix A: Model Comparison Matrix

| Attribute | GLM-4-Air | GLM-4-Flash | GLM-4-Plus | GLM-4.7 | GLM-5-Turbo | GLM-5.1 | KIMI-K2 |
|-----------|-----------|-------------|------------|---------|-------------|---------|---------|
| **Total Params** | 9B | 9B | 130B | 130B | 355B | 744B | 1T |
| **Active Params** | 9B | 9B | 130B | 130B | 32B | 40B | 32B |
| **Architecture** | Dense | Dense | MoE | MoE | MoE | MoE | MoE |
| **Context Window** | 128K | 128K | 128K | 200K | 128K | 202K | 256K |
| **Max Tokens** | 4K | 4K | 4K | 16K | 8K | 131K | 4K |
| **Temperature Default** | 0.7 | 0.7 | 1.0 | 0.7 | 1.0 | 1.0 | 0.7 |
| **Thinking** | No | No | Yes | Yes | Yes | Yes | Yes |
| **Tool Parser** | glm4 | glm4 | glm4 | glm47 | glm47 | glm47 | kimi |
| **Primary Use** | Edge | Speed | Quality | Coding | Workflow | Long-horizon | Long-context |
| **Provider** | z.ai | z.ai | z.ai | z.ai | z.ai | z.ai | Moonshot |
| **Cost Tier** | $ | $ | $$ | $$ | $$$ | $$$$ | $$$ |
| **Fallback To** | Flash | Air | 4.7 | Plus | 5.1 | Turbo | 4.7 |

## Appendix B: Provider Cascade Configuration

```yaml
# pmoves/config/provider_cascade.yml
provider_cascade:
  name: glm_kimi_cascade
  description: "Primary GLM with KIMI long-context fallback"
  
  tiers:
    - tier: 1
      name: "local_glm"
      providers:
        - glm-4-air
        - glm-4-flash
      condition: "available_local"
      
    - tier: 2
      name: "cloud_glm"
      providers:
        - glm-4-plus
        - glm-4.7
        - glm-5-turbo
        - glm-5.1
      condition: "local_unavailable OR quality_required"
      
    - tier: 3
      name: "kimi_specialist"
      providers:
        - kimi-k2-instruct
        - kimi-k2-thinking
      condition: "context > 128K OR chinese_language"
      
    - tier: 4
      name: "universal_fallback"
      providers:
        - openrouter
      condition: "all_tiers_exhausted"
```

## Appendix C: Environment Variable Reference

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `ZAI_API_KEY` | — | Zhipu AI API key for GLM models | YES |
| `MOONSHOT_API_KEY` | — | Moonshot API key for KIMI models | YES |
| `KIMI_API_KEY` | — | Legacy KIMI key (sunset 2026-10-01) | NO (deprecated) |
| `CACHE_EMBEDDING_MODEL` | `BAAI/bge-m3` | Embedding model for semantic cache | NO |
| `CACHE_EMBEDDING_DIM` | `1024` | Embedding dimension | NO |
| `CACHE_TTL_CHAT_SECS` | `300` | Chat cache TTL (seconds) | NO |
| `CACHE_TTL_EMBED_SECS` | `3600` | Embedding cache TTL (seconds) | NO |
| `CACHE_MAX_ENTRIES` | `10000` | Maximum cache entries | NO |
| `OPENROUTER_API_KEY` | — | OpenRouter fallback API key | NO |
| `TENSORZERO_GATEWAY_URL` | `http://localhost:3000` | TensorZero gateway endpoint | NO |

---

*GLM-4/KIMI-K2 Configuration Suite v2.0.0 — master specification for PMOVES.AI model orchestration. All parameters validated against AGNOTE4482 convergence requirements and CHIT signoff checklist (37/37).*

**GRAPHITI_MARK: MODEL-CONFIG::MASTER-SPEC::2026-07-09**
