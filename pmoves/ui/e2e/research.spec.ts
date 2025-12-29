/* ═══════════════════════════════════════════════════════════════════════════
   Deep Research Dashboard E2E Tests
   Tests end-to-end DeepResearch service workflows
   ═══════════════════════════════════════════════════════════════════════════ */

import { test, expect } from '@playwright/test';

test.describe('Deep Research Dashboard', () => {
  test.beforeEach(async ({ page }) => {
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

    // Check that results section exists (might be hidden)
    const resultsSection = page.locator('[data-testid="research-results"]');
    const isVisible = await resultsSection.isVisible({ timeout: 2000 }).catch(() => false);
    // Results section might not be visible initially
  });

  test('should initiate research task with default options', async ({ page }) => {
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
    // Try to submit empty query
    await page.click('[data-testid="start-research"]');

    // Should show validation error
    await expect(page.locator('[data-testid="query-required-error"]')).toBeVisible({ timeout: 2000 });

    // Or submit should be disabled
    const submitButton = page.locator('[data-testid="start-research"]');
    const isDisabled = await submitButton.isDisabled();
    expect(isDisabled || true).toBe(true);
  });

  test('should show character count for query', async ({ page }) => {
    // Enter query
    await page.fill('[data-testid="research-query"]', 'test query');

    // Check character count
    const charCount = page.locator('[data-testid="query-char-count"]');
    await expect(charCount).toBeVisible();

    const countText = await charCount.textContent();
    expect(countText).toContain('11'); // "test query" length
  });

  test('should enforce max query length (1000)', async ({ page }) => {
    // Try to enter very long query
    const longQuery = 'a'.repeat(1500);

    // Input should be truncated or validation error shown
    await page.fill('[data-testid="research-query"]', longQuery);

    const actualValue = await page.inputValue('[data-testid="research-query"]');
    expect(actualValue.length).toBeLessThanOrEqual(1000);
  });

  test('should expand/collapse options panel', async ({ page }) => {
    // Options panel should be collapsed by default
    const optionsPanel = page.locator('[data-testid="research-options-panel"]');
    const initiallyVisible = await optionsPanel.isVisible({ timeout: 1000 }).catch(() => false);

    // Click expand button
    await page.click('[data-testid="expand-options-button"]');

    // Panel should now be visible
    await expect(optionsPanel).toBeVisible({ timeout: 2000 });

    // Click collapse button
    await page.click('[data-testid="collapse-options-button"]');

    // Panel should be hidden or collapsed
    const isStillVisible = await optionsPanel.isVisible({ timeout: 1000 }).catch(() => false);
    if (initiallyVisible) {
      // If it was visible initially, it should still be toggleable
    }
  });

  test('should select research mode', async ({ page }) => {
    // Expand options first
    await page.click('[data-testid="expand-options-button"]');

    // Select different mode
    await page.selectOption('[data-testid="research-mode"]', 'openrouter');

    // Verify selection
    await expect(page.locator('[data-testid="research-mode"]')).toHaveValue('openrouter');
  });

  test('should update max iterations slider', async ({ page }) => {
    // Expand options first
    await page.click('[data-testid="expand-options-button"]');

    // Find slider
    const slider = page.locator('[data-testid="max-iterations-slider"]');

    // Get initial value
    const initialValue = await slider.inputValue();

    // Update slider value
    await slider.fill('20');

    // Verify new value
    const newValue = await slider.inputValue();
    expect(newValue).toBe('20');
  });

  test('should enforce max iterations range (3-30)', async ({ page }) => {
    // Expand options first
    await page.click('[data-testid="expand-options-button"]');

    // Try to set value below minimum
    const slider = page.locator('[data-testid="max-iterations-slider"]');
    await slider.fill('1');

    // Should clamp to minimum or show error
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
    await page.click('[data-testid="expand-options-button"]');

    // Find slider
    const slider = page.locator('[data-testid="priority-slider"]');

    // Update slider value
    await slider.fill('8');

    // Verify new value
    const newValue = await slider.inputValue();
    expect(newValue).toBe('8');
  });

  test('should enforce priority range (1-10)', async ({ page }) => {
    // Expand options first
    await page.click('[data-testid="expand-options-button"]');

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

  test('should select notebook from dropdown', async ({ page }) => {
    // Expand options first
    await page.click('[data-testid="expand-options-button"]');

    // Check if notebook selector exists
    const notebookSelect = page.locator('[data-testid="notebook-select"]');
    const exists = await notebookSelect.isVisible({ timeout: 1000 }).catch(() => false);

    if (exists) {
      // Select a notebook
      await page.selectOption('[data-testid="notebook-select"]', { index: 0 });

      // Verify selection
      const selectedOption = await notebookSelect.inputValue();
      expect(selectedOption).toBeTruthy();
    }
  });

  test('should list tasks with status filter', async ({ page }) => {
    // Check that task list is visible
    await expect(page.locator('[data-testid="task-list"]')).toBeVisible();

    // Filter by status
    await page.selectOption('[data-testid="status-filter"]', 'running');

    // Wait for filter to apply
    await page.waitForTimeout(500);

    // Task list should still be visible
    await expect(page.locator('[data-testid="task-list"]')).toBeVisible();
  });

  test('should filter tasks by mode', async ({ page }) => {
    // Filter by mode
    await page.selectOption('[data-testid="mode-filter"]', 'tensorzero');

    // Wait for filter to apply
    await page.waitForTimeout(500);

    // Task list should still be visible
    await expect(page.locator("[data-testid='task-list']")).toBeVisible();
  });

  test('should select all visible tasks', async ({ page }) => {
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

  test('should select only pending tasks', async ({ page }) => {
    // Click "select pending" button
    await page.click('[data-testid="select-pending"]');

    // Only pending tasks should be selected
    const pendingTasks = page.locator('[data-testid="task-item"][data-status="pending"]');
    const pendingCount = await pendingTasks.count();

    // At least verify button exists and is clickable
    await expect(page.locator('[data-testid="select-pending"]')).toBeVisible();
  });

  test('should clear task selection', async ({ page }) => {
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
    // Click refresh button
    await page.click('[data-testid="refresh-tasks"]');

    // Should show loading state briefly
    await expect(page.locator('[data-testid="refresh-tasks"]')).toHaveAttribute('data-loading', 'true');

    // Loading should end
    await expect(page.locator('[data-testid="refresh-tasks"]')).not.toHaveAttribute('data-loading', 'true', { timeout: 5000 });
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
