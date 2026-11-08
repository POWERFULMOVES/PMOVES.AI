import { test, expect, type Page } from '@playwright/test';

/**
 * E2E Tests for the Archon Prompt Forge (app/dashboard/archon-prompts/page.tsx)
 *
 * The page is a single view: an always-visible create/edit form, a search box, and a
 * table of prompts with inline Edit/Delete. There is no per-prompt detail route, no
 * category field, no delete confirmation, and no execute action (see the fixme notes).
 *
 * Backend-free: both data paths the page uses are mocked with page.route, so every
 * assertion is unconditional and deterministic.
 *   - list/search: the browser Supabase client, GET /rest/v1/archon_prompts
 *     (listArchonPrompts, lib/archonPrompts.ts:123-145)
 *   - writes: POST /api/archon-prompts, PATCH|DELETE /api/archon-prompts/:id
 *     (createPromptRequest..deletePromptRequest, page.tsx:43-87)
 *
 * @module e2e/archon-prompts
 */

type Prompt = {
  id: string;
  prompt_name: string;
  prompt: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

const STAMP = '2026-09-01T12:00:00.000Z';
const FIXTURE: Prompt[] = [
  {
    id: 'p-alpha',
    prompt_name: 'alpha_research',
    prompt: 'Research {{topic}} in depth.',
    description: 'Deep research starter',
    created_at: STAMP,
    updated_at: STAMP,
  },
  {
    id: 'p-beta',
    prompt_name: 'beta_summary',
    prompt: 'Summarise the input.',
    description: null,
    created_at: STAMP,
    updated_at: STAMP,
  },
];

type Write = { method: string; path: string; body: Record<string, unknown> | null };

interface ForgeMock {
  /** Query string of every list request the Supabase client made. */
  listQueries: URLSearchParams[];
  /** Every write sent to /api/archon-prompts[/:id]. */
  writes: Write[];
  /** When set, writes answer with this status and error payload instead of succeeding. */
  failWrites: { status: number; type?: string; message: string } | null;
}

const CORS = { 'access-control-allow-origin': '*' };

async function mockPromptForge(page: Page): Promise<ForgeMock> {
  const mock: ForgeMock = { listQueries: [], writes: [], failWrites: null };
  const rows = FIXTURE.map((p) => ({ ...p }));

  await page.route(/\/rest\/v1\/archon_prompts(\?|$)/, async (route) => {
    const req = route.request();
    if (req.method() === 'OPTIONS') {
      await route.fulfill({
        status: 204,
        headers: { ...CORS, 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' },
      });
      return;
    }
    const params = new URL(req.url()).searchParams;
    mock.listQueries.push(params);
    // PostgREST ilike filter as sent by listArchonPrompts: prompt_name=ilike.%term%
    const ilike = params.get('prompt_name');
    const term = ilike ? ilike.replace(/^ilike\./, '').replace(/%/g, '').toLowerCase() : '';
    const out = rows.filter((r) => r.prompt_name.toLowerCase().includes(term));
    await route.fulfill({ status: 200, contentType: 'application/json', headers: CORS, body: JSON.stringify(out) });
  });

  await page.route(/\/api\/archon-prompts(\/[^/?]+)?(\?.*)?$/, async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const raw = req.postData();
    const body = raw ? (JSON.parse(raw) as Record<string, unknown>) : null;
    mock.writes.push({ method: req.method(), path, body });

    if (mock.failWrites) {
      const { status, type, message } = mock.failWrites;
      await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify({ error: { type, message } }) });
      return;
    }
    const id = path.split('/').pop() as string;
    if (req.method() === 'POST') {
      const created = { id: 'p-new', created_at: STAMP, updated_at: STAMP, ...body };
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ data: created }) });
      return;
    }
    if (req.method() === 'PATCH') {
      const existing = rows.find((r) => r.id === id);
      const updated = { ...existing, ...body, updated_at: STAMP };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: updated }) });
      return;
    }
    if (req.method() === 'DELETE') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
      return;
    }
    await route.fulfill({ status: 405, contentType: 'application/json', body: '{}' });
  });

  return mock;
}

