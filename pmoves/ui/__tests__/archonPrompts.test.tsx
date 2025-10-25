import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { act } from 'react-dom/test-utils';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import ArchonPromptsPage from '../app/dashboard/archon-prompts/page';
import * as archonPromptsModule from '../lib/archonPrompts';
import {
  ArchonPrompt,
  ArchonPromptInput,
  DuplicatePromptNameError,
  PolicyViolationError,
} from '../lib/archonPrompts';

describe('archonPrompts helpers', () => {
  it('lists prompts and applies search filtering', async () => {
    const sample: ArchonPrompt[] = [
      {
        id: '1',
        prompt_name: 'research_default',
        prompt: 'Prompt content',
        description: 'Research',
        created_at: '2024-05-01T00:00:00.000Z',
        updated_at: '2024-05-01T00:00:00.000Z',
      },
    ];

    const promise = Promise.resolve({ data: sample, error: null });
    const query: any = {
      select: vi.fn().mockReturnThis(),
      order: vi.fn().mockReturnThis(),
      ilike: vi.fn().mockReturnThis(),
      then: promise.then.bind(promise),
      catch: promise.catch.bind(promise),
      finally: promise.finally.bind(promise),
    };

    const client: any = {
      from: vi.fn().mockReturnValue(query),
    };

    const result = await archonPromptsModule.listArchonPrompts('research', { client });

    expect(client.from).toHaveBeenCalledWith('archon_prompts');
    expect(query.ilike).toHaveBeenCalledWith('prompt_name', '%research%');
    expect(result).toEqual(sample);
  });

  it('creates prompts and maps duplicate errors', async () => {
    const inserted: ArchonPrompt = {
      id: '2',
      prompt_name: 'new_prompt',
      prompt: 'New prompt body',
      description: null,
      created_at: '2024-05-02T00:00:00.000Z',
      updated_at: '2024-05-02T00:00:00.000Z',
    };

    const single = vi.fn().mockResolvedValue({ data: inserted, error: null });
    const select = vi.fn().mockReturnValue({ single });
    const insert = vi.fn().mockReturnValue({ select });
    const from = vi.fn().mockReturnValue({ insert });
    const client: any = { from };

    const result = await archonPromptsModule.createArchonPrompt(
      { prompt_name: ' new_prompt ', prompt: 'New prompt body' },
      { client }
    );

    expect(insert).toHaveBeenCalledWith([
      { prompt_name: 'new_prompt', prompt: 'New prompt body', description: null },
    ]);
    expect(result).toEqual(inserted);

    single.mockResolvedValue({ data: null, error: { code: '23505', message: 'duplicate' } });

    await expect(
      archonPromptsModule.createArchonPrompt(
        { prompt_name: 'new_prompt', prompt: 'body' },
        { client }
      )
    ).rejects.toBeInstanceOf(DuplicatePromptNameError);
  });

  it('updates prompts and maps policy violations', async () => {
    const updated: ArchonPrompt = {
      id: '1',
      prompt_name: 'edited',
      prompt: 'Body',
      description: null,
      created_at: '2024-05-01T00:00:00.000Z',
      updated_at: '2024-05-03T00:00:00.000Z',
    };

    const single = vi.fn().mockResolvedValue({ data: updated, error: null });
    const select = vi.fn().mockReturnValue({ single });
    const eq = vi.fn().mockReturnValue({ select });
    const update = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ update });
    const client: any = {
      from,
    };

    const result = await archonPromptsModule.updateArchonPrompt(
      '1',
      { prompt_name: 'edited', prompt: 'Body' },
      { client }
    );

    expect(result).toEqual(updated);

    single.mockResolvedValue({
      data: null,
      error: { code: '42501', message: 'row level security' },
    });

    await expect(
      archonPromptsModule.updateArchonPrompt(
        '1',
        { prompt_name: 'edited', prompt: 'Body' },
        { client }
      )
    ).rejects.toBeInstanceOf(PolicyViolationError);
  });

  it('deletes prompts', async () => {
    const eq = vi.fn().mockResolvedValue({ error: null });
    const del = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ delete: del });
    const client: any = { from };

    await expect(
      archonPromptsModule.deleteArchonPrompt('1', { client })
    ).resolves.toBeUndefined();
    expect(del).toHaveBeenCalled();
  });
});

