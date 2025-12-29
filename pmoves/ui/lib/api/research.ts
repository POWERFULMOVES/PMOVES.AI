/**
 * @fileoverview DeepResearch API Client for PMOVES UI
 *
 * Integrates with DeepResearch service for:
 * - Research task initiation
 * - Task status monitoring
 * - Result retrieval
 * - Notebook publishing
 *
 * @module api/research
 */

import { logError, Result, ok, err, getErrorMessage } from '../errorUtils';

/**
 * Research task status values.
 */
export type ResearchStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

/**
 * Research execution mode.
 */
export type ResearchMode =
  | 'tensorzero'
  | 'openrouter'
  | 'local'
  | 'hybrid';

/**
 * A research task in the system.
 */
export interface ResearchTask {
  /** Unique task identifier */
  id: string;
  /** Research query/question */
  query: string;
  /** Current task status */
  status: ResearchStatus;
  /** Execution mode */
  mode: ResearchMode;
  /** ISO timestamp when task was created */
  createdAt: string;
  /** ISO timestamp when task started (if running/completed) */
  startedAt?: string;
  /** ISO timestamp when task completed/failed */
  completedAt?: string;
  /** Result summary (if completed) */
  resultSummary?: string;
  /** Associated Notebook source ID */
  notebookId?: string;
  /** Number of research iterations */
  iterations?: number;
  /** Error message (if failed) */
  errorMessage?: string;
}

/**
 * Full research results for a completed task.
 */
export interface ResearchResult {
  /** Task identifier */
  taskId: string;
  /** Research summary */
  summary: string;
  /** Extracted notes */
  notes: string[];
  /** Source citations */
  sources: Array<{
    title: string;
    url: string;
    snippet?: string;
  }>;
  /** Number of iterations performed */
  iterations: number;
  /** Total research time in seconds */
  duration: number;
  /** ISO timestamp of completion */
  completedAt: string;
}

/**
 * Options for initiating a research task.
 */
export interface ResearchOptions {
  /** Execution mode */
  mode?: ResearchMode;
  /** Notebook source ID for publishing results */
  notebookId?: string;
  /** Maximum iterations (default: 10) */
  maxIterations?: number;
  /** Priority (1-10, higher = sooner) */
  priority?: number;
}

/**
 * Default configuration for DeepResearch API.
 */
const RESEARCH_DEFAULT_URL = 'http://localhost:8098';
const RESEARCH_TIMEOUT = 120000; // 2 minutes (research can take time)

/**
 * Resolves DeepResearch base URL from environment or default.
 */
function getResearchUrl(): string {
  return (
    process.env.NEXT_PUBLIC_RESEARCH_URL ||
    process.env.RESEARCH_URL ||
    RESEARCH_DEFAULT_URL
  ).replace(/\/$/, '');
}

/**
 * Initiates a new research task.
 *
 * @param query - Research question/query
 * @param options - Optional research configuration
 * @returns Result with created task or error message
 *
 * @example
 * ```typescript
 * const result = await initiateResearch('What is quantum computing?', {
 *   mode: 'tensorzero',
 *   notebookId: 'notebook-123',
 *   maxIterations: 15
 * });
 * ```
 */
