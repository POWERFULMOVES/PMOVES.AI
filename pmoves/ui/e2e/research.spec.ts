/* ═══════════════════════════════════════════════════════════════════════════
   Deep Research Dashboard E2E Tests
   Tests end-to-end DeepResearch workflows against the built /dashboard/research UI
   (app/dashboard/research/page.tsx renders TaskInitiationForm :200 and
   ResearchTaskList :208). The DeepResearch service is mocked with page.route —
   never a live backend.
   ═══════════════════════════════════════════════════════════════════════════ */

import { test, expect, type Page } from '@playwright/test';

const CORS = { 'Access-Control-Allow-Origin': '*' };

const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();

const TASKS = [
  { id: 't-running', query: 'Running research', status: 'running', mode: 'tensorzero', createdAt: minutesAgo(5) },
  { id: 't-completed', query: 'Completed research', status: 'completed', mode: 'openrouter', createdAt: minutesAgo(90) },
  { id: 't-pending', query: 'Pending research', status: 'pending', mode: 'local', createdAt: minutesAgo(1) },
];

/**
 * Backend-free mock for GET /research/tasks. Later registrations win in Playwright,
 * so a test can call this after beforeEach's empty-list mock and reload.
 */
async function mockTaskList(page: Page, tasks: unknown[], delayMs = 0) {
  await page.route('**/research/tasks?*', async (route) => {
    if (delayMs) await new Promise((r) => setTimeout(r, delayMs));
    await route.fulfill({ status: 200, contentType: 'application/json', headers: CORS, body: JSON.stringify({ tasks }) });
  });
}

async function withTasks(page: Page, tasks: unknown[] = TASKS) {
  await mockTaskList(page, tasks);
  await page.reload();
  await page.waitForLoadState('networkidle');
}

const RESULT = {
  taskId: 't-completed',
  summary: 'Quantum computers use qubits to explore many states at once.',
  notes: ['Superposition note', 'Entanglement note'],
  sources: [{ title: 'Source A', url: 'https://example.test/a', snippet: 'A snippet' }],
  iterations: 7,
  duration: 150000,
  completedAt: minutesAgo(80),
};

/** Mock GET /research/tasks/:id/results; `status` is read per request so tests can flip it. */
async function mockResults(page: Page, status: () => number = () => 200, result: typeof RESULT = RESULT) {
  await page.route('**/research/tasks/*/results', (route) => {
    const code = status();
    return route.fulfill({
      status: code,
      contentType: 'application/json',
      headers: CORS,
      body: JSON.stringify(code === 200 ? result : { detail: 'mocked error' }),
    });
  });
}

/** Mock POST /research/tasks/:id/publish and capture path + body. */
async function mockPublish(page: Page, delayMs = 0) {
  const calls: Array<{ path: string; body: unknown }> = [];
  await page.route('**/research/tasks/*/publish', async (route) => {
    calls.push({ path: new URL(route.request().url()).pathname, body: JSON.parse(route.request().postData() || '{}') });
    if (delayMs) await new Promise((r) => setTimeout(r, delayMs));
    await route.fulfill({ status: 200, contentType: 'application/json', headers: CORS, body: '{}' });
  });
  return calls;
}

/** Seed the task list, select the completed task and wait for its results to render. */
async function openCompletedResults(page: Page, result: typeof RESULT = RESULT) {
  await mockResults(page, () => 200, result);
  await withTasks(page);
  await page.locator('[data-testid="task-item"][data-status="completed"]').click();
  await expect(page.locator('[data-testid="research-results"]')).toBeVisible({ timeout: 10000 });
}

/**
 * Assign a raw value to a range input the way a script would. Playwright's fill()
 * refuses out-of-range values on type=range ("Malformed value") because the browser
 * sanitises them, so assign directly and let the browser apply min/max clamping.
 */
async function setRangeValue(page: Page, testId: string, value: string) {
  return page.locator(`[data-testid="${testId}"]`).evaluate((el, v) => {
    (el as HTMLInputElement).value = v;
    return (el as HTMLInputElement).value;
  }, value);
}

