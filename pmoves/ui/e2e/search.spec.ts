/* ═══════════════════════════════════════════════════════════════════════════
   Search Interface E2E Tests
   Tests end-to-end search workflows against the built /dashboard/search UI
   (app/dashboard/search/page.tsx renders SearchBar :116, SearchFilters :148,
   SearchResults :168). Hi-RAG v2 is mocked with page.route — never a live backend.
   ═══════════════════════════════════════════════════════════════════════════ */

import { test, expect, type Page } from '@playwright/test';

const CORS = { 'Access-Control-Allow-Origin': '*' };

const RESULTS = [
  {
    id: 'r-youtube',
    content: 'A transcript chunk about quantum computing from a YouTube video.',
    score: 0.95,
    source: 'youtube',
    metadata: { title: 'Quantum Video', channel: 'PMOVES', video_id: 'vid123', url: 'https://example.test/v' },
  },
  {
    id: 'r-notebook',
    content: 'A notebook note about the same topic.',
    score: 0.75,
    source: 'notebook',
    metadata: { title: 'Notebook Note' },
  },
  {
    id: 'r-pdf',
    content: 'A PDF excerpt with lower relevance.',
    score: 0.4,
    source: 'pdf',
    metadata: { title: 'Paper.pdf' },
  },
];

type QueryBody = { query?: string; filters?: Record<string, unknown> };

/**
 * Backend-free mock for Hi-RAG v2 POST /hirag/query. Returns the captured request
 * bodies so tests can assert what the UI actually sent. `delayMs` keeps the loading
 * state observable.
 */
async function mockHiragQuery(
  page: Page,
  { results = RESULTS, delayMs = 0 }: { results?: typeof RESULTS; delayMs?: number } = {}
) {
  const requests: QueryBody[] = [];
  await page.route('**/hirag/query', async (route) => {
    requests.push(JSON.parse(route.request().postData() || '{}'));
    if (delayMs) await new Promise((r) => setTimeout(r, delayMs));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: CORS,
      body: JSON.stringify({ results, total: results.length, queryTime: 12 }),
    });
  });
  return requests;
}

async function seedHistory(page: Page, queries: string[]) {
  const history = queries.map((query, i) => ({ query, timestamp: Date.now() - i * 1000 }));
  await page.addInitScript((h) => {
    window.localStorage.setItem('pmoves_search_history', JSON.stringify(h));
  }, history);
  await page.reload();
  await page.waitForLoadState('networkidle');
}

async function openFilters(page: Page) {
  // Built behaviour: the filter panel is toggled by the SearchBar filter button
  // (SearchBar.tsx aria-label "Toggle filters"; page.tsx:20 showFilters defaults false).
  await page.getByRole('button', { name: 'Toggle filters' }).click();
  await expect(page.locator('[data-testid="search-filters"]')).toBeVisible();
}

async function runSearch(page: Page, query = 'test') {
  await page.fill('[data-testid="search-input"]', query);
  await page.click('[data-testid="search-submit"]');
}

