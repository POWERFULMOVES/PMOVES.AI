/* ═══════════════════════════════════════════════════════════════════════════
   TensorZero Smart Defaults Configuration Templates
   ═══════════════════════════════════════════════════════════════════════════ */

import type { SmartDefaultsTemplate, TensorZeroConfig, VariantTemplate } from './types';

/**
 * Low Latency Configuration - All local models via Ollama
 * Best for: Real-time chat, local development, offline scenarios
 */
export const lowLatencyConfig: SmartDefaultsTemplate = {
  id: 'low-latency',
  name: 'Low Latency (Local)',
  description: 'All models run locally via Ollama. Fastest response times, no API costs, works offline.',
  icon: '⚡',
  tags: ['local', 'fast', 'free'],
  config: {
    api_version: '1',
    providers: [
      {
        name: 'ollama',
        type: 'ollama',
        base_url: 'http://localhost:11434',
      },
    ],
    functions: [
      {
        name: 'chat',
        system_prompt: 'You are a helpful AI assistant.',
        variants: [
          {
            name: 'llama3.2',
            model: 'llama3.2',
            provider: 'ollama',
            temperature: 0.7,
            max_tokens: 2048,
          },
        ],
        weights: [
          { variant_name: 'llama3.2', weight: 1.0 },
        ],
      },
      {
        name: 'summarize',
        system_prompt: 'Summarize the following text concisely.',
        variants: [
          {
            name: 'llama3.2',
            model: 'llama3.2',
            provider: 'ollama',
            temperature: 0.3,
            max_tokens: 1024,
          },
        ],
      },
      {
        name: 'embed',
        system_prompt: 'Generate embeddings for text search.',
        variants: [
          {
            name: 'nomic-embed-text',
            model: 'nomic-embed-text',
            provider: 'ollama',
          },
        ],
      },
    ],
  },
};

/**
 * High Quality Configuration - Premium cloud providers
 * Best for: Content creation, complex reasoning, production applications
 */
export const highQualityConfig: SmartDefaultsTemplate = {
  id: 'high-quality',
  name: 'High Quality (Cloud)',
  description: 'Best-in-class models from Anthropic and OpenAI. Optimized for quality over cost.',
  icon: '💎',
  tags: ['cloud', 'quality', 'premium'],
  config: {
    api_version: '1',
    providers: [
      {
        name: 'anthropic',
        type: 'anthropic',
        api_key: '${ANTHROPIC_API_KEY}',
      },
      {
        name: 'openai',
        type: 'openai',
        api_key: '${OPENAI_API_KEY}',
      },
    ],
    functions: [
      {
        name: 'chat',
        description: 'General-purpose chat with high-quality responses',
        system_prompt: 'You are a helpful AI assistant.',
        variants: [
          {
            name: 'claude-opus',
            model: 'claude-3-opus-20240229',
            provider: 'anthropic',
            temperature: 0.7,
            max_tokens: 4096,
          },
          {
            name: 'gpt4-turbo',
            model: 'gpt-4-turbo-preview',
            provider: 'openai',
            temperature: 0.7,
            max_tokens: 4096,
          },
        ],
        weights: [
          { variant_name: 'claude-opus', weight: 0.7 },
          { variant_name: 'gpt4-turbo', weight: 0.3 },
        ],
      },
      {
        name: 'summarize',
        system_prompt: 'Summarize the following text concisely while preserving key information.',
        variants: [
          {
            name: 'claude-sonnet',
            model: 'claude-3-sonnet-20240229',
            provider: 'anthropic',
            temperature: 0.3,
            max_tokens: 2048,
          },
        ],
      },
      {
        name: 'code',
        system_prompt: 'You are an expert programmer. Write clean, efficient, well-documented code.',
        variants: [
          {
            name: 'claude-opus',
            model: 'claude-3-opus-20240229',
            provider: 'anthropic',
            temperature: 0.2,
            max_tokens: 4096,
          },
        ],
      },
    ],
  },
};

