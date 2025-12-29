/* ═══════════════════════════════════════════════════════════════════════════
   TensorZero API Client
   ═══════════════════════════════════════════════════════════════════════════ */

import axios, { AxiosInstance } from 'axios';
import type {
  TensorZeroConfig,
  TestRequest,
  TestResponse,
  ValidationResult,
} from './types';

/**
 * TensorZero API client configuration
 */
const TENSORZERO_API_URL = process.env.NEXT_PUBLIC_TENSORZERO_API_URL || 'http://localhost:3030';
const TENSORZERO_UI_URL = process.env.NEXT_PUBLIC_TENSORZERO_UI || 'http://localhost:4000';

/**
 * Create configured axios instance for TensorZero API
 */
function createApiClient(baseURL: string): AxiosInstance {
  return axios.create({
    baseURL,
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: 30000,
  });
}

const apiClient = createApiClient(TENSORZERO_API_URL);

/**
 * Fetch current TensorZero configuration
 */
export async function fetchConfig(): Promise<TensorZeroConfig> {
  try {
    const response = await apiClient.get('/config');
    return response.data;
  } catch (error) {
    console.error('Failed to fetch TensorZero config:', error);
    throw new Error('Unable to fetch TensorZero configuration. Is the gateway running?');
  }
}

/**
 * Update TensorZero configuration
 */
export async function updateConfig(config: TensorZeroConfig): Promise<void> {
  try {
    await apiClient.put('/config', config);
  } catch (error) {
    console.error('Failed to update TensorZero config:', error);
    throw new Error('Failed to update configuration. Please try again.');
  }
}

/**
 * Validate TensorZero configuration
 */
export async function validateConfig(config: TensorZeroConfig): Promise<ValidationResult> {
  try {
    const response = await apiClient.post('/config/validate', config);
    return response.data;
  } catch (error) {
    console.error('Failed to validate config:', error);
    return {
      valid: false,
      errors: [{ severity: 'error', field: 'config', message: 'Validation service unavailable' }],
      warnings: [],
    };
  }
}

/**
 * Send test request to TensorZero
 */
export async function testRequest(request: TestRequest): Promise<TestResponse> {
  try {
    const startTime = Date.now();
    const response = await apiClient.post('/v1/chat/completions', {
      model: request.function_name,
      messages: request.input.messages,
      stream: request.stream ?? false,
      ...(request.variant_name && { variant_name: request.variant_name }),
    });

    const latency = Date.now() - startTime;

    return {
      content: response.data.choices?.[0]?.message?.content,
      finish_reason: response.data.choices?.[0]?.finish_reason,
      usage: response.data.usage,
      latency_ms: latency,
    };
  } catch (error: any) {
    console.error('Test request failed:', error);
    return {
      error: error.response?.data?.message || error.message || 'Test request failed',
    };
  }
}

/**
 * Fetch metrics from TensorZero ClickHouse
 */
export async function fetchMetrics(timeRange: string = '1h'): Promise<any> {
  try {
    const response = await axios.get(`${TENSORZERO_API_URL}/metrics`, {
      params: { range: timeRange },
    });
    return response.data;
  } catch (error) {
    console.error('Failed to fetch metrics:', error);
    throw new Error('Unable to fetch metrics. Is ClickHouse running?');
  }
}

/**
 * Get TensorZero UI URL for embedding
 */
export function getTensorZeroUIUrl(): string {
  return TENSORZERO_UI_URL;
}

/**
 * Check TensorZero gateway health
 */
export async function checkHealth(): Promise<boolean> {
  try {
    await apiClient.get('/health');
    return true;
  } catch {
    return false;
  }
}

/**
 * Export configuration as TOML
 */
export function exportAsToml(config: TensorZeroConfig): string {
  // Basic TOML serialization (in production, use a proper TOML library)
  const lines: string[] = [];

  lines.push(`api_version = "${config.api_version}"`);
  lines.push('');

  // Providers section
  lines.push('[[providers]]');
  config.providers.forEach((provider, idx) => {
    lines.push(`  name = "${provider.name}"`);
    lines.push(`  type = "${provider.type}"`);
    if (provider.base_url) lines.push(`  base_url = "${provider.base_url}"`);
    if (provider.api_key) lines.push(`  api_key = "${provider.api_key}"`);
    if (idx < config.providers.length - 1) lines.push('');
  });
  lines.push('');

  // Functions section
  config.functions.forEach((func, fIdx) => {
    lines.push(`[functions.${func.name}]`);
    lines.push(`  system_prompt = """${func.system_prompt}"""`);
    if (func.description) {
      lines.push(`  description = """${func.description}"""`);
    }

    // Variants
    func.variants.forEach((variant, vIdx) => {
      lines.push(`  [[functions.${func.name}.variants]]`);
      lines.push(`    name = "${variant.name}"`);
      lines.push(`    model = "${variant.model}"`);
      lines.push(`    provider = "${variant.provider}"`);
      if (variant.system_prompt) {
        lines.push(`    system_prompt = """${variant.system_prompt}"""`);
      }
      if (variant.temperature !== undefined) {
        lines.push(`    temperature = ${variant.temperature}`);
      }
      if (variant.max_tokens !== undefined) {
        lines.push(`    max_tokens = ${variant.max_tokens}`);
      }
    });

    // Tools (if present)
    if (func.tools && func.tools.length > 0) {
      func.tools.forEach((tool) => {
        lines.push(`  [[functions.${func.name}.tools]]`);
        lines.push(`    name = "${tool.name}"`);
        lines.push(`    description = "${tool.description}"`);
        lines.push(`    input_schema = ${JSON.stringify(tool.input_schema)}`);
      });
    }

    // Weights
    if (func.weights && func.weights.length > 0) {
      lines.push(`  [[functions.${func.name}.weights]]`);
      func.weights.forEach((weight) => {
        lines.push(`    variant_name = "${weight.variant_name}"`);
        lines.push(`    weight = ${weight.weight}`);
      });
    }

    if (fIdx < config.functions.length - 1) lines.push('');
  });

  return lines.join('\n');
}

/**
 * Export configuration as JSON
 */
export function exportAsJson(config: TensorZeroConfig): string {
  return JSON.stringify(config, null, 2);
}

/**
 * Parse TOML configuration
 */
export async function parseToml(tomlContent: string): Promise<TensorZeroConfig> {
  // In production, use a proper TOML parser
  // For now, return a basic structure
  throw new Error('TOML parsing not yet implemented. Please use JSON format.');
}
