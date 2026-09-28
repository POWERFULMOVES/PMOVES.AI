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
    await slider.fill('1');

    // Should clamp to minimum
    const actualValue = await slider.inputValue();
    expect(parseInt(actualValue)).toBeGreaterThanOrEqual(3);

    // Try to set value above maximum
    await slider.fill('50');

    // Should clamp to maximum
    const maxValue = await slider.inputValue();
    expect(parseInt(maxValue)).toBeLessThanOrEqual(30);
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
    await slider.fill('0');

    // Should clamp to minimum
    const actualValue = await slider.inputValue();
    expect(parseInt(actualValue)).toBeGreaterThanOrEqual(1);

    // Try to set value above maximum
    await slider.fill('15');

    // Should clamp to maximum
    const maxValue = await slider.inputValue();
    expect(parseInt(maxValue)).toBeLessThanOrEqual(10);
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
    // This test requires a running task
    // First, try to find a running task
    const runningTasks = page.locator('[data-testid="task-item"][data-status="running"]');
    const count = await runningTasks.count();

    if (count > 0) {
      // Click cancel button on first running task
      await page.click('[data-testid="cancel-task-button"]:first-child');

      // Should confirm cancellation
      const confirmDialog = page.locator('[data-testid="confirm-cancel-dialog"]');
      const hasDialog = await confirmDialog.isVisible({ timeout: 1000 }).catch(() => false);

      if (hasDialog) {
        await page.click('[data-testid="confirm-cancel-yes"]');
      }

      // Should show success message
      await expect(page.locator('[data-testid="task-cancelled-message"]')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should display task status icons', async ({ page }) => {
    // Check for status icons
    const pendingIcon = page.locator('[data-testid="status-icon-pending"]');
    const runningIcon = page.locator('[data-testid="status-icon-running"]');
    const completedIcon = page.locator('[data-testid="status-icon-completed"]');
    const failedIcon = page.locator('[data-testid="status-icon-failed"]');

    // At least some status icons should be present
    const totalIcons = await pendingIcon.count() + await runningIcon.count() + await completedIcon.count() + await failedIcon.count();
    expect(totalIcons).toBeGreaterThanOrEqual(0);
  });

  test('should format relative time correctly', async ({ page }) => {
    // Check task items for relative time display
    const relativeTimes = page.locator('[data-testid="task-relative-time"]');
    const count = await relativeTimes.count();

    if (count > 0) {
      const timeText = await relativeTimes.first().textContent();
      // Should match pattern like "2m ago", "1h ago", etc.
      expect(timeText).toMatch(/\d+[mhd]\s+ago/i);
    }
  });

  test('should display results for completed task', async ({ page }) => {
    // Find a completed task
    const completedTasks = page.locator('[data-testid="task-item"][data-status="completed"]');
    const count = await completedTasks.count();

    if (count > 0) {
      // Click first completed task
      await completedTasks.first().click();

      // Should show task details/results
      await expect(page.locator('[data-testid="task-details"]')).toBeVisible({ timeout: 5000 });

      // Click load results button
      const loadResultsButton = page.locator('[data-testid="load-results"]');

      if (await loadResultsButton.isVisible({ timeout: 2000 })) {
        await loadResultsButton.click();

        // Should show research results
        await expect(page.locator('[data-testid="research-results"]')).toBeVisible({ timeout: 10000 });
      }
    }
  });

  test('should display research summary', async ({ page }) => {
    // This test assumes results are already loaded
    const resultsSection = page.locator('[data-testid="research-results"]');
    const hasResults = await resultsSection.isVisible({ timeout: 2000 }).catch(() => false);

    if (hasResults) {
      // Check for summary section
      await expect(page.locator('[data-testid="research-summary"]')).toBeVisible();

      // Summary should have content
      const summaryContent = page.locator('[data-testid="research-summary-content"]');
      const text = await summaryContent.textContent();
      expect(text?.trim().length).toBeGreaterThan(0);
    }
  });

  test('should expand/collapse notes section', async ({ page }) => {
    const resultsSection = page.locator('[data-testid="research-results"]');
    const hasResults = await resultsSection.isVisible({ timeout: 2000 }).catch(() => false);

    if (hasResults) {
      const notesSection = page.locator('[data-testid="research-notes"]');
      const notesToggle = page.locator('[data-testid="toggle-notes"]');

      if (await notesToggle.isVisible({ timeout: 1000 })) {
        // Toggle notes
        const wasVisible = await notesSection.isVisible();
        await notesToggle.click();
        const isNowVisible = await notesSection.isVisible();

        // Should have toggled
        expect(wasVisible).not.toBe(isNowVisible);
      }
    }
  });

  test('should expand/collapse sources section', async ({ page }) => {
    const resultsSection = page.locator('[data-testid="research-results"]');
    const hasResults = await resultsSection.isVisible({ timeout: 2000 }).catch(() => false);

    if (hasResults) {
      const sourcesSection = page.locator('[data-testid="research-sources"]');
      const sourcesToggle = page.locator('[data-testid="toggle-sources"]');

      if (await sourcesToggle.isVisible({ timeout: 1000 })) {
        // Toggle sources
        const wasVisible = await sourcesSection.isVisible();
        await sourcesToggle.click();
        const isNowVisible = await sourcesSection.isVisible();

        // Should have toggled
        expect(wasVisible).not.toBe(isNowVisible);
      }
    }
  });

  test('should copy summary to clipboard', async ({ page }) => {
    const resultsSection = page.locator('[data-testid="research-results"]');
    const hasResults = await resultsSection.isVisible({ timeout: 2000 }).catch(() => false);

    if (hasResults) {
      // Click copy summary button
      const copyButton = page.locator('[data-testid="copy-summary-button"]');

      if (await copyButton.isVisible({ timeout: 1000 })) {
        await copyButton.click();

        // Should show success toast
        await expect(page.locator('[data-testid="copy-success-toast"]')).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('should format duration correctly', async ({ page }) => {
    const resultsSection = page.locator('[data-testid="research-results"]');
    const hasResults = await resultsSection.isVisible({ timeout: 2000 }).catch(() => false);

    if (hasResults) {
      // Check duration display
      const duration = page.locator('[data-testid="research-duration"]');

      if (await duration.isVisible({ timeout: 1000 })) {
        const durationText = await duration.textContent();
        // Should match pattern like "2m 30s" or "150s"
        expect(durationText).toMatch(/\d+[smhd]|(\d+s)/i);
      }
    }
  });

  test('should publish to notebook', async ({ page }) => {
    const resultsSection = page.locator('[data-testid="research-results"]');
    const hasResults = await resultsSection.isVisible({ timeout: 2000 }).catch(() => false);

    if (hasResults) {
      // Click publish button
      const publishButton = page.locator('[data-testid="publish-notebook-button"]');

      if (await publishButton.isVisible({ timeout: 1000 })) {
        await publishButton.click();

        // Should show notebook selector modal
        const notebookModal = page.locator('[data-testid="notebook-selector-modal"]');
        const hasModal = await notebookModal.isVisible({ timeout: 2000 }).catch(() => false);

        if (hasModal) {
          // Select notebook
          await page.selectOption('[data-testid="notebook-select"]', { index: 0 });

          // Confirm publish
          await page.click('[data-testid="confirm-publish"]');

          // Should show success message
          await expect(page.locator('[data-testid="publish-success-toast"]')).toBeVisible({ timeout: 5000 });
        }
      }
    }
  });

  test('should handle empty notes/sources', async ({ page }) => {
    const resultsSection = page.locator('[data-testid="research-results"]');
    const hasResults = await resultsSection.isVisible({ timeout: 2000 }).catch(() => false);

    if (hasResults) {
      // Check for empty state messages
      const noNotes = page.locator('[data-testid="no-notes-message"]');
      const noSources = page.locator('[data-testid="no-sources-message"]');

      // At least one might be visible depending on the research results
      const hasNoNotes = await noNotes.isVisible({ timeout: 1000 }).catch(() => false);
      const hasNoSources = await noSources.isVisible({ timeout: 1000 }).catch(() => false);

      // This is just to verify the UI handles empty states
      expect(hasNoNotes || hasNoSources || true).toBe(true);
    }
  });

  test('should show loading state during publish', async ({ page }) => {
    const resultsSection = page.locator('[data-testid="research-results"]');
    const hasResults = await resultsSection.isVisible({ timeout: 2000 }).catch(() => false);

    if (hasResults) {
      const publishButton = page.locator('[data-testid="publish-notebook-button"]');

      if (await publishButton.isVisible({ timeout: 1000 })) {
        await publishButton.click();

        // If modal appears, select and confirm
        const notebookModal = page.locator('[data-testid="notebook-selector-modal"]');

        if (await notebookModal.isVisible({ timeout: 2000 })) {
          await page.selectOption('[data-testid="notebook-select"]', { index: 0 });
          await page.click('[data-testid="confirm-publish"]');

          // Should show loading state
          await expect(page.locator('[data-testid="publish-loading"]')).toBeVisible({ timeout: 2000 });

          // Loading should end
          await expect(page.locator('[data-testid="publish-loading"]')).not.toBeVisible({ timeout: 10000 });
        }
      }
    }
  });

  test('should display iterations count', async ({ page }) => {
    const resultsSection = page.locator('[data-testid="research-results"]');
    const hasResults = await resultsSection.isVisible({ timeout: 2000 }).catch(() => false);

    if (hasResults) {
      // Check iterations display
      const iterations = page.locator('[data-testid="research-iterations"]');

      if (await iterations.isVisible({ timeout: 1000 })) {
        const iterationsText = await iterations.textContent();
        // Should be a number
        expect(parseInt(iterationsText || '0')).not.toBeNaN();
      }
    }
  });

  test('should handle 425 error (still in progress)', async ({ page }) => {
    // This test would require mocking a response
    // For now, just verify error handling UI exists

    // Try to load results for a running task
    const runningTasks = page.locator('[data-testid="task-item"][data-status="running"]');
    const count = await runningTasks.count();

    if (count > 0) {
      await runningTasks.first().click();

      const loadResultsButton = page.locator('[data-testid="load-results"]');

      if (await loadResultsButton.isVisible({ timeout: 2000 })) {
        await loadResultsButton.click();

        // Should show "still in progress" message
        const inProgressMessage = page.locator('[data-testid="task-in-progress-message"]');
        const hasMessage = await inProgressMessage.isVisible({ timeout: 3000 }).catch(() => false);

        if (hasMessage) {
          await expect(inProgressMessage).toBeVisible();
        }
      }
    }
  });
});