describe('ArchonPromptsPage', () => {
  const listSpy = vi.spyOn(archonPromptsModule, 'listArchonPrompts');
  const originalFetch: typeof fetch | undefined = globalThis.fetch;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    listSpy.mockReset();
    listSpy.mockResolvedValue([]);
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    if (originalFetch) {
      globalThis.fetch = originalFetch;
    } else {
      delete (globalThis as any).fetch;
    }
    vi.clearAllMocks();
  });

  it('renders prompts returned by Supabase', async () => {
    const rows: ArchonPrompt[] = [
      {
        id: '1',
        prompt_name: 'research_default',
        prompt: 'Do research',
        description: 'Default flow',
        created_at: '2024-05-01T00:00:00.000Z',
        updated_at: '2024-05-01T00:00:00.000Z',
      },
      {
        id: '2',
        prompt_name: 'triage',
        prompt: 'Triage prompt',
        description: null,
        created_at: '2024-05-02T00:00:00.000Z',
        updated_at: '2024-05-02T00:00:00.000Z',
      },
    ];

    listSpy.mockResolvedValue(rows);

    render(<ArchonPromptsPage />);

    await waitFor(() => expect(screen.getAllByTestId('prompt-row')).toHaveLength(2));
    expect(screen.getByText('research_default')).toBeInTheDocument();
    expect(screen.getByText('triage')).toBeInTheDocument();
  });

  it('creates prompts and resets the form', async () => {
    listSpy.mockResolvedValueOnce([]);
    const createdPrompt: ArchonPrompt = {
      id: 'created-id',
      prompt_name: 'fresh_prompt',
      prompt: 'Fresh body',
      description: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    const createDeferred = deferred<Response>();
    fetchMock.mockImplementationOnce(() => createDeferred.promise);

    render(<ArchonPromptsPage />);

    await waitFor(() => expect(listSpy).toHaveBeenCalled());

    const nameInput = screen.getByLabelText('Prompt name');
    const promptInput = screen.getByLabelText('Prompt body');
    const descriptionInput = screen.getByLabelText('Description');

    await userEvent.type(nameInput, 'fresh_prompt');
    await userEvent.type(promptInput, 'Fresh body');
    await userEvent.type(descriptionInput, 'Optional');

    await act(async () => {
      fireEvent.submit(screen.getByTestId('prompt-form'));
    });

    await act(async () => {
      createDeferred.resolve(
        new Response(JSON.stringify({ data: createdPrompt }), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/archon-prompts');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toMatchObject<ArchonPromptInput>({
      prompt_name: 'fresh_prompt',
      prompt: 'Fresh body',
      description: 'Optional',
    });

    await waitFor(() => expect(nameInput).toHaveValue(''));
    await waitFor(() => expect(screen.getAllByTestId('prompt-row').length).toBeGreaterThan(0));
  });

  it('displays duplicate prompt errors', async () => {
    listSpy.mockResolvedValueOnce([]);
    const createDeferred = deferred<Response>();
    fetchMock.mockImplementationOnce(() => createDeferred.promise);

    render(<ArchonPromptsPage />);
    await waitFor(() => expect(listSpy).toHaveBeenCalled());

    await userEvent.type(screen.getByLabelText('Prompt name'), 'dupe');
    await userEvent.type(screen.getByLabelText('Prompt body'), 'body');

    await act(async () => {
      fireEvent.submit(screen.getByTestId('prompt-form'));
    });

    await act(async () => {
      createDeferred.resolve(
        new Response(
          JSON.stringify({
            error: {
              type: 'DuplicatePromptNameError',
              message: 'A prompt with this name already exists. Choose a different name.',
            },
          }),
          {
            status: 409,
            headers: { 'Content-Type': 'application/json' },
          }
        )
      );
    });

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('A prompt with this name already exists')
    );
  });

  it('optimistically deletes prompts and restores on failure', async () => {
    const row: ArchonPrompt = {
      id: 'row-1',
      prompt_name: 'delete_me',
      prompt: 'body',
      description: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    listSpy.mockResolvedValueOnce([row]);
    const deleteDeferred = deferred<Response>();
    fetchMock.mockImplementationOnce(() => deleteDeferred.promise);

    render(<ArchonPromptsPage />);
    await waitFor(() => expect(screen.getAllByTestId('prompt-row')).toHaveLength(1));

    await userEvent.click(screen.getByRole('button', { name: /delete/i }));

    await act(async () => {
      deleteDeferred.resolve(
        new Response(
          JSON.stringify({
            error: {
              type: 'PolicyViolationError',
              message: 'Action blocked by row level security policy. Use a service role key for writes.',
            },
          }),
          {
            status: 403,
            headers: { 'Content-Type': 'application/json' },
          }
        )
      );
    });

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Action blocked by row level security policy')
    );
    expect(fetchMock).toHaveBeenCalledWith(`/api/archon-prompts/${row.id}`, expect.objectContaining({ method: 'DELETE' }));
    expect(screen.getAllByTestId('prompt-row')).toHaveLength(1);
  });
});

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}
