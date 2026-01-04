/* ═══════════════════════════════════════════════════════════════════════════
   TensorZero Configuration Types
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Represents a model provider configuration
 */
export interface ProviderConfig {
  /** Provider name (e.g., "openai", "anthropic", "ollama") */
  name: string;
  /** Provider type (e.g., "openai", "anthropic", "ollama", "venice") */
  type: string;
  /** Base URL for the provider API (optional) */
  base_url?: string;
  /** API key (optional) */
  api_key?: string;
  /** Additional provider-specific configuration */
  [key: string]: any;
}

/**
 * Weight configuration for variant routing
 */
export interface WeightConfig {
  /** Variant identifier */
  variant_name: string;
  /** Weight for routing (0-1) */
  weight: number;
}

/**
 * Model variant configuration
 */
export interface VariantConfig {
  /** Variant identifier (e.g., "gpt4", "claude-opus") */
  name: string;
  /** Model identifier (e.g., "gpt-4", "claude-3-opus-20240229") */
  model: string;
  /** Provider to use for this variant */
  provider: string;
  /** System prompt override (optional) */
  system_prompt?: string;
  /** Temperature parameter (0-2) */
  temperature?: number;
  /** Max tokens to generate */
  max_tokens?: number;
  /** Top-p sampling parameter */
  top_p?: number;
  /** Additional model-specific parameters */
  parameters?: Record<string, any>;
}

/**
 * JSON Schema for tool input validation
 */
export interface ToolSchema {
  /** Schema type (usually "object") */
  type: string;
  /** Required properties */
  required?: string[];
  /** Property definitions */
  properties?: Record<string, SchemaProperty>;
  /** Additional schema properties */
  [key: string]: any;
}

/**
 * Property definition within JSON schema
 */
export interface SchemaProperty {
  /** Property type (e.g., "string", "number", "boolean", "array") */
  type: string;
  /** Property description */
  description?: string;
  /** Enum values for constrained properties */
  enum?: any[];
  /** Array item schema (for array types) */
  items?: SchemaProperty;
  /** Nested properties (for object types) */
  properties?: Record<string, SchemaProperty>;
  /** Required nested properties */
  required?: string[];
}

/**
 * Tool configuration for functions
 */
export interface ToolConfig {
  /** Tool identifier (e.g., "search_knowledge_base") */
  name: string;
  /** Tool description (seen by LLM) */
  description: string;
  /** MCP parameters (for MCP-connected tools) */
  parameters?: Record<string, any>;
  /** JSON schema for input validation */
  input_schema: ToolSchema;
}

/**
 * Function configuration
 */
export interface FunctionConfig {
  /** Function identifier (e.g., "chat", "summarize") */
  name: string;
  /** Function description (metadata only) */
  description?: string;
  /** System prompt for the function */
  system_prompt: string;
  /** Variant routing configuration */
  variants: VariantConfig[];
  /** Weight-based A/B testing configuration */
  weights?: WeightConfig[];
  /** Tools available to this function (optional) */
  tools?: ToolConfig[];
  /** Additional function-specific configuration */
  [key: string]: any;
}

/**
 * Complete TensorZero configuration
 */
export interface TensorZeroConfig {
  /** API version identifier */
  api_version: string;
  /** Model providers configuration */
  providers: ProviderConfig[];
  /** Functions configuration */
  functions: FunctionConfig[];
  /** Additional configuration */
  [key: string]: any;
}

/**
 * Configuration change entry for history tracking
 */
export interface ConfigHistoryEntry {
  /** Unique identifier */
  id: string;
  /** ISO timestamp of change */
  timestamp: string;
  /** Actor who made the change */
  author: string;
  /** Change description */
  description: string;
  /** Full configuration snapshot */
  config: TensorZeroConfig;
  /** Git commit hash (if versioned) */
  commit_hash?: string;
}

/**
 * Validation result for configuration
 */
export interface ValidationResult {
  /** Whether configuration is valid */
  valid: boolean;
  /** Validation errors (if any) */
  errors: ValidationError[];
  /** Validation warnings (if any) */
  warnings: ValidationWarning[];
}

/**
 * Validation error detail
 */
export interface ValidationError {
  /** Error severity ("error" or "warning") */
  severity: 'error' | 'warning';
  /** Field path with error (e.g., "functions.0.variants.0.model") */
  field: string;
  /** Error message */
  message: string;
  /** Suggested fix (optional) */
  suggestion?: string;
}

/**
 * Validation warning detail
 */
export interface ValidationWarning {
  /** Warning field path */
  field: string;
  /** Warning message */
  message: string;
}

/**
 * Test request payload
 */
export interface TestRequest {
  /** Function to test */
  function_name: string;
  /** Input message */
  input: {
    /** User message content */
    messages: Array<{
      /** Message role ("system", "user", "assistant") */
      role: string;
      /** Message content */
      content: string;
    }>;
  };
  /** Variant to use (optional) */
  variant_name?: string;
  /** Stream response flag */
  stream?: boolean;
  /** Additional test parameters */
  [key: string]: any;
}

/**
 * Test response from TensorZero API
 */
export interface TestResponse {
  /** Generated content */
  content?: string;
  /** Finish reason ("stop", "length", "error") */
  finish_reason?: string;
  /** Token usage */
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  /** Response latency in milliseconds */
  latency_ms?: number;
  /** Error message (if failed) */
  error?: string;
  /** Additional response metadata */
  [key: string]: any;
}

/**
 * Smart default configuration template
 */
export interface SmartDefaultsTemplate {
  /** Template identifier */
  id: string;
  /** Template name */
  name: string;
  /** Template description */
  description: string;
  /** Template icon (emoji) */
  icon: string;
  /** Full configuration */
  config: TensorZeroConfig;
  /** Configuration tags */
  tags: string[];
}

/**
 * Variant routing template type
 */
export type VariantTemplateType =
  | 'ab_test'
  | 'fallback_chain'
  | 'cost_based_routing'
  | 'latency_based_routing';

/**
 * Variant routing template
 */
export interface VariantTemplate {
  /** Template type */
  type: VariantTemplateType;
  /** Template name */
  name: string;
  /** Template description */
  description: string;
  /** Suggested variants configuration */
  variants: VariantConfig[];
  /** Suggested weights configuration */
  weights?: WeightConfig[];
  /** Routing logic explanation */
  routing_logic: string;
}

/**
 * UI tab configuration for TensorZero dashboard
 */
export interface DashboardTab {
  /** Tab identifier */
  id: string;
  /** Tab label */
  label: string;
  /** Tab icon (emoji) */
  icon: string;
  /** Tab description */
  description: string;
}
