/**
 * @fileoverview Archon API Client for PMOVES UI
 *
 * Integrates with Archon service for:
 * - Prompt template management (CRUD)
 * - Prompt execution via Agent Zero MCP
 * - Form and schema management
 * - Service health monitoring
 *
 * Archon provides a Supabase-backed prompt store with Agent Zero integration.
 *
 * @module api/archon
 */

import { logError, Result, ok, err, getErrorMessage } from '../errorUtils';
import { ErrorIds } from '../constants/errorIds';

/**
 * Service configuration for Archon.
 */
const ARCHON_SERVICE_CONFIG = {
  slug: 'archon',
  defaultPort: 8091,
  envVar: 'NEXT_PUBLIC_ARCHON_URL',
} as const;

const ARCHON_TIMEOUT = 30000; // 30 seconds

/**
 * Resolves Archon base URL from environment or default.
 */
function getArchonUrl(): string {
  return (
    process.env.NEXT_PUBLIC_ARCHON_URL ||
    process.env.ARCHON_URL ||
    `http://localhost:${ARCHON_SERVICE_CONFIG.defaultPort}`
  ).replace(/\/$/, '');
}

/**
 * Prompt template categories.
 */
export type PromptCategory =
  | 'agent'
  | 'coding'
  | 'research'
  | 'analysis'
  | 'creative'
  | 'utility';

/**
 * Prompt template metadata.
 */
export interface PromptTemplate {
  /** Unique prompt ID */
  id: string;
  /** Prompt name/title */
  name: string;
  /** Prompt description */
  description?: string;
  /** Prompt category */
  category: PromptCategory;
  /** Prompt template content with {{variables}} */
  template: string;
  /** Variable definitions */
  variables: PromptVariable[];
  /** Target model for this prompt */
  model?: string;
  /** Tags for discovery */
  tags: string[];
  /** Owner user ID */
  owner_id?: string;
  /** Is public/shared */
  is_public: boolean;
  /** Created timestamp */
  created_at: string;
  /** Updated timestamp */
  updated_at: string;
}

/**
 * Prompt variable definition.
 */
export interface PromptVariable {
  /** Variable name (used in template as {{name}}) */
  name: string;
  /** Variable type */
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  /** Variable description */
  description?: string;
  /** Default value */
  default?: unknown;
  /** Whether variable is required */
  required: boolean;
}

/**
 * Prompt execution request.
 */
export interface PromptExecutionRequest {
  /** Prompt template ID */
  promptId: string;
  /** Variable values to substitute */
  variables: Record<string, unknown>;
  /** Optional model override */
  model?: string;
  /** Optional max iterations */
  maxIterations?: number;
}

/**
 * Prompt execution response.
 */
export interface PromptExecutionResult {
  /** Execution ID for tracking */
  executionId: string;
  /** Execution status */
  status: 'pending' | 'running' | 'completed' | 'failed';
  /** Generated result */
  result?: unknown;
  /** Error if failed */
  error?: string;
  /** Started timestamp */
  startedAt: string;
  /** Completed timestamp */
  completedAt?: string;
}

/**
 * Form schema for structured input.
 */
export interface FormSchema {
  /** Form ID */
  id: string;
  /** Form name */
  name: string;
  /** Form description */
  description?: string;
  /** JSON Schema for form validation */
  schema: Record<string, unknown>;
  /** UI schema for rendering */
  uiSchema?: Record<string, unknown>;
  /** Associated prompt IDs */
  promptIds: string[];
  /** Created timestamp */
  created_at: string;
}

/**
 * Health check response.
 */
export interface ArchonHealth {
  /** Service health status */
  healthy: boolean;
  /** Service version */
  version?: string;
  /** Supabase connection status */
  supabase?: {
    connected: boolean;
    poolSize?: number;
  };
  /** Agent Zero connection status */
  agentZero?: {
    connected: boolean;
  };
  /** Total prompt count */
  promptCount?: number;
}

/**
 * Lists all prompt templates.
 *
 * @param options - Optional filters
 * @returns Result with prompt list or error message
 *
 * @example
 * ```typescript
 * const result = await archonListPrompts({
 *   category: 'agent',
 *   is_public: true
 * });
 * ```
 */
export async function archonListPrompts(options: {
  /** Filter by category */
  category?: PromptCategory;
  /** Filter by public status */
  is_public?: boolean;
  /** Search in name/description */
  search?: string;
  /** Tag filter */
  tag?: string;
  /** Maximum results */
  limit?: number;
} = {}): Promise<Result<PromptTemplate[], string>> {
  try {
    const params = new URLSearchParams();
    if (options.category) params.set('category', options.category);
    if (options.is_public !== undefined)
      params.set('is_public', String(options.is_public));
    if (options.search) params.set('search', options.search);
    if (options.tag) params.set('tag', options.tag);
    if (options.limit) params.set('limit', String(options.limit));

    const queryString = params.toString();
    const url = `${getArchonUrl()}/api/prompts${queryString ? `?${queryString}` : ''}`;

    const response = await fetch(url, {
      signal: AbortSignal.timeout(ARCHON_TIMEOUT),
    });

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Archon list prompts failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.ARCHON_PROMPT_LIST_FAILED,
          component: 'archon',
          action: 'list-prompts',
        }
      );
      return err(message);
    }

    const data = (await response.json()) as { prompts?: PromptTemplate[] };
    return ok(data.prompts ?? []);
  } catch (error) {
    logError('Archon list prompts error', error, 'warning', {
      errorId: ErrorIds.ARCHON_PROMPT_LIST_FAILED,
      component: 'archon',
      action: 'list-prompts',
    });
    return err('Failed to list prompts');
  }
}

