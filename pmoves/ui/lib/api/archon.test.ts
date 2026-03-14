/**
 * @fileoverview Archon API Client Integration Tests
 *
 * Tests prompt template management, execution, and health checks.
 *
 * @module api/archon.test
 */

import {
  archonHealth,
  archonListPrompts,
  archonGetPrompt,
  archonCreatePrompt,
  archonUpdatePrompt,
  archonDeletePrompt,
  archonExecutePrompt,
  archonListForms,
  archonGetForm,
  archonValidateVariables,
} from './archon';

// Mock fetch for testing
const mockFetch = jest.fn();
global.fetch = mockFetch as jest.MockedFunction<typeof fetch>;

describe('Archon API Client', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  const mockPrompt = {
    id: 'prompt-123',
    name: 'Test Prompt',
    description: 'A test prompt',
    category: 'agent' as const,
    template: 'Hello {{name}}, please help with {{task}}.',
    variables: [
      {
        name: 'name',
        type: 'string' as const,
        required: true,
      },
      {
        name: 'task',
        type: 'string' as const,
        required: true,
      },
    ],
    model: 'claude-sonnet-4',
    tags: ['test', 'demo'],
    is_public: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  describe('archonHealth', () => {
    it('should return healthy status when service is available', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          healthy: true,
          version: '1.0.0',
          supabase: { connected: true },
          agentZero: { connected: true },
          promptCount: 42,
        }),
      } as Response);

      const result = await archonHealth();

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.healthy).toBe(true);
        expect(result.data.supabase?.connected).toBe(true);
        expect(result.data.agentZero?.connected).toBe(true);
        expect(result.data.promptCount).toBe(42);
      }
    });

    it('should return error when service is unavailable', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Connection refused'));

      const result = await archonHealth();

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBe('Archon service unavailable');
      }
    });
  });

  describe('archonListPrompts', () => {
    it('should return list of prompts', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ prompts: [mockPrompt] }),
      } as Response);

      const result = await archonListPrompts({
        category: 'agent',
        is_public: true,
      });

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data).toHaveLength(1);
        expect(result.data[0].category).toBe('agent');
      }
    });

    it('should handle empty prompt list', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const result = await archonListPrompts();

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data).toEqual([]);
      }
    });
  });

  describe('archonGetPrompt', () => {
    it('should return prompt by ID', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPrompt,
      } as Response);

      const result = await archonGetPrompt('prompt-123');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.id).toBe('prompt-123');
        expect(result.data.name).toBe('Test Prompt');
      }
    });

    it('should handle not found error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      } as Response);

      const result = await archonGetPrompt('nonexistent');

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBe('Prompt not found');
      }
    });
  });

  describe('archonCreatePrompt', () => {
    it('should create new prompt', async () => {
      const newPrompt = {
        name: 'New Prompt',
        category: 'coding' as const,
        template: 'Write {{language}} code for {{task}}.',
        variables: [
          { name: 'language', type: 'string' as const, required: true },
          { name: 'task', type: 'string' as const, required: true },
        ],
        tags: ['coding'],
        is_public: false,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...newPrompt, id: 'prompt-456' }),
      } as Response);

      const result = await archonCreatePrompt(newPrompt);

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.id).toBe('prompt-456');
        expect(result.data.name).toBe('New Prompt');
      }
    });
  });

  describe('archonUpdatePrompt', () => {
    it('should update existing prompt', async () => {
      const updatedPrompt = {
        ...mockPrompt,
        name: 'Updated Prompt',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => updatedPrompt,
      } as Response);

      const result = await archonUpdatePrompt('prompt-123', {
        name: 'Updated Prompt',
      });

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.name).toBe('Updated Prompt');
      }
    });
  });

  describe('archonDeletePrompt', () => {
    it('should delete prompt', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const result = await archonDeletePrompt('prompt-123');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.deleted).toBe(true);
      }
    });
  });

  describe('archonExecutePrompt', () => {
    it('should execute prompt with variables', async () => {
      const executionResult = {
        executionId: 'exec-789',
        status: 'completed' as const,
        result: 'Hello World, please help with testing.',
        startedAt: new Date().toISOString(),
        completedAt: new Date().toISOString(),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => executionResult,
      } as Response);

      const result = await archonExecutePrompt({
        promptId: 'prompt-123',
        variables: {
          name: 'World',
          task: 'testing',
        },
      });

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.executionId).toBe('exec-789');
        expect(result.data.status).toBe('completed');
      }
    });
  });

  describe('archonListForms', () => {
    it('should return list of forms', async () => {
      const mockForm = {
        id: 'form-123',
        name: 'Test Form',
        schema: { type: 'object' },
        promptIds: ['prompt-123'],
        created_at: new Date().toISOString(),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ forms: [mockForm] }),
      } as Response);

      const result = await archonListForms();

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data).toHaveLength(1);
        expect(result.data[0].id).toBe('form-123');
      }
    });
  });

  describe('archonGetForm', () => {
    it('should return form by ID', async () => {
      const mockForm = {
        id: 'form-123',
        name: 'Test Form',
        schema: { type: 'object' },
        promptIds: ['prompt-123'],
        created_at: new Date().toISOString(),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockForm,
      } as Response);

      const result = await archonGetForm('form-123');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.id).toBe('form-123');
      }
    });
  });

  describe('archonValidateVariables', () => {
    it('should validate correct variables', () => {
      const schema = [
        { name: 'name', type: 'string' as const, required: true },
        { name: 'age', type: 'number' as const, required: false },
      ];

      const result = archonValidateVariables(
        { name: 'Alice', age: 30 },
        schema
      );

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.data.valid).toBe(true);
      }
    });

    it('should detect missing required variable', () => {
      const schema = [
        { name: 'name', type: 'string' as const, required: true },
      ];

      const result = archonValidateVariables({}, schema);

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error.errors).toContain(
          "Required variable 'name' is missing"
        );
      }
    });

    it('should detect type mismatch', () => {
      const schema = [
        { name: 'age', type: 'number' as const, required: true },
      ];

      const result = archonValidateVariables({ age: 'thirty' }, schema);

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error.errors).toContain("Variable 'age' must be a number");
      }
    });
  });
});