/**
 * Cost Optimized Configuration - Budget-friendly mix
 * Best for: High-volume applications, cost-sensitive projects
 */
export const costOptimizedConfig: SmartDefaultsTemplate = {
  id: 'cost-optimized',
  name: 'Cost Optimized',
  description: 'Mix of local models and budget cloud providers (Groq, Together AI). Best value for money.',
  icon: '💰',
  tags: ['budget', 'hybrid', 'scalable'],
  config: {
    api_version: '1',
    providers: [
      {
        name: 'ollama',
        type: 'ollama',
        base_url: 'http://localhost:11434',
      },
      {
        name: 'groq',
        type: 'groq',
        api_key: '${GROQ_API_KEY}',
        base_url: 'https://api.groq.com/openai/v1',
      },
      {
        name: 'together',
        type: 'together',
        api_key: '${TOGETHER_API_KEY}',
        base_url: 'https://api.together.xyz/v1',
      },
    ],
    functions: [
      {
        name: 'chat',
        system_prompt: 'You are a helpful AI assistant.',
        variants: [
          {
            name: 'llama3.2-local',
            model: 'llama3.2',
            provider: 'ollama',
            temperature: 0.7,
            max_tokens: 2048,
          },
          {
            name: 'llama3.2-groq',
            model: 'llama3.2-70b-versatile',
            provider: 'groq',
            temperature: 0.7,
            max_tokens: 2048,
          },
          {
            name: 'mistral-together',
            model: 'mistralai/Mixtral-8x7B-Instruct-v0.1',
            provider: 'together',
            temperature: 0.7,
            max_tokens: 2048,
          },
        ],
        weights: [
          { variant_name: 'llama3.2-local', weight: 0.5 },
          { variant_name: 'llama3.2-groq', weight: 0.3 },
          { variant_name: 'mistral-together', weight: 0.2 },
        ],
      },
      {
        name: 'summarize',
        system_prompt: 'Summarize the following text concisely.',
        variants: [
          {
            name: 'llama3.2-local',
            model: 'llama3.2',
            provider: 'ollama',
            temperature: 0.3,
            max_tokens: 1024,
          },
        ],
      },
    ],
  },
};

/**
 * Hybrid Fallback Configuration - Local primary, cloud fallback
 * Best for: Redundancy, high availability, cost control with cloud backup
 */
export const hybridFallbackConfig: SmartDefaultsTemplate = {
  id: 'hybrid-fallback',
  name: 'Hybrid Fallback',
  description: 'Primary local models with automatic cloud fallback. Best of both worlds.',
  icon: '🔄',
  tags: ['hybrid', 'reliable', 'redundant'],
  config: {
    api_version: '1',
    providers: [
      {
        name: 'ollama',
        type: 'ollama',
        base_url: 'http://localhost:11434',
      },
      {
        name: 'openai',
        type: 'openai',
        api_key: '${OPENAI_API_KEY}',
      },
    ],
    functions: [
      {
        name: 'chat',
        system_prompt: 'You are a helpful AI assistant.',
        variants: [
          {
            name: 'llama3.2-local',
            model: 'llama3.2',
            provider: 'ollama',
            temperature: 0.7,
            max_tokens: 2048,
          },
          {
            name: 'gpt4-fallback',
            model: 'gpt-4-turbo-preview',
            provider: 'openai',
            temperature: 0.7,
            max_tokens: 2048,
          },
        ],
        weights: [
          { variant_name: 'llama3.2-local', weight: 0.9 },
          { variant_name: 'gpt4-fallback', weight: 0.1 },
        ],
      },
      {
        name: 'summarize',
        system_prompt: 'Summarize the following text concisely.',
        variants: [
          {
            name: 'llama3.2-local',
            model: 'llama3.2',
            provider: 'ollama',
            temperature: 0.3,
            max_tokens: 1024,
          },
        ],
      },
    ],
  },
};

/**
 * Export all smart defaults templates
 */