/**
 * Gets a single prompt template by ID.
 *
 * @param promptId - Prompt ID
 * @returns Result with prompt template or error message
 */
export async function archonGetPrompt(
  promptId: string
): Promise<Result<PromptTemplate, string>> {
  try {
    const response = await fetch(
      `${getArchonUrl()}/api/prompts/${encodeURIComponent(promptId)}`,
      {
        signal: AbortSignal.timeout(ARCHON_TIMEOUT),
      }
    );

    if (!response.ok) {
      if (response.status === 404) {
        return err('Prompt not found');
      }
      const message = getErrorMessage(response.status);
      logError(
        `Archon get prompt failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.ARCHON_PROMPT_LIST_FAILED,
          component: 'archon',
          action: 'get-prompt',
          promptId,
        }
      );
      return err(message);
    }

    const data = (await response.json()) as PromptTemplate;
    return ok(data);
  } catch (error) {
    logError('Archon get prompt error', error, 'warning', {
      errorId: ErrorIds.ARCHON_PROMPT_LIST_FAILED,
      component: 'archon',
      action: 'get-prompt',
      promptId,
    });
    return err('Failed to get prompt');
  }
}

/**
 * Creates a new prompt template.
 *
 * @param prompt - Prompt template to create
 * @returns Result with created prompt or error message
 */
export async function archonCreatePrompt(
  prompt: Omit<PromptTemplate, 'id' | 'created_at' | 'updated_at'>
): Promise<Result<PromptTemplate, string>> {
  try {
    const response = await fetch(`${getArchonUrl()}/api/prompts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(prompt),
      signal: AbortSignal.timeout(ARCHON_TIMEOUT),
    });

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Archon create prompt failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.ARCHON_PROMPT_CREATE_FAILED,
          component: 'archon',
          action: 'create-prompt',
        }
      );
      return err(message);
    }

    const data = (await response.json()) as PromptTemplate;
    return ok(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Archon create prompt error', error, 'error', {
      errorId: ErrorIds.ARCHON_PROMPT_CREATE_FAILED,
      component: 'archon',
      action: 'create-prompt',
    });
    return err(message);
  }
}

/**
 * Updates an existing prompt template.
 *
 * @param promptId - Prompt ID to update
 * @param updates - Fields to update
 * @returns Result with updated prompt or error message
 */
export async function archonUpdatePrompt(
  promptId: string,
  updates: Partial<
    Omit<PromptTemplate, 'id' | 'owner_id' | 'created_at' | 'updated_at'>
  >
): Promise<Result<PromptTemplate, string>> {
  try {
    const response = await fetch(
      `${getArchonUrl()}/api/prompts/${encodeURIComponent(promptId)}`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
        signal: AbortSignal.timeout(ARCHON_TIMEOUT),
      }
    );

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Archon update prompt failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.ARCHON_PROMPT_UPDATE_FAILED,
          component: 'archon',
          action: 'update-prompt',
          promptId,
        }
      );
      return err(message);
    }

    const data = (await response.json()) as PromptTemplate;
    return ok(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Archon update prompt error', error, 'error', {
      errorId: ErrorIds.ARCHON_PROMPT_UPDATE_FAILED,
      component: 'archon',
      action: 'update-prompt',
      promptId,
    });
    return err(message);
  }
}

/**
 * Deletes a prompt template.
 *
 * @param promptId - Prompt ID to delete
 * @returns Result with success confirmation or error message
 */
export async function archonDeletePrompt(
  promptId: string
): Promise<Result<{ deleted: true }, string>> {
  try {
    const response = await fetch(
      `${getArchonUrl()}/api/prompts/${encodeURIComponent(promptId)}`,
      {
        method: 'DELETE',
        signal: AbortSignal.timeout(ARCHON_TIMEOUT),
      }
    );

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Archon delete prompt failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.ARCHON_PROMPT_DELETE_FAILED,
          component: 'archon',
          action: 'delete-prompt',
          promptId,
        }
      );
      return err(message);
    }

    return ok({ deleted: true });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Archon delete prompt error', error, 'error', {
      errorId: ErrorIds.ARCHON_PROMPT_DELETE_FAILED,
      component: 'archon',
      action: 'delete-prompt',
      promptId,
    });
    return err(message);
  }
}

/**
 * Executes a prompt template with variable substitution.
 *
 * @param request - Execution request
 * @returns Result with execution result or error message
 *
 * @example
 * ```typescript
 * const result = await archonExecutePrompt({
 *   promptId: 'agent-coder',
 *   variables: { task: 'Fix the bug', language: 'typescript' }
 * });
 * ```
 */
