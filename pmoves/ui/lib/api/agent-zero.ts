/**
 * @fileoverview Agent Zero MCP API Client for PMOVES UI
 *
 * Integrates with Agent Zero orchestrator for:
 * - MCP command execution
 * - Task submission and status tracking
 * - Subordinate agent creation
 * - Service health monitoring
 *
 * @module api/agent-zero
 */

import { logError, Result, ok, err, getErrorMessage } from '../errorUtils';
import { ErrorIds } from '../constants/errorIds';

/**
 * Service configuration for Agent Zero.
 */
const AGENT_ZERO_SERVICE_CONFIG = {
  slug: 'agent-zero',
  defaultPort: 8080,
  envVar: 'NEXT_PUBLIC_AGENT_ZERO_URL',
} as const;

const AGENT_ZERO_TIMEOUT = 60000; // 60 seconds for agent operations
const AGENT_ZERO_MCP_TIMEOUT = 120000; // 2 minutes for MCP commands

/**
 * Resolves Agent Zero base URL from environment or default.
 */
function getAgentZeroUrl(): string {
  return (
    process.env.NEXT_PUBLIC_AGENT_ZERO_URL ||
    process.env.AGENT_ZERO_URL ||
    `http://localhost:${AGENT_ZERO_SERVICE_CONFIG.defaultPort}`
  ).replace(/\/$/, '');
}

/**
 * Task status for Agent Zero operations.
 */
export type AgentZeroTaskStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

/**
 * MCP tool definition.
 */
export interface MCPTool {
  /** Tool name */
  name: string;
  /** Tool description */
  description: string;
  /** Input schema (JSON Schema) */
  inputSchema: Record<string, unknown>;
}

/**
 * MCP command response.
 */
export interface MCPCommandResponse {
  /** Command result */
  result: unknown;
  /** Error if command failed */
  error?: string;
  /** Execution time in milliseconds */
  executionTime?: number;
}

/**
 * Task submission response.
 */
export interface AgentZeroTask {
  /** Unique task ID */
  taskId: string;
  /** Task status */
  status: AgentZeroTaskStatus;
  /** Task result if completed */
  result?: unknown;
  /** Error if failed */
  error?: string;
  /** Created timestamp */
  createdAt: string;
  /** Updated timestamp */
  updatedAt: string;
}

/**
 * Subordinate agent configuration.
 */
export interface SubordinateAgentConfig {
  /** Agent name */
  name: string;
  /** Agent model */
  model: string;
  /** Agent instructions */
  instructions: string;
  /** Enabled MCP tools */
  tools?: string[];
  /** Maximum iterations */
  maxIterations?: number;
}

/**
 * Health check response.
 */
export interface AgentZeroHealth {
  /** Service health status */
  healthy: boolean;
  /** Service version */
  version?: string;
  /** Number of active tasks */
  activeTasks?: number;
  /** MCP server count */
  mcpServers?: number;
}

/**
 * Executes an MCP command via Agent Zero.
 *
 * @param command - MCP command to execute
 * @param params - Command parameters
 * @returns Result with command response or error message
 *
 * @example
 * ```typescript
 * const result = await agentZeroMCPCommand('search', {
 *   query: 'machine learning',
 *   top_k: 10
 * });
 * ```
 */
export async function agentZeroMCPCommand(
  command: string,
  params: Record<string, unknown> = {}
): Promise<Result<MCPCommandResponse, string>> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), AGENT_ZERO_MCP_TIMEOUT);

    const response = await fetch(`${getAgentZeroUrl()}/mcp/command`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        command,
        params,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Agent Zero MCP command failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.AGENT_ZERO_MCP_REQUEST_FAILED,
          component: 'agent-zero',
          action: 'mcp-command',
          command,
        }
      );
      return err(message);
    }

    const data = (await response.json()) as MCPCommandResponse;
    return ok(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Agent Zero MCP command error', error, 'error', {
      errorId:
        error instanceof Error && error.name === 'AbortError'
          ? ErrorIds.AGENT_ZERO_MCP_TIMEOUT
          : ErrorIds.AGENT_ZERO_MCP_REQUEST_FAILED,
      component: 'agent-zero',
      action: 'mcp-command',
      command,
    });
    return err(message);
  }
}

/**
 * Lists available MCP tools.
 *
 * @returns Result with available tools or error message
 */
export async function agentZeroListTools(): Promise<
  Result<MCPTool[], string>
> {
  try {
    const response = await fetch(`${getAgentZeroUrl()}/mcp/tools`, {
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Agent Zero list tools failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.AGENT_ZERO_MCP_REQUEST_FAILED,
          component: 'agent-zero',
          action: 'list-tools',
        }
      );
      return err(message);
    }

    const data = (await response.json()) as { tools?: MCPTool[] };
    return ok(data.tools ?? []);
  } catch (error) {
    logError('Agent Zero list tools error', error, 'warning', {
      errorId: ErrorIds.AGENT_ZERO_MCP_REQUEST_FAILED,
      component: 'agent-zero',
      action: 'list-tools',
    });
    return err('Failed to list MCP tools');
  }
}

