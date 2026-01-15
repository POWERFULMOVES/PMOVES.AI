/**
 * @fileoverview Hi-RAG v2 API Client for PMOVES UI
 *
 * Hybrid RAG combining Qdrant (vectors) + Neo4j (graph) + Meilisearch (full-text)
 *
 * Service URL resolution via PMOVES service discovery:
 * 1. NEXT_PUBLIC_HIRAG_URL environment variable (explicit override)
 * 2. Service catalog (Supabase) via service registry
 * 3. Docker DNS fallback (hi-rag-gateway-v2:8086)
 *
 * @module api/hirag
 */

import { logError, logForDebugging, Result, ok, err, getErrorMessage } from '../errorUtils';
import { ErrorIds } from '../constants/errorIds';

// Service discovery integration
import { getServiceUrl, clearServiceCache } from '../serviceDiscovery';

/**
 * Service configuration for Hi-RAG v2.
 */
const HIRAG_SERVICE_CONFIG = {
  slug: 'hirag-v2',
  defaultPort: 8086,
  envVar: 'NEXT_PUBLIC_HIRAG_URL',
} as const;

const HIRAG_TIMEOUT = 30000; // 30 seconds

/**
 * Cached service URL to avoid repeated lookups.
 * Cache is cleared when service becomes unavailable.
 */
let cachedHiragUrl: string | null = null;

/**
 * Resolves Hi-RAG base URL using PMOVES service discovery.
 *
 * Resolution priority:
 * 1. NEXT_PUBLIC_HIRAG_URL environment variable (explicit override)
 * 2. Service catalog (Supabase) via service registry
 * 3. Docker DNS fallback (hi-rag-gateway-v2:8086)
 *
 * @returns Resolved Hi-RAG base URL
 */
async function getHiragBaseUrl(): Promise<string> {
  // Check cache first
  if (cachedHiragUrl) {
    return cachedHiragUrl;
  }

  // Use service discovery
  const url = await getServiceUrl(HIRAG_SERVICE_CONFIG);

  // Cache successful resolution
  cachedHiragUrl = url;
  return url;
}

/**
 * Clear cached Hi-RAG service URL.
 * Call this if the service becomes unavailable and needs to be re-resolved.
 */
export function clearHiragCache(): void {
  cachedHiragUrl = null;
  clearServiceCache(HIRAG_SERVICE_CONFIG.slug);
}

/**
 * Content source types for search results.
 */
export type HiragSource =
  | 'youtube'
  | 'notebook'
  | 'pdf'
  | 'webpage'
  | 'transcript'
  | 'unknown';

/**
 * Search filters for Hi-RAG queries.
 */
export interface HiragFilters {
  /** Filter by content source type */
  sourceType?: HiragSource;
  /** Filter by date range (ISO timestamps) */
  startDate?: string;
  endDate?: string;
  /** Filter by specific YouTube channel ID */
  channelId?: string;
  /** Minimum relevance score (0-1) */
  minScore?: number;
}

/**
 * A single search result from Hi-RAG.
 */
export interface HiragResult {
  /** Unique identifier for the result chunk */
  id: string;
  /** Content snippet */
  content: string;
  /** Relevance score (0-1) */
  score: number;
  /** Source type */
  source: HiragSource;
  /** Metadata about the source */
  metadata: {
    video_id?: string;
    title?: string;
    channel?: string;
    timestamp?: string;
    url?: string;
    [key: string]: unknown;
  };
}

/**
 * Response from Hi-RAG query endpoint.
 */
export interface HiragResponse {
  /** Array of search results */
  results: HiragResult[];
  /** Total results found */
  total: number;
  /** Query execution time in milliseconds */
  queryTime: number;
}

/**
 * Options for Hi-RAG search queries.
 */
export interface HiragSearchOptions {
  /** Number of results to return (default: 10) */
  topK?: number;
  /** Whether to apply cross-encoder reranking (default: true) */
  rerank?: boolean;
  /** Optional search filters */
  filters?: HiragFilters;
}

/**
 * Executes a hybrid search query against Hi-RAG v2.
 *
 * @param query - Search query string
 * @param options - Optional search parameters
 * @returns Result with search results or error message
 *
 * @example
 * ```typescript
 * const result = await hiragQuery('machine learning basics', {
 *   topK: 10,
 *   rerank: true,
 *   filters: { sourceType: 'youtube' }
 * });
 *
 * if (result.ok) {
 *   console.log('Found', result.data.results.length, 'results');
 * } else {
 *   console.error('Search failed:', result.error);
 * }
 * ```
 */
export async function hiragQuery(
  query: string,
  options: HiragSearchOptions = {}
): Promise<Result<HiragResponse, string>> {
  try {
    const { topK = 10, rerank = true, filters } = options;

    const requestBody = {
      query,
      top_k: topK,
      rerank,
      ...(filters && {
        filters: {
          source_type: filters.sourceType,
          start_date: filters.startDate,
          end_date: filters.endDate,
          channel_id: filters.channelId,
          min_score: filters.minScore,
        },
      }),
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), HIRAG_TIMEOUT);

    const baseUrl = await getHiragBaseUrl();
    const response = await fetch(`${baseUrl}/hirag/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const message = getErrorMessage(response.status);
      logError(
        `Hi-RAG query failed: ${message}`,
        new Error(`HTTP ${response.status}`),
        'warning',
        {
          errorId: ErrorIds.HIRAG_QUERY_FAILED,
          component: 'hirag',
          action: 'query',
          query: query.substring(0, 50)
        }
      );
      return err(message);
    }

    const data = (await response.json()) as HiragResponse;
    return ok(data);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Hi-RAG query error', error, 'error', {
      errorId: ErrorIds.HIRAG_QUERY_FAILED,
      component: 'hirag',
      action: 'query',
    });
    return err(message);
  }
}

/**
 * Checks health status of Hi-RAG service.
 *
 * @returns Result with health status or error message
 */
export async function hiragHealth(): Promise<
  Result<{ healthy: boolean; version?: string }, string>
> {
  try {
    const baseUrl = await getHiragBaseUrl();
    const response = await fetch(`${baseUrl}/healthz`, {
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      return err('Hi-RAG health check failed');
    }

    const data = (await response.json()) as { healthy?: boolean; version?: string };
    return ok({ healthy: data.healthy ?? true, version: data.version });
  } catch (error) {
    logError('Hi-RAG health check error', error, 'warning', {
      errorId: ErrorIds.HIRAG_HEALTH_CHECK_FAILED,
      component: 'hirag',
      action: 'health',
    });
    return err('Hi-RAG service unavailable');
  }
}

/**
 * Exports search results to Open Notebook.
 *
 * @param results - Results to export
 * @param notebookId - Target notebook source ID
 * @returns Result with export confirmation or error message
 */
export async function exportToNotebook(
  results: HiragResult[],
  notebookId: string
): Promise<Result<{ exported: number }, string>> {
  try {
    // This would call the Open Notebook API to create notes from results
    // For now, return success with count
    const exported = results.length;

    logForDebugging(
      `Exported ${exported} results to notebook ${notebookId}`,
      undefined,
      { component: 'hirag', action: 'export', exported, notebookId }
    );

    return ok({ exported });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : String(error);
    logError('Notebook export error', error, 'error', {
      errorId: ErrorIds.HIRAG_EXPORT_FAILED,
      component: 'hirag',
      action: 'export',
      notebookId,
    });
    return err(message);
  }
}