async function openForge(page: Page): Promise<ForgeMock> {
  const mock = await mockPromptForge(page);
  await page.goto('/dashboard/archon-prompts');
  await expect(page.getByTestId('prompt-row')).toHaveCount(FIXTURE.length);
  return mock;
}

/** The page's own feedback region (page.tsx:290-301); Next's route announcer is also role=alert. */
function feedback(page: Page, role: 'alert' | 'status') {
  return page.getByTestId('archon-prompts-page').getByRole(role);
}

function row(page: Page, name: string) {
  return page.getByTestId('prompt-row').filter({ hasText: name });
}

test.describe('Archon Prompts - List View', () => {
  // renamed-from: displays prompts list with search and filters
  test('displays prompts list with search', async ({ page }) => {
    await openForge(page);

    await expect(page.getByTestId('archon-prompts-page')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Archon Prompt Forge' })).toBeVisible();
    await expect(page.getByRole('searchbox', { name: 'Search prompts' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeVisible();
  });

  // renamed-from: displays prompt cards with key information
  test('displays prompt rows with key information', async ({ page }) => {
    const mock = await openForge(page);

    // listArchonPrompts orders by name (lib/archonPrompts.ts:130-132)
    expect(mock.listQueries[0].get('order')).toBe('prompt_name.asc');

    const alpha = row(page, 'alpha_research');
    await expect(alpha.getByRole('cell').nth(0)).toHaveText('alpha_research');
    await expect(alpha.getByRole('cell').nth(1)).toHaveText('Deep research starter');
    await expect(alpha.getByRole('button', { name: 'Edit' })).toBeVisible();
    await expect(alpha.getByRole('button', { name: 'Delete' })).toBeVisible();

    // A null description renders as an em dash (page.tsx:393)
    await expect(row(page, 'beta_summary').getByRole('cell').nth(1)).toHaveText('—');
  });

  // fixme: FEATURE NOT BUILT: prompts have no category. ArchonPrompt has no category field
  // (lib/archonPrompts.ts:3-10) and app/dashboard/archon-prompts/page.tsx:271-580 renders no
  // category control. The old body was guarded by `if (count > 0)` and could never fail.
  // The body states the intended behaviour so it fails loudly once un-fixme'd.
  test.fixme('filters prompts by category', async ({ page }) => {
    await openForge(page);
    const categoryFilter = page.getByRole('combobox', { name: /category/i });
    await expect(categoryFilter).toBeVisible();
    await categoryFilter.selectOption({ index: 1 });
    await expect(page.getByTestId('prompt-row')).toHaveCount(1);
  });

  test('searches prompts by text', async ({ page }) => {
    const mock = await openForge(page);
    const search = page.getByRole('searchbox', { name: 'Search prompts' });

    // Typing filters the loaded rows client-side (filteredPrompts, page.tsx:130-141)
    await search.fill('alpha');
    await expect(page.getByTestId('prompt-row')).toHaveCount(1);
    await expect(row(page, 'alpha_research')).toBeVisible();

    // Submitting re-queries Supabase with an ilike filter (onSearchSubmit, page.tsx:266-269)
    await search.press('Enter');
    // (the initial load can run twice under React dev StrictMode, so match by content, not index)
    await expect
      .poll(() => mock.listQueries.map((q) => q.get('prompt_name')))
      .toContain('ilike.%alpha%');
    await expect(page.getByTestId('prompt-row')).toHaveCount(1);

    // No match: the empty state replaces the table
    await search.fill('zzz-no-such-prompt');
    await expect(page.getByText('No prompts found.')).toBeVisible();
    await expect(page.getByTestId('prompt-row')).toHaveCount(0);
  });
});

test.describe('Archon Prompts - Create', () => {
  test('shows create prompt button', async ({ page }) => {
    await openForge(page);
    const form = page.getByTestId('prompt-form');
    await expect(form.getByRole('heading', { name: 'Create Prompt' })).toBeVisible();
    await expect(form.getByRole('button', { name: 'Create prompt' })).toBeEnabled();
  });

  // renamed-from: opens create form with required fields
  test('shows create form with required fields', async ({ page }) => {
    await openForge(page);
    const form = page.getByTestId('prompt-form');

    // The form is always rendered (no open step): Prompt name, Prompt body, Description
    const name = form.getByRole('textbox', { name: 'Prompt name' });
    const body = form.getByRole('textbox', { name: 'Prompt body' });
    const description = form.getByRole('textbox', { name: 'Description' });
    await expect(name).toBeVisible();
    await expect(body).toBeVisible();
    await expect(description).toBeVisible();
    await expect(name).toHaveAttribute('required', '');
    await expect(body).toHaveAttribute('required', '');
    await expect(description).not.toHaveAttribute('required', '');
  });

  test('validates required fields on create', async ({ page }) => {
    const mock = await openForge(page);
    const form = page.getByTestId('prompt-form');
    const name = form.getByRole('textbox', { name: 'Prompt name' });
    const submit = form.getByRole('button', { name: 'Create prompt' });

    // Empty fields: native `required` validation blocks the submit
    await submit.click();
    expect(await name.evaluate((el) => (el as HTMLInputElement).validity.valueMissing)).toBe(true);

    // Whitespace-only passes `required`, then the page's own trim check rejects it (page.tsx:171-174)
    await name.fill('   ');
    await form.getByRole('textbox', { name: 'Prompt body' }).fill('   ');
    await submit.click();
    await expect(feedback(page, 'alert')).toHaveText('Prompt name and prompt body are required.');

    expect(mock.writes).toHaveLength(0);
  });

  test('creates a prompt', async ({ page }) => {
    const mock = await openForge(page);
    const form = page.getByTestId('prompt-form');

    await form.getByRole('textbox', { name: 'Prompt name' }).fill('  gamma_plan  ');
    await form.getByRole('textbox', { name: 'Prompt body' }).fill('Plan the next step.');
    await form.getByRole('button', { name: 'Create prompt' }).click();

    await expect(feedback(page, 'status')).toHaveText('Prompt created successfully.');
    expect(mock.writes).toEqual([
      {
        method: 'POST',
        path: '/api/archon-prompts',
        body: { prompt_name: 'gamma_plan', prompt: 'Plan the next step.', description: null },
      },
    ]);
    await expect(row(page, 'gamma_plan')).toBeVisible();
    await expect(page.getByTestId('prompt-row')).toHaveCount(FIXTURE.length + 1);
    // Form resets after a successful create
    await expect(form.getByRole('textbox', { name: 'Prompt name' })).toHaveValue('');
  });

  test('shows the duplicate-name error and rolls back the optimistic row', async ({ page }) => {
    const mock = await openForge(page);
    mock.failWrites = { status: 409, type: 'DuplicatePromptNameError', message: 'duplicate' };
    const form = page.getByTestId('prompt-form');

    await form.getByRole('textbox', { name: 'Prompt name' }).fill('alpha_research');
    await form.getByRole('textbox', { name: 'Prompt body' }).fill('Again.');
    await form.getByRole('button', { name: 'Create prompt' }).click();

    await expect(feedback(page, 'alert')).toHaveText(
      'A prompt with this name already exists. Choose a different name.'
    );
    await expect(page.getByTestId('prompt-row')).toHaveCount(FIXTURE.length);
  });
});

test.describe('Archon Prompts - Edit', () => {
  // renamed-from: navigates to edit page from list
  test('loads a prompt into the form from the list', async ({ page }) => {
    await openForge(page);
    const form = page.getByTestId('prompt-form');

    // There is no detail route: Edit loads the row into the same form (startEditing, page.tsx:257-264)
    await row(page, 'alpha_research').getByRole('button', { name: 'Edit' }).click();
    await expect(form.getByRole('heading', { name: 'Edit Prompt' })).toBeVisible();
    await expect(form.getByRole('textbox', { name: 'Prompt name' })).toHaveValue('alpha_research');
    await expect(form.getByRole('textbox', { name: 'Prompt body' })).toHaveValue('Research {{topic}} in depth.');
    await expect(form.getByRole('textbox', { name: 'Description' })).toHaveValue('Deep research starter');
    await expect(form.getByRole('button', { name: 'Save changes' })).toBeVisible();

    // Cancel returns the form to create mode
    await form.getByRole('button', { name: 'Cancel' }).click();
    await expect(form.getByRole('heading', { name: 'Create Prompt' })).toBeVisible();
    await expect(form.getByRole('textbox', { name: 'Prompt name' })).toHaveValue('');
  });

  test('saves prompt changes', async ({ page }) => {
    const mock = await openForge(page);
    const form = page.getByTestId('prompt-form');

    await row(page, 'alpha_research').getByRole('button', { name: 'Edit' }).click();
    await form.getByRole('textbox', { name: 'Prompt name' }).fill('alpha_research_v2');
    await form.getByRole('button', { name: 'Save changes' }).click();

    await expect(feedback(page, 'status')).toHaveText('Prompt updated successfully.');
    expect(mock.writes).toEqual([
      {
        method: 'PATCH',
        path: '/api/archon-prompts/p-alpha',
        body: {
          prompt_name: 'alpha_research_v2',
          prompt: 'Research {{topic}} in depth.',
          description: 'Deep research starter',
        },
      },
    ]);
    await expect(row(page, 'alpha_research_v2')).toBeVisible();
    await expect(form.getByRole('heading', { name: 'Create Prompt' })).toBeVisible();
  });
});

test.describe('Archon Prompts - Delete', () => {
  test('deletes a prompt from the list', async ({ page }) => {
    const mock = await openForge(page);

    await row(page, 'beta_summary').getByRole('button', { name: 'Delete' }).click();

    await expect(feedback(page, 'status')).toHaveText('Prompt deleted successfully.');
    expect(mock.writes).toEqual([{ method: 'DELETE', path: '/api/archon-prompts/p-beta', body: null }]);
    await expect(row(page, 'beta_summary')).toHaveCount(0);
    await expect(page.getByTestId('prompt-row')).toHaveCount(FIXTURE.length - 1);
  });

  // fixme: FEATURE NOT BUILT: there is no delete confirmation. handleDelete
  // (app/dashboard/archon-prompts/page.tsx:236-254) removes the row and calls DELETE immediately,
  // and the page renders no dialog. The old body was guarded by `if (count > 0)` against a
  // /dashboard/archon-prompts/test-prompt route that does not exist, so it could never fail.
  test.fixme('shows delete confirmation', async ({ page }) => {
    const mock = await openForge(page);
    await row(page, 'beta_summary').getByRole('button', { name: 'Delete' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    expect(mock.writes).toHaveLength(0);
  });

  // fixme: FEATURE NOT BUILT: there is no delete confirmation to cancel (handleDelete,
  // app/dashboard/archon-prompts/page.tsx:236-254, deletes immediately). Old body was guarded
  // by `if (count > 0)` against a nonexistent detail route.
  test.fixme('cancels delete on confirmation cancel', async ({ page }) => {
    const mock = await openForge(page);
    await row(page, 'beta_summary').getByRole('button', { name: 'Delete' }).click();
    await page.getByRole('dialog').getByRole('button', { name: /cancel/i }).click();
    await expect(row(page, 'beta_summary')).toBeVisible();
    expect(mock.writes).toHaveLength(0);
  });
});

test.describe('Archon Prompts - Execute', () => {
  // fixme: FEATURE NOT BUILT: prompts cannot be executed from the UI. app/dashboard/archon-prompts/
  // holds only page.tsx (no detail route), the row actions are Edit/Delete only (page.tsx:395-407),
  // and app/api/archon-prompts/[id]/route.ts exports only PATCH and DELETE. Old body was guarded.
  test.fixme('shows execute button on prompt detail', async ({ page }) => {
    await openForge(page);
    await expect(row(page, 'alpha_research').getByRole('button', { name: /execute|run/i })).toBeVisible();
  });

  // fixme: FEATURE NOT BUILT: no execute flow, so no template-variable form (see the test above;
  // the {{topic}} placeholder in a prompt body is stored verbatim and never parsed by the page).
  test.fixme('shows variable input form for template variables', async ({ page }) => {
    await openForge(page);
    await row(page, 'alpha_research').getByRole('button', { name: /execute|run/i }).click();
    await expect(page.getByRole('dialog').getByRole('textbox', { name: /topic/i })).toBeVisible();
  });
});