/**
 * Submits a task to Agent Zero.
 *
 * @param prompt - Task prompt/instructions
 * @param options - Optional task configuration
 * @returns Result with task info or error message
 */
export async function agentZeroSubmitTask(
  prompt: string,
  options: {
    model?: string;
    maxIterations?: number;
    tools?: string[];
  } = {}
): Promise<Result<AgentZeroTask, string>> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), AGENT_ZERO_TIMEOUT);

    const response = await fetch(`${getAgentZeroUrl()}/mcp/task`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt,
        ...options,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Agent Zero task submit failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.AGENT_ZERO_TASK_SUBMIT_FAILED,
          component: 'agent-zero',
          action: 'task-submit',
        }
      );
      return err(message);
    }

    const data = (await response.json()) as AgentZeroTask;
    return ok(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Agent Zero task submit error', error, 'error', {
      errorId: ErrorIds.AGENT_ZERO_TASK_SUBMIT_FAILED,
      component: 'agent-zero',
      action: 'task-submit',
    });
    return err(message);
  }
}

/**
 * Gets the status of a submitted task.
 *
 * @param taskId - Task ID to check
 * @returns Result with task status or error message
 */
export async function agentZeroTaskStatus(
  taskId: string
): Promise<Result<AgentZeroTask, string>> {
  try {
    const response = await fetch(
      `${getAgentZeroUrl()}/mcp/task/${encodeURIComponent(taskId)}`,
      {
        signal: AbortSignal.timeout(10000),
      }
    );

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Agent Zero task status failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.AGENT_ZERO_TASK_STATUS_FAILED,
          component: 'agent-zero',
          action: 'task-status',
          taskId,
        }
      );
      return err(message);
    }

    const data = (await response.json()) as AgentZeroTask;
    return ok(data);
  } catch (error) {
    logError('Agent Zero task status error', error, 'warning', {
      errorId: ErrorIds.AGENT_ZERO_TASK_STATUS_FAILED,
      component: 'agent-zero',
      action: 'task-status',
      taskId,
    });
    return err('Failed to get task status');
  }
}

/**
 * Creates a subordinate agent.
 *
 * @param config - Agent configuration
 * @returns Result with agent ID or error message
 */
export async function agentZeroCreateSubordinate(
  config: SubordinateAgentConfig
): Promise<Result<{ agentId: string }, string>> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), AGENT_ZERO_TIMEOUT);

    const response = await fetch(`${getAgentZeroUrl()}/mcp/subordinate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Agent Zero create subordinate failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.AGENT_ZERO_TASK_SUBMIT_FAILED,
          component: 'agent-zero',
          action: 'create-subordinate',
        }
      );
      return err(message);
    }

    const data = (await response.json()) as { agentId: string };
    return ok(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Agent Zero create subordinate error', error, 'error', {
      errorId: ErrorIds.AGENT_ZERO_TASK_SUBMIT_FAILED,
      component: 'agent-zero',
      action: 'create-subordinate',
    });
    return err(message);
  }
}

/**
 * Checks health status of Agent Zero service.
 *
 * @returns Result with health status or error message
 */
export async function agentZeroHealth(): Promise<
  Result<AgentZeroHealth, string>
> {
  try {
    const response = await fetch(`${getAgentZeroUrl()}/healthz`, {
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      return err('Agent Zero health check failed');
    }

    const data = (await response.json()) as AgentZeroHealth;
    return ok({ ...data, healthy: true });
  } catch (error) {
    logError('Agent Zero health check error', error, 'warning', {
      errorId: ErrorIds.AGENT_ZERO_HEALTH_CHECK_FAILED,
      component: 'agent-zero',
      action: 'health',
    });
    return err('Agent Zero service unavailable');
  }
}

/**
 * Queries available MCP servers.
 *
 * @returns Result with server list or error message
 */
export async function agentZeroListMCPServers(): Promise<
  Result<
    Array<{
      name: string;
      status: 'connected' | 'disconnected' | 'error';
      toolCount: number;
    }>,
    string
  >
> {
  try {
    const response = await fetch(`${getAgentZeroUrl()}/mcp/servers`, {
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      return err('Failed to list MCP servers');
    }

    const data = (await response.json()) as {
      servers?: Array<{
        name: string;
        status: 'connected' | 'disconnected' | 'error';
        toolCount: number;
      }>;
    };
    return ok(data.servers ?? []);
  } catch (error) {
    logError('Agent Zero list MCP servers error', error, 'warning', {
      errorId: ErrorIds.AGENT_ZERO_MCP_REQUEST_FAILED,
      component: 'agent-zero',
      action: 'list-servers',
    });
    return err('Failed to list MCP servers');
  }
}
