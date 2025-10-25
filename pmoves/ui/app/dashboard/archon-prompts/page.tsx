'use client';

import React, { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArchonPrompt,
  ArchonPromptInput,
  DuplicatePromptNameError,
  PolicyViolationError,
  listArchonPrompts,
} from '../../../lib/archonPrompts';

type ArchonPromptErrorPayload = {
  error?: {
    type?: string;
    message?: string;
  };
};

async function readJson(response: Response) {
  try {
    return (await response.json()) as ArchonPromptErrorPayload | { data: ArchonPrompt };
  } catch (err) {
    return null;
  }
}

async function handleApiError(response: Response, fallback: string): Promise<never> {
  const payload = (await readJson(response)) as ArchonPromptErrorPayload | null;
  const message = payload?.error?.message ?? fallback;
  const type = payload?.error?.type;

  if (type === 'DuplicatePromptNameError') {
    throw new DuplicatePromptNameError(message);
  }

  if (type === 'PolicyViolationError') {
    throw new PolicyViolationError(message);
  }

  throw new Error(message);
}

async function createPromptRequest(payload: ArchonPromptInput): Promise<ArchonPrompt> {
  const response = await fetch('/api/archon-prompts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    await handleApiError(response, 'Failed to create prompt.');
  }

  const body = (await readJson(response)) as { data?: ArchonPrompt } | null;
  if (!body?.data) {
    throw new Error('Supabase did not return the created prompt.');
  }
  return body.data;
}

async function updatePromptRequest(id: string, payload: ArchonPromptInput): Promise<ArchonPrompt> {
  const response = await fetch(`/api/archon-prompts/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    await handleApiError(response, 'Failed to update prompt.');
  }

  const body = (await readJson(response)) as { data?: ArchonPrompt } | null;
  if (!body?.data) {
    throw new Error('Supabase did not return the updated prompt.');
  }
  return body.data;
}

async function deletePromptRequest(id: string): Promise<void> {
  const response = await fetch(`/api/archon-prompts/${id}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    await handleApiError(response, 'Failed to delete prompt.');
  }
}

type FormState = {
  prompt_name: string;
  prompt: string;
  description: string;
};

const EMPTY_FORM: FormState = {
  prompt_name: '',
  prompt: '',
  description: '',
};

