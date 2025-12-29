/* ═══════════════════════════════════════════════════════════════════════════
   Hi-RAG API Client Tests
   Tests hybrid RAG search with Qdrant, Neo4j, and Meilisearch
   ═══════════════════════════════════════════════════════════════════════════ */

import { hiragQuery, hiragHealth, exportToNotebook } from './hirag';
import { ok, type Result } from '../errorUtils';

// Mock fetch
global.fetch = jest.fn();

// Mock errorUtils
jest.mock('../errorUtils', () => ({
  logError: jest.fn(),
  ok: (value: unknown) => ({ ok: true, data: value }),
  err: (error: string) => ({ ok: false, error }),
  getErrorMessage: (status: number) => `HTTP Error ${status}`,
}));

describe('Hi-RAG API', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    process.env.NEXT_PUBLIC_HIRAG_URL = undefined;
  });

  describe('hiragQuery', () => {
    it('should query with default options', async () => {
      const mockResponse = {
        results: [
          {
            id: '1',
            content: 'Test result',
            score: 0.9,
            source: 'youtube' as const,
            metadata: { title: 'Test Video' },
          },
        ],
        total: 1,
        queryTime: 150,
      };

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await hiragQuery('test query');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.results).toHaveLength(1);
        expect(result.data.results[0].content).toBe('Test result');
      }

      // Check the actual URL called - it will use the default from the API
      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls.length).toBeGreaterThan(0);
      const calledUrl = fetchCalls[0][0];
      expect(calledUrl).toContain('/hirag/query');

      const callOptions = fetchCalls[0][1];
      expect(callOptions).toEqual(
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"top_k":10'),
        })
      );
    });

    it('should query with custom top_k and rerank', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [], total: 0, queryTime: 100 }),
      } as Response);

      await hiragQuery('test query', { topK: 20, rerank: false });

      const callArgs = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls[0];
      const body = JSON.parse(callArgs[1]?.body as string);

      expect(body.top_k).toBe(20);
      expect(body.rerank).toBe(false);
    });

    it('should map filters to request params', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [], total: 0, queryTime: 100 }),
      } as Response);

      await hiragQuery('test query', {
        filters: {
          sourceType: 'youtube',
          startDate: '2025-01-01',
          endDate: '2025-12-31',
          channelId: 'UCxxx',
          minScore: 0.7,
        },
      });

      const callArgs = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls[0];
      const body = JSON.parse(callArgs[1]?.body as string);

      expect(body.filters).toEqual({
        source_type: 'youtube',
        start_date: '2025-01-01',
        end_date: '2025-12-31',
        channel_id: 'UCxxx',
        min_score: 0.7,
      });
    });

    it('should handle HTTP errors gracefully', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: false,
        status: 500,
      } as Response);

      const result = await hiragQuery('test query');

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toContain('HTTP Error');
      }
    });

    it('should return error on 401', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: false,
        status: 401,
      } as Response);

      const result = await hiragQuery('test query');

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toContain('401');
      }
    });

    it('should return error on 400 (bad request)', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: false,
        status: 400,
      } as Response);

      const result = await hiragQuery('test query');

      expect(result.ok).toBe(false);
    });

    it('should handle timeout errors', async () => {
      // Simulate AbortError when timeout
      const abortError = new Error('Aborted') as Error & { name: string };
      abortError.name = 'AbortError';

      (global.fetch as jest.MockedFunction<typeof fetch>).mockRejectedValueOnce(abortError);

      const result = await hiragQuery('test query');

      expect(result.ok).toBe(false);
    });

    it('should use custom URL from env var', async () => {
      process.env.NEXT_PUBLIC_HIRAG_URL = 'http://custom-hirag:8086';

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [], total: 0, queryTime: 100 }),
      } as Response);

      await hiragQuery('test query');

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      const calledUrl = fetchCalls[0][0];
      expect(calledUrl).toBe('http://custom-hirag:8086/hirag/query');
    });
  });

  describe('hiragHealth', () => {
    it('should check health status', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ healthy: true, version: '2.0.0' }),
      } as Response);

      const result = await hiragHealth();

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.healthy).toBe(true);
        expect(result.data.version).toBe('2.0.0');
      }
    });

    it('should handle unhealthy status', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ healthy: false }),
      } as Response);

      const result = await hiragHealth();

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.healthy).toBe(false);
      }
    });

    it('should handle missing version field', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ healthy: true }),
      } as Response);

      const result = await hiragHealth();

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.healthy).toBe(true);
        expect(result.data.version).toBeUndefined();
      }
    });

    it('should return error on failure', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: false,
        status: 503,
      } as Response);

      const result = await hiragHealth();

      expect(result.ok).toBe(false);
    });

    it('should return error on network failure', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockRejectedValueOnce(
        new Error('Network error')
      );

      const result = await hiragHealth();

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBe('Hi-RAG service unavailable');
      }
    });
  });

  describe('exportToNotebook', () => {
    it('should export results to notebook', async () => {
      const mockResults = [
        {
          id: '1',
          content: 'Test result 1',
          score: 0.9,
          source: 'youtube' as const,
          metadata: { title: 'Test' },
        },
        {
          id: '2',
          content: 'Test result 2',
          score: 0.8,
          source: 'notebook' as const,
          metadata: { title: 'Test 2' },
        },
      ];

      const result = await exportToNotebook(mockResults, 'notebook-123');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.exported).toBe(2);
      }
    });

    it('should handle empty results', async () => {
      const result = await exportToNotebook([], 'notebook-123');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.exported).toBe(0);
      }
    });
  });

  describe('URL resolution', () => {
    it('should strip trailing slash from URL', async () => {
      process.env.NEXT_PUBLIC_HIRAG_URL = 'http://localhost:8086/';

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [], total: 0, queryTime: 100 }),
      } as Response);

      await hiragQuery('test');

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8086/hirag/query',
        expect.any(Object)
      );
    });
  });
});