test.describe('Search Interface', () => {
  test.beforeEach(async ({ page }) => {
    // Hi-RAG health probe and Supabase service-catalog lookup are mocked/aborted so
    // the page never reaches a live service.
    await page.route('**/healthz', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', headers: CORS, body: JSON.stringify({ healthy: true }) })
    );
    await page.route('http://127.0.0.1:54321/**', (route) => route.abort('connectionrefused'));
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

    // Filters live behind the filter toggle (page.tsx:146 renders SearchFilters only
    // when showFilters is true); hidden initially, visible once toggled.
    await expect(page.locator('[data-testid="search-filters"]')).toBeHidden();
    await openFilters(page);

    // Initially, no results should be shown
    await expect(page.locator('[data-testid="search-results"]')).not.toBeVisible();
  });

  test('should search and display results', async ({ page }) => {
    const requests = await mockHiragQuery(page);

    await runSearch(page, 'test query');

    // Wait for results to load
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Every mocked result is rendered
    await expect(page.locator('[data-testid="search-result-item"]')).toHaveCount(RESULTS.length);
    expect(requests.some((r) => r.query === 'test query')).toBe(true);
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
    const requests = await mockHiragQuery(page);

    await runSearch(page, 'video');
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Filter to YouTube only. Built behaviour: filters apply on change (no Apply
    // button) — SearchFilters.tsx onChange -> page.tsx setFilters -> handleSearch
    // dependency re-runs the debounced search with the new filters.
    await openFilters(page);
    await page.selectOption('[data-testid="source-filter"]', 'youtube');

    await expect
      .poll(() => requests.at(-1)?.filters?.source_type, { timeout: 5000 })
      .toBe('youtube');
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible();
  });

  test('should filter by date range', async ({ page }) => {
    const requests = await mockHiragQuery(page);

    await runSearch(page);
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Set date range filter (applies on change; there is no Apply button in the built UI)
    await openFilters(page);
    await page.fill('[data-testid="filter-start-date"]', '2025-01-01');
    await page.fill('[data-testid="filter-end-date"]', '2025-12-31');

    await expect
      .poll(() => {
        const f = requests.at(-1)?.filters;
        return f ? `${f.start_date}|${f.end_date}` : null;
      }, { timeout: 5000 })
      .toBe('2025-01-01|2025-12-31');
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible();
  });

  test('should filter by minimum score', async ({ page }) => {
    const requests = await mockHiragQuery(page);

    await runSearch(page);
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Built minimum-score control is a preset select (SearchFilters.tsx MIN_SCORE_OPTIONS),
    // not a free-text 0-100 field: "High (70%+)" has value 0.7.
    await openFilters(page);
    await page.selectOption('[data-testid="filter-min-score"]', '0.7');

    await expect.poll(() => requests.at(-1)?.filters?.min_score, { timeout: 5000 }).toBe(0.7);
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible();
  });

  test('should clear all filters', async ({ page }) => {
    await openFilters(page);

    // Set some filters first
    await page.selectOption('[data-testid="source-filter"]', 'youtube');
    await page.fill('[data-testid="filter-start-date"]', '2025-01-01');
    await page.selectOption('[data-testid="filter-min-score"]', '0.7');

    // Click clear filters
    await page.click('[data-testid="clear-filters"]');

    // Verify filters are cleared
    await expect(page.locator('[data-testid="source-filter"]')).toHaveValue('');
    await expect(page.locator('[data-testid="filter-start-date"]')).toHaveValue('');
    await expect(page.locator('[data-testid="filter-min-score"]')).toHaveValue('');
  });

  test('should display active filter count', async ({ page }) => {
    await openFilters(page);

    // Set multiple filters
    await page.selectOption('[data-testid="source-filter"]', 'youtube');
    await page.selectOption('[data-testid="filter-min-score"]', '0.7');

    // Built UI summarises active filters as one chip per filter
    // (SearchFilters.tsx "Active filters summary"), not a numeric badge.
    const chips = page.locator('[data-testid="active-filters"] [data-testid="active-filter-chip"]');
    await expect(chips).toHaveCount(2);
    await expect(chips.nth(0)).toHaveText('Source: youtube');
    await expect(chips.nth(1)).toHaveText('Score: 70%+');
  });

  test('should expand and collapse search results', async ({ page }) => {
    await mockHiragQuery(page);
    await runSearch(page);

    // Wait for results
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Built expand control is the per-result chevron button (SearchResults.tsx
    // aria-label "Expand"/"Collapse"), not a click on the whole card.
    const first = page.locator('[data-testid="search-result-item"]').first();
    await expect(first.locator('[data-testid="result-content"]')).toBeHidden();
    await first.getByRole('button', { name: 'Expand' }).click();

    // Expanded content should be visible
    await expect(first.locator('[data-testid="result-content"]')).toBeVisible();

    // Click again to collapse
    await first.getByRole('button', { name: 'Collapse' }).click();
    await expect(first.locator('[data-testid="result-content"]')).toBeHidden();
  });

  test('should copy result to clipboard', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await mockHiragQuery(page);
    await runSearch(page);

    // Wait for results
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Click copy button on first result
    await page.locator('[data-testid="copy-result-button"]').first().click();

    // Check for success toast (page.tsx notification, cleared after 2s)
    const toast = page.locator('[data-testid="search-toast"]');
    await expect(toast).toHaveText('Copied to clipboard', { timeout: 5000 });
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(RESULTS[0].content);

    // Toast should disappear after a few seconds
    await expect(toast).not.toBeVisible({ timeout: 5000 });
  });

  // fixme: REAL UI BUG #3232: exportToNotebook (lib/api/hirag.ts:269-277) is a TODO stub that returns ok
  // without calling any API, so the "Exported to notebook" toast reports a success that never
  // happened. Passing this test would certify the stub. The body is kept: it becomes a real check
  // once the export is wired (add an assertion on the outgoing notebook request then).
  test.fixme('should export result to notebook', async ({ page }) => {
    await mockHiragQuery(page);
    await runSearch(page);

    // Wait for results
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Click export button on first result. Built flow exports to the "default"
    // notebook with no selector modal (page.tsx handleExport; exportToNotebook in
    // lib/api/hirag.ts is still a TODO stub that returns ok without an API call).
    await page.locator('[data-testid="export-notebook-button"]').first().click();

    // Check for success message
    await expect(page.locator('[data-testid="search-toast"]')).toHaveText('Exported to notebook', { timeout: 5000 });
  });

  test('should show empty state for no results', async ({ page }) => {
    await mockHiragQuery(page, { results: [] });

    // Search for something unlikely to exist
    await runSearch(page, 'xyzabc123nonexistent');

    // Wait for empty state
    await expect(page.locator('[data-testid="no-results"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="search-result-item"]')).toHaveCount(0);
  });

  test('should show loading state during search', async ({ page }) => {
    await mockHiragQuery(page, { delayMs: 1500 });

    // Submit search and immediately check for loading state
    await runSearch(page);

    // Loading indicator should be visible briefly
    await expect(page.locator('[data-testid="search-loading"]')).toBeVisible({ timeout: 1000 });

    // Wait for loading to complete
    await expect(page.locator('[data-testid="search-loading"]')).not.toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible();
  });

  test('should display score badges with correct colors', async ({ page }) => {
    await mockHiragQuery(page);
    await runSearch(page);

    // Wait for results
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // Score badges show the percentage, coloured by band (SearchResults.tsx getScoreColor)
    const scoreBadges = page.locator('[data-testid="score-badge"]');
    await expect(scoreBadges).toHaveCount(3);
    await expect(scoreBadges.nth(0)).toHaveText('95%');
    await expect(scoreBadges.nth(0)).toHaveClass(/text-green-600/);
    await expect(scoreBadges.nth(2)).toHaveText('40%');
  });

  // Operator decision 2026-09-28: below 50% is red (SearchResults.tsx getScoreColor bands).
  test('should colour low scores (< 50%) red', async ({ page }) => {
    await mockHiragQuery(page);
    await runSearch(page);
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    const lowBadge = page.locator('[data-testid="score-badge"]').nth(2);
    await expect(lowBadge).toHaveText('40%');
    await expect(lowBadge).toHaveClass(/text-red-600/);
  });

  test('should display correct source type icons', async ({ page }) => {
    await mockHiragQuery(page);
    await runSearch(page);

    // Wait for results
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });

    // One badge per mocked source type
    await expect(page.locator('[data-testid="source-badge"][data-source="youtube"]')).toHaveCount(1);
    await expect(page.locator('[data-testid="source-badge"][data-source="notebook"]')).toHaveCount(1);
    await expect(page.locator('[data-testid="source-badge"][data-source="pdf"]')).toHaveCount(1);
    await expect(page.locator('[data-testid="source-badge"][data-source="youtube"]')).toContainText('📺');
  });

  test('should show search history', async ({ page }) => {
    await seedHistory(page, ['first query', 'second query']);

    // Built behaviour: the history dropdown opens on focus (SearchBar.tsx onFocus);
    // typing schedules a debounced search that closes it, so we assert on focus.
    await page.click('[data-testid="search-input"]');

    const historyDropdown = page.locator('[data-testid="search-history-dropdown"]');
    await expect(historyDropdown).toBeVisible();
    await expect(historyDropdown.locator('[data-testid="search-history-item"]')).toHaveCount(2);
  });

  test('should clear search history', async ({ page }) => {
    await seedHistory(page, ['first query']);

    // Focus search input
    await page.click('[data-testid="search-input"]');

    const clearButton = page.locator('[data-testid="clear-search-history"]');
    await expect(clearButton).toBeVisible();
    await clearButton.click();

    // History should be cleared
    await expect(page.locator('[data-testid="search-history-dropdown"]')).not.toBeVisible();
    expect(await page.evaluate(() => window.localStorage.getItem('pmoves_search_history'))).toBeNull();
  });

  test('should handle error state gracefully', async ({ page }) => {
    // Mock a failed search by intercepting the request
    await page.route('**/hirag/query', async (route) => {
      await route.abort('failed');
    });

    // Try to search
    await runSearch(page);

    // Should show error message
    await expect(page.locator('[data-testid="search-error"]')).toBeVisible({ timeout: 5000 });
  });

  test('should validate minimum score input (0-100)', async ({ page }) => {
    await openFilters(page);

    // Built control is a preset select (SearchFilters.tsx MIN_SCORE_OPTIONS), so an
    // out-of-range value cannot be entered: every option is "any" or a fraction in (0, 1].
    const values = await page
      .locator('[data-testid="filter-min-score"] option')
      .evaluateAll((opts) => opts.map((o) => (o as HTMLOptionElement).value));
    expect(values.length).toBeGreaterThan(1);
    for (const v of values) {
      if (v === '') continue;
      const n = Number(v);
      expect(n).toBeGreaterThan(0);
      expect(n).toBeLessThanOrEqual(1);
    }
  });

  // fixme: behaviour mismatch: SearchFilters.tsx:130-156 renders two independent date inputs with no end>=start validation and no date-validation-error element (and no Apply button); needs an operator decision on whether to build validation. Tracked in #3225
  test.fixme('should validate date range (end >= start)', async ({ page }) => {
    // Set invalid date range (end before start)
    await page.fill('[data-testid="filter-start-date"]', '2025-12-31');
    await page.fill('[data-testid="filter-end-date"]', '2025-01-01');

    // Apply filters
    await page.click('[data-testid="apply-filters"]');

    // Should show validation error
    await expect(page.locator('[data-testid="date-validation-error"]')).toBeVisible({ timeout: 1000 });
  });

  test('should prevent empty query submission', async ({ page }) => {
    const requests = await mockHiragQuery(page);

    // Built behaviour: submit is disabled while the query is empty (SearchBar.tsx
    // disabled={loading || !query.trim()}) and handleSearch ignores blank queries.
    await expect(page.locator('[data-testid="search-submit"]')).toBeDisabled();
    await page.fill('[data-testid="search-input"]', '   ');
    await expect(page.locator('[data-testid="search-submit"]')).toBeDisabled();

    await page.waitForTimeout(600); // longer than the 300ms search debounce
    expect(requests).toHaveLength(0);
    await expect(page.locator('[data-testid="search-results"]')).not.toBeVisible();
  });

  test('should rerun search from history item', async ({ page }) => {
    const requests = await mockHiragQuery(page);
    await seedHistory(page, ['history query']);

    await page.click('[data-testid="search-input"]');
    const historyItems = page.locator('[data-testid="search-history-item"]');
    await expect(historyItems).toHaveCount(1);

    // Click first history item
    await historyItems.first().click();

    // Search should be performed
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="search-input"]')).toHaveValue('history query');
    expect(requests.some((r) => r.query === 'history query')).toBe(true);
  });
});