async function expandOptions(page: Page) {
  await page.click('[data-testid="expand-options-button"]');
  await expect(page.locator('[data-testid="research-options-panel"]')).toBeVisible();
}

test.describe('Deep Research Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Health and an empty task list are mocked so no test reaches a live DeepResearch.
    await page.route('**/healthz', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', headers: CORS, body: JSON.stringify({ healthy: true }) })
    );
    await mockTaskList(page, []);
    // Navigate to research dashboard
    await page.goto('/dashboard/research');
    // Wait for page to load
    await page.waitForLoadState('networkidle');
  });

  test('should load research page with initial state', async ({ page }) => {
    // Check that task initiation form is present
    await expect(page.locator('[data-testid="task-initiation-form"]')).toBeVisible();

    // Check that task list is present
    await expect(page.locator('[data-testid="task-list"]')).toBeVisible();

    // Results are only rendered once a completed task is selected (page.tsx:296)
    await expect(page.locator('[data-testid="research-results"]')).toHaveCount(0);
  });

  // fixme: behaviour mismatch: built submit flow shows no task-started message and does not clear the query — page.tsx:89-101 handleInitiate only refreshes the task list; TaskInitiationForm.tsx handleSubmit keeps the query. Operator to decide whether to build the confirmation + reset. Tracked in #3226
  test.fixme('should initiate research task with default options', async ({ page }) => {
    // Enter research query
    await page.fill('[data-testid="research-query"]', 'What is quantum computing?');

    // Submit with default options
    await page.click('[data-testid="start-research"]');

    // Should show success message or task started indicator
    await expect(page.locator('[data-testid="task-started-message"]')).toBeVisible({ timeout: 5000 });

    // Query input should be cleared
    await expect(page.locator('[data-testid="research-query"]')).toHaveValue('');
  });

  test('should validate non-empty query', async ({ page }) => {
    // Built behaviour: submit is disabled while the query is empty/blank
    // (TaskInitiationForm.tsx disabled={loading || !query.trim()}), no error element.
    const submitButton = page.locator('[data-testid="start-research"]');
    await expect(submitButton).toBeDisabled();
    await page.fill('[data-testid="research-query"]', '   ');
    await expect(submitButton).toBeDisabled();
    await page.fill('[data-testid="research-query"]', 'a real question');
    await expect(submitButton).toBeEnabled();
  });

  test('should show character count for query', async ({ page }) => {
    // Enter query
    await page.fill('[data-testid="research-query"]', 'test query');

    // Check character count ("test query" is 10 characters)
    const charCount = page.locator('[data-testid="query-char-count"]');
    await expect(charCount).toBeVisible();
    await expect(charCount).toHaveText('10 / 1000');
  });

  test('should enforce max query length (1000)', async ({ page }) => {
    // Try to enter very long query
    const longQuery = 'a'.repeat(1500);

    // Input should be truncated (textarea maxLength={1000})
    await page.fill('[data-testid="research-query"]', longQuery);

    const actualValue = await page.inputValue('[data-testid="research-query"]');
    expect(actualValue.length).toBeLessThanOrEqual(1000);
  });

  test('should expand/collapse options panel', async ({ page }) => {
    // Options panel should be collapsed by default
    const optionsPanel = page.locator('[data-testid="research-options-panel"]');
    await expect(optionsPanel).toBeHidden();

    // Click expand button
    await page.click('[data-testid="expand-options-button"]');

    // Panel should now be visible
    await expect(optionsPanel).toBeVisible({ timeout: 2000 });

    // Click collapse button (same toggle; its test id follows the expanded state)
    await page.click('[data-testid="collapse-options-button"]');

    // Panel should be hidden
    await expect(optionsPanel).toBeHidden();
  });

  test('should select research mode', async ({ page }) => {
    // Expand options first
    await expandOptions(page);

    // Select different mode
    await page.selectOption('[data-testid="research-mode"]', 'openrouter');

    // Verify selection
    await expect(page.locator('[data-testid="research-mode"]')).toHaveValue('openrouter');
  });

  test('should update max iterations slider', async ({ page }) => {
    // Expand options first
    await expandOptions(page);

    // Find slider
    const slider = page.locator('[data-testid="max-iterations-slider"]');

    // Update slider value
    await slider.fill('20');

    // Verify new value (DOM and the component state reflected in the label)
    expect(await slider.inputValue()).toBe('20');
    await expect(page.getByText('Max Iterations: 20')).toBeVisible();
  });

  test('should enforce max iterations range (3-30)', async ({ page }) => {
    // Expand options first
    await expandOptions(page);

    // Try to set value below minimum
    const slider = page.locator('[data-testid="max-iterations-slider"]');
    await expect(slider).toHaveAttribute('min', '3');
    await expect(slider).toHaveAttribute('max', '30');
    await setRangeValue(page, 'max-iterations-slider', '1');

    // Should clamp to minimum
    const actualValue = await slider.inputValue();
    expect(parseInt(actualValue)).toBe(3);

    // Try to set value above maximum
    await setRangeValue(page, 'max-iterations-slider', '50');

    // Should clamp to maximum
    const maxValue = await slider.inputValue();
    expect(parseInt(maxValue)).toBe(30);
  });

  test('should update priority slider', async ({ page }) => {
    // Expand options first
    await expandOptions(page);

    // Find slider
    const slider = page.locator('[data-testid="priority-slider"]');

    // Update slider value
    await slider.fill('8');

    // Verify new value (DOM and the component state reflected in the label)
    expect(await slider.inputValue()).toBe('8');
    await expect(page.getByText('Priority: 8')).toBeVisible();
  });

  test('should enforce priority range (1-10)', async ({ page }) => {
    // Expand options first
    await expandOptions(page);

    // Try to set value below minimum
    const slider = page.locator('[data-testid="priority-slider"]');
    await expect(slider).toHaveAttribute('min', '1');
    await expect(slider).toHaveAttribute('max', '10');
    await setRangeValue(page, 'priority-slider', '0');

    // Should clamp to minimum
    const actualValue = await slider.inputValue();
    expect(parseInt(actualValue)).toBe(1);

    // Try to set value above maximum
    await setRangeValue(page, 'priority-slider', '15');

    // Should clamp to maximum
    const maxValue = await slider.inputValue();
    expect(parseInt(maxValue)).toBe(10);
  });

  // fixme: UI unwired: TaskInitiationForm notebook select not rendered (TaskInitiationForm.tsx:180 renders it only when notebooks.length > 0; page.tsx:200-203 passes no notebooks prop). Tracked in #3226
  test.fixme('should select notebook from dropdown', async ({ page }) => {
    // Expand options first
    await page.click('[data-testid="expand-options-button"]');

    // Select a notebook
    const notebookSelect = page.locator('[data-testid="notebook-select"]');
    await expect(notebookSelect).toBeVisible({ timeout: 1000 });
    await page.selectOption('[data-testid="notebook-select"]', { index: 1 });

    // Verify selection
    const selectedOption = await notebookSelect.inputValue();
    expect(selectedOption).toBeTruthy();
  });

  test('should list tasks with status filter', async ({ page }) => {
    await withTasks(page);

    // Check that task list is visible with all mocked tasks
    await expect(page.locator('[data-testid="task-list"]')).toBeVisible();
    await expect(page.locator('[data-testid="task-item"]')).toHaveCount(TASKS.length);

    // Filter by status (client-side filter, ResearchTaskList.tsx statusFilter)
    await page.selectOption('[data-testid="status-filter"]', 'running');

    // Only the running task remains
    const items = page.locator('[data-testid="task-item"]');
    await expect(items).toHaveCount(1);
    await expect(items.first()).toHaveAttribute('data-status', 'running');
    await expect(page.locator('[data-testid="task-list"]')).toBeVisible();
  });

  // fixme: UI unwired: mode filter not rendered (ResearchTaskList.tsx:94-107 renders only the status filter; lib/api/research.ts listResearchTasks accepts `mode` but no UI passes it). Tracked in #3226
  test.fixme('should filter tasks by mode', async ({ page }) => {
    // Filter by mode
    await page.selectOption('[data-testid="mode-filter"]', 'tensorzero');

    // Wait for filter to apply
    await page.waitForTimeout(500);

    // Task list should still be visible
    await expect(page.locator("[data-testid='task-list']")).toBeVisible();
  });

  // fixme: UI unwired: task multi-select not rendered on /dashboard/research (ResearchTaskList.tsx has no checkboxes or selection controls; "Select All Visible" exists only in components/ingestion/BulkApprovalActions.tsx:130). Tracked in #3226
  test.fixme('should select all visible tasks', async ({ page }) => {
    // Click "select all visible" button
    await page.click('[data-testid="select-all-visible"]');

    // All visible tasks should be selected
    const taskCheckboxes = page.locator('[data-testid="task-checkbox"]');
    const count = await taskCheckboxes.count();

    for (let i = 0; i < count; i++) {
      const checkbox = taskCheckboxes.nth(i);
      await expect(checkbox).toBeChecked();
    }
  });

  // fixme: UI unwired: task multi-select not rendered on /dashboard/research (ResearchTaskList.tsx has no selection controls; "Select Pending" exists only in components/ingestion/BulkApprovalActions.tsx:133). Tracked in #3226
  test.fixme('should select only pending tasks', async ({ page }) => {
    // Click "select pending" button
    await page.click('[data-testid="select-pending"]');

    // Only pending tasks should be selected
    page.locator('[data-testid="task-item"][data-status="pending"]');

    // At least verify button exists and is clickable
    await expect(page.locator('[data-testid="select-pending"]')).toBeVisible();
  });

  // fixme: UI unwired: task multi-select not rendered on /dashboard/research (ResearchTaskList.tsx has no selection controls; clear-selection exists only in components/ingestion/BulkApprovalActions.tsx). Tracked in #3226
  test.fixme('should clear task selection', async ({ page }) => {
    // First select some tasks
    await page.click('[data-testid="select-all-visible"]');

    // Then clear selection
    await page.click('[data-testid="clear-selection"]');

    // All tasks should be unchecked
    const taskCheckboxes = page.locator('[data-testid="task-checkbox"]');
    const count = await taskCheckboxes.count();

    for (let i = 0; i < count; i++) {
      const checkbox = taskCheckboxes.nth(i);
      const isChecked = await checkbox.isChecked();
      expect(isChecked).toBe(false);
    }
  });

  test('should refresh task list', async ({ page }) => {
    // Slow the next list response so the refreshing state is observable
    await mockTaskList(page, TASKS, 1000);

    // Click refresh button
    await page.click('[data-testid="refresh-tasks"]');

    // Should show loading state briefly
    await expect(page.locator('[data-testid="refresh-tasks"]')).toHaveAttribute('data-loading', 'true');

    // Loading should end and the refreshed tasks render
    await expect(page.locator('[data-testid="refresh-tasks"]')).not.toHaveAttribute('data-loading', 'true', { timeout: 5000 });
    await expect(page.locator('[data-testid="task-item"]')).toHaveCount(TASKS.length);
  });

  test('should cancel running task', async ({ page }) => {
    // Stateful list mock: a task reports "cancelled" once its cancel endpoint was hit.
    const cancelled: string[] = [];
    const cancelRequests: string[] = [];
    await page.route('**/research/tasks?*', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: CORS,
        body: JSON.stringify({
          tasks: TASKS.map((t) => (cancelled.includes(t.id) ? { ...t, status: 'cancelled' } : t)),
        }),
      })
    );
    await page.route('**/research/tasks/*/cancel', async (route) => {
      cancelRequests.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
      cancelled.push(route.request().url().split('/').at(-2) as string);
      await route.fulfill({ status: 200, contentType: 'application/json', headers: CORS, body: '{}' });
    });
    await page.reload();
    await page.waitForLoadState('networkidle');

    const runningItem = page.locator('[data-testid="task-item"]', { hasText: 'Running research' });
    await expect(runningItem).toHaveAttribute('data-status', 'running');

    // Only running tasks offer a cancel button (ResearchTaskList.tsx)
    await expect(page.locator('[data-testid="cancel-task-button"]')).toHaveCount(1);
    await runningItem.locator('[data-testid="cancel-task-button"]').click();

    // Built flow (page.tsx:115-120): POST /cancel, then refresh the list. There is no
    // confirm dialog and no cancelled toast; the refreshed status is the feedback.
    expect(cancelRequests).toEqual(['POST /research/tasks/t-running/cancel']);
    await expect(runningItem).toHaveAttribute('data-status', 'cancelled');
    await expect(page.locator('[data-testid="cancel-task-button"]')).toHaveCount(0);
  });

  test('should display task status icons', async ({ page }) => {
    await withTasks(page, [
      ...TASKS,
      { id: 't-failed', query: 'Failed research', status: 'failed', mode: 'hybrid', createdAt: minutesAgo(2), errorMessage: 'boom' },
    ]);

    // One icon per seeded status (ResearchTaskList.tsx STATUS_ICONS)
    await expect(page.locator('[data-testid="status-icon-pending"]')).toHaveText('⏳');
    await expect(page.locator('[data-testid="status-icon-running"]')).toHaveText('🔄');
    await expect(page.locator('[data-testid="status-icon-completed"]')).toHaveText('✅');
    await expect(page.locator('[data-testid="status-icon-failed"]')).toHaveText('❌');
  });

  test('should format relative time correctly', async ({ page }) => {
    // Timestamps are built at test time so the minute buckets cannot drift.
    await withTasks(page, [
      { id: 'a', query: 'Five minutes', status: 'pending', mode: 'local', createdAt: minutesAgo(5.5) },
      { id: 'b', query: 'Ninety minutes', status: 'pending', mode: 'local', createdAt: minutesAgo(90) },
      { id: 'c', query: 'Seconds ago', status: 'pending', mode: 'local', createdAt: new Date().toISOString() },
    ]);

    // ResearchTaskList.tsx formatDate: <1m "Just now", <60m "Nm ago", <24h "Nh ago"
    await expect(page.locator('[data-testid="task-relative-time"]')).toHaveText(['5m ago', '1h ago', 'Just now']);
  });

  test('should display results for completed task', async ({ page }) => {
    // First results fetch fails, so the page offers "Load Results"; the retry succeeds.
    let resultsStatus = 500;
    await mockResults(page, () => resultsStatus);
    await withTasks(page);

    await page.locator('[data-testid="task-item"][data-status="completed"]').click();

    // Should show task details
    await expect(page.locator('[data-testid="task-details"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('[data-testid="task-details"]')).toContainText('Completed research');

    const loadResultsButton = page.locator('[data-testid="load-results"]');
    await expect(loadResultsButton).toBeVisible();
    await expect(page.locator('[data-testid="research-results"]')).toHaveCount(0);

    resultsStatus = 200;
    await loadResultsButton.click();

    // Should show research results
    await expect(page.locator('[data-testid="research-results"]')).toBeVisible({ timeout: 10000 });
    await expect(loadResultsButton).toHaveCount(0);
  });

  test('should display research summary', async ({ page }) => {
    await openCompletedResults(page);

    await expect(page.locator('[data-testid="research-summary"]')).toBeVisible();
    await expect(page.locator('[data-testid="research-summary-content"]')).toHaveText(RESULT.summary);
  });

  test('should expand/collapse notes section', async ({ page }) => {
    await openCompletedResults(page);

    const notesSection = page.locator('[data-testid="research-notes"]');
    const notesToggle = page.locator('[data-testid="toggle-notes"]');

    // Notes start expanded (ResearchResults.tsx expandedNotes = true)
    await expect(notesSection.locator('li')).toHaveCount(RESULT.notes.length);
    await notesToggle.click();
    await expect(notesSection).toBeHidden();
    await notesToggle.click();
    await expect(notesSection).toBeVisible();
  });

  test('should expand/collapse sources section', async ({ page }) => {
    await openCompletedResults(page);

    const sourcesSection = page.locator('[data-testid="research-sources"]');
    const sourcesToggle = page.locator('[data-testid="toggle-sources"]');

    await expect(sourcesSection.locator('a')).toHaveAttribute('href', RESULT.sources[0].url);
    await sourcesToggle.click();
    await expect(sourcesSection).toBeHidden();
    await sourcesToggle.click();
    await expect(sourcesSection).toBeVisible();
  });

  test('should copy summary to clipboard', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await openCompletedResults(page);

    const copyButton = page.locator('[data-testid="copy-summary-button"]');
    await expect(copyButton).toHaveText('Copy summary');
    await copyButton.click();

    // Built feedback is the button label (ResearchResults.tsx copiedSection), not a toast
    await expect(copyButton).toHaveText('Copied!');
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(RESULT.summary);
    await expect(copyButton).toHaveText('Copy summary', { timeout: 5000 });
  });

  // fixme: behaviour mismatch: duration units disagree across the contract — lib/api/research.ts:81 documents ResearchResult.duration as SECONDS, ResearchResults.tsx:49-55 formatDuration treats it as MILLISECONDS (150 renders "0s"), and services/deepresearch/worker.py:381 emits `duration_ms`. Operator to pick the unit. Tracked in #3226
  test.fixme('should format duration correctly', async ({ page }) => {
    await openCompletedResults(page, { ...RESULT, duration: 150 });

    // 150 seconds, per the documented contract
    await expect(page.locator('[data-testid="research-duration"]')).toHaveText('2m 30s');
  });

  test('should publish to notebook', async ({ page }) => {
    const publishBodies = await mockPublish(page);
    await openCompletedResults(page);

    await page.click('[data-testid="publish-notebook-button"]');

    // Built flow publishes to the "default" notebook with no selector modal
    // (page.tsx:122-135) and confirms with a status banner.
    await expect(page.locator('[data-testid="research-success"]')).toContainText('Results published to notebook');
    expect(publishBodies).toEqual([{ path: '/research/tasks/t-completed/publish', body: { notebook_id: 'default' } }]);
  });

  test('should handle empty notes/sources', async ({ page }) => {
    await openCompletedResults(page, { ...RESULT, notes: [], sources: [] });

    // Built empty state: the Notes and Sources sections are omitted
    // (ResearchResults.tsx renders them only when non-empty); the summary still shows.
    await expect(page.locator('[data-testid="research-summary-content"]')).toHaveText(RESULT.summary);
    await expect(page.locator('[data-testid="research-notes"]')).toHaveCount(0);
    await expect(page.locator('[data-testid="toggle-notes"]')).toHaveCount(0);
    await expect(page.locator('[data-testid="research-sources"]')).toHaveCount(0);
    await expect(page.locator('[data-testid="toggle-sources"]')).toHaveCount(0);
  });

  test('should show loading state during publish', async ({ page }) => {
    await mockPublish(page, 1000);
    await openCompletedResults(page);

    await page.click('[data-testid="publish-notebook-button"]');

    // Should show loading state
    await expect(page.locator('[data-testid="publish-loading"]')).toBeVisible({ timeout: 2000 });
    await expect(page.locator('[data-testid="publish-notebook-button"]')).toBeDisabled();

    // Loading should end
    await expect(page.locator('[data-testid="publish-loading"]')).not.toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="research-success"]')).toBeVisible();
  });

  test('should display iterations count', async ({ page }) => {
    await openCompletedResults(page);

    await expect(page.locator('[data-testid="research-iterations"]')).toHaveText(String(RESULT.iterations));
  });

  // fixme: behaviour mismatch: lib/api/research.ts:302-303 maps HTTP 425 to "Research still in progress", but page.tsx:107-112 handleSelectTask drops the error (only result.ok is handled), so no in-progress message is ever shown; the task-in-progress-message element does not exist. Tracked in #3226
  test.fixme('should handle 425 error (still in progress)', async ({ page }) => {
    await mockResults(page, () => 425);
    await withTasks(page);

    await page.locator('[data-testid="task-item"][data-status="completed"]').click();

    // Should show "still in progress" message
    await expect(page.locator('[data-testid="task-in-progress-message"]')).toBeVisible({ timeout: 3000 });
  });
});
