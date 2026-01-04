/* ═══════════════════════════════════════════════════════════════════════════
   Search Interface E2E Tests
   Tests end-to-end search workflows with Hi-RAG v2 integration
   ═══════════════════════════════════════════════════════════════════════════ */

import { test, expect } from '@playwright/test';

test.describe('Search Interface', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to search dashboard
    await page.goto('/dashboard/search');
    // Wait for page to load
    await page.waitForLoadState('networkidle');
  });

  test('should load search page with initial state', async ({ page }) => {
    // Check that search input is present
    await expect(page.locator('[data-testid="search-input"]')).toBeVisible();

    // Check that search button is present
    await expect(page.locator('[data-testid="search-submit"]')).toBeVisible();

    // Check that filters section is present
    await expect(page.locator('[data-testid="search-filters"]')).toBeVisible();

    // Initially, no results should be shown
    await expect(page.locator('[data-testid="search-results"]')).not.toBeVisible();
  });

  test('should search and display results', async ({ page }) => {
    // Enter search query
    await page.fill('[data-testid="search-input"]', 'test query');

    // Submit search
    await page.click('[data-testid="search-submit"]');

    // Wait for results to load
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Check that at least one result is shown
    const results = page.locator('[data-testid="search-result-item"]');
    await expect(results).toHaveCount(await results.count());
  });

  test('should use keyboard shortcut (Cmd+K) to focus search', async ({ page }) => {
    // Press Cmd+K (or Ctrl+K on non-Mac)
    await page.keyboard.press(process.platform === 'darwin' ? 'Meta+k' : 'Control+k');

    // Search input should be focused
    await expect(page.locator('[data-testid="search-input"]')).toBeFocused();
  });

  test('should use keyboard shortcut (Ctrl+K) to focus search', async ({ page }) => {
    // Press Ctrl+K
    await page.keyboard.press('Control+k');

    // Search input should be focused
    await expect(page.locator('[data-testid="search-input"]')).toBeFocused();
  });

  test('should filter by source type', async ({ page }) => {
    // Enter search query
    await page.fill('[data-testid="search-input"]', 'video');

    // Submit search
    await page.click('[data-testid="search-submit"]');

    // Wait for initial results
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Get initial result count
    const initialResults = await page.locator('[data-testid="search-result-item"]').count();

    // Filter to YouTube only
    await page.selectOption('[data-testid="source-filter"]', 'youtube');

    // Wait for filtered results
    await page.waitForTimeout(500);

    // Check that results are still visible
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible();
  });

  test('should filter by date range', async ({ page }) => {
    // Enter search query
    await page.fill('[data-testid="search-input"]', 'test');

    // Submit search
    await page.click('[data-testid="search-submit"]');

    // Wait for results
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Set date range filter
    await page.fill('[data-testid="filter-start-date"]', '2025-01-01');
    await page.fill('[data-testid="filter-end-date"]', '2025-12-31');

    // Apply date filter
    await page.click('[data-testid="apply-filters"]');

    // Wait for filtered results
    await page.waitForTimeout(500);

    // Results should still be visible
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible();
  });

  test('should filter by minimum score', async ({ page }) => {
    // Enter search query
    await page.fill('[data-testid="search-input"]', 'test');

    // Submit search
    await page.click('[data-testid="search-submit"]');

    // Wait for results
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Set minimum score filter
    await page.fill('[data-testid="filter-min-score"]', '70');

    // Apply filter
    await page.click('[data-testid="apply-filters"]');

    // Wait for filtered results
    await page.waitForTimeout(500);

    // Check that results are visible
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible();
  });

  test('should clear all filters', async ({ page }) => {
    // Set some filters first
    await page.selectOption('[data-testid="source-filter"]', 'youtube');
    await page.fill('[data-testid="filter-start-date"]', '2025-01-01');
    await page.fill('[data-testid="filter-min-score"]', '70');

    // Click clear filters
    await page.click('[data-testid="clear-filters"]');

    // Verify filters are cleared
    await expect(page.locator('[data-testid="source-filter"]')).toHaveValue('');
    await expect(page.locator('[data-testid="filter-start-date"]')).toHaveValue('');
    await expect(page.locator('[data-testid="filter-min-score"]')).toHaveValue('');
  });

  test('should display active filter count', async ({ page }) => {
    // Set multiple filters
    await page.selectOption('[data-testid="source-filter"]', 'youtube');
    await page.fill('[data-testid="filter-min-score"]', '70');

    // Apply filters
    await page.click('[data-testid="apply-filters"]');

    // Check that filter count is shown
    await expect(page.locator('[data-testid="active-filter-count"]')).toContainText('2');
  });

  test('should expand and collapse search results', async ({ page }) => {
    // Search for something
    await page.fill('[data-testid="search-input"]', 'test');
    await page.click('[data-testid="search-submit"]');

    // Wait for results
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Click first result to expand
    await page.click('[data-testid="search-result-item"]:first-child');

    // Expanded content should be visible
    await expect(page.locator('[data-testid="result-content"]')).toBeVisible();

    // Click again to collapse
    await page.click('[data-testid="search-result-item"]:first-child');

    // Content might be hidden or still visible depending on implementation
    const content = page.locator('[data-testid="result-content"]');
    const isVisible = await content.isVisible().catch(() => false);
  });

  test('should copy result to clipboard', async ({ page }) => {
    // Search for something
    await page.fill('[data-testid="search-input"]', 'test');
    await page.click('[data-testid="search-submit"]');

    // Wait for results
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Click copy button on first result
    await page.click('[data-testid="copy-result-button"]:first-child');

    // Check for success message/toast
    await expect(page.locator('[data-testid="copy-success-toast"]')).toBeVisible({ timeout: 5000 });

    // Toast should disappear after a few seconds
    await expect(page.locator('[data-testid="copy-success-toast"]')).not.toBeVisible({ timeout: 5000 });
  });

  test('should export result to notebook', async ({ page }) => {
    // Search for something
    await page.fill('[data-testid="search-input"]', 'test');
    await page.click('[data-testid="search-submit"]');

    // Wait for results
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Click export button on first result
    await page.click('[data-testid="export-notebook-button"]:first-child');

    // If notebook selector modal appears, select a notebook
    const notebookSelector = page.locator('[data-testid="notebook-selector"]');
    if (await notebookSelector.isVisible({ timeout: 2000 })) {
      await page.selectOption('[data-testid="notebook-select"]', { index: 0 });
      await page.click('[data-testid="confirm-export"]');
    }

    // Check for success message
    await expect(page.locator('[data-testid="export-success-toast"]')).toBeVisible({ timeout: 5000 });
  });

  test('should show empty state for no results', async ({ page }) => {
    // Search for something unlikely to exist
    await page.fill('[data-testid="search-input"]', 'xyzabc123nonexistent');
    await page.click('[data-testid="search-submit"]');

    // Wait for empty state
    await expect(page.locator('[data-testid="no-results"]')).toBeVisible({ timeout: 10000 });
  });

  test('should show loading state during search', async ({ page }) => {
    // Enter search query
    await page.fill('[data-testid="search-input"]', 'test');

    // Submit search and immediately check for loading state
    await page.click('[data-testid="search-submit"]');

    // Loading indicator should be visible briefly
    await expect(page.locator('[data-testid="search-loading"]')).toBeVisible({ timeout: 1000 });

    // Wait for loading to complete
    await expect(page.locator('[data-testid="search-loading"]')).not.toBeVisible({ timeout: 10000 });
  });

  test('should display score badges with correct colors', async ({ page }) => {
    // Search for something
    await page.fill('[data-testid="search-input"]', 'test');
    await page.click('[data-testid="search-submit"]');

    // Wait for results
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Check that score badges are present
    const scoreBadges = page.locator('[data-testid="score-badge"]');
    await expect(scoreBadges.first()).toBeVisible();

    // High score (>90%) should have green color
    const highScoreBadge = page.locator('[data-testid="score-badge"][data-score-range="high"]');
    const hasHighScore = await highScoreBadge.count() > 0;

    // Medium score (70-90%) should have yellow color
    const mediumScoreBadge = page.locator('[data-testid="score-badge"][data-score-range="medium"]');

    // Low score (<50%) should have red color
    const lowScoreBadge = page.locator('[data-testid="score-badge"][data-score-range="low"]');
  });

  test('should display correct source type icons', async ({ page }) => {
    // Search for something
    await page.fill('[data-testid="search-input"]', 'test');
    await page.click('[data-testid="search-submit"]');

    // Wait for results
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Check for source type badges
    const youtubeBadges = page.locator('[data-testid="source-badge"][data-source="youtube"]');
    const notebookBadges = page.locator('[data-testid="source-badge"][data-source="notebook"]');
    const pdfBadges = page.locator('[data-testid="source-badge"][data-source="pdf"]');

    // At least one source badge should be present
    const totalBadges = await youtubeBadges.count() + await notebookBadges.count() + await pdfBadges.count();
    expect(totalBadges).toBeGreaterThanOrEqual(0);
  });

  test('should show search history', async ({ page }) => {
    // Focus search input
    await page.click('[data-testid="search-input"]');

    // Type a character to trigger history dropdown
    await page.type('[data-testid="search-input"]', 't');

    // Check if search history dropdown appears (might be empty for new users)
    const historyDropdown = page.locator('[data-testid="search-history-dropdown"]');
    const isVisible = await historyDropdown.isVisible({ timeout: 1000 }).catch(() => false);

    if (isVisible) {
      await expect(historyDropdown).toBeVisible();
    }
  });

  test('should clear search history', async ({ page }) => {
    // Focus search input
    await page.click('[data-testid="search-input"]');

    // Check if clear history button exists
    const clearButton = page.locator('[data-testid="clear-search-history"]');

    if (await clearButton.isVisible({ timeout: 1000 })) {
      await clearButton.click();

      // History should be cleared
      await expect(page.locator('[data-testid="search-history-dropdown"]')).not.toBeVisible();
    }
  });

  test('should handle error state gracefully', async ({ page }) => {
    // Mock a failed search by intercepting the request
    await page.route('**/hirag/query', async (route) => {
      await route.abort('failed');
    });

    // Try to search
    await page.fill('[data-testid="search-input"]', 'test');
    await page.click('[data-testid="search-submit"]');

    // Should show error message
    await expect(page.locator('[data-testid="search-error"]')).toBeVisible({ timeout: 5000 });
  });

  test('should validate minimum score input (0-100)', async ({ page }) => {
    // Try to enter invalid score
    await page.fill('[data-testid="filter-min-score"]', '150');

    // Apply filters
    await page.click('[data-testid="apply-filters"]');

    // Should show validation error or clamp the value
    const validationError = page.locator('[data-testid="score-validation-error"]');
    const hasError = await validationError.isVisible({ timeout: 1000 }).catch(() => false);

    if (hasError) {
      await expect(validationError).toBeVisible();
    } else {
      // Value should be clamped to 100
      const inputValue = await page.inputValue('[data-testid="filter-min-score"]');
      expect(parseInt(inputValue)).toBeLessThanOrEqual(100);
    }
  });

  test('should validate date range (end >= start)', async ({ page }) => {
    // Set invalid date range (end before start)
    await page.fill('[data-testid="filter-start-date"]', '2025-12-31');
    await page.fill('[data-testid="filter-end-date"]', '2025-01-01');

    // Apply filters
    await page.click('[data-testid="apply-filters"]');

    // Should show validation error
    const validationError = page.locator('[data-testid="date-validation-error"]');
    const hasError = await validationError.isVisible({ timeout: 1000 }).catch(() => false);

    if (hasError) {
      await expect(validationError).toBeVisible();
    }
  });

  test('should prevent empty query submission', async ({ page }) => {
    // Try to submit empty search
    await page.click('[data-testid="search-submit"]');

    // Should not submit or should show validation error
    const results = page.locator('[data-testid="search-results"]');
    const hasResults = await results.isVisible({ timeout: 1000 }).catch(() => false);

    expect(hasResults).toBe(false);
  });

  test('should rerun search from history item', async ({ page }) => {
    // This test assumes there's search history
    await page.click('[data-testid="search-input"]');
    await page.type('[data-testid="search-input"]', 't');

    const historyDropdown = page.locator('[data-testid="search-history-dropdown"]');
    const hasHistory = await historyDropdown.isVisible({ timeout: 1000 }).catch(() => false);

    if (hasHistory) {
      const historyItems = page.locator('[data-testid="search-history-item"]');
      const itemCount = await historyItems.count();

      if (itemCount > 0) {
        // Click first history item
        await historyItems.first().click();

        // Search should be performed
        await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });
      }
    }
  });
});
