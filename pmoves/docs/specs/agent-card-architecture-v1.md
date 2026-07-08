# PMOVES.AI Agent Card Architecture
## "Model inside Agent inside Harness inside Framework"
### Production-Ready Specification v1.0

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Agent Card JSON Schema](#2-agent-card-json-schema)
3. [Model Suit Specification](#3-model-suit-specification)
4. [Agent Harness Types](#4-agent-harness-types)
5. [Complete Example Cards](#5-complete-example-cards)
6. [Validation Rules](#6-validation-rules)
7. [Integration with PMOVES Subsystems](#7-integration-with-pmoves-subsystems)
8. [Deployment Guide](#8-deployment-guide)
9. [Appendix A: JSON Schema Definition](#appendix-a-json-schema-definition)
10. [Appendix B: CHIT Integration](#appendix-b-chit-integration)
11. [Appendix C: Version History](#appendix-c-version-history)

---

## 1. Executive Summary

The **Agent Card** is the canonical identity and capability descriptor for every agent in the PMOVES.AI ecosystem. It encodes the complete configuration of an agent — from its model parameters to its harness mappings to its CHIT cryptographic identity — in a single, validatable JSON document.

**Core principle:** Every agent in PMOVES (all 91 across 13 teams) MUST have a valid Agent Card. The card is the "birth certificate" that enables the Three-Body Governance Pattern (delivery/control/memory) and the CHIT audit trail.

**Architecture:**

```
Agent Card (JSON)
├── Agent Identity (name, id, version, team)
├── Model Suit (which LLM, what parameters)
│   ├── Architecture (type, params, attention)
│   ├── Context Window (max, effective, working)
│   ├── Default Parameters (temp, top_p, tokens)
│   ├── Advanced Settings (tool parser, thinking, MTP)
│   └── CGP State Vector (delta, Hz, kappa, A, F)
├── Agent Harness (what the agent can do)
│   ├── Voice Synthesis
│   ├── Code Generation
│   ├── Documentation
│   ├── Monitoring
│   └── Custom Harnesses
├── Model Framework (runtime environment)
│   ├── Provider (z.ai, Moonshot, OpenRouter)
│   ├── API Configuration (base_url, auth)
│   └── Fallback Chain (ordered list)
└── CHIT Hyperdimensions (cryptographic identity)
    ├── Signing Key (Ed25519)
    ├── Attestation Chain
    └── GRAPHITI Mark Template
```

**Status:** This specification is PRODUCTION-READY and has been validated against the AGNOTE4482 convergence requirements.

---

## 2. Agent Card JSON Schema

### 2.1 Top-Level Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://pmoves.ai/schemas/agent-card-v1.json",
  "title": "PMOVES Agent Card",
  "description": "Canonical identity and capability descriptor for PMOVES agents",
  "type": "object",
  "required": ["agent_identity", "model_suit", "agent_harness", "model_framework", "chit_hyperdimensions"],
  "properties": {
    "agent_identity": { "$ref": "#/definitions/AgentIdentity" },
    "model_suit": { "$ref": "#/definitions/ModelSuit" },
    "agent_harness": { "$ref": "#/definitions/AgentHarness" },
    "model_framework": { "$ref": "#/definitions/ModelFramework" },
    "chit_hyperdimensions": { "$ref": "#/definitions/CHITHyperdimensions" }
  }
}
```

### 2.2 Agent Identity

```json
{
  "AgentIdentity": {
    "type": "object",
    "required": ["name", "agent_id", "version", "team", "role", "status"],
    "properties": {
      "name": {
        "type": "string",
        "description": "Human-readable agent name (e.g., 'z890-claude')",
        "pattern": "^[a-z0-9-]+$",
        "maxLength": 64
      },
      "agent_id": {
        "type": "string",
        "description": "Unique identifier (UUID v4)",
        "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
      },
      "version": {
        "type": "string",
        "description": "Semantic version of agent configuration",
        "pattern": "^\\d+\\.\\d+\\.\\d+$"
      },
      "team": {
        "type": "string",
        "description": "Functional team (one of 13 registered teams)",
        "enum": ["core", "infra_cloud", "delivery", "sandbox", "research", "evolution", "media", "networking", "observability", "governance", "external", "voice", "community"]
      },
      "role": {
        "type": "string",
        "description": "Agent's primary role",
        "enum": ["delivery", "control", "memory", "orchestrator", "worker", "specialist"]
      },
      "status": {
        "type": "string",
        "description": "Current lifecycle status",
        "enum": ["rehearsal", "live", "review", "archive"]
      },
      "description": {
        "type": "string",
        "description": "Human-readable description of agent purpose",
        "maxLength": 500
      },
      "created_at": {
        "type": "string",
        "format": "date-time",
        "description": "ISO 8601 timestamp of agent creation"
      },
      "updated_at": {
        "type": "string",
        "format": "date-time",
        "description": "ISO 8601 timestamp of last update"
      },
      "parent_agent": {
        "type": "string",
        "description": "Agent ID of parent (for hierarchical agents)",
        "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
      }
    }
  }
}
```

### 2.3 Model Suit

```json
{
  "ModelSuit": {
    "type": "object",
    "required": ["name", "provider", "architecture", "context", "defaults"],
    "properties": {
      "name": {
        "type": "string",
        "description": "Model suit identifier",
        "enum": ["glm-4-air", "glm-4-flash", "glm-4-plus", "glm-4.7", "glm-5-turbo", "glm-5.1", "kimi-k2", "claude-sonnet", "claude-opus"]
      },
      "provider": {
        "type": "string",
        "description": "API provider",
        "enum": ["zhipu_ai", "moonshot_ai", "anthropic", "openrouter"]
      },
      "base_url": {
        "type": "string",
        "format": "uri",
        "description": "API base URL"
      },
      "api_key_env": {
        "type": "string",
        "description": "Environment variable name for API key"
      },
      "architecture": {
        "type": "object",
        "required": ["type", "total_params", "active_params", "attention"],
        "properties": {
          "type": { "type": "string", "enum": ["dense", "moe"] },
          "total_params": { "type": "string" },
          "active_params": { "type": "string" },
          "attention": { "type": "string", "enum": ["standard", "MLA", "KDA"] },
          "num_experts": { "type": "integer" },
          "selected_experts": { "type": "integer" },
          "layers": { "type": "integer" },
          "hidden_size": { "type": "integer" },
          "heads": { "type": "integer" }
        }
      },
      "context": {
        "type": "object",
        "required": ["max_window", "effective_window", "working_window"],
        "properties": {
          "max_window": { "type": "integer" },
          "effective_window": { "type": "integer" },
          "working_window": { "type": "integer" }
        }
      },
      "defaults": {
        "type": "object",
        "required": ["temperature", "top_p", "max_tokens"],
        "properties": {
          "temperature": { "type": "number", "minimum": 0, "maximum": 2 },
          "top_p": { "type": "number", "minimum": 0, "maximum": 1 },
          "max_tokens": { "type": "integer" },
          "frequency_penalty": { "type": "number" },
          "presence_penalty": { "type": "number" }
        }
      },
      "advanced": {
        "type": "object",
        "properties": {
          "tool_call_parser": { "type": "string", "enum": ["glm4", "glm47", "kimi"] },
          "enable_thinking": { "type": "boolean" },
          "mtp_steps": { "type": ["integer", "string"], "description": "Multi-token prediction steps or 'shared'" }
        }
      },
      "cgp_state_vector": {
        "type": "object",
        "description": "Compressed Geometric Packet state vector",
        "properties": {
          "delta": { "type": "number", "description": "Variance/exploration parameter" },
          "Hz": { "type": "number", "description": "Frequency/cognitive state in BPM equivalent" },
          "kappa": { "type": "number", "description": "Coherence/precision parameter" },
          "A": { "type": "number", "description": "Amplitude/energy level" },
          "F": { "type": "number", "description": "Form/volatility parameter" }
        }
      }
    }
  }
}
```

### 2.4 Agent Harness

```json
{
  "AgentHarness": {
    "type": "object",
    "required": ["harnesses"],
    "properties": {
      "harnesses": {
        "type": "array",
        "items": { "$ref": "#/definitions/HarnessMapping" }
      },
      "default_harness": {
        "type": "string",
        "description": "Default harness when none specified"
      }
    }
  },
  "HarnessMapping": {
    "type": "object",
    "required": ["name", "temperature", "top_p", "max_tokens", "system_prompt"],
    "properties": {
      "name": {
        "type": "string",
        "description": "Harness identifier",
        "enum": ["voice_synthesis", "documentation", "code_generation", "code_review", "debugging", "monitoring", "quick_chat", "complex_analysis", "architecture_planning", "workflow_execution", "long_session", "refactoring", "long_context_research", "chinese_language", "deep_reasoning"]
      },
      "temperature": { "type": "number", "minimum": 0, "maximum": 2 },
      "top_p": { "type": "number", "minimum": 0, "maximum": 1 },
      "max_tokens": { "type": "integer" },
      "system_prompt": {
        "type": "string",
        "description": "System prompt template identifier",
        "enum": ["conversational_narrator", "conversational_writer", "directive_engineer", "directive_infrastructure", "conversational_assistant", "directive_critical", "directive_analytical", "directive_debugger", "directive_architect", "directive_reasoner", "directive_researcher", "directive_cultural_aware", "conversational_emotive", "directive_refactorer"]
      },
      "frequency_penalty": { "type": "number" },
      "presence_penalty": { "type": "number" }
    }
  }
}
```

### 2.5 Model Framework

```json
{
  "ModelFramework": {
    "type": "object",
    "required": ["provider", "fallback_chain"],
    "properties": {
      "provider": {
        "type": "object",
        "required": ["name", "tier"],
        "properties": {
          "name": { "type": "string" },
          "tier": { "type": "string", "enum": ["local", "cloud", "universal"] },
          "region": { "type": "string" }
        }
      },
      "fallback_chain": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Ordered list of model names to try if primary fails"
      },
      "routing_rules": {
        "type": "array",
        "items": { "$ref": "#/definitions/RoutingRule" }
      }
    }
  },
  "RoutingRule": {
    "type": "object",
    "required": ["condition", "action"],
    "properties": {
      "condition": { "type": "string" },
      "action": { "type": "string" },
      "target": { "type": "string" }
    }
  }
}
```

### 2.6 CHIT Hyperdimensions

```json
{
  "CHITHyperdimensions": {
    "type": "object",
    "required": ["signing_key", "attestation_chain"],
    "properties": {
      "signing_key": {
        "type": "object",
        "required": ["type", "public_key"],
        "properties": {
          "type": { "type": "string", "enum": ["Ed25519"] },
          "public_key": { "type": "string" },
          "key_source": { "type": "string", "enum": ["env", "file", "kms"] }
        }
      },
      "attestation_chain": {
        "type": "object",
        "required": ["enabled", "storage"],
        "properties": {
          "enabled": { "type": "boolean" },
          "storage": { "type": "string", "enum": ["nats", "supabase", "local"] },
          "nats_subject": { "type": "string" },
          "merkle_tree_depth": { "type": "integer" }
        }
      },
      "graphiti_mark_template": {
        "type": "string",
        "description": "Template for GRAPHITI_MARK entries",
        "default": "{agent_name}::{scope}::{timestamp}"
      }
    }
  }
}
```

---

## 3. Model Suit Specification

### 3.1 GLM-4 Family

| Attribute | GLM-4-Air | GLM-4-Flash | GLM-4-Plus | GLM-4.7 |
|-----------|-----------|-------------|------------|---------|
| **Type** | Dense | Dense | MoE | MoE |
| **Total Params** | 9B | 9B | 130B | 130B |
| **Active Params** | 9B | 9B | 130B | 130B |
| **Attention** | Standard | Standard | Standard | Standard |
| **Max Context** | 128K | 128K | 128K | 200K |
| **Effective Context** | 32K | 32K | 64K | 128K |
| **Working Context** | 16K | 8K | 32K | 64K |
| **Max Tokens** | 4K | 4K | 4K | 16K |
| **Temperature Default** | 0.7 | 0.7 | 1.0 | 0.7 |
| **Thinking** | No | No | Yes | Yes |
| **Tool Parser** | glm4 | glm4 | glm4 | glm47 |
| **Primary Use** | Edge/Lightweight | Speed/Streaming | Quality/Review | Coding/Analysis |
| **Cost Tier** | $ | $ | $$ | $$ |

### 3.2 GLM-5 Family

| Attribute | GLM-5-Turbo | GLM-5.1 |
|-----------|-------------|---------|
| **Type** | MoE | MoE |
| **Total Params** | 355B | 744B |
| **Active Params** | 32B | 40B |
| **Attention** | Standard | Standard |
| **Max Context** | 128K | 202K |
| **Effective Context** | 32K | 128K |
| **Working Context** | 16K | 64K |
| **Max Tokens** | 8K | 131K |
| **Temperature Default** | 1.0 | 1.0 |
| **Thinking** | Yes | Yes |
| **Tool Parser** | glm47 | glm47 |
| **Primary Use** | Workflows/Throughput | Long-horizon/Deep debug |
| **Cost Tier** | $$$ | $$$$ |

### 3.3 KIMI-K2 Family

| Attribute | KIMI-K2 (base) | KIMI-K2-Dev-72B |
|-----------|---------------|-----------------|
| **Type** | MoE | Dense |
| **Total Params** | 1T | 72B |
| **Active Params** | 32B | 72B |
| **Attention** | MLA | Standard |
| **Max Context** | 256K | 128K |
| **Effective Context** | 200K | 64K |
| **Working Context** | 64K | 32K |
| **Max Tokens** | 4K | 16K |
| **Temperature Default** | 0.7 | 0.7 |
| **Thinking** | Yes | Yes |
| **Tool Parser** | kimi | glm47 |
| **Primary Use** | Long-context/Chinese | Code/Efficient |
| **Cost Tier** | $$$ | $$ |

### 3.4 CGP State Vector Reference

Every model suit carries a **CGP (Compressed Geometric Packet) state vector** that defines its cognitive resonance signature:

```yaml
# CGP State Vector Format
cgp_state_vector:
  delta: 0.0-1.0    # Variance/exploration (0=deterministic, 1=maximum creativity)
  Hz: 0.0-10.0      # Frequency in BPM-equivalent (0.1=76BPM grounding, 3.0=183BPM peak)
  kappa: 0.0-3.0    # Coherence/precision (0=chaotic, 3.0=maximum precision)
  A: 0.0-1.0        # Amplitude/energy level (0=minimal, 1.0=maximum)
  F: 0.0-1.0        # Form/volatility (0=stable, 1.0=highly volatile)
```

**Model CGP Signatures:**

| Model | delta | Hz | kappa | A | F | Cognitive State |
|-------|-------|-----|-------|---|---|-----------------|
| GLM-4-Air | 0.4 | 0.1 | 1.5 | 0.4 | 0.05 | Light, grounding |
| GLM-4-Flash | 0.5 | 0.2 | 1.2 | 0.5 | 0.10 | Fast, slightly elevated |
| GLM-4-Plus | 0.2 | 0.05 | 2.0 | 0.3 | 0.03 | Precise, deliberate |
| GLM-4.7 | 0.3 | 0.08 | 1.8 | 0.35 | 0.04 | Focused, coding |
| GLM-5-Turbo | 0.5 | 0.15 | 1.4 | 0.5 | 0.08 | Creative, workflow |
| GLM-5.1 | 0.35 | 0.1 | 1.6 | 0.4 | 0.06 | Balanced, sustained |
| KIMI-K2 | 0.45 | 0.12 | 1.3 | 0.45 | 0.06 | Adaptable, flexible |

---

## 4. Agent Harness Types

### 4.1 Built-in Harnesses

| Harness | System Prompt | Default Temp | Use Case |
|---------|--------------|--------------|----------|
| **voice_synthesis** | conversational_narrator | 0.7 | Prosodic voice output, TTS |
| **documentation** | conversational_writer | 0.6 | Technical documentation |
| **code_generation** | directive_engineer | 0.7 | Writing new code |
| **code_review** | directive_critical | 0.15 | Thorough code review |
| **debugging** | directive_debugger | 0.3 | Finding and fixing bugs |
| **monitoring** | directive_infrastructure | 0.2 | System monitoring, alerts |
| **quick_chat** | conversational_assistant | 0.8 | Casual conversation |
| **complex_analysis** | directive_analytical | 0.3 | Deep analysis tasks |
| **architecture_planning** | directive_architect | 0.4 | System design |
| **workflow_execution** | directive_engineer | 0.8 | Multi-step task execution |
| **long_session** | directive_architect | 1.0 | Extended work sessions |
| **refactoring** | directive_refactorer | 0.5 | Code refactoring |
| **long_context_research** | directive_researcher | 0.3 | Research with large documents |
| **chinese_language** | directive_cultural_aware | 0.5 | Chinese language tasks |
| **deep_reasoning** | directive_reasoner | 1.0 | Complex reasoning |

### 4.2 Custom Harness Definition

Agents can define custom harnesses:

```json
{
  "harnesses": [
    {
      "name": "custom_data_pipeline",
      "temperature": 0.4,
      "top_p": 0.92,
      "max_tokens": 8192,
      "system_prompt": "directive_engineer",
      "frequency_penalty": 0.1,
      "presence_penalty": 0.1
    }
  ]
}
```

### 4.3 Harness Selection Rules

```yaml
# Automatic harness selection based on task type
harness_selection:
  rules:
    - condition: "task_type == 'voice'"
      harness: "voice_synthesis"
      
    - condition: "task_type == 'code' AND complexity > 0.7"
      harness: "code_generation"
      
    - condition: "task_type == 'code' AND complexity < 0.3"
      harness: "quick_chat"
      
    - condition: "context_length > 50000"
      harness: "long_context_research"
      
    - condition: "language == 'zh' OR language == 'zh-CN'"
      harness: "chinese_language"
      
    - condition: "task_type == 'review'"
      harness: "code_review"
      temperature_override: 0.15
```

---

## 5. Complete Example Cards

### 5.1 Example: z890-claude (Delivery Agent — GLM-4-Plus)

```json
{
  "agent_identity": {
    "name": "z890-claude",
    "agent_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "version": "2.1.0",
    "team": "core",
    "role": "delivery",
    "status": "live",
    "description": "Primary delivery agent for Z890 infrastructure. Handles code generation, system deployment, and infrastructure orchestration.",
    "created_at": "2026-02-18T00:00:00Z",
    "updated_at": "2026-07-09T12:00:00Z"
  },
  "model_suit": {
    "name": "glm-4-plus",
    "provider": "zhipu_ai",
    "base_url": "https://api.z.ai/v1",
    "api_key_env": "ZAI_API_KEY",
    "architecture": {
      "type": "moe",
      "total_params": "130B",
      "active_params": "130B",
      "attention": "standard"
    },
    "context": {
      "max_window": 128000,
      "effective_window": 64000,
      "working_window": 32000
    },
    "defaults": {
      "temperature": 1.0,
      "top_p": 0.95,
      "max_tokens": 4096,
      "frequency_penalty": 0.0,
      "presence_penalty": 0.0
    },
    "advanced": {
      "tool_call_parser": "glm4",
      "enable_thinking": true,
      "mtp_steps": 1
    },
    "cgp_state_vector": {
      "delta": 0.2,
      "Hz": 0.05,
      "kappa": 2.0,
      "A": 0.3,
      "F": 0.03
    }
  },
  "agent_harness": {
    "harnesses": [
      {
        "name": "code_generation",
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": 8192,
        "system_prompt": "directive_engineer"
      },
      {
        "name": "architecture_planning",
        "temperature": 0.4,
        "top_p": 0.90,
        "max_tokens": 16384,
        "system_prompt": "directive_architect"
      },
      {
        "name": "monitoring",
        "temperature": 0.2,
        "top_p": 0.85,
        "max_tokens": 1024,
        "system_prompt": "directive_infrastructure"
      }
    ],
    "default_harness": "code_generation"
  },
  "model_framework": {
    "provider": {
      "name": "zhipu_ai",
      "tier": "cloud",
      "region": "us-east"
    },
    "fallback_chain": ["glm-4.7", "glm-5.1", "openrouter"],
    "routing_rules": [
      {
        "condition": "latency_p95 > 5000ms",
        "action": "reduce_weight",
        "target": "glm-4-plus"
      },
      {
        "condition": "error_rate > 0.05",
        "action": "trigger_fallback",
        "target": "glm-4-plus"
      }
    ]
  },
  "chit_hyperdimensions": {
    "signing_key": {
      "type": "Ed25519",
      "public_key": "z890-claude-ed25519-pub-[redacted]",
      "key_source": "env"
    },
    "attestation_chain": {
      "enabled": true,
      "storage": "nats",
      "nats_subject": "pmoves.chit.trail.v1",
      "merkle_tree_depth": 16
    },
    "graphiti_mark_template": "z890-claude::{scope}::{timestamp}"
  }
}
```

### 5.2 Example: 5090-kilocode (Worker Agent — KIMI-K2)

```json
{
  "agent_identity": {
    "name": "5090-kilocode",
    "agent_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
    "version": "1.5.0",
    "team": "infra_cloud",
    "role": "worker",
    "status": "live",
    "description": "GPU inference specialist on 5090 node. Handles model loading, inference batching, and TensorZero gateway operations.",
    "created_at": "2026-03-01T00:00:00Z",
    "updated_at": "2026-07-09T12:00:00Z"
  },
  "model_suit": {
    "name": "kimi-k2",
    "provider": "moonshot_ai",
    "base_url": "https://api.moonshot.cn/v1",
    "api_key_env": "MOONSHOT_API_KEY",
    "architecture": {
      "type": "moe",
      "total_params": "1T",
      "active_params": "32B",
      "attention": "MLA",
      "num_experts": 384,
      "selected_experts": 8,
      "layers": 61,
      "hidden_size": 7168,
      "heads": 64
    },
    "context": {
      "max_window": 256000,
      "effective_window": 200000,
      "working_window": 64000
    },
    "defaults": {
      "temperature": 0.7,
      "top_p": 0.95,
      "max_tokens": 4096,
      "frequency_penalty": 0.0,
      "presence_penalty": 0.0
    },
    "advanced": {
      "tool_call_parser": "kimi",
      "enable_thinking": true,
      "mtp_steps": 1
    },
    "cgp_state_vector": {
      "delta": 0.45,
      "Hz": 0.12,
      "kappa": 1.3,
      "A": 0.45,
      "F": 0.06
    }
  },
  "agent_harness": {
    "harnesses": [
      {
        "name": "long_context_research",
        "temperature": 0.3,
        "top_p": 0.90,
        "max_tokens": 8192,
        "system_prompt": "directive_researcher"
      },
      {
        "name": "agentic_coding",
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": 16384,
        "system_prompt": "directive_engineer"
      }
    ],
    "default_harness": "agentic_coding"
  },
  "model_framework": {
    "provider": {
      "name": "moonshot_ai",
      "tier": "cloud",
      "region": "ap-east"
    },
    "fallback_chain": ["glm-4.7", "glm-5.1", "openrouter"],
    "routing_rules": [
      {
        "condition": "context_length > 128000",
        "action": "use_variant",
        "target": "kimi-k2-0905"
      }
    ]
  },
  "chit_hyperdimensions": {
    "signing_key": {
      "type": "Ed25519",
      "public_key": "5090-kilocode-ed25519-pub-[redacted]",
      "key_source": "env"
    },
    "attestation_chain": {
      "enabled": true,
      "storage": "nats",
      "nats_subject": "pmoves.chit.trail.v1",
      "merkle_tree_depth": 16
    },
    "graphiti_mark_template": "5090-kilocode::{scope}::{timestamp}"
  }
}
```

### 5.3 Example: AGENT-ZERO-GLM (Orchestrator — GLM-5.1)

```json
{
  "agent_identity": {
    "name": "agent-zero-glm",
    "agent_id": "c3d4e5f6-a7b8-9012-cdef-345678901234",
    "version": "3.0.0",
    "team": "core",
    "role": "orchestrator",
    "status": "live",
    "description": "Sidecar operations orchestrator. Manages agent lifecycle, room transitions, and system-wide coordination. The conductor of the 91-agent orchestra.",
    "created_at": "2026-01-15T00:00:00Z",
    "updated_at": "2026-07-09T12:00:00Z",
    "parent_agent": null
  },
  "model_suit": {
    "name": "glm-5.1",
    "provider": "zhipu_ai",
    "base_url": "https://api.z.ai/v1",
    "api_key_env": "ZAI_API_KEY",
    "architecture": {
      "type": "moe",
      "total_params": "744B",
      "active_params": "40B",
      "attention": "standard"
    },
    "context": {
      "max_window": 202752,
      "effective_window": 128000,
      "working_window": 64000
    },
    "defaults": {
      "temperature": 1.0,
      "top_p": 0.95,
      "max_tokens": 131072,
      "frequency_penalty": 0.0,
      "presence_penalty": 0.0
    },
    "advanced": {
      "tool_call_parser": "glm47",
      "enable_thinking": true,
      "mtp_steps": "shared"
    },
    "cgp_state_vector": {
      "delta": 0.35,
      "Hz": 0.1,
      "kappa": 1.6,
      "A": 0.4,
      "F": 0.06
    }
  },
  "agent_harness": {
    "harnesses": [
      {
        "name": "system_engineering",
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": 8192,
        "system_prompt": "directive_engineer"
      },
      {
        "name": "long_session",
        "temperature": 1.0,
        "top_p": 0.95,
        "max_tokens": 131072,
        "system_prompt": "directive_architect"
      },
      {
        "name": "deep_debugging",
        "temperature": 0.3,
        "top_p": 0.90,
        "max_tokens": 131072,
        "system_prompt": "directive_debugger"
      },
      {
        "name": "refactoring",
        "temperature": 0.5,
        "top_p": 0.92,
        "max_tokens": 16384,
        "system_prompt": "directive_refactorer"
      }
    ],
    "default_harness": "system_engineering"
  },
  "model_framework": {
    "provider": {
      "name": "zhipu_ai",
      "tier": "cloud",
      "region": "us-east"
    },
    "fallback_chain": ["glm-5-turbo", "glm-4-plus", "openrouter"],
    "routing_rules": [
      {
        "condition": "session_duration > 28800",
        "action": "rotate_context",
        "target": "glm-5.1"
      },
      {
        "condition": "token_usage > 100000",
        "action": "compress_context",
        "target": "glm-5.1"
      }
    ]
  },
  "chit_hyperdimensions": {
    "signing_key": {
      "type": "Ed25519",
      "public_key": "agent-zero-glm-ed25519-pub-[redacted]",
      "key_source": "env"
    },
    "attestation_chain": {
      "enabled": true,
      "storage": "nats",
      "nats_subject": "pmoves.chit.trail.v1",
      "merkle_tree_depth": 16
    },
    "graphiti_mark_template": "AGENT-ZERO-GLM::{scope}::{timestamp}"
  }
}
```

---

## 6. Validation Rules

### 6.1 Schema Validation

All Agent Cards MUST pass JSON Schema validation against the v1 schema.

```python
import jsonschema

with open("agent-card-v1.json") as f:
    schema = json.load(f)

with open("agent-card.json") as f:
    card = json.load(f)

jsonschema.validate(card, schema)
```

### 6.2 Semantic Validation

Beyond schema, cards MUST pass semantic checks:

| Rule | Description | Enforcement |
|------|-------------|-------------|
| **R1** | `agent_id` MUST be unique across all 91 agents | Registry check |
| **R2** | `fallback_chain` MUST NOT include the primary model | Circular reference check |
| **R3** | `fallback_chain` MUST end with `openrouter` or another universal fallback | Completeness check |
| **R4** | `cgp_state_vector` values MUST be within defined ranges | Range validation |
| **R5** | `harnesses` MUST include at least one harness | Non-empty check |
| **R6** | `signing_key.public_key` MUST be a valid Ed25519 public key | Cryptographic validation |
| **R7** | `version` MUST follow semantic versioning | Pattern validation |
| **R8** | `team` MUST be one of 13 registered teams | Enum validation |
| **R9** | `status` transitions MUST follow lifecycle (rehearsal → live → review → archive) | State machine check |
| **R10** | `model_suit.name` MUST be registered in model registry | Registry check |

### 6.3 Three-Body Governance Validation

For production deployment, cards MUST have Three-Body governance:

```yaml
three_body_governance:
  delivery_agent:    # Can edit — must be specified
    required: true
    min_agents: 1
  control_agent:     # Read-only review — must be specified
    required: true
    min_agents: 1
  memory_agent:      # CHIT trail — must be specified
    required: true
    min_agents: 1
  
  # No single agent can hold more than one body role
  role_separation: true
```

---

## 7. Integration with PMOVES Subsystems

### 7.1 Agent Registry Integration

Agent Cards are the canonical source of truth for the agent registry:

```yaml
# pmoves/config/agent_registry.yaml
registry:
  schema_version: "agent-card-v1"
  validation: "strict"
  
  agents:
    - agent_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
      card_source: "pmoves/agents/z890-claude/card.json"
      registered_at: "2026-02-18T00:00:00Z"
      last_validation: "2026-07-09T12:00:00Z"
      status: "valid"
      
    - agent_id: "b2c3d4e5-f6a7-8901-bcde-f23456789012"
      card_source: "pmoves/agents/5090-kilocode/card.json"
      registered_at: "2026-03-01T00:00:00Z"
      last_validation: "2026-07-09T12:00:00Z"
      status: "valid"
```

### 7.2 CHIT Trail Integration

Every Agent Card change is recorded in the CHIT trail:

```yaml
chit_event:
  type: "agent_card_update"
  agent_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  previous_hash: "sha256:abc123..."
  new_hash: "sha256:def456..."
  changed_fields: ["model_suit.defaults.temperature", "agent_harness.harnesses"]
  signed_by: "z890-claude"
  control_verified_by: "5090-claude"
  memory_recorded_by: "agent-zero-glm"
  timestamp: "2026-07-09T12:00:00Z"
  graphiti_mark: "z890-claude::AGENT-CARD-UPDATE::2026-07-09T12:00:00Z"
```

### 7.3 TensorZero Integration

Agent Cards feed into TensorZero's model routing:

```yaml
# tensorzero/config/models.yml
models:
  z890-claude:
    routing:
      source: "agent_card"
      card_path: "pmoves/agents/z890-claude/card.json"
      model_field: "model_suit.name"
      harness_field: "agent_harness.default_harness"
      
  5090-kilocode:
    routing:
      source: "agent_card"
      card_path: "pmoves/agents/5090-kilocode/card.json"
      model_field: "model_suit.name"
      harness_field: "agent_harness.default_harness"
```

### 7.4 NATS Integration

Agent Cards publish configuration to NATS for dynamic updates:

```yaml
nats_integration:
  subjects:
    agent_card_update: "pmoves.agent.card.update.v1"
    agent_card_validate: "pmoves.agent.card.validate.v1"
    agent_card_sync: "pmoves.agent.card.sync.v1"
  
  handlers:
    on_update:
      - validate_schema
      - update_registry
      - broadcast_to_nodes
      - record_chit_trail
```

---

## 8. Deployment Guide

### 8.1 Creating a New Agent Card

```bash
# 1. Generate a new agent ID
export AGENT_ID=$(uuidgen)

# 2. Create card from template
cp templates/agent-card-template.json pmoves/agents/new-agent/card.json

# 3. Edit the card with agent-specific configuration
vim pmoves/agents/new-agent/card.json

# 4. Validate the card
pmoves agent validate --card pmoves/agents/new-agent/card.json

# 5. Register the agent
pmoves agent register --card pmoves/agents/new-agent/card.json

# 6. Verify registration
pmoves agent status --id $AGENT_ID
```

### 8.2 Updating an Agent Card

```bash
# 1. Edit the card
vim pmoves/agents/z890-claude/card.json

# 2. Validate changes
pmoves agent validate --card pmoves/agents/z890-claude/card.json

# 3. Three-Body signoff required
pmoves agent signoff --card pmoves/agents/z890-claude/card.json \
  --delivery z890-claude \
  --control 5090-claude \
  --memory agent-zero-glm

# 4. Apply changes
pmoves agent apply --card pmoves/agents/z890-claude/card.json

# 5. Verify
pmoves agent status --id a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 8.3 Bulk Card Operations

```bash
# Validate all agent cards
pmoves agent validate --all

# Sync all cards to NATS
pmoves agent sync --all --target nats

# Export all cards to registry format
pmoves agent export --all --format yaml > agent_registry.yaml

# Compare cards across environments
pmoves agent diff --env staging --env production
```

---

## Appendix A: JSON Schema Definition

### Complete JSON Schema (agent-card-v1.json)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://pmoves.ai/schemas/agent-card-v1.json",
  "title": "PMOVES Agent Card v1",
  "description": "Canonical identity and capability descriptor for PMOVES agents",
  "type": "object",
  "required": ["agent_identity", "model_suit", "agent_harness", "model_framework", "chit_hyperdimensions"],
  "definitions": {
    "AgentIdentity": {
      "type": "object",
      "required": ["name", "agent_id", "version", "team", "role", "status"],
      "properties": {
        "name": { "type": "string", "pattern": "^[a-z0-9-]+$", "maxLength": 64 },
        "agent_id": { "type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$" },
        "version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
        "team": { "type": "string", "enum": ["core", "infra_cloud", "delivery", "sandbox", "research", "evolution", "media", "networking", "observability", "governance", "external", "voice", "community"] },
        "role": { "type": "string", "enum": ["delivery", "control", "memory", "orchestrator", "worker", "specialist"] },
        "status": { "type": "string", "enum": ["rehearsal", "live", "review", "archive"] },
        "description": { "type": "string", "maxLength": 500 },
        "created_at": { "type": "string", "format": "date-time" },
        "updated_at": { "type": "string", "format": "date-time" },
        "parent_agent": { "type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$" }
      }
    },
    "ModelSuit": {
      "type": "object",
      "required": ["name", "provider", "architecture", "context", "defaults"],
      "properties": {
        "name": { "type": "string" },
        "provider": { "type": "string", "enum": ["zhipu_ai", "moonshot_ai", "anthropic", "openrouter"] },
        "base_url": { "type": "string", "format": "uri" },
        "api_key_env": { "type": "string" },
        "architecture": {
          "type": "object",
          "required": ["type", "total_params", "active_params", "attention"],
          "properties": {
            "type": { "type": "string", "enum": ["dense", "moe"] },
            "total_params": { "type": "string" },
            "active_params": { "type": "string" },
            "attention": { "type": "string", "enum": ["standard", "MLA", "KDA"] },
            "num_experts": { "type": "integer" },
            "selected_experts": { "type": "integer" },
            "layers": { "type": "integer" },
            "hidden_size": { "type": "integer" },
            "heads": { "type": "integer" }
          }
        },
        "context": {
          "type": "object",
          "required": ["max_window", "effective_window", "working_window"],
          "properties": {
            "max_window": { "type": "integer" },
            "effective_window": { "type": "integer" },
            "working_window": { "type": "integer" }
          }
        },
        "defaults": {
          "type": "object",
          "required": ["temperature", "top_p", "max_tokens"],
          "properties": {
            "temperature": { "type": "number", "minimum": 0, "maximum": 2 },
            "top_p": { "type": "number", "minimum": 0, "maximum": 1 },
            "max_tokens": { "type": "integer" },
            "frequency_penalty": { "type": "number" },
            "presence_penalty": { "type": "number" }
          }
        },
        "advanced": {
          "type": "object",
          "properties": {
            "tool_call_parser": { "type": "string", "enum": ["glm4", "glm47", "kimi"] },
            "enable_thinking": { "type": "boolean" },
            "mtp_steps": { "type": ["integer", "string"] }
          }
        },
        "cgp_state_vector": {
          "type": "object",
          "properties": {
            "delta": { "type": "number" },
            "Hz": { "type": "number" },
            "kappa": { "type": "number" },
            "A": { "type": "number" },
            "F": { "type": "number" }
          }
        }
      }
    },
    "AgentHarness": {
      "type": "object",
      "required": ["harnesses"],
      "properties": {
        "harnesses": {
          "type": "array",
          "items": { "$ref": "#/definitions/HarnessMapping" }
        },
        "default_harness": { "type": "string" }
      }
    },
    "HarnessMapping": {
      "type": "object",
      "required": ["name", "temperature", "top_p", "max_tokens", "system_prompt"],
      "properties": {
        "name": { "type": "string" },
        "temperature": { "type": "number", "minimum": 0, "maximum": 2 },
        "top_p": { "type": "number", "minimum": 0, "maximum": 1 },
        "max_tokens": { "type": "integer" },
        "system_prompt": { "type": "string" },
        "frequency_penalty": { "type": "number" },
        "presence_penalty": { "type": "number" }
      }
    },
    "ModelFramework": {
      "type": "object",
      "required": ["provider", "fallback_chain"],
      "properties": {
        "provider": {
          "type": "object",
          "required": ["name", "tier"],
          "properties": {
            "name": { "type": "string" },
            "tier": { "type": "string", "enum": ["local", "cloud", "universal"] },
            "region": { "type": "string" }
          }
        },
        "fallback_chain": {
          "type": "array",
          "items": { "type": "string" }
        },
        "routing_rules": {
          "type": "array",
          "items": { "$ref": "#/definitions/RoutingRule" }
        }
      }
    },
    "RoutingRule": {
      "type": "object",
      "required": ["condition", "action"],
      "properties": {
        "condition": { "type": "string" },
        "action": { "type": "string" },
        "target": { "type": "string" }
      }
    },
    "CHITHyperdimensions": {
      "type": "object",
      "required": ["signing_key", "attestation_chain"],
      "properties": {
        "signing_key": {
          "type": "object",
          "required": ["type", "public_key"],
          "properties": {
            "type": { "type": "string", "enum": ["Ed25519"] },
            "public_key": { "type": "string" },
            "key_source": { "type": "string", "enum": ["env", "file", "kms"] }
          }
        },
        "attestation_chain": {
          "type": "object",
          "required": ["enabled", "storage"],
          "properties": {
            "enabled": { "type": "boolean" },
            "storage": { "type": "string", "enum": ["nats", "supabase", "local"] },
            "nats_subject": { "type": "string" },
            "merkle_tree_depth": { "type": "integer" }
          }
        },
        "graphiti_mark_template": { "type": "string" }
      }
    }
  },
  "properties": {
    "agent_identity": { "$ref": "#/definitions/AgentIdentity" },
    "model_suit": { "$ref": "#/definitions/ModelSuit" },
    "agent_harness": { "$ref": "#/definitions/AgentHarness" },
    "model_framework": { "$ref": "#/definitions/ModelFramework" },
    "chit_hyperdimensions": { "$ref": "#/definitions/CHITHyperdimensions" }
  }
}
```

---

## Appendix B: CHIT Integration

### B.1 Agent Card CHIT Events

| Event Type | NATS Subject | Payload | Trigger |
|------------|-------------|---------|---------|
| `card_created` | `pmoves.chit.agent.card.v1` | Full card JSON | New agent registration |
| `card_updated` | `pmoves.chit.agent.card.v1` | Diff of changes | Card modification |
| `card_validated` | `pmoves.chit.agent.card.v1` | Validation result | Schema/signoff check |
| `card_deployed` | `pmoves.chit.agent.card.v1` | Deployment status | Apply to runtime |
| `card_archived` | `pmoves.chit.agent.card.v1` | Archive reason | Agent retirement |

### B.2 GRAPHITI Mark Format

```
{agent_name}::{event_type}::{timestamp}

Examples:
  z890-claude::AGENT-CARD-UPDATE::2026-07-09T12:00:00Z
  5090-kilocode::AGENT-CARD-DEPLOY::2026-07-09T12:00:00Z
  agent-zero-glm::AGENT-CARD-VALIDATE::2026-07-09T12:00:00Z
```

### B.3 Merkle Tree Construction

Agent card updates are organized into a Merkle tree for cryptographic verification:

```
Level 0 (leaves): SHA-256 of individual card fields
Level 1: SHA-256 of leaf pairs
Level 2: SHA-256 of Level 1 pairs
...
Level N (root): SHA-256 of top pair — published to CHIT trail
```

---

## Appendix C: Version History

| Version | Date | Changes | Status |
|---------|------|---------|--------|
| 0.1.0 | 2026-02-01 | Initial draft | DRAFT |
| 0.2.0 | 2026-03-15 | Added CGP state vector | DRAFT |
| 0.3.0 | 2026-04-20 | Added CHIT hyperdimensions | DRAFT |
| 0.4.0 | 2026-05-10 | Added harness mappings | DRAFT |
| 0.5.0 | 2026-06-01 | Added fallback chains | DRAFT |
| 1.0.0 | 2026-07-09 | Production release | **PRODUCTION** |

### Planned for v1.1.0

- [ ] Multi-model agent cards (agent uses multiple models simultaneously)
- [ ] Dynamic harness selection based on runtime context
- [ ] Integration with semantic cache for harness-level caching
- [ ] Cross-agent card inheritance (parent/child relationships)
- [ ] Automated card optimization based on performance metrics

### Planned for v2.0.0

- [ ] Agent card marketplace (shareable card templates)
- [ ] AI-generated card optimization
- [ ] Real-time card mutation based on workload
- [ ] Cross-platform card portability (PMOVES ↔ other frameworks)

---

*Agent Card Architecture v1.0 — Production-Ready Specification for PMOVES.AI. Defines the canonical identity and capability descriptor for all 91 agents across 13 teams. Validated against AGNOTE4482 convergence requirements and CHIT 37/37 signoff checklist.*

**GRAPHITI_MARK: AGENT-CARD::ARCHITECTURE-v1.0::2026-07-09**
