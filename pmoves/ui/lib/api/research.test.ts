/* ═══════════════════════════════════════════════════════════════════════════
   Research API Client Tests
   Tests DeepResearch service integration
   ═══════════════════════════════════════════════════════════════════════════ */

import {
  initiateResearch,
  getResearchTask,
  listResearchTasks,
  getResearchResults,
  cancelResearch,
  researchHealth,
  publishToNotebook,
} from './research';

// Mock fetch
global.fetch = jest.fn();

// Mock errorUtils
jest.mock('../errorUtils', () => ({
  logError: jest.fn(),
  ok: (value: unknown) => ({ ok: true, data: value }),
  err: (error: string) => ({ ok: false, error }),
  getErrorMessage: (status: number) => `HTTP Error ${status}`,
}));

describe('Research API', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    process.env.NEXT_PUBLIC_RESEARCH_URL = undefined;
  });

  describe('initiateResearch', () => {
    it('should initiate research with query', async () => {
      const mockTask = {
        id: 'task-123',
        query: 'What is quantum computing?',
        status: 'pending' as const,
        mode: 'tensorzero' as const,
        createdAt: '2025-01-15T10:00:00Z',
      };

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => mockTask,
      } as Response);

      const result = await initiateResearch('What is quantum computing?');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.id).toBe('task-123');
        expect(result.data.query).toBe('What is quantum computing?');
        expect(result.data.status).toBe('pending');
      }
    });

    it('should use default options when not provided', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 'task-123',
          query: 'test',
          status: 'pending' as const,
          mode: 'tensorzero' as const,
          createdAt: '2025-01-15T10:00:00Z',
        }),
      } as Response);

      await initiateResearch('test');

      const body = JSON.parse((global.fetch as jest.MockedFunction<typeof fetch>).mock.calls[0][1]?.body as string);
      expect(body.mode).toBe('tensorzero');
      expect(body.max_iterations).toBe(10);
      expect(body.priority).toBe(5);
    });

    it('should pass custom options', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 'task-123',
          query: 'test',
          status: 'pending' as const,
          mode: 'openrouter' as const,
          createdAt: '2025-01-15T10:00:00Z',
        }),
      } as Response);

      await initiateResearch('test', {
        mode: 'openrouter',
        notebookId: 'nb-123',
        maxIterations: 20,
        priority: 8,
      });

      const body = JSON.parse((global.fetch as jest.MockedFunction<typeof fetch>).mock.calls[0][1]?.body as string);
      expect(body.mode).toBe('openrouter');
      expect(body.notebook_id).toBe('nb-123');
      expect(body.max_iterations).toBe(20);
      expect(body.priority).toBe(8);
    });
  });

  describe('listResearchTasks', () => {
    it('should list tasks with pagination', async () => {
      const mockTasks = [
        {
          id: '1',
          query: 'Task 1',
          status: 'pending' as const,
          mode: 'tensorzero' as const,
          createdAt: '2025-01-15T10:00:00Z',
        },
        {
          id: '2',
          query: 'Task 2',
          status: 'completed' as const,
          mode: 'local' as const,
          createdAt: '2025-01-14T10:00:00Z',
        },
      ];

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tasks: mockTasks }),
      } as Response);

      const result = await listResearchTasks({ limit: 10, offset: 0 });

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data).toHaveLength(2);
      }

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('limit=10&offset=0');
    });

    it('should filter tasks by status', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tasks: [] }),
      } as Response);

      await listResearchTasks({ status: 'running' });

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('status=running');
    });

    it('should filter tasks by mode', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tasks: [] }),
      } as Response);

      await listResearchTasks({ mode: 'tensorzero' });

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('mode=tensorzero');
    });

    it('should return empty array when tasks field missing', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const result = await listResearchTasks();

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data).toEqual([]);
      }
    });
  });

  describe('getResearchTask', () => {
    it('should fetch task by ID', async () => {
      const mockTask = {
        id: 'task-123',
        query: 'Test query',
        status: 'running' as const,
        mode: 'tensorzero' as const,
        createdAt: '2025-01-15T10:00:00Z',
        startedAt: '2025-01-15T10:01:00Z',
        iterations: 5,
      };

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => mockTask,
      } as Response);

      const result = await getResearchTask('task-123');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.id).toBe('task-123');
        expect(result.data.iterations).toBe(5);
      }

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('/research/tasks/task-123');
    });

    it('should return error on 404', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: false,
        status: 404,
      } as Response);

      const result = await getResearchTask('nonexistent');

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBe('Research task not found');
      }
    });
  });

  describe('getResearchResults', () => {
    it('should fetch results for completed task', async () => {
      const mockResults = {
        taskId: 'task-123',
        summary: 'Research complete',
        notes: ['Note 1', 'Note 2'],
        sources: [
          { title: 'Source 1', url: 'https://example.com/1' },
          { title: 'Source 2', url: 'https://example.com/2' },
        ],
        iterations: 12,
        duration: 125000,
        completedAt: '2025-01-15T12:00:00Z',
      };

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResults,
      } as Response);

      const result = await getResearchResults('task-123');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.summary).toBe('Research complete');
        expect(result.data.notes).toHaveLength(2);
        expect(result.data.sources).toHaveLength(2);
      }
    });

    it('should return error on 404', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: false,
        status: 404,
      } as Response);

      const result = await getResearchResults('task-123');

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBe('Research results not found');
      }
    });

    it('should return error on 425 (still in progress)', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: false,
        status: 425,
      } as Response);

      const result = await getResearchResults('task-123');

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBe('Research still in progress');
      }
    });
  });

  describe('cancelResearch', () => {
    it('should cancel running task', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const result = await cancelResearch('task-123');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.cancelled).toBe(true);
      }

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('/research/tasks/task-123/cancel');
    });

    it('should return error on 409 (already completed)', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: false,
        status: 409,
      } as Response);

      const result = await cancelResearch('task-123');

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBe('Task already completed');
      }
    });
  });

  describe('researchHealth', () => {
    it('should check health status', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ healthy: true, version: '1.5.0' }),
      } as Response);

      const result = await researchHealth();

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.healthy).toBe(true);
        expect(result.data.version).toBe('1.5.0');
      }
    });

    it('should return error on failure', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: false,
        status: 503,
      } as Response);

      const result = await researchHealth();

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBe('DeepResearch health check failed');
      }
    });

    it('should return error on network failure', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockRejectedValueOnce(
        new Error('Connection refused')
      );

      const result = await researchHealth();

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBe('DeepResearch service unavailable');
      }
    });
  });

  describe('publishToNotebook', () => {
    it('should publish to notebook', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ note_id: 'note-abc' }),
      } as Response);

      const result = await publishToNotebook('task-123', 'notebook-123');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.published).toBe(true);
        expect(result.data.noteId).toBe('note-abc');
      }

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('/research/tasks/task-123/publish');

      const body = JSON.parse(fetchCalls[0][1]?.body as string);
      expect(body.notebook_id).toBe('notebook-123');
    });

    it('should handle missing note_id in response', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const result = await publishToNotebook('task-123', 'notebook-123');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.noteId).toBeUndefined();
      }
    });
  });

  describe('URL resolution', () => {
    it('should use custom URL from env var', async () => {
      process.env.NEXT_PUBLIC_RESEARCH_URL = 'http://custom-research:8098';

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ healthy: true }),
      } as Response);

      await researchHealth();

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('http://custom-research:8098/healthz');
    });

    it('should strip trailing slash from URL', async () => {
      process.env.NEXT_PUBLIC_RESEARCH_URL = 'http://localhost:8098/';

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ healthy: true }),
      } as Response);

      await researchHealth();

      const fetchCalls = (global.fetch as jest.MockedFunction<typeof fetch>).mock.calls;
      expect(fetchCalls[0][0]).toContain('http://localhost:8098/healthz');
    });
  });

  describe('Error handling', () => {
    it('should handle network errors gracefully', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockRejectedValueOnce(
        new Error('Network error')
      );

      const result = await initiateResearch('test');

      expect(result.ok).toBe(false);
    });

    it('should handle timeout errors', async () => {
      const abortError = new Error('Aborted') as Error & { name: string };
      abortError.name = 'AbortError';

      (global.fetch as jest.MockedFunction<typeof fetch>).mockRejectedValueOnce(abortError);

      const result = await getResearchTask('task-123');

      expect(result.ok).toBe(false);
    });
  });
});