export async function initiateResearch(
  query: string,
  options: ResearchOptions = {}
): Promise<Result<ResearchTask, string>> {
  try {
    const {
      mode = 'tensorzero',
      notebookId,
      maxIterations = 10,
      priority = 5,
    } = options;

    const requestBody = {
      query,
      mode,
      notebook_id: notebookId,
      max_iterations: maxIterations,
      priority,
    };

    const response = await fetch(`${getResearchUrl()}/research/initiate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody),
      signal: AbortSignal.timeout(30000), // 30s timeout for initiation
    });

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Research initiation failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        { component: 'research', action: 'initiate', query: query.substring(0, 50) }
      );
      return err(message);
    }

    const data = (await response.json()) as ResearchTask;
    return ok(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Research initiation error', error, 'error', {
      component: 'research',
      action: 'initiate',
    });
    return err(message);
  }
}

/**
 * Fetches a research task by ID.
 *
 * @param taskId - Task identifier
 * @returns Result with task details or error message
 */
export async function getResearchTask(
  taskId: string
): Promise<Result<ResearchTask, string>> {
  try {
    const response = await fetch(
      `${getResearchUrl()}/research/tasks/${taskId}`,
      {
        signal: AbortSignal.timeout(10000),
      }
    );

    if (!response.ok) {
      if (response.status === 404) {
        return err('Research task not found');
      }
      return err('Failed to fetch research task');
    }

    const data = (await response.json()) as ResearchTask;
    return ok(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Research task fetch error', error, 'error', {
      component: 'research',
      action: 'get-task',
      taskId,
    });
    return err(message);
  }
}

/**
 * Lists research tasks with optional filters.
 *
 * @param options - Optional filters
 * @returns Result with array of tasks or error message
 */
export async function listResearchTasks(options: {
  /** Filter by status */
  status?: ResearchStatus;
  /** Filter by mode */
  mode?: ResearchMode;
  /** Maximum results to return */
  limit?: number;
  /** Offset for pagination */
  offset?: number;
} = {}): Promise<Result<ResearchTask[], string>> {
  try {
    const { status, mode, limit = 50, offset = 0 } = options;
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });

    if (status) params.set('status', status);
    if (mode) params.set('mode', mode);

    const response = await fetch(
      `${getResearchUrl()}/research/tasks?${params}`,
      {
        signal: AbortSignal.timeout(10000),
      }
    );

    if (!response.ok) {
      return err('Failed to list research tasks');
    }

    const data = (await response.json()) as { tasks?: ResearchTask[] };
    return ok(data.tasks ?? []);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Research task list error', error, 'error', {
      component: 'research',
      action: 'list-tasks',
    });
    return err(message);
  }
}

/**
 * Fetches full research results for a completed task.
 *
 * @param taskId - Task identifier
 * @returns Result with research results or error message
 */
export async function getResearchResults(
  taskId: string
): Promise<Result<ResearchResult, string>> {
  try {
    const response = await fetch(
      `${getResearchUrl()}/research/tasks/${taskId}/results`,
      {
        signal: AbortSignal.timeout(RESEARCH_TIMEOUT),
      }
    );

    if (!response.ok) {
      if (response.status === 404) {
        return err('Research results not found');
      }
      if (response.status === 425) {
        return err('Research still in progress');
      }
      return err('Failed to fetch research results');
    }

    const data = (await response.json()) as ResearchResult;
    return ok(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Research results fetch error', error, 'error', {
      component: 'research',
      action: 'get-results',
      taskId,
    });
    return err(message);
  }
}

/**
 * Cancels a running research task.
 *
 * @param taskId - Task identifier
 * @returns Result with cancellation confirmation or error message
 */
export async function cancelResearch(
  taskId: string
): Promise<Result<{ cancelled: true }, string>> {
  try {
    const response = await fetch(
      `${getResearchUrl()}/research/tasks/${taskId}/cancel`,
      {
        method: 'POST',
        signal: AbortSignal.timeout(10000),
      }
    );

    if (!response.ok) {
      if (response.status === 404) {
        return err('Research task not found');
      }
      if (response.status === 409) {
        return err('Task already completed');
      }
      return err('Failed to cancel research task');
    }

    return ok({ cancelled: true });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Research cancel error', error, 'error', {
      component: 'research',
      action: 'cancel',
      taskId,
    });
    return err(message);
  }
}

/**
 * Checks health status of DeepResearch service.
 *
 * @returns Result with health status or error message
 */
export async function researchHealth(): Promise<
  Result<{ healthy: boolean; version?: string }, string>
> {
  try {
    const response = await fetch(`${getResearchUrl()}/healthz`, {
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      return err('DeepResearch health check failed');
    }

    const data = (await response.json()) as { healthy?: boolean; version?: string };
    return ok({ healthy: data.healthy ?? true, version: data.version });
  } catch (error) {
    logError('DeepResearch health check error', error, 'warning', {
      component: 'research',
      action: 'health',
    });
    return err('DeepResearch service unavailable');
  }
}

/**
 * Publishes research results to Open Notebook.
 *
 * @param taskId - Task identifier with completed research
 * @param notebookId - Target notebook source ID
 * @returns Result with publishing confirmation or error message
 */
export async function publishToNotebook(
  taskId: string,
  notebookId: string
): Promise<Result<{ published: true; noteId?: string }, string>> {
  try {
    const response = await fetch(
      `${getResearchUrl()}/research/tasks/${taskId}/publish`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notebook_id: notebookId }),
        signal: AbortSignal.timeout(30000),
      }
    );

    if (!response.ok) {
      return err('Failed to publish to notebook');
    }

    const data = (await response.json()) as { note_id?: string };
    return ok({ published: true, noteId: data.note_id });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Notebook publish error', error, 'error', {
      component: 'research',
      action: 'publish',
      taskId,
      notebookId,
    });
    return err(message);
  }
}