export default function ArchonPromptsPage() {
  const [prompts, setPrompts] = useState<ArchonPrompt[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [formState, setFormState] = useState<FormState>(EMPTY_FORM);
  const [editingPrompt, setEditingPrompt] = useState<ArchonPrompt | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadPrompts = useCallback(async (query?: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listArchonPrompts(query);
      setPrompts(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load prompts.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPrompts();
  }, [loadPrompts]);

  const filteredPrompts = useMemo(() => {
    if (!searchTerm.trim()) {
      return prompts;
    }
    const term = searchTerm.trim().toLowerCase();
    return prompts.filter((prompt) =>
      [prompt.prompt_name, prompt.description ?? '', prompt.prompt]
        .join(' ')
        .toLowerCase()
        .includes(term)
    );
  }, [prompts, searchTerm]);

  const resetForm = () => {
    setFormState(EMPTY_FORM);
    setEditingPrompt(null);
  };

  const handleError = useCallback((err: unknown) => {
    if (err instanceof DuplicatePromptNameError) {
      setError('A prompt with this name already exists. Choose a different name.');
    } else if (err instanceof PolicyViolationError) {
      setError('Action blocked by row level security policy. Use a service role key for writes.');
    } else if (err instanceof Error) {
      setError(err.message);
    } else {
      setError('An unexpected error occurred.');
    }
  }, []);

  const upsertPrompt = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setStatus(null);

    const payload: ArchonPromptInput = {
      prompt_name: formState.prompt_name.trim(),
      prompt: formState.prompt.trim(),
      description: formState.description.trim() || null,
    };

    if (!payload.prompt_name || !payload.prompt) {
      setError('Prompt name and prompt body are required.');
      return;
    }

    setSaving(true);

    if (editingPrompt) {
      const optimistic = prompts.map((prompt) =>
        prompt.id === editingPrompt.id
          ? {
              ...prompt,
              ...payload,
              description: payload.description,
              updated_at: new Date().toISOString(),
            }
          : prompt
      );
      const previous = prompts;
      setPrompts(optimistic);

      try {
        const updated = await updatePromptRequest(editingPrompt.id, payload);
        setPrompts((current) =>
          current.map((prompt) => (prompt.id === updated.id ? updated : prompt))
        );
        setStatus('Prompt updated successfully.');
        resetForm();
      } catch (err) {
        setPrompts(previous);
        handleError(err);
      } finally {
        setSaving(false);
      }
      return;
    }

    const temporaryId = `temp-${Date.now()}`;
    const optimisticPrompt: ArchonPrompt = {
      id: temporaryId,
      prompt_name: payload.prompt_name,
      prompt: payload.prompt,
      description: payload.description,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    const previous = prompts;
    setPrompts((current) => [optimisticPrompt, ...current]);

    try {
      const created = await createPromptRequest(payload);
      setPrompts((current) =>
        current.map((prompt) => (prompt.id === temporaryId ? created : prompt))
      );
      setStatus('Prompt created successfully.');
      resetForm();
    } catch (err) {
      setPrompts(previous);
      handleError(err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (prompt: ArchonPrompt) => {
    setError(null);
    setStatus(null);
    setDeletingId(prompt.id);
    const previous = prompts;
    setPrompts((current) => current.filter((item) => item.id !== prompt.id));

    try {
      await deletePromptRequest(prompt.id);
      if (editingPrompt?.id === prompt.id) {
        resetForm();
      }
      setStatus('Prompt deleted successfully.');
    } catch (err) {
      setPrompts(previous);
      handleError(err);
    } finally {
      setDeletingId(null);
    }
  };

  const startEditing = (prompt: ArchonPrompt) => {
    setEditingPrompt(prompt);
    setFormState({
      prompt_name: prompt.prompt_name,
      prompt: prompt.prompt,
      description: prompt.description ?? '',
    });
  };

  const onSearchSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await loadPrompts(searchTerm);
  };

  return (
    <div className="archon-prompts-page" data-testid="archon-prompts-page">
      <header>
        <h1 className="title">Archon Prompt Catalog</h1>
        <p className="subtitle">
          Manage prompt templates stored in Supabase. Authenticated users can read; service-role writes honor RLS.
        </p>
      </header>

      <section className="feedback" aria-live="polite">
        {error && (
          <div role="alert" className="feedback-error">
            {error}
          </div>
        )}
        {status && (
          <div role="status" className="feedback-status">
            {status}
          </div>
        )}
      </section>

      <section className="layout">
        <form className="prompt-form" onSubmit={upsertPrompt} data-testid="prompt-form">
          <h2>{editingPrompt ? 'Edit Prompt' : 'Create Prompt'}</h2>
          <label className="form-field">
            <span>Prompt name</span>
            <input
              name="prompt_name"
              value={formState.prompt_name}
              onChange={(event) =>
                setFormState((current) => ({ ...current, prompt_name: event.target.value }))
              }
              placeholder="Example: research_default"
              required
            />
          </label>

          <label className="form-field">
            <span>Prompt body</span>
            <textarea
              name="prompt"
              value={formState.prompt}
              onChange={(event) =>
                setFormState((current) => ({ ...current, prompt: event.target.value }))
              }
              rows={6}
              placeholder="Full prompt text"
              required
            />
          </label>

          <label className="form-field">
            <span>Description</span>
            <textarea
              name="description"
              value={formState.description}
              onChange={(event) =>
                setFormState((current) => ({ ...current, description: event.target.value }))
              }
              rows={3}
              placeholder="Optional context"
            />
          </label>

          <div className="form-actions">
            <button type="submit" disabled={saving}>
              {saving ? 'Saving…' : editingPrompt ? 'Save changes' : 'Create prompt'}
            </button>
            {editingPrompt && (
              <button type="button" onClick={resetForm} className="secondary">
                Cancel
              </button>
            )}
          </div>
        </form>

        <div className="prompt-table">
          <form className="search" onSubmit={onSearchSubmit} role="search">
            <label htmlFor="prompt-search" className="sr-only">
              Search prompts
            </label>
            <input
              id="prompt-search"
              type="search"
              placeholder="Search prompts"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
            />
            <button type="submit">Search</button>
          </form>

          {loading ? (
            <p>Loading prompts…</p>
          ) : filteredPrompts.length === 0 ? (
            <p>No prompts found.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th scope="col">Prompt name</th>
                  <th scope="col">Description</th>
                  <th scope="col">Updated</th>
                  <th scope="col" className="actions-column">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredPrompts.map((prompt) => (
                  <tr key={prompt.id} data-testid="prompt-row">
                    <td>{prompt.prompt_name}</td>
                    <td>{prompt.description ?? '—'}</td>
                    <td>{new Date(prompt.updated_at).toLocaleString()}</td>
                    <td className="actions">
                      <button type="button" onClick={() => startEditing(prompt)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(prompt)}
                        disabled={deletingId === prompt.id}
                        className="danger"
                      >
                        {deletingId === prompt.id ? 'Deleting…' : 'Delete'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <style>{`
        .archon-prompts-page {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
          padding: 2rem;
        }

        .title {
          margin: 0;
          font-size: 1.75rem;
        }

        .subtitle {
          margin: 0.25rem 0 0;
          color: #4b5563;
        }

        .feedback-error {
          background: #fee2e2;
          border: 1px solid #f87171;
          color: #991b1b;
          padding: 0.75rem;
          border-radius: 0.5rem;
        }

        .feedback-status {
          background: #dcfce7;
          border: 1px solid #86efac;
          color: #166534;
          padding: 0.75rem;
          border-radius: 0.5rem;
          margin-top: 0.5rem;
        }

        .layout {
          display: flex;
          flex-direction: column;
          gap: 2rem;
        }

        @media (min-width: 960px) {
          .layout {
            flex-direction: row;
            align-items: flex-start;
          }
        }

        .prompt-form,
        .prompt-table {
          flex: 1;
          background: #ffffff;
          border-radius: 0.75rem;
          padding: 1.5rem;
          box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
        }

        .prompt-form h2 {
          margin-top: 0;
        }

        .form-field {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          margin-bottom: 1rem;
        }

        .form-field input,
        .form-field textarea {
          padding: 0.65rem 0.75rem;
          border: 1px solid #d1d5db;
          border-radius: 0.5rem;
          font-size: 0.95rem;
        }

        .form-actions {
          display: flex;
          gap: 0.75rem;
        }

        button {
          cursor: pointer;
          border: none;
          border-radius: 0.5rem;
          padding: 0.6rem 1rem;
          font-weight: 600;
          background: #2563eb;
          color: white;
          transition: background 0.2s ease;
        }

        button:hover:not(:disabled) {
          background: #1d4ed8;
        }

        button:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }

        .secondary {
          background: #e5e7eb;
          color: #111827;
        }

        .secondary:hover:not(:disabled) {
          background: #d1d5db;
        }

        .danger {
          background: #ef4444;
        }

        .danger:hover:not(:disabled) {
          background: #dc2626;
        }

        .search {
          display: flex;
          gap: 0.75rem;
          margin-bottom: 1rem;
        }

        .search input[type='search'] {
          flex: 1;
          padding: 0.6rem 0.75rem;
          border-radius: 0.5rem;
          border: 1px solid #d1d5db;
        }

        table {
          width: 100%;
          border-collapse: collapse;
        }

        th,
        td {
          text-align: left;
          padding: 0.75rem 0.5rem;
          border-bottom: 1px solid #e5e7eb;
        }

        .actions {
          display: flex;
          gap: 0.5rem;
        }

        .actions-column {
          width: 150px;
        }

        .sr-only {
          position: absolute;
          width: 1px;
          height: 1px;
          padding: 0;
          margin: -1px;
          overflow: hidden;
          clip: rect(0, 0, 0, 0);
          border: 0;
        }
      `}</style>
    </div>
  );
}