export async function archonExecutePrompt(
  request: PromptExecutionRequest
): Promise<Result<PromptExecutionResult, string>> {
  try {
    const controller = new AbortController();
    // Allow longer timeout for prompt execution (includes Agent Zero time)
    const timeoutId = setTimeout(() => controller.abort(), 120000);

    const response = await fetch(`${getArchonUrl()}/api/prompts/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Archon execute prompt failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.ARCHON_PROMPT_EXECUTE_FAILED,
          component: 'archon',
          action: 'execute-prompt',
          promptId: request.promptId,
        }
      );
      return err(message);
    }

    const data = (await response.json()) as PromptExecutionResult;
    return ok(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Archon execute prompt error', error, 'error', {
      errorId:
        error instanceof Error && error.name === 'AbortError'
          ? ErrorIds.AGENT_ZERO_MCP_TIMEOUT
          : ErrorIds.ARCHON_PROMPT_EXECUTE_FAILED,
      component: 'archon',
      action: 'execute-prompt',
      promptId: request.promptId,
    });
    return err(message);
  }
}

/**
 * Lists all form schemas.
 *
 * @returns Result with form schemas or error message
 */
export async function archonListForms(): Promise<
  Result<FormSchema[], string>
> {
  try {
    const response = await fetch(`${getArchonUrl()}/api/forms`, {
      signal: AbortSignal.timeout(ARCHON_TIMEOUT),
    });

    if (!response.ok) {
      return err('Failed to list forms');
    }

    const data = (await response.json()) as { forms?: FormSchema[] };
    return ok(data.forms ?? []);
  } catch (error) {
    logError('Archon list forms error', error, 'warning', {
      errorId: ErrorIds.ARCHON_PROMPT_LIST_FAILED,
      component: 'archon',
      action: 'list-forms',
    });
    return err('Failed to list forms');
  }
}

/**
 * Gets a form schema by ID.
 *
 * @param formId - Form ID
 * @returns Result with form schema or error message
 */
export async function archonGetForm(
  formId: string
): Promise<Result<FormSchema, string>> {
  try {
    const response = await fetch(
      `${getArchonUrl()}/api/forms/${encodeURIComponent(formId)}`,
      {
        signal: AbortSignal.timeout(ARCHON_TIMEOUT),
      }
    );

    if (!response.ok) {
      if (response.status === 404) {
        return err('Form not found');
      }
      return err('Failed to get form');
    }

    const data = (await response.json()) as FormSchema;
    return ok(data);
  } catch (error) {
    logError('Archon get form error', error, 'warning', {
      errorId: ErrorIds.ARCHON_PROMPT_LIST_FAILED,
      component: 'archon',
      action: 'get-form',
      formId,
    });
    return err('Failed to get form');
  }
}

/**
 * Checks health status of Archon service.
 *
 * @returns Result with health status or error message
 */
export async function archonHealth(): Promise<Result<ArchonHealth, string>> {
  try {
    const response = await fetch(`${getArchonUrl()}/healthz`, {
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      return err('Archon health check failed');
    }

    const data = (await response.json()) as ArchonHealth;
    return ok({ ...data, healthy: true });
  } catch (error) {
    logError('Archon health check error', error, 'warning', {
      errorId: ErrorIds.ARCHON_HEALTH_CHECK_FAILED,
      component: 'archon',
      action: 'health',
    });
    return err('Archon service unavailable');
  }
}

/**
 * Validates prompt template variables against a schema.
 *
 * @param variables - Variable values to validate
 * @param schema - Variable definitions
 * @returns Result with validation result or error message
 */
export function archonValidateVariables(
  variables: Record<string, unknown>,
  schema: PromptVariable[]
): Result<{ valid: true }, { valid: false; errors: string[] }> {
  const errors: string[] = [];

  for (const def of schema) {
    const value = variables[def.name];

    // Check required variables
    if (def.required && (value === undefined || value === null)) {
      errors.push(`Required variable '${def.name}' is missing`);
      continue;
    }

    // Skip type validation if value is undefined and not required
    if (value === undefined) {
      continue;
    }

    // Type validation
    switch (def.type) {
      case 'string':
        if (typeof value !== 'string') {
          errors.push(`Variable '${def.name}' must be a string`);
        }
        break;
      case 'number':
        if (typeof value !== 'number' || isNaN(value)) {
          errors.push(`Variable '${def.name}' must be a number`);
        }
        break;
      case 'boolean':
        if (typeof value !== 'boolean') {
          errors.push(`Variable '${def.name}' must be a boolean`);
        }
        break;
      case 'array':
        if (!Array.isArray(value)) {
          errors.push(`Variable '${def.name}' must be an array`);
        }
        break;
      case 'object':
        if (typeof value !== 'object' || Array.isArray(value) || value === null) {
          errors.push(`Variable '${def.name}' must be an object`);
        }
        break;
    }
  }

  if (errors.length > 0) {
    return err({ valid: false, errors });
  }

  return ok({ valid: true });
}
