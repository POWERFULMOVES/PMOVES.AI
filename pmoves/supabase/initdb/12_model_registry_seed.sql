-- Seed data: Model Registry for PMOVES.AI
-- Purpose: Initial model configuration for quick start
--
-- This seed provides:
-- 1. Default providers (Ollama local, Z.ai cloud, OpenAI, Venice)
-- 2. Common local models for immediate use
-- 3. Service mappings for agent_zero and langextract functions
--
-- Idempotent: Uses ON CONFLICT to allow safe re-seeding

-- =============================================================================
-- Providers
-- =============================================================================

-- Ollama local (primary local provider)
INSERT INTO pmoves_core.model_providers (name, type, api_base, api_key_env_var, description, active, metadata)
VALUES (
  'ollama_local',
  'ollama',
  'http://pmoves-ollama:11434/v1',
  NULL,
  'Local Ollama instance on Docker network',
  true,
  '{"network": "internal", "location": "local"}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
  api_base = EXCLUDED.api_base,
  description = EXCLUDED.description,
  updated_at = NOW();

-- Ollama edge (for edge/Jetson devices)
INSERT INTO pmoves_core.model_providers (name, type, api_base, api_key_env_var, description, active, metadata)
VALUES (
  'ollama_edge',
  'ollama',
  'http://jetson-ollama:11434/v1',
  NULL,
  'Edge Ollama instance on Jetson devices',
  true,
  '{"network": "internal", "location": "edge"}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
  api_base = EXCLUDED.api_base,
  description = EXCLUDED.description,
  updated_at = NOW();

-- Z.ai (primary cloud provider)
INSERT INTO pmoves_core.model_providers (name, type, api_base, api_key_env_var, description, active, metadata)
VALUES (
  'zai_primary',
  'openai_compatible',
  'https://api.z.ai/api/coding/paas/v4',
  'Z_AI_API_KEY',
  'Z.ai cloud provider (gpt-4o-mini, glm-4-flash)',
  true,
  '{"location": "cloud", "supports_chinese": true}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
  api_base = EXCLUDED.api_base,
  api_key_env_var = EXCLUDED.api_key_env_var,
  description = EXCLUDED.description,
  updated_at = NOW();

-- OpenAI (standard cloud provider)
INSERT INTO pmoves_core.model_providers (name, type, api_base, api_key_env_var, description, active, metadata)
VALUES (
  'openai_platform',
  'openai_compatible',
  'https://api.openai.com/v1',
  'OPENAI_API_KEY',
  'OpenAI official API (gpt-4o-mini, text-embedding-3-small)',
  true,
  '{"location": "cloud"}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
  api_base = EXCLUDED.api_base,
  api_key_env_var = EXCLUDED.api_key_env_var,
  description = EXCLUDED.description,
  updated_at = NOW();

-- Venice (privacy-focused cloud provider)
INSERT INTO pmoves_core.model_providers (name, type, api_base, api_key_env_var, description, active, metadata)
VALUES (
  'venice_primary',
  'openai_compatible',
  'https://api.venice.ai/api/v1',
  'VENICE_API_KEY',
  'Venice.ai privacy-focused provider',
  true,
  '{"location": "cloud", "privacy": "high"}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
  api_base = EXCLUDED.api_base,
  api_key_env_var = EXCLUDED.api_key_env_var,
  description = EXCLUDED.description,
  updated_at = NOW();

-- Groq (fast inference)
INSERT INTO pmoves_core.model_providers (name, type, api_base, api_key_env_var, description, active, metadata)
VALUES (
  'groq_primary',
  'openai_compatible',
  'https://api.groq.com/openai/v1',
  'GROQ_API_KEY',
  'Groq fast inference provider',
  true,
  '{"location": "cloud", "speed": "fast"}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
  api_base = EXCLUDED.api_base,
  api_key_env_var = EXCLUDED.api_key_env_var,
  description = EXCLUDED.description,
  updated_at = NOW();

-- OpenRouter (multi-model aggregator)
INSERT INTO pmoves_core.model_providers (name, type, api_base, api_key_env_var, description, active, metadata)
VALUES (
  'openrouter_primary',
  'openai_compatible',
  'https://openrouter.ai/api/v1',
  'OPENROUTER_API_KEY',
  'OpenRouter multi-model aggregator',
  true,
  '{"location": "cloud", "model_count": "high"}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
  api_base = EXCLUDED.api_base,
  api_key_env_var = EXCLUDED.api_key_env_var,
  description = EXCLUDED.description,
  updated_at = NOW();

-- Together AI
INSERT INTO pmoves_core.model_providers (name, type, api_base, api_key_env_var, description, active, metadata)
VALUES (
  'together_primary',
  'openai_compatible',
  'https://api.together.xyz/v1',
  'TOGETHER_AI_API_KEY',
  'Together AI open-source models',
  true,
  '{"location": "cloud", "model_type": "opensource"}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
  api_base = EXCLUDED.api_base,
  api_key_env_var = EXCLUDED.api_key_env_var,
  description = EXCLUDED.description,
  updated_at = NOW();

-- =============================================================================
-- Local Chat Models (Ollama)
-- =============================================================================

-- Helper to get provider IDs (done via separate queries for compatibility)
DO $$
DECLARE
  v_ollama_local_id UUID;
  v_ollama_edge_id UUID;
BEGIN
  SELECT id INTO v_ollama_local_id FROM pmoves_core.model_providers WHERE name = 'ollama_local';
  SELECT id INTO v_ollama_edge_id FROM pmoves_core.model_providers WHERE name = 'ollama_edge';

  -- Qwen3 8B - General purpose local model
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_ollama_local_id,
    'qwen3_8b_local',
    'qwen3:8b',
    'chat',
    '["chat", "function_calling", "json_mode"]'::jsonb,
    8000,
    32768,
    'Qwen3 8B - Efficient general-purpose model for orchestration and research',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    vram_mb = EXCLUDED.vram_mb,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Qwen2.5 32B - Flagship local model
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_ollama_local_id,
    'qwen2_5_32b',
    'qwen2.5:32b',
    'chat',
    '["chat", "function_calling", "json_mode", "tool_use"]'::jsonb,
    20000,
    32768,
    'Qwen2.5 32B - Flagship general-purpose model with strong reasoning',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    vram_mb = EXCLUDED.vram_mb,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Qwen2.5 14B - Efficient alternative
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_ollama_local_id,
    'qwen2_5_14b',
    'qwen2.5:14b',
    'chat',
    '["chat", "function_calling", "json_mode"]'::jsonb,
    9000,
    32768,
    'Qwen2.5 14B - Efficient model for resource-constrained environments',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    vram_mb = EXCLUDED.vram_mb,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Qwen2-VL 7B - Vision-language model
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_ollama_local_id,
    'qwen2_vl_7b',
    'qwen2-vl:7b',
    'vl',
    '["chat", "vision", "image_analysis"]'::jsonb,
    6000,
    32768,
    'Qwen2-VL 7B - Multimodal vision-language model for image analysis',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    vram_mb = EXCLUDED.vram_mb,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Qwen3 Reranker 4B
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_ollama_local_id,
    'qwen3_reranker_4b',
    'qwen3-reranker:4b',
    'reranker',
    '["reranking"]'::jsonb,
    3000,
    32768,
    'Qwen3 Reranker 4B - Cross-encoder reranking for Hi-RAG v2',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    vram_mb = EXCLUDED.vram_mb,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Nemotron Mini - NVIDIA research model
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_ollama_local_id,
    'nemotron_mini',
    'nemotron-mini',
    'chat',
    '["chat", "function_calling", "research"]'::jsonb,
    4000,
    128000,
    'Nemotron Mini - NVIDIA efficient research model for DeepResearch',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    vram_mb = EXCLUDED.vram_mb,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Llama3.1
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_ollama_local_id,
    'llama3_1',
    'llama3.1',
    'chat',
    '["chat", "function_calling"]'::jsonb,
    5000,
    128000,
    'Llama3.1 - Meta open-source chat model',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    vram_mb = EXCLUDED.vram_mb,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Edge models (Jetson)
  -- Mistral 7B Edge
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_ollama_edge_id,
    'mistral_7b_edge',
    'mistral:7b-instruct',
    'chat',
    '["chat", "function_calling"]'::jsonb,
    4000,
    32768,
    'Mistral 7B - Edge deployment on Jetson devices',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    vram_mb = EXCLUDED.vram_mb,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Phi3 Mini Edge
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_ollama_edge_id,
    'phi3_mini_edge',
    'phi3:3.8b-mini-128k-instruct',
    'chat',
    '["chat", "function_calling", "json_mode"]'::jsonb,
    2500,
    128000,
    'Phi3 Mini 3.8B - Edge deployment with 128k context',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    vram_mb = EXCLUDED.vram_mb,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

END $$;

-- =============================================================================
-- Cloud Chat Models
-- =============================================================================

DO $$
DECLARE
  v_zai_id UUID;
  v_openai_id UUID;
  v_venice_id UUID;
  v_groq_id UUID;
  v_openrouter_id UUID;
  v_together_id UUID;
BEGIN
  SELECT id INTO v_zai_id FROM pmoves_core.model_providers WHERE name = 'zai_primary';
  SELECT id INTO v_openai_id FROM pmoves_core.model_providers WHERE name = 'openai_platform';
  SELECT id INTO v_venice_id FROM pmoves_core.model_providers WHERE name = 'venice_primary';
  SELECT id INTO v_groq_id FROM pmoves_core.model_providers WHERE name = 'groq_primary';
  SELECT id INTO v_openrouter_id FROM pmoves_core.model_providers WHERE name = 'openrouter_primary';
  SELECT id INTO v_together_id FROM pmoves_core.model_providers WHERE name = 'together_primary';

  -- Z.ai GPT-4o-mini
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_zai_id,
    'chat_zai',
    'gpt-4o-mini',
    'chat',
    '["chat", "function_calling", "json_mode", "tool_use"]'::jsonb,
    0,
    128000,
    'Z.ai GPT-4o-mini - Primary cloud model via Z.ai endpoint',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Z.ai GLM-4-Flash (Chinese support)
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_zai_id,
    'chat_zai_glm',
    'glm-4-flash',
    'chat',
    '["chat", "function_calling", "chinese"]'::jsonb,
    0,
    128000,
    'Z.ai GLM-4-Flash - Chinese language model with fast inference',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- OpenAI GPT-4o-mini
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_openai_id,
    'chat_openai_platform',
    'gpt-4o-mini',
    'chat',
    '["chat", "function_calling", "json_mode", "tool_use"]'::jsonb,
    0,
    128000,
    'OpenAI GPT-4o-mini - Official OpenAI endpoint',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Venice GPT-4o-mini
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_venice_id,
    'chat_venice',
    'venice/gpt-4o-mini',
    'chat',
    '["chat", "function_calling", "privacy"]'::jsonb,
    0,
    128000,
    'Venice GPT-4o-mini - Privacy-focused cloud model',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Groq Llama 3.1 8B
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_groq_id,
    'chat_groq',
    'llama-3.1-8b-instant',
    'chat',
    '["chat", "function_calling", "speed"]'::jsonb,
    0,
    128000,
    'Groq Llama 3.1 8B - Fast inference on Groq hardware',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- OpenRouter GPT-4o-mini
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_openrouter_id,
    'chat_openrouter',
    'openai/gpt-4o-mini',
    'chat',
    '["chat", "function_calling"]'::jsonb,
    0,
    128000,
    'OpenRouter GPT-4o-mini - Via OpenRouter aggregator',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Together Llama 3.1 70B
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_together_id,
    'chat_together',
    'meta-llama/Meta-Llama-3.1-70B-Instruct',
    'chat',
    '["chat", "function_calling"]'::jsonb,
    0,
    128000,
    'Together Llama 3.1 70B - Large open-source model via Together',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

END $$;

-- =============================================================================
-- Embedding Models
-- =============================================================================

DO $$
DECLARE
  v_ollama_local_id UUID;
  v_together_id UUID;
  v_openai_id UUID;
  v_openrouter_id UUID;
  v_venice_id UUID;
  v_model_id UUID;
BEGIN
  SELECT id INTO v_ollama_local_id FROM pmoves_core.model_providers WHERE name = 'ollama_local';
  SELECT id INTO v_together_id FROM pmoves_core.model_providers WHERE name = 'together_primary';
  SELECT id INTO v_openai_id FROM pmoves_core.model_providers WHERE name = 'openai_platform';
  SELECT id INTO v_openrouter_id FROM pmoves_core.model_providers WHERE name = 'openrouter_primary';
  SELECT id INTO v_venice_id FROM pmoves_core.model_providers WHERE name = 'venice_primary';

  -- Qwen3 Embedding 4B (local)
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_ollama_local_id,
    'qwen3_embedding_4b_local',
    'qwen3-embedding:4b',
    'embedding',
    '["embeddings"]'::jsonb,
    3000,
    32768,
    'Qwen3 Embedding 4B - Local embedding model',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    vram_mb = EXCLUDED.vram_mb,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW()
  RETURNING id INTO v_model_id;

  -- Alias for default embedding
  INSERT INTO pmoves_core.model_aliases (model_id, alias, context)
  VALUES (v_model_id, 'default_embedding', 'tensorzero')
  ON CONFLICT (model_id, context) DO NOTHING;

  -- Qwen3 Embedding 8B (local, high-quality)
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_ollama_local_id,
    'qwen3_embedding_8b_local',
    'qwen3-embedding:8b',
    'embedding',
    '["embeddings"]'::jsonb,
    6000,
    32768,
    'Qwen3 Embedding 8B - High-quality local embedding (4096-dim, RTX 5090)',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    vram_mb = EXCLUDED.vram_mb,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Gemma Embedding (local, lightweight)
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_ollama_local_id,
    'gemma_embed_local',
    'embeddinggemma:300m',
    'embedding',
    '["embeddings"]'::jsonb,
    1500,
    32768,
    'Gemma Embedding 300M - Lightweight local embedding model',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    vram_mb = EXCLUDED.vram_mb,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Nomic Embed Text (local, popular)
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_ollama_local_id,
    'archon_nomic_embed_local',
    'nomic-embed-text',
    'embedding',
    '["embeddings"]'::jsonb,
    1000,
    8192,
    'Nomic Embed Text - Popular local embedding model',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    vram_mb = EXCLUDED.vram_mb,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- BGE Large (Together)
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_together_id,
    'archon_bge_large_together',
    'BAAI/bge-large-en-v1.5',
    'embedding',
    '["embeddings"]'::jsonb,
    0,
    512,
    'BGE Large v1.5 - High-quality English embedding via Together',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- E5 Large (Together)
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_together_id,
    'archon_e5_large_together',
    'intfloat/e5-large-v2',
    'embedding',
    '["embeddings"]'::jsonb,
    0,
    512,
    'E5 Large v2 - Dense retrieval embedding via Together',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- OpenAI text-embedding-3-small
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_openai_id,
    'openai_text_embedding_small',
    'text-embedding-3-small',
    'embedding',
    '["embeddings"]'::jsonb,
    0,
    8191,
    'OpenAI text-embedding-3-small - Official OpenAI embedding',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- OpenRouter multilingual embedding
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_openrouter_id,
    'openrouter_embedding',
    'voyage/multilingual-2',
    'embedding',
    '["embeddings", "multilingual"]'::jsonb,
    0,
    32000,
    'OpenRouter Multilingual - Multilingual embedding via OpenRouter',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Venice embedding
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_venice_id,
    'venice_embedding',
    'venice/embedding-gemma-300m',
    'embedding',
    '["embeddings", "privacy"]'::jsonb,
    0,
    32768,
    'Venice Embedding Gemma - Privacy-focused embedding via Venice',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

  -- Together text-embedding-20-light
  INSERT INTO pmoves_core.models (provider_id, name, model_id, model_type, capabilities, vram_mb, context_length, description, active)
  VALUES (
    v_together_id,
    'together_embedding',
    'togethercomputer/text-embedding-20-light',
    'embedding',
    '["embeddings"]'::jsonb,
    0,
    512,
    'Together text-embedding-20-light - Fast embedding via Together',
    true
  )
  ON CONFLICT (provider_id, model_id) DO UPDATE SET
    name = EXCLUDED.name,
    capabilities = EXCLUDED.capabilities,
    context_length = EXCLUDED.context_length,
    description = EXCLUDED.description,
    updated_at = NOW();

END $$;

-- =============================================================================
-- Service Model Mappings
-- =============================================================================

DO $$
DECLARE
  -- Local model IDs
  v_qwen3_8b_id UUID;
  v_qwen2_5_32b_id UUID;
  v_nemotron_id UUID;
  v_qwen3_emb_4b_id UUID;

  -- Edge model IDs
  v_mistral_edge_id UUID;
  v_phi3_edge_id UUID;

  -- Cloud model IDs
  v_zai_id UUID;
  v_openai_id UUID;
  v_venice_id UUID;
  v_groq_id UUID;
  v_openrouter_id UUID;
BEGIN
  -- Get local model IDs
  SELECT id INTO v_qwen3_8b_id FROM pmoves_core.models WHERE model_id = 'qwen3:8b' LIMIT 1;
  SELECT id INTO v_qwen2_5_32b_id FROM pmoves_core.models WHERE model_id = 'qwen2.5:32b' LIMIT 1;
  SELECT id INTO v_nemotron_id FROM pmoves_core.models WHERE model_id = 'nemotron-mini' LIMIT 1;
  SELECT id INTO v_qwen3_emb_4b_id FROM pmoves_core.models WHERE model_id = 'qwen3-embedding:4b' LIMIT 1;

  -- Get edge model IDs
  SELECT id INTO v_mistral_edge_id FROM pmoves_core.models WHERE model_id = 'mistral:7b-instruct' AND name LIKE '%edge%' LIMIT 1;
  SELECT id INTO v_phi3_edge_id FROM pmoves_core.models WHERE model_id = 'phi3:3.8b-mini-128k-instruct' AND name LIKE '%edge%' LIMIT 1;

  -- Get cloud model IDs
  SELECT id INTO v_zai_id FROM pmoves_core.models WHERE model_id = 'gpt-4o-mini' AND name = 'chat_zai' LIMIT 1;
  SELECT id INTO v_openai_id FROM pmoves_core.models WHERE model_id = 'gpt-4o-mini' AND name = 'chat_openai_platform' LIMIT 1;
  SELECT id INTO v_venice_id FROM pmoves_core.models WHERE model_id = 'venice/gpt-4o-mini' LIMIT 1;
  SELECT id INTO v_groq_id FROM pmoves_core.models WHERE model_id = 'llama-3.1-8b-instant' LIMIT 1;
  SELECT id INTO v_openrouter_id FROM pmoves_core.models WHERE model_id = 'openai/gpt-4o-mini' LIMIT 1;

  -- agent_zero function mappings
  -- Local Qwen3 8B (default local)
  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('agent_zero', 'chat', v_qwen3_8b_id, 'local_qwen8b', 1, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

  -- Local Qwen2.5 32B (high-quality local)
  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('agent_zero', 'chat', v_qwen2_5_32b_id, 'local_qwen32b', 2, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

  -- Edge Mistral 7B
  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('agent_zero', 'chat', v_mistral_edge_id, 'edge_mistral7b', 3, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

  -- Edge Phi3 Mini
  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('agent_zero', 'chat', v_phi3_edge_id, 'edge_phi3_mini', 4, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

  -- Cloud Z.ai (primary cloud)
  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('agent_zero', 'chat', v_zai_id, 'hosted_zai', 10, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

  -- Cloud OpenAI
  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('agent_zero', 'chat', v_openai_id, 'hosted_openai', 11, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

  -- Cloud Venice
  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('agent_zero', 'chat', v_venice_id, 'hosted_venice', 12, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

  -- Cloud OpenRouter
  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('agent_zero', 'chat', v_openrouter_id, 'hosted_openrouter', 13, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

  -- langextract function mappings
  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('langextract', 'nlp', v_qwen3_8b_id, 'langextract_local_qwen8b', 1, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('langextract', 'nlp', v_mistral_edge_id, 'langextract_edge_mistral7b', 2, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('langextract', 'nlp', v_openai_id, 'langextract_openai', 10, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

  -- deepresearch function mappings
  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('deepresearch', 'planning', v_nemotron_id, 'nemotron_mini', 1, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('deepresearch', 'planning', v_qwen2_5_32b_id, 'qwen2_5_32b', 2, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

  -- embeddings function mappings
  INSERT INTO pmoves_core.service_model_mappings (service_name, function_name, model_id, variant_name, priority, weight)
  VALUES ('tensorzero', 'embeddings', v_qwen3_emb_4b_id, 'local', 1, 1.0)
  ON CONFLICT (service_name, function_name, variant_name) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    priority = EXCLUDED.priority,
    weight = EXCLUDED.weight;

END $$;

-- =============================================================================
-- Audit Log Entry
-- =============================================================================

INSERT INTO pmoves_core.model_providers (name, type, description, active, metadata)
VALUES ('_seed_audit', 'custom', 'Model registry seed data initialized', true, '{"seeded_at": "' || NOW()::text || '", "version": "1.0"}'::jsonb)
ON CONFLICT (name) DO UPDATE SET
  metadata = EXCLUDED.metadata,
  updated_at = NOW();