export const smartDefaultsTemplates: SmartDefaultsTemplate[] = [
  lowLatencyConfig,
  highQualityConfig,
  costOptimizedConfig,
  hybridFallbackConfig,
];

/**
 * Variant Routing Templates
 */
export const variantTemplates: VariantTemplate[] = [
  {
    type: 'ab_test',
    name: 'A/B Test',
    description: 'Evenly split traffic between variants for comparison',
    variants: [
      {
        name: 'variant-a',
        model: 'llama3.2',
        provider: 'ollama',
        temperature: 0.7,
        max_tokens: 2048,
      },
      {
        name: 'variant-b',
        model: 'gpt-4-turbo-preview',
        provider: 'openai',
        temperature: 0.7,
        max_tokens: 2048,
      },
    ],
    weights: [
      { variant_name: 'variant-a', weight: 0.5 },
      { variant_name: 'variant-b', weight: 0.5 },
    ],
    routing_logic: 'Traffic is split evenly between variants based on configured weights. Use metrics to compare performance.',
  },
  {
    type: 'fallback_chain',
    name: 'Fallback Chain',
    description: 'Primary variant with secondary variants as fallbacks',
    variants: [
      {
        name: 'primary',
        model: 'claude-3-opus-20240229',
        provider: 'anthropic',
        temperature: 0.7,
        max_tokens: 4096,
      },
      {
        name: 'secondary',
        model: 'gpt-4-turbo-preview',
        provider: 'openai',
        temperature: 0.7,
        max_tokens: 4096,
      },
      {
        name: 'tertiary',
        model: 'llama3.2',
        provider: 'ollama',
        temperature: 0.7,
        max_tokens: 2048,
      },
    ],
    weights: [
      { variant_name: 'primary', weight: 0.95 },
      { variant_name: 'secondary', weight: 0.04 },
      { variant_name: 'tertiary', weight: 0.01 },
    ],
    routing_logic: '95% traffic to primary, 4% to secondary, 1% to tertiary. If primary fails, traffic automatically shifts to fallbacks.',
  },
  {
    type: 'cost_based_routing',
    name: 'Cost-Based Routing',
    description: 'Route to cheapest option that meets quality threshold',
    variants: [
      {
        name: 'budget',
        model: 'llama3.2',
        provider: 'ollama',
        temperature: 0.7,
        max_tokens: 2048,
      },
      {
        name: 'mid-tier',
        model: 'gpt-3.5-turbo',
        provider: 'openai',
        temperature: 0.7,
        max_tokens: 2048,
      },
      {
        name: 'premium',
        model: 'claude-3-opus-20240229',
        provider: 'anthropic',
        temperature: 0.7,
        max_tokens: 4096,
      },
    ],
    weights: [
      { variant_name: 'budget', weight: 0.7 },
      { variant_name: 'mid-tier', weight: 0.25 },
      { variant_name: 'premium', weight: 0.05 },
    ],
    routing_logic: '70% budget, 25% mid-tier, 5% premium. Adjust weights based on cost budget and quality requirements.',
  },
  {
    type: 'latency_based_routing',
    name: 'Latency-Based Routing',
    description: 'Prioritize fastest models for time-sensitive applications',
    variants: [
      {
        name: 'ultra-fast',
        model: 'llama3.2',
        provider: 'ollama',
        temperature: 0.7,
        max_tokens: 2048,
      },
      {
        name: 'fast',
        model: 'llama3.2-70b-versatile',
        provider: 'groq',
        temperature: 0.7,
        max_tokens: 2048,
      },
      {
        name: 'normal',
        model: 'gpt-4-turbo-preview',
        provider: 'openai',
        temperature: 0.7,
        max_tokens: 2048,
      },
    ],
    weights: [
      { variant_name: 'ultra-fast', weight: 0.6 },
      { variant_name: 'fast', weight: 0.3 },
      { variant_name: 'normal', weight: 0.1 },
    ],
    routing_logic: '60% ultra-fast (local), 30% fast (Groq), 10% normal. Prioritize latency over everything else.',
  },
];
